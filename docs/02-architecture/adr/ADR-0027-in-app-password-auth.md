# ADR-0027: In-app userid/password sign-in; no external identity provider

- Status: Accepted
- Date: 2026-11-09

## Context

The product is deployed in-house. A bundled Keycloak ([ADR-0011](ADR-0011-identity-keycloak-bff.md))
added a container, a realm to operate, and user provisioning through the Keycloak admin API, for a
single-tenant install that does not need an external broker. Service-account and personal API-key
access is already handled in the product and needs no identity provider.

## Decision

Sign-in is the product's own **userid/password** check. `POST /api/v1/auth/login` verifies the
password against an argon2id hash on the `users` row and issues the existing BFF session
(`ar_session` HttpOnly + `ar_csrf` cookies, server-side state in Valkey). Users are provisioned with
a password in the database (`scripts/seed_tenant.py`, invitations, an admin set/reset); there is no
external identity provider, and the Keycloak container, OIDC flow and admin client are removed. API
clients continue to use `ark_` keys or key-id+secret service-account keys. Roles and permissions come
from the tenant's rows, exactly as before.

## Consequences

Self-contained in-house install; one fewer service to operate; sign-in works from an empty database.
The product now owns password hashing, login rate-limiting/lockout, and (as follow-ups, [OQ-122](../../open-questions.md))
TOTP MFA, self-service password reset, and multi-tenant login resolution. Enterprise SSO federation
(SAML/OIDC brokering) is dropped; if a customer needs it, it returns as an explicit capability.

## Alternatives considered

Keep Keycloak as an optional bundled IdP (rejected: still operated, and the admin-API/org coupling
remained); point at the customer's own OIDC IdP only (rejected for the default in-house path: needs
an IdP the smallest installs do not have — remains possible later as a connector).
