{{- define "ar.thirdPartyImage" -}}
{{- $root := index . 0 -}}
{{- $repo := index . 1 -}}
{{- $tag := index . 2 | toString -}}
{{- $registry := trimSuffix "/" ($root.Values.global.imageRegistry | default "") -}}
{{- if $registry -}}
{{- printf "%s/%s:%s" $registry $repo $tag -}}
{{- else -}}
{{- printf "%s:%s" $repo $tag -}}
{{- end -}}
{{- end -}}

{{/*
  Cluster roles the migrate Job logs in as. The bundled superuser is
  postgres.username (ar_app). Alembic rewrites that URL to ar_owner, and the
  first revision only creates ar_owner when it can already connect. This
  statement runs as the image superuser during database init, before migrate.
  The ar_owner password is the one owner_database_url rewrites to.
*/}}
{{- define "ar.postgresRolesSql" -}}
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ar_owner') THEN
    CREATE ROLE ar_owner LOGIN PASSWORD 'ar_owner' SUPERUSER BYPASSRLS;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ar_app') THEN
    CREATE ROLE ar_app LOGIN PASSWORD 'ar_app' NOSUPERUSER NOBYPASSRLS;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ar_platform') THEN
    CREATE ROLE ar_platform LOGIN PASSWORD 'ar_platform' NOSUPERUSER BYPASSRLS;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ar_readonly') THEN
    CREATE ROLE ar_readonly LOGIN PASSWORD 'ar_readonly' NOSUPERUSER NOBYPASSRLS;
  END IF;
END $$;
{{- end -}}
