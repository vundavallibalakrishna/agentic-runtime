# ADR-0024: External participants are guest principals, not users

- Status: Accepted
- Date: 2026-10-20

## Context

Some people who are not employees need time-boxed access to specific records. The v1 non-goal forbids anonymous chat, and identity today is employees and service accounts in Keycloak. Putting guests in `users` would give them group membership, roles and agent access the product does not want. A pack may label a portal for its own audience. Core does not.

## Decision

Guests are a separate principal type (`guest_principals`), invited by email, authenticated with a magic link plus TOTP or a tenant IdP that allows guests. Grants name a portal and a set of record ids. Sessions cannot call agents or tools in 1.0 ([OQ-26](../../open-questions.md)). Downloads of PDF and images are watermarked. M1 tables and the M1 task list are not modified; the guest tables are an additive migration in M14-T11. Normative behaviour: [spec 21 §4](../../03-specs/21-records-governance.md#4-guest-principals).

## Consequences

Authorisation has one more principal type beside user, service account and platform admin. Guest sessions use a separate cookie. Pack portals consume grants; they do not invent a second account system.

## Alternatives considered

Keycloak users with a restricted role (rejected: they would still be employees in SCIM, teams and the agent catalogue, and IdP-less auditors would need accounts in the corporate realm). Sharing links without a principal (rejected: every access must be audited to a named invitee).
