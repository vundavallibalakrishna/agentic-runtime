"""Docker driver: one ``ar-sandbox`` container per sandbox, started and claimed.

The manager runs this in development and CI. A container runs the sandbox-agent, which
the gateway reaches over HTTP; the workspace lives in the container, not a host mount.
Spec: docs/03-specs/12-sandbox-manager.md §6.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from typing import Any


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


async def start_sandbox(
    image: str,
    name: str,
    *,
    token: str = "",
    network: str | None = None,
    port: int = 8080,
    wait_s: float = 30.0,
) -> dict[str, object]:
    """Start a sandbox container from ``image`` and return once its agent is healthy.

    On a named internal network the agent is reached at ``http://<name>:<port>``; without
    one the port is published and reached on loopback (development and the test).
    """
    import aiodocker  # noqa: PLC0415

    docker = aiodocker.Docker()
    try:
        host_config: dict[str, Any] = {}
        config: dict[str, Any] = {
            "Image": image,
            "Env": [f"AR_SANDBOX_TOKEN={token}", f"AR_SANDBOX_AGENT_HOST_PORT={port}"],
            "ExposedPorts": {f"{port}/tcp": {}},
            "HostConfig": host_config,
        }
        if network:
            host_config["NetworkMode"] = network
        else:
            host_config["PublishAllPorts"] = True
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
    async with httpx.AsyncClient(timeout=5.0) as client:
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
