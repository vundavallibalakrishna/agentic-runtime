# ADR-0011: Keycloak (Organizations) as identity broker; BFF session for the web app

- Status: Accepted
- Date: 2026-10-20

## Context

Each tenant brings its own IdP (OIDC/SAML), SCIM provisioning, MFA/step-up; tokens must not live in the browser; RFC 8693 token exchange is needed for downstream APIs.

## Decision

Keycloak 26 realm `agentic-runtime` with one Organization per tenant and brokered IdPs; `api` acts as BFF (confidential client `ar-web`), stores tokens server-side in Valkey sessions and issues `ar_session` (HttpOnly) + `ar_csrf` cookies. API clients use `ark_` keys or bearer JWTs. Offline tokens enable delegation for background runs.

## Consequences

Standard protocols, enterprise SSO, no tokens in JS. Cost: Keycloak operations (HA, upgrades).

## Alternatives considered

Auth SaaS (rejected: on-prem requirement); own identity server (rejected: security risk and effort).
