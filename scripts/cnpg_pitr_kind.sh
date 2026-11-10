#!/usr/bin/env bash
# CloudNativePG point-in-time restore against MinIO. Proof: contract.
# The host does not publish 5432. Queries run with kubectl exec.
set -euo pipefail

namespace="${PITR_NAMESPACE:-ar-pitr}"
operator_url="${CNPG_OPERATOR_URL:-https://raw.githubusercontent.com/cloudnative-pg/cloudnative-pg/release-1.30/releases/cnpg-1.30.1.yaml}"

if ! command -v kubectl >/dev/null 2>&1; then
  echo "kubectl is required" >&2
  exit 1
fi

if ! kubectl cluster-info >/dev/null 2>&1; then
  if ! command -v kind >/dev/null 2>&1; then
    arch="$(uname -m)"
    case "$arch" in
      x86_64) kind_arch=amd64 ;;
      aarch64|arm64) kind_arch=arm64 ;;
      *) echo "unsupported arch $arch" >&2; exit 1 ;;
    esac
    curl -fsSL -o /tmp/kind "https://kind.sigs.k8s.io/dl/v0.30.0/kind-linux-${kind_arch}"
    chmod +x /tmp/kind
    export PATH="/tmp:$PATH"
  fi
  kind create cluster --name ar-pitr
  kubectl config use-context kind-ar-pitr
fi

kubectl apply --server-side -f "$operator_url"
kubectl rollout status deployment -n cnpg-system cnpg-controller-manager --timeout=180s
kubectl create namespace "$namespace" --dry-run=client -o yaml | kubectl apply -f -

# Docker Hub no longer publishes minio/minio. The official binaries are the release
# assets. The image is loaded into kind so the node does not pull a missing tag.
build_minio_image() {
  local work minio_tag mc_tag ctx
  work="$(mktemp -d)"
  minio_tag="RELEASE.2025-09-07T16-13-09Z"
  mc_tag="RELEASE.2025-08-13T08-35-41Z"
  curl -fsSL -o "${work}/minio" \
    "https://github.com/minio/minio/releases/download/${minio_tag}/minio.linux-amd64.${minio_tag}"
  curl -fsSL -o "${work}/mc" \
    "https://github.com/minio/mc/releases/download/${mc_tag}/mc.linux-amd64.${mc_tag}"
  chmod 755 "${work}/minio" "${work}/mc"
  cat > "${work}/Dockerfile" <<'EOF'
FROM debian:bookworm-slim
COPY minio /usr/local/bin/minio
COPY mc /usr/local/bin/mc
ENTRYPOINT ["/usr/local/bin/minio"]
EOF
  docker build -t ar-minio:dev "${work}"
  rm -rf "${work}"
  ctx="$(kubectl config current-context)"
  if [[ "${ctx}" == kind-* ]]; then
    kind load docker-image ar-minio:dev --name "${ctx#kind-}"
  fi
}

dump_namespace() {
  kubectl -n "$namespace" get pods -o wide >&2 || true
  kubectl -n "$namespace" describe pods >&2 || true
  kubectl -n "$namespace" logs -l app=minio --tail=80 >&2 || true
}

build_minio_image

cat <<'YAML' | kubectl apply -n "$namespace" -f -
apiVersion: v1
kind: Secret
metadata:
  name: minio-creds
type: Opaque
stringData:
  ACCESS_KEY_ID: minio
  ACCESS_SECRET_KEY: minio12345
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: minio
spec:
  replicas: 1
  selector:
    matchLabels:
      app: minio
  template:
    metadata:
      labels:
        app: minio
    spec:
      containers:
        - name: minio
          image: ar-minio:dev
          imagePullPolicy: IfNotPresent
          args: ["server", "/data"]
          env:
            - name: MINIO_ROOT_USER
              value: minio
            - name: MINIO_ROOT_PASSWORD
              value: minio12345
          ports:
            - containerPort: 9000
          readinessProbe:
            tcpSocket:
              port: 9000
            initialDelaySeconds: 2
          volumeMounts:
            - name: data
              mountPath: /data
      volumes:
        - name: data
          emptyDir: {}
---
apiVersion: v1
kind: Service
metadata:
  name: minio
spec:
  selector:
    app: minio
  ports:
    - port: 9000
YAML

if ! kubectl -n "$namespace" rollout status deploy/minio --timeout=300s; then
  dump_namespace
  exit 1
fi

cat <<'YAML' | kubectl apply -n "$namespace" -f -
apiVersion: batch/v1
kind: Job
metadata:
  name: minio-bucket
spec:
  backoffLimit: 6
  template:
    spec:
      restartPolicy: OnFailure
      containers:
        - name: mc
          image: ar-minio:dev
          imagePullPolicy: IfNotPresent
          command:
            - /bin/sh
            - -c
            - |
              /usr/local/bin/mc alias set local http://minio:9000 minio minio12345
              /usr/local/bin/mc mb -p local/ar-backup || true
YAML

if ! kubectl -n "$namespace" wait --for=condition=complete job/minio-bucket --timeout=180s; then
  dump_namespace
  kubectl -n "$namespace" logs job/minio-bucket --tail=80 >&2 || true
  exit 1
fi

cat <<YAML | kubectl apply -n "$namespace" -f -
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: ar-src
spec:
  instances: 1
  enableSuperuserAccess: true
  bootstrap:
    initdb:
      database: app
      owner: app
  storage:
    size: 1Gi
  backup:
    barmanObjectStore:
      destinationPath: s3://ar-backup/pg
      endpointURL: http://minio.${namespace}.svc:9000
      s3Credentials:
        accessKeyId:
          name: minio-creds
          key: ACCESS_KEY_ID
        secretAccessKey:
          name: minio-creds
          key: ACCESS_SECRET_KEY
      wal:
        compression: gzip
        archiveAdditionalCommandArgs:
          - "--addressing-style=path"
      data:
        compression: gzip
        additionalCommandArgs:
          - "--addressing-style=path"
YAML

for _ in $(seq 1 60); do
  phase="$(kubectl -n "$namespace" get cluster ar-src -o jsonpath='{.status.phase}' 2>/dev/null || true)"
  if [[ "$phase" == "Cluster in healthy state" ]]; then
    break
  fi
  sleep 10
done
phase="$(kubectl -n "$namespace" get cluster ar-src -o jsonpath='{.status.phase}')"
if [[ "$phase" != "Cluster in healthy state" ]]; then
  kubectl -n "$namespace" describe cluster ar-src >&2 || true
  echo "source cluster did not become ready: $phase" >&2
  exit 1
fi

psql() {
  kubectl -n "$namespace" exec ar-src-1 -- psql -U postgres -d app -v ON_ERROR_STOP=1 -c "$1"
}

psql "CREATE TABLE IF NOT EXISTS stage12_pitr (id int primary key, kind text)"
psql "INSERT INTO stage12_pitr (id, kind) VALUES (1, 'before') ON CONFLICT (id) DO UPDATE SET kind = EXCLUDED.kind"

cat <<YAML | kubectl apply -n "$namespace" -f -
apiVersion: postgresql.cnpg.io/v1
kind: Backup
metadata:
  name: stage12-base
spec:
  cluster:
    name: ar-src
  method: barmanObjectStore
YAML

for _ in $(seq 1 60); do
  backup="$(kubectl -n "$namespace" get backup stage12-base -o jsonpath='{.status.phase}' 2>/dev/null || true)"
  if [[ "$backup" == "completed" ]]; then
    break
  fi
  if [[ "$backup" == "failed" ]]; then
    kubectl -n "$namespace" describe backup stage12-base >&2 || true
    exit 1
  fi
  sleep 10
done
backup="$(kubectl -n "$namespace" get backup stage12-base -o jsonpath='{.status.phase}')"
if [[ "$backup" != "completed" ]]; then
  echo "base backup did not complete: $backup" >&2
  exit 1
fi

target="$(kubectl -n "$namespace" exec ar-src-1 -- psql -U postgres -d app -tAc "SELECT to_char(clock_timestamp() AT TIME ZONE 'UTC', 'YYYY-MM-DD\"T\"HH24:MI:SS\"Z\"')")"
target="$(echo "$target" | tr -d '[:space:]')"
sleep 3
psql "INSERT INTO stage12_pitr (id, kind) VALUES (2, 'after') ON CONFLICT (id) DO UPDATE SET kind = EXCLUDED.kind"
psql "SELECT pg_switch_wal()"
sleep 15

cat <<YAML | kubectl apply -n "$namespace" -f -
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: ar-restored
spec:
  instances: 1
  bootstrap:
    recovery:
      source: ar-src
      recoveryTarget:
        targetTime: "${target}"
  externalClusters:
    - name: ar-src
      barmanObjectStore:
        destinationPath: s3://ar-backup/pg
        endpointURL: http://minio.${namespace}.svc:9000
        s3Credentials:
          accessKeyId:
            name: minio-creds
            key: ACCESS_KEY_ID
          secretAccessKey:
            name: minio-creds
            key: ACCESS_SECRET_KEY
        wal:
          compression: gzip
          restoreAdditionalCommandArgs:
            - "--addressing-style=path"
        data:
          restoreAdditionalCommandArgs:
            - "--addressing-style=path"
  storage:
    size: 1Gi
YAML

for _ in $(seq 1 60); do
  phase="$(kubectl -n "$namespace" get cluster ar-restored -o jsonpath='{.status.phase}' 2>/dev/null || true)"
  if [[ "$phase" == "Cluster in healthy state" ]]; then
    break
  fi
  sleep 10
done
phase="$(kubectl -n "$namespace" get cluster ar-restored -o jsonpath='{.status.phase}')"
if [[ "$phase" != "Cluster in healthy state" ]]; then
  kubectl -n "$namespace" describe cluster ar-restored >&2 || true
  echo "restored cluster did not become ready: $phase" >&2
  exit 1
fi

rows="$(kubectl -n "$namespace" exec ar-restored-1 -- psql -U postgres -d app -tAc "SELECT kind FROM stage12_pitr ORDER BY id")"
printf '%s\n' "$rows"
if ! printf '%s\n' "$rows" | grep -qx "before"; then
  echo "restored data is missing the row from before the target" >&2
  exit 1
fi
if printf '%s\n' "$rows" | grep -qx "after"; then
  echo "restored data includes the row written after the target" >&2
  exit 1
fi
echo "pitr contract passed target=${target}"
