{{- define "ar.platformDbEgress" -}}
{{- if and .Values.postgres.bundled (eq .Values.postgres.mode "cnpg") }}
- to:
    - podSelector:
        matchLabels:
          cnpg.io/cluster: {{ .Release.Name }}-pg
          cnpg.io/podRole: pooler
  ports:
    - {port: 5432, protocol: TCP}
{{- else if and .Values.postgres.bundled (eq .Values.postgres.mode "statefulset") }}
- to:
    - podSelector:
        matchLabels:
          app.kubernetes.io/name: postgres
          app.kubernetes.io/instance: {{ .Release.Name }}
  ports:
    - {port: 5432, protocol: TCP}
{{- else if not .Values.postgres.bundled }}
{{- $cidrs := .Values.postgres.externalCidrs | default list }}
{{- if not $cidrs }}
{{- fail "airgap.isolatePlatformDb is on, but Postgres is external and postgres.externalCidrs is empty. Set the platform database CIDR, or turn isolatePlatformDb off." }}
{{- end }}
{{- range $cidrs }}
- to:
    - ipBlock:
        cidr: {{ . | quote }}
  ports:
    - {port: 5432, protocol: TCP}
{{- end }}
{{- else }}
{{- fail (printf "airgap.isolatePlatformDb does not know postgres.mode %q. Use cnpg, statefulset, or an external database with postgres.externalCidrs." .Values.postgres.mode) }}
{{- end }}
{{- end }}
{{- define "ar.tenantDbEgress" -}}
{{- $ports := .Values.airgap.tenantDbPorts | default (list 5432 3306) }}
{{- range (.Values.airgap.tenantDbCidrs | default list) }}
- to:
    - ipBlock:
        cidr: {{ . | quote }}
  ports:
    {{- range $ports }}
    - {port: {{ . }}, protocol: TCP}
    {{- end }}
{{- end }}
{{- end }}
{{- define "ar.egressOpensDatabase" -}}
{{- $ports := .Values.airgap.egressPorts | default (list 443 80) }}
{{- $dbPorts := .Values.airgap.tenantDbPorts | default (list 5432 3306) }}
{{- range $ports -}}
{{- $needle := . | toString -}}
{{- range $dbPorts -}}
{{- if eq $needle (. | toString) }}yes{{- end -}}
{{- end -}}
{{- end -}}
{{- end }}
{{- define "ar.externalDbEgress" -}}
{{- range (.Values.postgres.externalCidrs | default list) }}
- to:
    - ipBlock:
        cidr: {{ . | quote }}
  ports:
    - {port: 5432, protocol: TCP}
{{- end }}
{{- end }}
