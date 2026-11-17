"""Render assertions for the umbrella chart. Invoked by scripts/check_helm.sh."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

from ar_common.settings import CATALOGUE_ENV

ROOT = Path(__file__).resolve().parents[1]
CHART = ROOT / "deploy/helm/agentic-runtime"
PASSWORDS = ROOT / "tests/fixtures/helm-db-passwords.yaml"
PRESETS = (
    "values-dev.yaml",
    "values-small.yaml",
    "values-large.yaml",
    "values-saas.yaml",
    "values-loadtest.yaml",
    "values-external.yaml",
    "values-airgap.yaml",
)


def template(*extra: str) -> str:
    result = subprocess.run(  # noqa: S603
        ["helm", "template", "agentic-runtime", str(CHART), "-f", str(PASSWORDS), *extra],  # noqa: S607
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def docs(rendered: str) -> list[dict[str, object]]:
    return [doc for doc in yaml.safe_load_all(rendered) if isinstance(doc, dict)]


def kinds(rendered: str) -> set[str]:
    return {str(doc.get("kind")) for doc in docs(rendered)}


def names(rendered: str, kind: str) -> set[str]:
    found: set[str] = set()
    for doc in docs(rendered):
        if doc.get("kind") != kind:
            continue
        meta = doc.get("metadata")
        if isinstance(meta, dict):
            found.add(str(meta.get("name")))
    return found


SECRET_PASSWORDS = {
    "AR_DB_OWNER_PASSWORD",
    "AR_DB_PLATFORM_PASSWORD",
    "AR_DB_APP_PASSWORD",
    "AR_DB_READONLY_PASSWORD",
    "AR_DB_TEMPORAL_PASSWORD",
}


def assert_catalogue(rendered: str) -> None:
    keys: set[str] = set()
    secret_keys: set[str] = set()
    created_install_secret = False
    for doc in docs(rendered):
        if doc.get("kind") not in {"ConfigMap", "Secret"}:
            continue
        data = doc.get("data") or doc.get("stringData") or {}
        if isinstance(data, dict):
            keys.update(str(key) for key in data)
        meta = doc.get("metadata")
        name = str(meta.get("name")) if isinstance(meta, dict) else ""
        if doc.get("kind") == "Secret" and name.endswith("-secrets") and isinstance(data, dict):
            created_install_secret = True
            secret_keys.update(str(key) for key in data)
    missing = sorted((CATALOGUE_ENV - SECRET_PASSWORDS) - keys)
    if missing:
        raise SystemExit("rendered config is missing " + ", ".join(missing))
    if created_install_secret:
        absent = sorted(SECRET_PASSWORDS - secret_keys)
        if absent:
            raise SystemExit("install secret is missing " + ", ".join(absent))


def assert_rollout(rendered: str) -> None:
    text = rendered
    if "maxUnavailable: 0" not in text:
        raise SystemExit("rolling update must keep maxUnavailable at 0")
    if "helm.sh/hook: pre-install,pre-upgrade" not in text:
        raise SystemExit("migrate hook missing")
    if 'helm.sh/hook-weight: "-20"' not in text:
        raise SystemExit("install secret hook is not weight -20")
    if "TEMPORAL_WORKER_BUILD_ID" not in text:
        raise SystemExit("worker build id missing")
    if "PodDisruptionBudget" not in kinds(rendered):
        raise SystemExit("pdb missing")


def assert_fails(args: list[str], needle: str) -> None:
    result = subprocess.run(  # noqa: S603
        ["helm", "template", "agentic-runtime", str(CHART), *args],  # noqa: S607
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0 or needle not in result.stderr + result.stdout:
        raise SystemExit(f"expected failure containing {needle}")


def main() -> None:
    default = template()
    assert_catalogue(default)
    assert_rollout(default)
    if "qdrant" in names(default, "StatefulSet"):
        raise SystemExit("qdrant must stay disabled by default")
    enabled = template("--set", "qdrant.enabled=true")
    if "agentic-runtime-qdrant" not in names(enabled, "StatefulSet"):
        raise SystemExit("qdrant subchart did not render")
    saas = template("-f", str(CHART / "values-saas.yaml"))
    if "agentic-runtime-bootstrap" in names(saas, "Job"):
        raise SystemExit("saas must not run the single-tenant bootstrap job")
    small = template("-f", str(CHART / "values-small.yaml"))
    if "agentic-runtime-bootstrap" not in names(small, "Job"):
        raise SystemExit("small install must bootstrap the tenant")
    assert_bootstrap_secret(default)
    assert_bootstrap_secret(small)
    airgap = template("-f", str(CHART / "values-airgap.yaml"))
    if "0.0.0.0/0" in airgap:
        raise SystemExit("air-gap render allows world egress")
    dev = template("-f", str(CHART / "values-dev.yaml"))
    if "RuntimeClass" in kinds(dev):
        raise SystemExit("dev preset must not install RuntimeClass")
    for preset in PRESETS:
        template("-f", str(CHART / preset))
    assert_fails(
        ["-f", str(PASSWORDS), "--set", "bootstrap.adminEmail="],
        "bootstrap.adminEmail",
    )
    assert_fails(
        ["-f", str(PASSWORDS), "--set", "secrets.data.AR_DB_OWNER_PASSWORD="],
        "AR_DB_OWNER_PASSWORD",
    )
    assert_fails(
        ["-f", str(PASSWORDS), "--set", "secrets.data.AR_DB_OWNER_PASSWORD=Ar_Owner"],
        "AR_DB_OWNER_PASSWORD",
    )
    assert_fails(
        ["-f", str(PASSWORDS), "--set", "secrets.data.AR_DB_APP_PASSWORD=ChangeMe"],
        "AR_DB_APP_PASSWORD",
    )
    assert_fails(
        ["-f", str(PASSWORDS), "--set", "secrets.create=false"],
        "existingRoleSecrets",
    )
    template(
        "-f",
        str(PASSWORDS),
        "--set",
        "secrets.create=false",
        "--set",
        "postgres.existingRoleSecrets=true",
    )
    assert_roles(default)
    assert_cnpg_contract(default)
    assert_hook_env(default)
    assert_hook_env(dev)
    assert_init_script(dev)
    if "reconcile-roles" not in dev:
        raise SystemExit("statefulset upgrade does not reconcile roles")
    if "reconcile-roles" in default:
        raise SystemExit("cnpg render includes the statefulset role job")
    again = template()
    if _role_secret(default, "ar-owner") != _role_secret(again, "ar-owner"):
        raise SystemExit("role password changed between two renders of the same values")
    assert_fails(
        [
            "-f",
            str(PASSWORDS),
            "--set",
            "global.env=prod",
            "--set",
            "sandboxes.driver=docker",
        ],
        "sandboxes.driver",
    )
    assert_fails(
        ["-f", str(PASSWORDS), "--set", "global.env=prod", "--set", "sandboxes.driver=host"],
        "must be one of",
    )
    assert_fails(["-f", str(PASSWORDS), "--set", "process.shared=false"], "stay at 1")
    assert_stage6(default)
    assert_stage8(default)
    assert_core(default, dev)
    assert_fails(
        [
            "-f",
            str(PASSWORDS),
            "--set",
            "airgap.lockdown=true",
            "--set",
            "config.AR_DEV_MODEL_BASE_URL=https://api.example.com/v1",
        ],
        "egressCIDRs",
    )
    sys.stdout.write("helm render checks ok\n")


def _role_secret(rendered: str, suffix: str) -> str:
    for doc in docs(rendered):
        if doc.get("kind") != "Secret":
            continue
        meta = doc.get("metadata")
        name = str(meta.get("name")) if isinstance(meta, dict) else ""
        if not name.endswith(f"-db-role-{suffix}"):
            continue
        data = doc.get("stringData")
        if isinstance(data, dict):
            return str(data.get("password"))
    raise SystemExit(f"missing role secret {suffix}")


def assert_init_script(rendered: str) -> None:
    script = ""
    for doc in docs(rendered):
        if doc.get("kind") != "ConfigMap":
            continue
        data = doc.get("data")
        if isinstance(data, dict) and "01-roles.sh" in data:
            script = str(data["01-roles.sh"])
    if "NOSUPERUSER" not in script or "BYPASSRLS" not in script:
        raise SystemExit("statefulset init script does not set the role attributes")
    if "CREATE EXTENSION IF NOT EXISTS vector" not in script:
        raise SystemExit("statefulset init script does not install extensions")
    if "helm-owner-secret" in script or "PASSWORD '" in script:
        raise SystemExit("statefulset init script contains a password")


def assert_cnpg_contract(rendered: str) -> None:
    """Extensions are installed. ar_owner is not a member of the other roles."""
    if "CREATE EXTENSION IF NOT EXISTS vector" not in rendered:
        raise SystemExit("CloudNativePG role contract is incomplete")
    if "inRoles:" in rendered or "WITH ADMIN OPTION" in rendered:
        raise SystemExit("ar_owner must not be granted the other roles")


def assert_hook_env(rendered: str) -> None:
    """Every hook Job carries AR_ENV, and role passwords come from the Secret."""
    found = False
    for doc in docs(rendered):
        if doc.get("kind") != "Job":
            continue
        found = True
        meta = doc.get("metadata")
        name = str(meta.get("name")) if isinstance(meta, dict) else "job"
        spec = doc.get("spec")
        template = spec.get("template", {}) if isinstance(spec, dict) else {}
        pod = template.get("spec", {}) if isinstance(template, dict) else {}
        containers = pod.get("containers", []) if isinstance(pod, dict) else []
        env = containers[0].get("env", []) if containers and isinstance(containers[0], dict) else []
        names = {str(item.get("name")) for item in env if isinstance(item, dict)}
        if "AR_ENV" not in names:
            raise SystemExit(f"{name} does not set AR_ENV")
        reconcile = name.endswith("-reconcile-roles")
        migrate = name.endswith("-migrate")
        for item in env:
            if not isinstance(item, dict):
                continue
            secret_name = item.get("name") in {"POSTGRES_PASSWORD", "AR_DB_OWNER_PASSWORD"}
            if secret_name and "value" in item:
                raise SystemExit(f"{name} embeds a database password")
            ref = item.get("valueFrom", {})
            key_ref = ref.get("secretKeyRef", {}) if isinstance(ref, dict) else {}
            referenced = str(key_ref.get("name", "")) if isinstance(key_ref, dict) else ""
            owner = item.get("name") == "AR_DB_OWNER_PASSWORD"
            if owner and reconcile and not referenced.endswith("-secrets-hook"):
                raise SystemExit(f"{name} does not read the hook secret")
            if owner and migrate and referenced.endswith("-secrets-hook"):
                message = f"{name} must read the release secret"
                raise SystemExit(message)
            owner_key = item.get("name") == "AR_DB_OWNER_PASSWORD"
            bootstrap_secret = owner_key and name.endswith("-bootstrap")
            release_secret = referenced.endswith("-secrets") and not referenced.endswith(
                "-secrets-hook"
            )
            if bootstrap_secret and not release_secret:
                raise SystemExit(f"{name} must read the release secret")
    if not found:
        raise SystemExit("render has no hook jobs")


def assert_roles(rendered: str) -> None:
    """Application roles are not superuser, and the init script has no password literal."""
    if "PASSWORD 'ar_" in rendered or "\n        superuser: true" in rendered:
        raise SystemExit("rendered manifest still has a public superuser role")
    roles: dict[str, dict[str, object]] = {}
    for doc in docs(rendered):
        if doc.get("kind") != "Cluster":
            continue
        spec = doc.get("spec")
        managed = spec.get("managed", {}) if isinstance(spec, dict) else {}
        listed = managed.get("roles", []) if isinstance(managed, dict) else []
        if isinstance(listed, list):
            for role in listed:
                if isinstance(role, dict):
                    roles[str(role.get("name"))] = role
    owner = roles["ar_owner"]
    if (
        owner.get("superuser") is not False
        or owner.get("bypassrls") is not True
        or owner.get("createdb") is not False
        or owner.get("createrole") is not False
        or owner.get("inRoles")
    ):
        raise SystemExit("ar_owner must bypass row security and must not be superuser")
    if roles["ar_platform"].get("bypassrls") is not True:
        raise SystemExit("ar_platform must bypass row security")
    temporal_role = roles.get("ar_temporal")
    bypass = temporal_role.get("bypassrls") if temporal_role else None
    superuser = temporal_role.get("superuser") if temporal_role else None
    if bypass is not False or superuser is not False:
        raise SystemExit("ar_temporal must be a normal login with no bypass")
    if (
        roles["ar_app"].get("bypassrls") is not False
        or roles["ar_readonly"].get("bypassrls") is not False
    ):
        raise SystemExit("ar_app and ar_readonly must not bypass row security")


def assert_bootstrap_secret(rendered: str) -> None:
    """Staging and production refuse the dev cursor secret, so the job must receive one."""
    for doc in docs(rendered):
        if doc.get("kind") != "Job":
            continue
        meta = doc.get("metadata")
        name = str(meta.get("name")) if isinstance(meta, dict) else ""
        if not name.endswith("-bootstrap"):
            continue
        spec = doc.get("spec")
        template_spec = spec.get("template", {}).get("spec", {}) if isinstance(spec, dict) else {}
        containers = template_spec.get("containers", [])
        if not isinstance(containers, list):
            continue
        for container in containers:
            if not isinstance(container, dict):
                continue
            env = container.get("env", [])
            names_in_env = {
                str(item.get("name")) for item in env if isinstance(item, dict) and item.get("name")
            }
            if "AR_CURSOR_SECRET" not in names_in_env or "AR_DB_OWNER_PASSWORD" not in names_in_env:
                raise SystemExit(f"{name} must receive the cursor secret and the owner password")


def assert_stage6(rendered: str) -> None:
    """api, worker, gateway and sandbox-manager are separate, and only the manager has a token."""
    workloads = {"api", "runtime-worker", "mcp-gateway", "sandbox-manager"}
    found: dict[str, dict[str, object]] = {}
    for doc in docs(rendered):
        if doc.get("kind") != "Deployment":
            continue
        meta = doc.get("metadata")
        if not isinstance(meta, dict):
            continue
        name = str(meta.get("name") or "")
        short = name.removeprefix("agentic-runtime-")
        if short in workloads:
            found[short] = doc
    missing = workloads - set(found)
    if missing:
        raise SystemExit("missing deployments: " + ", ".join(sorted(missing)))
    for short, doc in found.items():
        spec = doc.get("spec")
        template = spec.get("template") if isinstance(spec, dict) else None
        pod = template.get("spec") if isinstance(template, dict) else None
        token = pod.get("automountServiceAccountToken") if isinstance(pod, dict) else None
        if short == "sandbox-manager" and token is not True:
            raise SystemExit("sandbox-manager must mount a token so it can create pods")
        if short != "sandbox-manager" and token is not False:
            raise SystemExit(f"{short} must not mount a service account token")
    policies = names(rendered, "NetworkPolicy")
    for short in workloads:
        if f"agentic-runtime-{short}" not in policies:
            raise SystemExit(f"network policy for {short} is missing")
    text = rendered
    if "ar.io/purpose: sandboxes" not in text:
        raise SystemExit("sandbox namespace purpose label missing")


def assert_stage8(rendered: str) -> None:
    """Two API replicas, production env, and no memory-only durable flag."""
    if 'AR_DURABLE_STATE: "memory"' in rendered or "AR_DURABLE_STATE: memory" in rendered:
        raise SystemExit("chart must not pin the read model to process memory")
    if 'AR_ENV: "prod"' not in rendered and "AR_ENV: prod" not in rendered:
        raise SystemExit("default chart must set AR_ENV to prod")
    for short, minimum in (("api", 2), ("runtime-worker", 2)):
        found = _replicas(rendered, short)
        if found < minimum:
            raise SystemExit(f"{short} replicas are {found}; a second replica must be able to read")


def _pod_spec(doc: dict[str, object]) -> dict[str, object]:
    spec = doc.get("spec")
    template = spec.get("template") if isinstance(spec, dict) else None
    pod = template.get("spec") if isinstance(template, dict) else None
    return pod if isinstance(pod, dict) else {}


def _env_names(container: dict[str, object]) -> set[str]:
    env = container.get("env")
    if not isinstance(env, list):
        return set()
    return {str(item.get("name")) for item in env if isinstance(item, dict)}


def assert_core(ha: str, dev: str) -> None:
    """Temporal persistence, model egress, API ingress, and migrate ordering."""
    assert_temporal(ha, dev)
    assert_model_egress(ha)
    assert_api_ingress(ha)
    assert_migrate_order(ha)


def assert_temporal(default: str, dev: str) -> None:
    """The chart runs one Temporal server on Postgres. SQLite is not a chart mode."""
    for rendered in (default, dev):
        if "start-dev" in rendered or "temporal.db" in rendered:
            raise SystemExit("chart Temporal must not use the SQLite dev server")
        servers = [
            doc
            for doc in docs(rendered)
            if doc.get("kind") == "Deployment"
            and str((doc.get("metadata") or {}).get("name", "")).endswith("-temporal")
        ]
        if len(servers) != 1:
            raise SystemExit("chart must run one Temporal deployment")
        pod = _pod_spec(servers[0])
        containers = pod.get("containers")
        server = containers[0] if isinstance(containers, list) and containers else None
        if not isinstance(server, dict):
            raise SystemExit("temporal pod has no server container")
        present = _env_names(server)
        for required in ("DB", "POSTGRES_SEEDS", "POSTGRES_PWD", "NUM_HISTORY_SHARDS", "DBNAME"):
            if required not in present:
                raise SystemExit(f"temporal pod is missing {required}")
        if _env_value(server, "NUM_HISTORY_SHARDS") != "4":
            raise SystemExit("NUM_HISTORY_SHARDS default is 4")
        inits = pod.get("initContainers")
        init_names = (
            {str(item.get("name")) for item in inits if isinstance(item, dict)}
            if isinstance(inits, list)
            else set()
        )
        if "temporal-schema" not in init_names:
            raise SystemExit("temporal pod does not set up its schema before serving")


def _env_value(container: dict[str, object], key: str) -> str:
    env = container.get("env")
    if not isinstance(env, list):
        return ""
    for item in env:
        if isinstance(item, dict) and item.get("name") == key:
            return str(item.get("value", ""))
    return ""


def assert_model_egress(rendered: str) -> None:
    """With lockdown off, api and runtime-worker get the same any-443 rule as mcp-gateway."""
    for short in ("api", "runtime-worker", "mcp-gateway"):
        if not _has_open_443(rendered, short):
            raise SystemExit(f"{short} has no model egress on 443 while lockdown is off")


def _has_open_443(rendered: str, short: str) -> bool:
    for doc in docs(rendered):
        if doc.get("kind") != "NetworkPolicy":
            continue
        meta = doc.get("metadata")
        name = str(meta.get("name")) if isinstance(meta, dict) else ""
        if not name.endswith(f"-{short}"):
            continue
        spec = doc.get("spec")
        for rule in spec.get("egress", []) if isinstance(spec, dict) else []:
            if not isinstance(rule, dict) or rule.get("to"):
                continue
            ports = rule.get("ports") or []
            if any(isinstance(item, dict) and item.get("port") == 443 for item in ports):
                return True
    return False


def assert_api_ingress(rendered: str) -> None:
    """API ingress is web, channels, and the configured controller. Not every namespace."""
    for doc in docs(rendered):
        if doc.get("kind") != "NetworkPolicy":
            continue
        meta = doc.get("metadata")
        name = str(meta.get("name")) if isinstance(meta, dict) else ""
        if not name.endswith("-api"):
            continue
        spec = doc.get("spec")
        for rule in spec.get("ingress", []) if isinstance(spec, dict) else []:
            if not isinstance(rule, dict):
                continue
            for peer in rule.get("from") or []:
                if not isinstance(peer, dict):
                    continue
                selector = peer.get("namespaceSelector")
                if selector == {}:
                    raise SystemExit("API ingress matches every namespace")
                if isinstance(selector, dict) and selector.get("matchLabels") == {}:
                    raise SystemExit("API ingress matches every namespace")


def assert_migrate_order(rendered: str) -> None:
    """Migrate is post-install and waits, so it cannot run before the database exists."""
    found = False
    for doc in docs(rendered):
        if doc.get("kind") != "Job":
            continue
        meta = doc.get("metadata")
        if not isinstance(meta, dict) or not str(meta.get("name", "")).endswith("-migrate"):
            continue
        found = True
        annotations = meta.get("annotations")
        hook = str(annotations.get("helm.sh/hook")) if isinstance(annotations, dict) else ""
        if "pre-install" in hook or "pre-upgrade" in hook:
            raise SystemExit("migrate hook can run before the database exists")
        if "post-install" not in hook or "post-upgrade" not in hook:
            raise SystemExit("migrate hook is not post-install,post-upgrade")
        pod = _pod_spec(doc)
        containers = pod.get("containers")
        command = None
        if isinstance(containers, list) and containers and isinstance(containers[0], dict):
            command = containers[0].get("command")
        if not isinstance(command, list) or "ar_domain.db.schema_gate" not in command:
            raise SystemExit("migrate does not wait for the database before upgrading")
    if not found:
        raise SystemExit("migrate job missing")


def _replicas(rendered: str, short: str) -> int:
    for doc in docs(rendered):
        if doc.get("kind") != "Deployment":
            continue
        meta = doc.get("metadata")
        name = str(meta.get("name") or "") if isinstance(meta, dict) else ""
        if name != f"agentic-runtime-{short}":
            continue
        spec = doc.get("spec")
        if isinstance(spec, dict) and isinstance(spec.get("replicas"), int):
            return int(spec["replicas"])
    return 0


if __name__ == "__main__":
    main()
