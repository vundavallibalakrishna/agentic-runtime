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
  Install secret. Role passwords are keys in this secret. Helm never generates them:
  a render without a caller-supplied value fails, and `secrets.existingSecret`
  is the same keys created outside the chart (GitOps / external secrets).
*/}}
{{- define "ar.installSecret" -}}
{{- .Values.secrets.existingSecret | default (printf "%s-secrets" .Release.Name) -}}
{{- end -}}

{{- define "ar.roleSecret" -}}
{{- $root := index . 0 -}}
{{- $role := index . 1 -}}
{{- printf "%s-db-role-%s" $root.Release.Name ($role | replace "_" "-") -}}
{{- end -}}

{{- define "ar.refuseDatabasePassword" -}}
{{- $value := index . 0 | toString | lower | trim -}}
{{- $role := index . 1 | toString | lower -}}
{{- $label := index . 2 -}}
{{- $bad := list "" "ar-install-db" "airgap-set-a-real-password" "changeme" "change-me" "password" "placeholder" "postgres" "install-time" "ar_owner" "ar_app" "ar_platform" "ar_readonly" -}}
{{- if or (has $value $bad) (eq $value $role) -}}
{{- fail (printf "%s is unset, a placeholder, or the role name" $label) -}}
{{- end -}}
{{- end -}}

{{/*
  Refuses placeholder and role-name passwords wherever the chart is the one
  writing the Secret. When secrets.create is false (values-large, values-saas,
  values-external, and any existingSecret install) this render check does not
  run. Staging and production then refuse the same values in
  assert_installed_database_secrets, which the API, Alembic and bootstrap call.
  A bundled CloudNativePG install with secrets.create false does not create
  the <release>-db-role-ar-* basic-auth secrets the cluster references. Create
  those four secrets, or the role passwords and POSTGRES_PASSWORD in the
  install secret, before install.
*/}}
{{- define "ar.assertDatabasePasswords" -}}
{{- if .Values.secrets.create -}}
{{- range $key, $role := dict "AR_DB_OWNER_PASSWORD" "ar_owner" "AR_DB_PLATFORM_PASSWORD" "ar_platform" "AR_DB_APP_PASSWORD" "ar_app" "AR_DB_READONLY_PASSWORD" "ar_readonly" -}}
{{- include "ar.refuseDatabasePassword" (list (index $.Values.secrets.data $key | default "") $role $key) -}}
{{- end -}}
{{- if and .Values.postgres.bundled (eq .Values.postgres.mode "statefulset") -}}
{{- include "ar.refuseDatabasePassword" (list (.Values.postgres.superuserPassword | default "") "postgres" "postgres.superuserPassword") -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "ar.rolePasswordEnv" -}}
{{- $secret := include "ar.installSecret" . -}}
{{- range $key := list "AR_DB_OWNER_PASSWORD" "AR_DB_PLATFORM_PASSWORD" "AR_DB_APP_PASSWORD" "AR_DB_READONLY_PASSWORD" }}
- name: {{ $key }}
  valueFrom:
    secretKeyRef:
      name: {{ $secret }}
      key: {{ $key }}
{{- end }}
{{- end -}}
