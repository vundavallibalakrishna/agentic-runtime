-- Extensions and the extra database. Roles are created by 01-roles.sh.
-- Spec: docs/07-ops/local-dev.md and docs/04-data/rls.md
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
CREATE DATABASE langfuse OWNER ar_owner;
