# ADR-0031: Production identity is OIDC

- Status: Accepted
- Date: 2026-11-10

## Context

[ADR-0011](ADR-0011-identity-keycloak-bff.md) bundled Keycloak. [ADR-0027](ADR-0027-in-app-password-auth.md) removed every external identity provider and made userid/password the only sign-in. A production install needs the customer's identity system. A laptop and a single-tenant trial still need a way to sign in without one.

## Decision

Production identity is OIDC.

- The browser uses the authorization-code flow.
- Integrators send a JWT bearer token, checked against the tenant's JWKS.
- Local passwords are a documented development and single-tenant mode only. They are not the Helm default.

Stage 3 implements this. [ADR-0027](ADR-0027-in-app-password-auth.md) remains the description of the password mode. It is not the production default.

## Consequences

Helm does not enable password login unless the operator turns that mode on. Cookies for the browser session are `Secure`. Lockout state is in Valkey, so it is shared across API replicas. API keys stay as they are; the bearer JWT is an additional integrator path, not a replacement for `ark_` keys.

## Alternatives

Keep passwords as the Helm default and offer OIDC as an option. Rejected: the default would be the weaker mode. Bundle one identity product again. Rejected: the customer already has an OIDC provider, and core must not pick a vendor.
