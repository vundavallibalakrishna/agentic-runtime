# ADR-0025: Sign-off binds a statement and a content hash, separate from tool-call approval

- Status: Accepted
- Date: 2026-10-20

## Context

Approvals authorise a tool call's arguments ([ADR-0015](ADR-0015-approval-args-hash.md)). GRC work also needs a human to attest an output: a questionnaire answer, a policy, a risk acceptance, a report. That attestation is about the bytes the human saw, and it must be redone when those bytes change. Segregation of duties (preparer, reviewer and approver are different people; an agent owner cannot sign the agent's own output) does not fit inside the tool-call approver rule.

## Decision

Sign-off is a second mechanism. A review item binds `statement_hash` and `content_hash`. A decision echoes both hashes. A change of content supersedes the item and requires a new signature. Standing approvals never satisfy a sign-off. Multi-level chains, delegation (one hop) and step-up are properties of the review queue. Platform SoD invariants are always on; conflicting role pairs are tenant data, simulated with policy simulation. Normative behaviour: [spec 09 §11–§12](../../03-specs/09-policy-approvals.md#11-reviews-and-sign-off).

## Consequences

The approvals inbox and the review queue are different screens and different tables. Channels can deep-link to a review item; W3-style step-up still happens on the web. Pack workflows create review items; they do not embed a private approval table.

## Alternatives considered

Reusing `approvals` for outputs by inventing a fake tool call (rejected: the hash would not cover the statement text, and SoD would be optional). A free-text "approved" comment with no hash (rejected: the content can change after the comment).
