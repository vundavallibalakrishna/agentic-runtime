"""A tenant that has set only its answers model can still make and publish an agent."""

from ar_domain.agents.validation import reference_issues, split_issues
from ar_domain.references import ResolveContext


def _issues(aliases: set[str]) -> tuple[list, list]:
    definition = {"model": {"alias": "quick", "fast_alias": "fast", "vision_alias": "vision"}}
    issues, _ = reference_issues(definition, ResolveContext(tenant_id="t", alias_names=aliases))
    return split_issues(issues)


def test_a_missing_image_or_background_model_is_a_warning_that_says_what_happens() -> None:
    errors, warnings = _issues({"quick"})

    assert errors == []
    by_field = {issue.loc: issue.msg for issue in warnings}
    assert "the answers model does background work instead" in by_field[("model", "fastAlias")]
    assert "cannot read images" in by_field[("model", "visionAlias")]


def test_a_missing_answers_model_still_blocks() -> None:
    errors, _ = _issues({"fast", "vision"})

    assert [issue.loc for issue in errors] == [("model", "alias")]


def test_every_alias_set_gives_no_finding() -> None:
    assert _issues({"quick", "fast", "vision"}) == ([], [])
