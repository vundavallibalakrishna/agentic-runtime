"""Step-up problem body. Spec: docs/03-specs/09-policy-approvals.md §5."""

from typing import TYPE_CHECKING

from ar_common.errors import ForbiddenError

if TYPE_CHECKING:
    from pydantic import JsonValue


class StepUpRequiredError(ForbiddenError):
    """The session must step up before this decision."""

    def __init__(self) -> None:
        super().__init__("step-up authentication is required")

    def to_problem(self, *, instance: str, request_id: str) -> dict[str, JsonValue]:
        body = super().to_problem(instance=instance, request_id=request_id)
        body["stepUpRequired"] = True
        return body
