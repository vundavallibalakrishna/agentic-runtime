"""Kubernetes sandbox pod and network policy. Spec: docs/03-specs/12-sandbox-manager.md §4.1."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

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


def network_policy() -> dict[str, Any]:
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
                    "from": [
                        {"podSelector": {"matchLabels": {"app.kubernetes.io/name": "mcp-gateway"}}},
                        {
                            "podSelector": {
                                "matchLabels": {"app.kubernetes.io/name": "sandbox-manager"}
                            }
                        },
                    ],
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
