"""Exercise the local durable stack; retain a paused routine and its reviewable runs.

Run after ``make dev``: ``uv run python scripts/full_stack_smoke.py``.
Uses the seeded administrator and fake model; it never resets the database.
"""

import argparse
import asyncio
import uuid

import httpx
from temporalio.client import Client, WorkflowExecutionStatus

from ar_common.host_ports import local_endpoint


def checked(response: httpx.Response) -> dict[str, object]:
    response.raise_for_status()
    return response.json()


async def verify(url: str, temporal_address: str) -> None:
    label = f"Local verification {uuid.uuid4().hex[:6]}"
    temporal = await Client.connect(temporal_address)
    async with httpx.AsyncClient(base_url=url, timeout=60) as client:
        login = await client.post("/api/v1/auth/dev-login", json={"email": "admin@dev.local"})
        if login.status_code != 303 or "ar_csrf" not in client.cookies:
            raise RuntimeError("Seeded local sign-in failed")
        client.headers.update({"origin": url, "x-csrf-token": client.cookies["ar_csrf"]})
        agent = checked(
            await client.post(
                "/api/v1/agents",
                json={
                    "name": label,
                    "slug": label.lower().replace(" ", "-"),
                },
            )
        )
        agent_id = str(agent["id"])
        checked(
            await client.put(
                f"/api/v1/agents/{agent_id}/versions/draft",
                json={
                    "definition": {
                        "persona": {"displayName": label},
                        "instructions": "Be brief.",
                        "model": {"alias": "reasoning"},
                        "budget": {"maxSteps": 4, "maxTokens": 1000},
                    },
                },
            )
        )
        checked(await client.post(f"/api/v1/agents/{agent_id}:publish"))
        conversation = checked(
            await client.post("/api/v1/conversations", json={"agentId": agent_id})
        )
        posted = checked(
            await client.post(
                f"/api/v1/conversations/{conversation['id']}/messages",
                json={"text": "Verify this published assistant"},
            )
        )
        run_id = str(posted["run"]["id"])
        await completed(client, run_id)
        state = await temporal.get_workflow_handle(f"run-{run_id}").describe()
        if state.status != WorkflowExecutionStatus.COMPLETED:
            raise RuntimeError("The runtime workflow did not complete")
        print(f"Published agent and runtime reply: {agent_id} / {run_id}")

        collection = checked(
            await client.post(
                "/api/v1/knowledge/collections",
                json={
                    "name": label,
                    "slug": label.lower().replace(" ", "-"),
                },
            )
        )
        uploaded = checked(
            await client.post(
                "/api/v1/files:upload",
                files={
                    "upload": (
                        "verification.md",
                        b"The local office opens at 09:30 on weekdays.",
                        "text/markdown",
                    ),
                },
            )
        )
        checked(
            await client.post(
                f"/api/v1/knowledge/collections/{collection['id']}/documents",
                json={"fileIds": [uploaded["id"]]},
            )
        )
        documents = checked(
            await client.get(f"/api/v1/knowledge/collections/{collection['id']}/documents")
        )
        if not any(row["status"] == "indexed" for row in documents["items"]):
            raise RuntimeError("The uploaded document was not indexed")
        print(f"Ingested document: {documents['items'][0]['id']}")

        routine = checked(
            await client.post(
                "/api/v1/routines",
                json={
                    "name": label,
                    "agentId": agent_id,
                    "instructions": "Write a short update.",
                    "trigger": {
                        "type": "schedule",
                        "cron": "0 9 * * 1",
                        "timezone": "Asia/Kolkata",
                    },
                },
            )
        )
        routine_id = str(routine["id"])
        schedule = temporal.get_schedule_handle(f"routine-{routine_id}")
        try:
            manual = checked(await client.post(f"/api/v1/routines/{routine_id}:run", json={}))
            await completed(client, str(manual["runId"]))
            await schedule.trigger()
            for _ in range(100):
                events = checked(await client.get(f"/api/v1/routines/{routine_id}/events"))
                if any(
                    row["source"] == "schedule" and row["status"] == "started"
                    for row in events["items"]
                ):
                    break
                await asyncio.sleep(0.2)
            else:
                raise RuntimeError("The scheduled routine did not finish")
            checked(await client.post(f"/api/v1/routines/{routine_id}:pause"))
            if not (await schedule.describe()).schedule.state.paused:
                raise RuntimeError("Temporal did not pause the schedule")
            checked(await client.post(f"/api/v1/routines/{routine_id}:resume"))
            if (await schedule.describe()).schedule.state.paused:
                raise RuntimeError("Temporal did not resume the schedule")
            print(f"Manual and scheduled routine, pause/resume: {routine_id}")
        finally:
            checked(await client.post(f"/api/v1/routines/{routine_id}:pause"))


async def completed(client: httpx.AsyncClient, run_id: str) -> None:
    response = await client.get(f"/api/v1/runs/{run_id}/events")
    response.raise_for_status()
    if "event: run.completed" not in response.text:
        raise RuntimeError(f"Run {run_id} did not stream a completed reply")
    if checked(await client.get(f"/api/v1/runs/{run_id}"))["status"] != "completed":
        raise RuntimeError(f"Run {run_id} was not persisted as completed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--url",
        default=local_endpoint("AR_PUBLIC_URL", "http://localhost:{port}", "AR_WEB_HOST_PORT"),
    )
    parser.add_argument(
        "--temporal-address",
        default=local_endpoint("AR_TEMPORAL_ADDRESS", "localhost:{port}", "AR_TEMPORAL_HOST_PORT"),
    )
    args = parser.parse_args()
    asyncio.run(verify(args.url.rstrip("/"), args.temporal_address))
