#!/bin/sh
# Application roles for an image-init database (compose and the StatefulSet).
# Passwords come from the environment. CloudNativePG uses managed roles instead.
# The refused values match ar_common.database_roles.PLACEHOLDERS. The unit test
# test_placeholder_copies_match keeps this list and the Helm list on that set.
set -eu

refuse() {
  role=$1
  value=$(printf '%s' "$2" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
  folded=$(printf '%s' "$value" | tr '[:upper:]' '[:lower:]')
  if [ -z "$folded" ]; then
    echo "database password for ${role} is empty, a placeholder, or a role name" >&2
    exit 1
  fi
  case $folded in
    ar-install-db|airgap-set-a-real-password|changeme|change-me|password|placeholder|postgres|install-time|ar_owner|ar_app|ar_platform|ar_readonly)
      echo "database password for ${role} is empty, a placeholder, or a role name" >&2
      exit 1
      ;;
  esac
}

refuse ar_owner "${AR_DB_OWNER_PASSWORD:?AR_DB_OWNER_PASSWORD is required}"
refuse ar_platform "${AR_DB_PLATFORM_PASSWORD:?AR_DB_PLATFORM_PASSWORD is required}"
refuse ar_app "${AR_DB_APP_PASSWORD:?AR_DB_APP_PASSWORD is required}"
refuse ar_readonly "${AR_DB_READONLY_PASSWORD:?AR_DB_READONLY_PASSWORD is required}"

# \getenv reads the process environment. Passwords are not psql argv, so they
# do not show up in the process list.
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<'SQL'
\getenv owner_pw AR_DB_OWNER_PASSWORD
\getenv platform_pw AR_DB_PLATFORM_PASSWORD
\getenv app_pw AR_DB_APP_PASSWORD
\getenv readonly_pw AR_DB_READONLY_PASSWORD
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS citext;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS btree_gin;
SELECT format(
  CASE WHEN EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ar_owner')
       THEN 'ALTER ROLE ar_owner WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE BYPASSRLS PASSWORD %L'
       ELSE 'CREATE ROLE ar_owner WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE BYPASSRLS PASSWORD %L'
  END, :'owner_pw') \gexec
SELECT format(
  CASE WHEN EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ar_platform')
       THEN 'ALTER ROLE ar_platform WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE BYPASSRLS PASSWORD %L'
       ELSE 'CREATE ROLE ar_platform WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE BYPASSRLS PASSWORD %L'
  END, :'platform_pw') \gexec
SELECT format(
  CASE WHEN EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ar_app')
       THEN 'ALTER ROLE ar_app WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS PASSWORD %L'
       ELSE 'CREATE ROLE ar_app WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS PASSWORD %L'
  END, :'app_pw') \gexec
SELECT format(
  CASE WHEN EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ar_readonly')
       THEN 'ALTER ROLE ar_readonly WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS PASSWORD %L'
       ELSE 'CREATE ROLE ar_readonly WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS PASSWORD %L'
  END, :'readonly_pw') \gexec
SELECT format('ALTER DATABASE %I OWNER TO ar_owner', current_database()) \gexec
SELECT format('GRANT CONNECT ON DATABASE %I TO ar_app, ar_platform, ar_readonly', current_database()) \gexec
GRANT ar_app TO ar_owner WITH ADMIN OPTION;
GRANT ar_platform TO ar_owner WITH ADMIN OPTION;
GRANT ar_readonly TO ar_owner WITH ADMIN OPTION;
SQL
