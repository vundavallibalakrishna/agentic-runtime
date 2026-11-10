"""Stage 7: proof labels, hidden connector tools, and the capability matrix."""

from __future__ import annotations

import uuid

import pytest

from ar_domain.chat.service import ChatService
from ar_domain.connectors.catalog import CONNECTORS
from ar_domain.evals.gym.cli import _artifact_refusal
from ar_domain.evals.gym.score import Report
from ar_domain.proof import (
    CONTRACT,
    LIVE,
    UNIT,
    connector_proof,
    matrix_path,
    offered_to_model,
    render_capability_matrix,
)
from ar_domain.tools.pipeline import ToolPipeline
from ar_domain.tools.seed_tools import seed

_NOT_LIVE = frozenset(
    {
        "slack",
        "teams",
        "gcal",
        "m365-calendar",
        "gdrive",
        "sharepoint",
        "jira",
        "confluence",
        "notion",
        "servicenow",
        "salesforce",
        "zendesk",
        "hubspot",
        "okta",
        "entra",
        "aws",
        "azure",
        "gcp",
    }
)


@pytest.mark.unit
def test_eighteen_connectors_are_unit_and_not_offered() -> None:
    by_slug = {item.slug: item for item in CONNECTORS}
    assert _NOT_LIVE <= set(by_slug)
    not_live = [item for item in CONNECTORS if item.verification == "not_live"]
    assert len(not_live) == 18
    assert {item.slug for item in not_live} == _NOT_LIVE
    for connector in not_live:
        assert connector_proof(connector) == UNIT
        for tool in connector.tools:
            qualified = f"connectors.{tool.name}"
            assert offered_to_model(qualified) is False
    assert connector_proof(by_slug["github"]) == LIVE
    assert connector_proof(by_slug["email"]) == LIVE
    github_tool = by_slug["github"].tools[0].name
    assert offered_to_model(f"connectors.{github_tool}") is True
    assert connector_proof(by_slug["s3"]) == CONTRACT
    s3_tool = by_slug["s3"].tools[0].name
    assert offered_to_model(f"connectors.{s3_tool}") is False


@pytest.mark.unit
def test_not_live_connector_tools_are_hidden_from_the_model() -> None:
    store = ChatService()
    seed(store, tenant=False)
    rows = ToolPipeline(store)._bound("connectors", ["*"], uuid.uuid4())
    names = {str(row["qualified_name"]) for row in rows}
    assert any(name.startswith("connectors.github_") for name in names)
    assert any(name.startswith("connectors.email_") for name in names)
    assert not any("slack" in name for name in names)
    assert not any("notion" in name for name in names)
    assert not any(name.startswith("connectors.s3_") or ".s3_" in name for name in names)


@pytest.mark.unit
def test_live_report_requires_a_model_and_a_date() -> None:
    dry = Report(mode="dry-run", scores=())
    assert dry.proof == UNIT
    with pytest.raises(ValueError, match="model id"):
        Report(mode="live", scores=())
    live = Report(mode="live", scores=(), model_id="example-model", reported_on="2026-11-10")
    assert live.proof == LIVE
    from pathlib import Path

    assert _artifact_refusal(Path("live-scorecard.md"), live=True) == ""
    assert _artifact_refusal(Path("m33c-scorecard.md"), live=True)
    assert _artifact_refusal(Path("live-scorecard.md"), live=False)
    assert _artifact_refusal(Path("m33c-scorecard.md"), live=False) == ""


@pytest.mark.unit
def test_capability_matrix_matches_the_committed_file() -> None:
    text = render_capability_matrix()
    assert "not_live" in text
    assert "| capability | `password-sign-in` | `contract` |" in text
    assert "records." not in text
    assert "fill_questionnaire" not in text
    assert "`assurance`" not in text
    assert matrix_path().read_text(encoding="utf-8") == text
