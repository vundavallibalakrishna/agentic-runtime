#!/bin/sh
# Render one Postgres config and start every Temporal service in this process.
# numHistoryShards is fixed for the life of the databases.
set -eu

shards="${NUM_HISTORY_SHARDS:-4}"
case "$shards" in
  ''|*[!0-9]*)
    echo "NUM_HISTORY_SHARDS must be a positive integer" >&2
    exit 1
    ;;
esac
if [ "$shards" -lt 1 ]; then
  echo "NUM_HISTORY_SHARDS must be a positive integer" >&2
  exit 1
fi

: "${POSTGRES_SEEDS:?POSTGRES_SEEDS is required}"
: "${POSTGRES_USER:?POSTGRES_USER is required}"
: "${POSTGRES_PWD:?POSTGRES_PWD is required}"
: "${DB_PORT:=5432}"
: "${DBNAME:=temporal}"
: "${VISIBILITY_DBNAME:=temporal_visibility}"
: "${BIND_ON_IP:=0.0.0.0}"

if [ -z "${TEMPORAL_BROADCAST_ADDRESS:-}" ]; then
  TEMPORAL_BROADCAST_ADDRESS="$(getent hosts "$(hostname)" | awk '{print $1; exit}')"
  if [ -z "$TEMPORAL_BROADCAST_ADDRESS" ]; then
    TEMPORAL_BROADCAST_ADDRESS=127.0.0.1
  fi
fi

# YAML double-quoted escaping. The password is not printed.
yaml_escape() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

password="$(yaml_escape "$POSTGRES_PWD")"
mkdir -p /tmp/temporal
cat > /tmp/temporal/config.yaml <<EOF
log:
  stdout: true
  level: info
persistence:
  numHistoryShards: ${shards}
  defaultStore: default
  visibilityStore: visibility
  datastores:
    default:
      sql:
        pluginName: postgres12
        databaseName: ${DBNAME}
        connectAddr: "${POSTGRES_SEEDS}:${DB_PORT}"
        connectProtocol: tcp
        user: ${POSTGRES_USER}
        password: "${password}"
        maxConns: 20
        maxIdleConns: 20
        maxConnLifetime: 1h
    visibility:
      sql:
        pluginName: postgres12
        databaseName: ${VISIBILITY_DBNAME}
        connectAddr: "${POSTGRES_SEEDS}:${DB_PORT}"
        connectProtocol: tcp
        user: ${POSTGRES_USER}
        password: "${password}"
        maxConns: 10
        maxIdleConns: 10
        maxConnLifetime: 1h
global:
  membership:
    maxJoinDuration: 30s
    broadcastAddress: "${TEMPORAL_BROADCAST_ADDRESS}"
  pprof:
    port: 0
services:
  frontend:
    rpc:
      grpcPort: 7233
      membershipPort: 6933
      bindOnIP: "${BIND_ON_IP}"
      httpPort: 7243
  history:
    rpc:
      grpcPort: 7234
      membershipPort: 6934
      bindOnIP: "${BIND_ON_IP}"
  matching:
    rpc:
      grpcPort: 7235
      membershipPort: 6935
      bindOnIP: "${BIND_ON_IP}"
  worker:
    rpc:
      grpcPort: 7239
      membershipPort: 6939
      bindOnIP: "${BIND_ON_IP}"
clusterMetadata:
  enableGlobalNamespace: false
  failoverVersionIncrement: 10
  masterClusterName: active
  currentClusterName: active
  clusterInformation:
    active:
      enabled: true
      initialFailoverVersion: 1
      rpcName: frontend
      rpcAddress: "127.0.0.1:7233"
      httpAddress: "127.0.0.1:7243"
dcRedirectionPolicy:
  policy: noop
archival:
  history:
    state: disabled
  visibility:
    state: disabled
namespaceDefaults:
  archival:
    history:
      state: disabled
    visibility:
      state: disabled
dynamicConfigClient:
  filepath: /etc/temporal/dynamicconfig.yaml
  pollInterval: 60s
EOF

exec temporal-server --config-file /tmp/temporal/config.yaml --allow-no-auth start
