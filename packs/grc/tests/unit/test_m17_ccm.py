"""Control tests, findings, the CCM activity and the pack eval suites."""

import uuid
from datetime import timedelta

import pytest
from temporalio import activity, workflow
from temporalio.common import RetryPolicy
from temporalio.worker import UnsandboxedWorkflowRunner, Worker

from ar_common.errors import ConflictError
from ar_domain.agents.access import Actor
from ar_domain.chat.service import ChatService
from ar_domain.demo_ids import demo_id
from ar_domain.evals.book import EvalBook
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.records.memory import blobs, bucket
from ar_domain.tools.logic import call_args_hash
from ar_domain.tools.pipeline import ToolPipeline
from ar_pack_grc.ccm import ensure_routine, judge, run_test, seed_monitoring
from ar_pack_grc.connectors.kit import MemoryTransport
from ar_pack_grc.evals import documents, enforce_evidence_hash, hashes_present, run_suites
from ar_pack_grc.findings import close_finding, list_findings
from ar_pack_grc.frameworks import create_control
from ar_pack_grc.install import install_for
from ar_pack_grc.tests import create_test, list_results
from ar_system.workflows.eval_run import EVAL_QUEUE, EvalRunWorkflow, execute_eval_activity

_CCM: dict[str, object] = {}


@activity.defn(name="grc_ccm_run")
async def ccm_activity(payload: dict[str, str]) -> dict[str, str]:
    body = run_test(
        _CCM["store"],
        _CCM["actor"],  # type: ignore[arg-type]
        uuid.UUID(payload["test_id"]),
        run_id=uuid.UUID(payload["run_id"]),
    )
    result = body["result"]
    result_id = result["id"] if isinstance(result, dict) else ""
    return {"outcome": str(body["outcome"]), "result_id": str(result_id)}


@workflow.defn(name="GrcCcmWorkflow")
class GrcCcmWorkflow:
    @workflow.run
    async def run(self, payload: dict[str, str]) -> dict[str, str]:
        return await workflow.execute_activity(
            ccm_activity,
            payload,
            start_to_close_timeout=timedelta(seconds=20),
            retry_policy=RetryPolicy(maximum_attempts=1),
        )


PERMS = PERMISSION_KEYS | frozenset(
    {
        "grc.controls:read",
        "grc.controls:manage",
        "grc.evidence:link",
        "grc.tests:read",
        "grc.tests:run",
        "grc.findings:read",
        "grc.findings:manage",
        "evidence:read",
        "evidence:capture",
        "evals:manage",
        "routines:create",
    }
)


def _ready() -> tuple[ChatService, Actor]:
    store = ChatService()
    actor = Actor(
        tenant_id=demo_id("tenant"),
        user_id=demo_id("admin"),
        permissions=PERMS,
        roles=frozenset({"tenant_admin"}),
        display_name="Admin",
    )
    install_for(store, actor)
    return store, actor


def _control_test(store: ChatService, actor: Actor, key: str = "aws-config") -> dict[str, object]:
    control = create_control(store, actor, {"key": key, "title": key, "statement": "Check it."})
    return create_test(
        store,
        actor,
        {
            "control_id": control["id"],
            "key": key,
            "procedure": "Fail when an AWS Config rule is not compliant.",
            "schedule": "0 6 * * *",
            "freshness_days": 30,
        },
    )


def test_failing_fixture_opens_a_finding_that_needs_verified_evidence() -> None:
    store, actor = _ready()
    created = _control_test(store, actor)
    first = run_test(store, actor, uuid.UUID(str(created["id"])))
    assert first["outcome"] == "fail"
    assert first["finding"] is not None
    finding_id = uuid.UUID(str(first["finding"]["id"]))
    evidence_id = uuid.UUID(str(first["evidence_item_ids"][0]))
    with pytest.raises(ConflictError, match="closure_evidence_required"):
        close_finding(store, actor, finding_id, {})
    original = bytes(blobs(store, "evidence")[evidence_id])
    blobs(store, "evidence")[evidence_id] = b"tampered"
    with pytest.raises(ConflictError, match="closure_evidence_required"):
        close_finding(store, actor, finding_id, {"evidence_item_id": str(evidence_id)})
    blobs(store, "evidence")[evidence_id] = original
    closed = close_finding(store, actor, finding_id, {"evidence_item_id": str(evidence_id)})
    assert closed["status"] == "closed"
    routine = ensure_routine(store, actor)
    assert routine["name"] == "grc-ccm"
    assert routine["delivery"] == []


def test_passing_fixture_records_a_result_and_no_finding() -> None:
    store, actor = _ready()
    pages = [
        {"status": 200, "body": {"items": [{"id": "ok", "compliant": True}], "nextCursor": "n"}},
        {"status": 200, "body": {"items": [{"id": "also", "compliant": True}]}},
    ]
    transport = MemoryTransport(pages)
    store.grc_transports = {"grc_aws": {"list_config_rules": transport}}
    created = _control_test(store, actor, "aws-pass")
    run_id = uuid.uuid4()
    test_id = uuid.UUID(str(created["id"]))
    first = run_test(store, actor, test_id, run_id=run_id)
    second = run_test(store, actor, test_id, run_id=run_id)
    assert first["outcome"] == "pass"
    assert first["finding"] is None
    assert second["result"]["id"] == first["result"]["id"]
    assert list_findings(store, actor, {})["items"] == []
    assert list_results(store, actor, {"outcome": "pass"})["items"]
    assert judge(store, []) == "error"


def test_findings_create_is_w2() -> None:
    store, actor = _ready()
    version = next(
        row
        for row in store.tool_versions.values()
        if row["qualified_name"] == "grc.findings.create"
    )
    assert version["risk_class"] == "W2"
    arguments = {"title": "Gap", "severity": "high"}
    digest = call_args_hash(str(version["id"]), arguments)
    held = ToolPipeline(store).execute(
        {
            "tenant_id": actor.tenant_id,
            "user_id": actor.user_id,
            "synthetic": True,
            "tool_version_id": version["id"],
            "arguments": arguments,
            "args_hash": digest,
            "model_call_id": "finding",
        }
    )
    assert held["status"] == "awaiting_approval"
    assert list_findings(store, actor, {})["items"] == []
    approval_id = uuid.UUID(str(held["approval_id"]))
    store.approvals[approval_id]["status"] = "approved"
    done = ToolPipeline(store).execute(
        {
            "tenant_id": actor.tenant_id,
            "user_id": actor.user_id,
            "synthetic": True,
            "tool_version_id": version["id"],
            "arguments": arguments,
            "args_hash": digest,
            "approval_id": approval_id,
            "model_call_id": "finding-2",
        }
    )
    assert done["status"] == "succeeded"
    assert list_findings(store, actor, {"status": "open"})["items"][0]["title"] == "Gap"


@pytest.mark.asyncio
async def test_pack_suites_pass_and_a_missing_hash_fails(temporal_env: object) -> None:
    from ar_system.routines_store import bind_store

    store, actor = _ready()
    bind_store(store)
    assert len(documents()) == 2
    routine = ensure_routine(store, actor)
    agent_id = uuid.UUID(str(routine["agent_id"]))
    summaries = run_suites(store, actor, agent_id)
    assert summaries
    assert all(item["gate_passed"] for item in summaries)
    case = next(row for row in store.eval_cases.values() if row.get("name") == "aws-config-hash")
    assert hashes_present(case)
    case["tool_mocks"][0]["result"].pop("evidenceHash")
    store.defer_eval_runs = True
    suite_id = case["suite_id"]
    started = EvalBook(store).start_run(actor, suite_id, {"agent_version_ref": "published"})
    run_id = uuid.UUID(str(started["id"]))
    client = temporal_env.client  # type: ignore[attr-defined]
    async with Worker(
        client,
        task_queue=EVAL_QUEUE,
        workflows=[EvalRunWorkflow],
        activities=[execute_eval_activity],
    ):
        await client.execute_workflow(
            EvalRunWorkflow.run,
            {"eval_run_id": str(run_id)},
            id=f"eval-{run_id}",
            task_queue=EVAL_QUEUE,
        )
    assert enforce_evidence_hash(store, run_id) is False
    assert store.eval_runs[run_id]["summary"]["gate_passed"] is False
    assert suite_id in EvalBook(store).gated_suite_ids(actor, agent_id)


@pytest.mark.asyncio
async def test_ccm_temporal_routine_is_idempotent(temporal_env: object) -> None:
    store, actor = _ready()
    created = _control_test(store, actor, "aws-temporal")
    test_id = str(created["id"])
    run_id = str(uuid.uuid4())
    _CCM["store"] = store
    _CCM["actor"] = actor
    client = temporal_env.client  # type: ignore[attr-defined]
    async with Worker(
        client,
        task_queue="grc-ccm",
        workflows=[GrcCcmWorkflow],
        activities=[ccm_activity],
        workflow_runner=UnsandboxedWorkflowRunner(),
    ):
        first = await client.execute_workflow(
            GrcCcmWorkflow.run,
            {"test_id": test_id, "run_id": run_id},
            id=f"ccm-{run_id}",
            task_queue="grc-ccm",
        )
        second = await client.execute_workflow(
            GrcCcmWorkflow.run,
            {"test_id": test_id, "run_id": run_id},
            id=f"ccm-{run_id}-again",
            task_queue="grc-ccm",
        )
    assert first["outcome"] == "fail"
    assert second["result_id"] == first["result_id"]
    matches = [
        row
        for row in bucket(store, "grc_test_results").values()
        if str(row.get("run_id")) == run_id
    ]
    assert len(matches) == 1


def test_dev_seed_captures_without_a_link() -> None:
    store, actor = _ready()
    seeded = seed_monitoring(store, actor)
    assert seeded is not None
    assert seeded["outcome"] == "fail"
    from ar_pack_grc.evidence_links import list_links

    assert list_links(store, actor, {})["items"] == []
    assert list_findings(store, actor, {"status": "open"})["items"]
