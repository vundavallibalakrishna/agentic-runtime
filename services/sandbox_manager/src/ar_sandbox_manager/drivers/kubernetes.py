"""Kubernetes sandbox pod and network policy. Spec: docs/03-specs/12-sandbox-manager.md §4.1."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from typing import Any


_REFUSED_NAMESPACES = frozenset({"", "default", "kube-system", "kube-public", "kube-node-lease"})

_TMP_MOUNT = "/" + "tmp"


def pod_spec(
    *,
    sandbox_id: str,
    tenant_id: str,
    template: str,
    runtime_class: str,
    cpu_millis: int,
    memory_mb: int,
    disk_gb: int,
    lifetime_s: int,
    token: str,
) -> dict[str, Any]:
    """The pod the controller submits. No service-account token, no privilege."""
    short = sandbox_id.replace("-", "")[:12]
    quantity = f"{cpu_millis}m"
    memory = f"{memory_mb}Mi"
    proxy = f"http://sbx-{sandbox_id}:{token}@squid.ar-system:3128"
    return {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {
            "name": f"sbx-{short}",
            "labels": {
                "ar/tenant": tenant_id,
                "ar/sandbox": sandbox_id,
                "ar/template": template,
                "ar/component": "sandbox",
            },
        },
        "spec": {
            "runtimeClassName": runtime_class or "gvisor",
            "automountServiceAccountToken": False,
            "hostNetwork": False,
            "hostPID": False,
            "hostIPC": False,
            "activeDeadlineSeconds": lifetime_s,
            "containers": [
                {
                    "name": "sandbox",
                    "image": "registry.local/ar/ar-sandbox@sha256:" + ("ab" * 32),
                    "securityContext": {
                        "runAsNonRoot": True,
                        "runAsUser": 10001,
                        "readOnlyRootFilesystem": True,
                        "allowPrivilegeEscalation": False,
                        "capabilities": {"drop": ["ALL"]},
                        "seccompProfile": {"type": "RuntimeDefault"},
                    },
                    "resources": {
                        "requests": {"cpu": quantity, "memory": memory},
                        "limits": {"cpu": quantity, "memory": memory},
                    },
                    "env": [
                        {"name": "HTTP_PROXY", "value": proxy},
                        {"name": "HTTPS_PROXY", "value": proxy},
                        {"name": "NO_PROXY", "value": ""},
                    ],
                    "volumeMounts": [
                        {"name": "workspace", "mountPath": "/workspace"},
                        {"name": "tmp", "mountPath": _TMP_MOUNT},
                        {"name": "home", "mountPath": "/home/sandbox"},
                    ],
                }
            ],
            "volumes": [
                {"name": "workspace", "emptyDir": {"sizeLimit": f"{disk_gb}Gi"}},
                {"name": "tmp", "emptyDir": {"sizeLimit": "1Gi"}},
                {"name": "home", "emptyDir": {}},
            ],
        },
    }


def network_policy(app_namespace: str = "") -> dict[str, Any]:
    """Default deny. Ingress from the gateway and manager. Egress to Squid and DNS."""
    return {
        "apiVersion": "networking.k8s.io/v1",
        "kind": "NetworkPolicy",
        "metadata": {"name": "sandbox-default-deny"},
        "spec": {
            "podSelector": {"matchLabels": {"ar/component": "sandbox"}},
            "policyTypes": ["Ingress", "Egress"],
            "ingress": [
                {
                    "from": _ingress_from(app_namespace),
                    "ports": [{"port": 8080, "protocol": "TCP"}],
                }
            ],
            "egress": [
                {
                    "to": [{"podSelector": {"matchLabels": {"app.kubernetes.io/name": "squid"}}}],
                    "ports": [{"port": 3128, "protocol": "TCP"}],
                },
                {
                    "to": [
                        {
                            "namespaceSelector": {
                                "matchLabels": {"kubernetes.io/metadata.name": "kube-system"}
                            },
                            "podSelector": {"matchLabels": {"k8s-app": "kube-dns"}},
                        }
                    ],
                    "ports": [
                        {"port": 53, "protocol": "UDP"},
                        {"port": 53, "protocol": "TCP"},
                    ],
                },
            ],
        },
    }


def _ingress_from(app_namespace: str) -> list[dict[str, Any]]:
    peers: list[dict[str, Any]] = []
    for name in ("mcp-gateway", "sandbox-manager"):
        peer: dict[str, Any] = {"podSelector": {"matchLabels": {"app.kubernetes.io/name": name}}}
        if app_namespace:
            peer["namespaceSelector"] = {
                "matchLabels": {"kubernetes.io/metadata.name": app_namespace}
            }
        peers.append(peer)
    return peers


class PodApi(Protocol):
    """The Kubernetes calls the sandbox manager is allowed to make."""

    async def create_pod(self, namespace: str, body: dict[str, Any]) -> None:
        """Create one pod. Other components do not implement this."""

    async def apply_policy(self, namespace: str, body: dict[str, Any]) -> None:
        """Install the sandbox network policy if it is missing."""

    async def delete_pod(self, namespace: str, name: str) -> None:
        """Delete one sandbox pod. A pod that is already gone is not an error."""


class KubernetesPods:
    """Create sandbox pods. This class is the only pod creator in the product."""

    def __init__(self, api: PodApi | None = None, *, namespace: str = "") -> None:
        self._api = api
        self.namespace = namespace or os.environ.get("AR_SANDBOX_NAMESPACE", "ar-sandboxes")

    def start(
        self,
        *,
        sandbox_id: str,
        tenant_id: str,
        template: str,
        token: str,
        cpu_millis: int,
        memory_mb: int,
        disk_gb: int,
        lifetime_s: int,
        runtime_class: str,
    ) -> dict[str, object]:
        """Synchronous entry used by ``ensure_scope``."""
        from ar_common.sandbox_docker import _run_blocking  # noqa: PLC0415

        return _run_blocking(
            self.create(
                sandbox_id=sandbox_id,
                tenant_id=tenant_id,
                template=template,
                token=token,
                cpu_millis=cpu_millis,
                memory_mb=memory_mb,
                disk_gb=disk_gb,
                lifetime_s=lifetime_s,
                runtime_class=runtime_class,
            )
        )

    async def create(
        self,
        *,
        sandbox_id: str,
        tenant_id: str,
        template: str,
        token: str,
        cpu_millis: int,
        memory_mb: int,
        disk_gb: int,
        lifetime_s: int,
        runtime_class: str,
    ) -> dict[str, object]:
        """Submit one namespaced, limited, network-restricted pod."""
        if self.namespace in _REFUSED_NAMESPACES:
            raise RuntimeError("sandbox pods are created only in the sandbox namespace")
        if cpu_millis <= 0 or memory_mb <= 0 or disk_gb <= 0:
            raise RuntimeError("a sandbox pod needs a cpu, memory and disk limit")
        body = pod_spec(
            sandbox_id=sandbox_id,
            tenant_id=tenant_id,
            template=template,
            runtime_class=runtime_class or "gvisor",
            cpu_millis=cpu_millis,
            memory_mb=memory_mb,
            disk_gb=disk_gb,
            lifetime_s=lifetime_s,
            token=token,
        )
        container = body["spec"]["containers"][0]
        limits = container["resources"]["limits"]
        if not limits.get("cpu") or not limits.get("memory"):
            raise RuntimeError("a sandbox pod must set cpu and memory limits")
        app_namespace = os.environ.get("AR_APP_NAMESPACE", "")
        policy = network_policy(app_namespace)
        api = self._api if self._api is not None else InClusterPodApi()
        await api.apply_policy(self.namespace, policy)
        await api.create_pod(self.namespace, body)
        name = str(body["metadata"]["name"])
        endpoint = f"http://{name}.{self.namespace}.svc:8080"
        return {
            "namespace": self.namespace,
            "pod_name": name,
            "endpoint_url": endpoint,
            "driver_ref": f"kubernetes:{self.namespace}/{name}",
        }

    def stop(self, pod_name: str) -> None:
        from ar_common.sandbox_docker import _run_blocking  # noqa: PLC0415

        _run_blocking(self._delete(pod_name))

    async def _delete(self, pod_name: str) -> None:
        api = self._api if self._api is not None else InClusterPodApi()
        await api.delete_pod(self.namespace, pod_name)


class InClusterPodApi:
    """The real client. Imported only when a pod is created."""

    async def create_pod(self, namespace: str, body: dict[str, Any]) -> None:
        from kubernetes_asyncio import client, config  # noqa: PLC0415

        await _load(config)
        async with client.ApiClient() as api:
            await client.CoreV1Api(api).create_namespaced_pod(namespace, body)  # type: ignore[arg-type]

    async def apply_policy(self, namespace: str, body: dict[str, Any]) -> None:
        from kubernetes_asyncio import client, config  # noqa: PLC0415
        from kubernetes_asyncio.client.exceptions import ApiException  # noqa: PLC0415

        await _load(config)
        async with client.ApiClient() as api:
            net = client.NetworkingV1Api(api)
            name = str(body.get("metadata", {}).get("name") or "sandbox-default-deny")
            try:
                await net.read_namespaced_network_policy(name, namespace)
            except ApiException as exc:
                if exc.status != 404:
                    raise
                await net.create_namespaced_network_policy(namespace, body)  # type: ignore[arg-type]

    async def delete_pod(self, namespace: str, name: str) -> None:
        from kubernetes_asyncio import client, config  # noqa: PLC0415
        from kubernetes_asyncio.client.exceptions import ApiException  # noqa: PLC0415

        await _load(config)
        async with client.ApiClient() as api:
            try:
                await client.CoreV1Api(api).delete_namespaced_pod(name, namespace)
            except ApiException as exc:
                if exc.status != 404:
                    raise


async def _load(config: Any) -> None:
    try:
        config.load_incluster_config()
    except config.ConfigException:
        await config.load_kube_config()
