-- Local roles. Spec: docs/07-ops/local-dev.md and docs/04-data/rls.md
ALTER ROLE ar_owner BYPASSRLS;
CREATE ROLE ar_app LOGIN PASSWORD 'ar_app' NOSUPERUSER NOBYPASSRLS;
CREATE ROLE ar_platform LOGIN PASSWORD 'ar_platform' NOSUPERUSER BYPASSRLS;
CREATE ROLE ar_readonly LOGIN PASSWORD 'ar_readonly' NOSUPERUSER NOBYPASSRLS;
GRANT CONNECT ON DATABASE agentic_runtime TO ar_app, ar_platform, ar_readonly;
GRANT USAGE ON SCHEMA public TO ar_app, ar_platform, ar_readonly;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
CREATE DATABASE langfuse OWNER ar_owner;
