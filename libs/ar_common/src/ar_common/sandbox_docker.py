"""Start and stop an ``ar-sandbox`` container over the docker daemon.

Infrastructure only: one container per sandbox runs the sandbox-agent, reached over HTTP;
the workspace lives in the container, not a host mount. The manager uses this in its driver,
and the api/runtime worker register a :class:`DockerSandboxLauncher` on the chat store so
``ensure_scope`` can start a container in process (M40-T01e). ``aiodocker`` is imported
lazily so importing this module costs nothing until a container is actually launched.
Spec: docs/03-specs/12-sandbox-manager.md §4.2.
"""

from __future__ import annotations

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any
from urllib.parse import quote, urlsplit

import httpx

from ar_common.egress_http import async_client

_HOST_NETWORKS = frozenset({"", "host"})
_TMP = "/" + "tmp"

# Labels every sandbox container carries. The sweep that removes containers nobody owns
# reads only containers with the product label and this install's id, so it can never
# touch another install's containers or a container this product did not start.
LABEL_PRODUCT = "io.agentic-runtime.sandbox"
LABEL_SANDBOX = "io.agentic-runtime.sandbox-id"
LABEL_TENANT = "io.agentic-runtime.tenant-id"
LABEL_INSTALL = "io.agentic-runtime.install-id"
LABEL_OWNER = "io.agentic-runtime.owner"
# Containers started before the labels existed are known only by this name prefix.
NAME_PREFIX = "ar-sbx-"

if TYPE_CHECKING:
    from collections.abc import Coroutine


def docker_available() -> bool:
    """True when the docker client can see a daemon. A missing socket is not fatal."""
    try:
        import aiodocker  # noqa: PLC0415
    except ImportError:
        return False
    try:
        client: Any = aiodocker.Docker()
    except Exception:  # noqa: BLE001 - a missing socket must not crash the process
        return False
    del client
    return True


async def image_present(image: str) -> bool:
    """True when ``image`` is available to the local daemon; any error means absent."""
    try:
        import aiodocker  # noqa: PLC0415
    except ImportError:
        return False
    docker: Any = aiodocker.Docker()
    try:
        await docker.images.inspect(image)
    except Exception:  # noqa: BLE001 - a missing image or daemon means absent
        return False
    else:
        return True
    finally:
        await docker.close()


def sandbox_limits() -> tuple[int, int, int]:
    """CPU millis, memory mebibytes and pid limit for a confined sandbox."""
    return (
        _positive("AR_SANDBOX_CPU_MILLIS", 500),
        _positive("AR_SANDBOX_MEMORY_MB", 512),
        _positive("AR_SANDBOX_PIDS_LIMIT", 256),
    )


def confined_host_config(
    network: str, *, cpu_millis: int, memory_mb: int, pids_limit: int
) -> dict[str, Any]:
    """Docker HostConfig for a sandbox that cannot reach the host network.

    The root filesystem is read-only. Writable paths are tmpfs mounts. Capabilities
    are dropped. The named network is the only interface.
    """
    if network.strip().lower() in _HOST_NETWORKS:
        raise RuntimeError("a sandbox container cannot use the host network")
    if cpu_millis <= 0 or memory_mb <= 0 or pids_limit <= 0:
        raise RuntimeError("a sandbox container needs a cpu, memory and pid limit")
    return {
        "NetworkMode": network,
        "ReadonlyRootfs": True,
        "CapDrop": ["ALL"],
        "SecurityOpt": ["no-new-privileges:true"],
        "Memory": memory_mb * 1024 * 1024,
        "NanoCpus": cpu_millis * 1_000_000,
        "PidsLimit": pids_limit,
        "Tmpfs": {
            _TMP: "rw,nosuid,size=64m,mode=1777",
            "/workspace": "rw,nosuid,size=1g,mode=1777",
            "/home/sandbox": "rw,nosuid,size=256m,mode=1777",
            "/run": "rw,noexec,nosuid,size=16m,mode=1777",
        },
    }


def proxy_url(base: str, sandbox_id: str, token: str) -> str:
    """Basic-auth proxy URL the sandbox presents to Squid. Empty when unset."""
    if not base.strip() or not sandbox_id.strip() or not token:
        return ""
    parts = urlsplit(base.strip())
    host = parts.hostname or ""
    if not host:
        return ""
    port = f":{parts.port}" if parts.port else ""
    user = quote(f"sbx-{sandbox_id}", safe="")
    secret = quote(token, safe="")
    scheme = parts.scheme or "http"
    return f"{scheme}://{user}:{secret}@{host}{port}"


def _positive(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        message = f"{name} must be a positive integer"
        raise RuntimeError(message) from exc
    if value <= 0:
        message = f"{name} must be a positive integer"
        raise RuntimeError(message)
    return value


async def start_sandbox(
    image: str,
    name: str,
    *,
    token: str = "",
    network: str | None = None,
    port: int = 8080,
    wait_s: float = 30.0,
    proxy: str | None = None,
    sandbox_id: str = "",
    labels: dict[str, str] | None = None,
) -> dict[str, object]:
    """Start a sandbox container from ``image`` and return once its agent is healthy.

    A named network confines the container: no host network, dropped capabilities,
    a read-only root, resource limits, and HTTP(S) egress through the proxy. Without
    a network the port is published on loopback for a test that opts into that path.
    ``labels`` say whose container this is, so the sweep can find it later.
    """
    import aiodocker  # noqa: PLC0415

    docker = aiodocker.Docker()
    try:
        env = [
            f"AR_SANDBOX_TOKEN={token}",
            f"AR_SANDBOX_AGENT_HOST_PORT={port}",
            "PYTHONDONTWRITEBYTECODE=1",
            "HOME=/home/sandbox",
        ]
        config: dict[str, Any] = {
            "Image": image,
            "Env": env,
            "ExposedPorts": {f"{port}/tcp": {}},
            "Labels": dict(labels or {}),
        }
        if network:
            cpu_millis, memory_mb, pids_limit = sandbox_limits()
            host_config = confined_host_config(
                network, cpu_millis=cpu_millis, memory_mb=memory_mb, pids_limit=pids_limit
            )
            config["User"] = "10001:10001"
            config["HostConfig"] = host_config
            proxied = proxy_url(proxy or "", sandbox_id, token)
            if proxied:
                env.extend([f"HTTP_PROXY={proxied}", f"HTTPS_PROXY={proxied}", "NO_PROXY="])
        else:
            config["HostConfig"] = {"PublishAllPorts": True}
        container = await docker.containers.create_or_replace(name=name, config=config)
        await container.start()
        endpoint = await _endpoint(container, network, port)
        await _wait_healthy(endpoint, token, wait_s)
        return {"container_id": container.id, "endpoint_url": endpoint, "token": token}
    finally:
        await docker.close()


async def stop_sandbox(container_id: str) -> None:
    """Stop and remove a sandbox container. A container already gone is not an error."""
    import aiodocker  # noqa: PLC0415

    docker = aiodocker.Docker()
    try:
        container = await docker.containers.get(container_id)
        await container.delete(force=True)
    except aiodocker.exceptions.DockerError:
        return
    finally:
        await docker.close()


def sandbox_labels(
    *, install_id: str, owner: str, sandbox_id: str, tenant_id: str
) -> dict[str, str]:
    """The labels of one sandbox container: the product, the install, and whose it is."""
    return {
        LABEL_PRODUCT: "true",
        LABEL_INSTALL: install_id,
        LABEL_OWNER: owner,
        LABEL_SANDBOX: sandbox_id,
        LABEL_TENANT: tenant_id,
    }


async def list_sandboxes(install_id: str) -> list[dict[str, object]]:
    """Every container, running or not, that carries the product label and this install's id.

    The daemon does the filtering, so a container of another install, or one with no
    label, is never in the answer. An empty install id lists nothing.
    """
    if not install_id.strip():
        return []
    import aiodocker  # noqa: PLC0415

    docker = aiodocker.Docker()
    try:
        found = await docker.containers.list(
            all=True,
            filters={"label": [f"{LABEL_PRODUCT}=true", f"{LABEL_INSTALL}={install_id}"]},
        )
        return [_described(item) for item in found]
    finally:
        await docker.close()


async def unlabelled_sandboxes() -> list[str]:
    """Names of containers called ``ar-sbx-*`` that carry no product label.

    A release before the labels started them. Nothing removes them automatically, because
    without a label there is no telling which install they belong to.
    """
    import aiodocker  # noqa: PLC0415

    docker = aiodocker.Docker()
    try:
        found = await docker.containers.list(all=True, filters={"name": [NAME_PREFIX]})
        described = [_described(item) for item in found]
    finally:
        await docker.close()
    return sorted(
        str(item["name"])
        for item in described
        if str(item["name"]).startswith(NAME_PREFIX) and LABEL_PRODUCT not in _labels(item)
    )


def _labels(item: dict[str, object]) -> dict[str, str]:
    raw = item.get("labels")
    return {str(key): str(value) for key, value in raw.items()} if isinstance(raw, dict) else {}


def _described(container: Any) -> dict[str, object]:
    """One listed container as plain data: id, name, labels and when it was created."""
    raw = getattr(container, "_container", None)
    info: dict[str, Any] = raw if isinstance(raw, dict) else {}
    names = info.get("Names")
    name = str(names[0]).lstrip("/") if isinstance(names, list) and names else ""
    labels = info.get("Labels")
    created = info.get("Created")
    return {
        "container_id": str(info.get("Id") or getattr(container, "id", "")),
        "name": name,
        "labels": dict(labels) if isinstance(labels, dict) else {},
        "created": float(created) if isinstance(created, (int, float)) else 0.0,
    }


async def _endpoint(container: Any, network: str | None, port: int) -> str:
    info = await container.show()
    settings = info.get("NetworkSettings", {}) if isinstance(info, dict) else {}
    if network:
        networks = settings.get("Networks", {})
        address = networks.get(network, {}).get("IPAddress") if isinstance(networks, dict) else ""
        name = str(info.get("Name", "")).lstrip("/")
        host = address or name
        return f"http://{host}:{port}"
    ports = settings.get("Ports", {}) if isinstance(settings, dict) else {}
    mapping = ports.get(f"{port}/tcp") if isinstance(ports, dict) else None
    host_port = mapping[0]["HostPort"] if isinstance(mapping, list) and mapping else str(port)
    return f"http://127.0.0.1:{host_port}"


async def _wait_healthy(endpoint: str, token: str, wait_s: float) -> None:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    deadline = asyncio.get_running_loop().time() + wait_s
    async with async_client(mode="cluster", timeout=5.0) as client:
        while True:
            try:
                response = await client.get(f"{endpoint}/healthz", headers=headers)
                if response.status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            if asyncio.get_running_loop().time() >= deadline:
                raise RuntimeError(f"the sandbox agent at {endpoint} did not become healthy")
            await asyncio.sleep(0.3)


def _run_blocking[T](coro: Coroutine[Any, Any, T]) -> T:
    """Run ``coro`` to completion whether or not a loop is already running on this thread.

    ``ensure_scope`` is synchronous and called both off the loop (a tool call on a worker
    thread) and from an async request handler (the computer panel). ``asyncio.run`` fails
    inside a running loop, so there we drive the coroutine on a throwaway loop in one thread.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


class DockerSandboxLauncher:
    """A synchronous launcher the chat store calls to start and stop sandbox containers.

    Bound to one image (and optionally an internal network) at registration, it bridges
    ``ensure_scope`` to the async docker primitives above.
    """

    def __init__(
        self,
        image: str,
        *,
        network: str | None = None,
        port: int = 8080,
        wait_s: float = 30.0,
        proxy: str | None = None,
        install_id: str = "",
        owner: str = "",
    ) -> None:
        self._image = image
        self._network = network
        self._port = port
        self._wait_s = wait_s
        self._proxy = proxy
        # The install whose containers these are, and the process that starts them.
        self.install_id = install_id
        self.owner = owner

    def start(
        self, name: str, token: str, sandbox_id: str = "", tenant_id: str = ""
    ) -> dict[str, object]:
        """Start a labelled container and return ``{container_id, endpoint_url, token}``."""
        return _run_blocking(
            start_sandbox(
                self._image,
                name,
                token=token,
                network=self._network,
                port=self._port,
                wait_s=self._wait_s,
                proxy=self._proxy,
                sandbox_id=sandbox_id,
                labels=sandbox_labels(
                    install_id=self.install_id,
                    owner=self.owner,
                    sandbox_id=sandbox_id,
                    tenant_id=tenant_id,
                ),
            )
        )

    def stop(self, container_id: str) -> None:
        """Stop and remove the container; a container already gone is not an error."""
        _run_blocking(stop_sandbox(container_id))

    def containers(self) -> list[dict[str, object]]:
        """This install's sandbox containers, each with its labels and creation time."""
        return _run_blocking(list_sandboxes(self.install_id))

    def unlabelled(self) -> list[str]:
        """Names of ``ar-sbx-*`` containers from before the labels. They are only reported."""
        return _run_blocking(unlabelled_sandboxes())
