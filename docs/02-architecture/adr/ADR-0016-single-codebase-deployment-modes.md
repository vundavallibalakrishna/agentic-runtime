# ADR-0016: One codebase for SaaS and single-tenant installs

- Status: Accepted
- Date: 2026-10-20

## Context

The product ships as multi-tenant SaaS and as a single-tenant install on Kubernetes/on-prem; diverging codebases would double the work.

## Decision

`AR_DEPLOYMENT_MODE=saas|single_tenant` toggles behaviour (self-signup, platform admin UI, bootstrap tenant `AR_BOOTSTRAP_TENANT_SLUG`, content-capture defaults); the same images and Helm chart with different values ([deployment-modes](../../00-overview/deployment-modes.md)).

## Consequences

One test matrix with two modes. Cost: mode checks must be centralised (`ar_common.settings.mode`) and tested.

## Alternatives considered

Separate on-prem fork (rejected).
