{{- define "ar.platformDbHost" -}}
{{- if and .Values.postgres.bundled (eq .Values.postgres.mode "statefulset") -}}
{{- printf "%s-postgres:5432" .Release.Name -}}
{{- else if .Values.postgres.bundled -}}
{{- printf "%s-pg-pooler:5432" .Release.Name -}}
{{- else -}}
{{- .Values.postgres.host | default "postgres:5432" -}}
{{- end -}}
{{- end }}
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
{{- define "ar.ip4" -}}
{{- $octets := splitList "." . -}}
{{- add (mul (index $octets 0 | int) 16777216) (add (mul (index $octets 1 | int) 65536) (add (mul (index $octets 2 | int) 256) (index $octets 3 | int))) -}}
{{- end }}
{{- define "ar.pow2" -}}
{{- $n := 1 -}}
{{- range until (int .) -}}
{{- $n = mul $n 2 -}}
{{- end -}}
{{- $n -}}
{{- end }}
{{- define "ar.cidrRelation" -}}
{{- $parent := index . 0 -}}
{{- $child := index . 1 -}}
{{- if or (contains ":" $parent) (contains ":" $child) -}}
ipv6
{{- else -}}
{{- $p := splitList "/" $parent -}}
{{- $c := splitList "/" $child -}}
{{- $pp := index $p 1 | int -}}
{{- $cp := index $c 1 | int -}}
{{- $pb := include "ar.ip4" (index $p 0) | trim | int -}}
{{- $cb := include "ar.ip4" (index $c 0) | trim | int -}}
{{- if and (eq $pp $cp) (eq $pb $cb) -}}
equal
{{- else if lt $pp $cp -}}
{{- $block := include "ar.pow2" (sub 32 $pp) | trim | int -}}
{{- if eq (div $pb $block) (div $cb $block) -}}
contains
{{- else -}}
other
{{- end -}}
{{- else if gt $pp $cp -}}
{{- $block := include "ar.pow2" (sub 32 $cp) | trim | int -}}
{{- if eq (div $pb $block) (div $cb $block) -}}
inside
{{- else -}}
other
{{- end -}}
{{- else -}}
other
{{- end -}}
{{- end -}}
{{- end }}
{{- define "ar.exceptLines" -}}
{{- $cidr := index . 0 -}}
{{- $root := index . 1 -}}
{{- $candidates := list -}}
{{- if $root.Values.cluster.podCIDR -}}
{{- $candidates = append $candidates $root.Values.cluster.podCIDR -}}
{{- end -}}
{{- if $root.Values.cluster.serviceCIDR -}}
{{- $candidates = append $candidates $root.Values.cluster.serviceCIDR -}}
{{- end -}}
{{- range ($root.Values.postgres.denyCidrs | default list) -}}
{{- $candidates = append $candidates . -}}
{{- end -}}
{{- $seen := dict -}}
{{- range $candidates -}}
{{- $rel := include "ar.cidrRelation" (list $cidr .) | trim -}}
{{- if eq $rel "equal" -}}
{{- fail (printf "CIDR %s equals %s, so a NetworkPolicy cannot exclude it. Use a narrower CIDR." $cidr .) -}}
{{- else if eq $rel "ipv6" -}}
{{- fail "cluster CIDR checks support IPv4 only." -}}
{{- else if eq $rel "inside" -}}
{{- fail (printf "CIDR %s sits inside %s, so it would reopen platform pods. Remove it from the database allow list." $cidr .) -}}
{{- else if eq $rel "contains" -}}
{{- $_ := set $seen . "1" -}}
{{- end -}}
{{- end -}}
{{- range $key, $_ := $seen }}
- {{ $key | quote }}
{{- end -}}
{{- end }}
{{- define "ar.tenantDbEgress" -}}
{{- $ports := .Values.airgap.tenantDbPorts | default (list 5432 3306) }}
{{- $cidrs := .Values.airgap.tenantDbCidrs | default list }}
{{- if and $cidrs (not .Values.cluster.podCIDR) }}
{{- fail "airgap.tenantDbCidrs is set but cluster.podCIDR is empty, so a wide CIDR would reopen platform database pods. Set cluster.podCIDR." }}
{{- end }}
{{- range $cidrs }}
{{- $except := include "ar.exceptLines" (list . $) }}
- to:
    - ipBlock:
        cidr: {{ . | quote }}
        {{- if $except }}
        except:
          {{- $except | nindent 10 }}
        {{- end }}
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
{{- define "ar.otelEgress" -}}
- to:
    - podSelector:
        matchLabels:
          app.kubernetes.io/name: {{ .Values.otel.name | default "otel-collector" }}
  ports:
    - {port: 4317, protocol: TCP}
{{- range (.Values.otel.cidrs | default list) }}
- to:
    - ipBlock:
        cidr: {{ . | quote }}
  ports:
    - {port: 4317, protocol: TCP}
{{- end }}
{{- end }}
{{- define "ar.apiServerEgress" -}}
{{- $cidrs := .Values.cluster.apiServerCidrs | default list }}
{{- if and .Values.airgap.lockdown (not $cidrs) }}
{{- fail "airgap.lockdown requires cluster.apiServerCidrs so database and sandbox pods reach the Kubernetes API without opening every address." }}
{{- end }}
{{- if $cidrs }}
- to:
    {{- range $cidrs }}
    - ipBlock:
        cidr: {{ . | quote }}
    {{- end }}
  ports:
    - {port: 443, protocol: TCP}
    - {port: 6443, protocol: TCP}
{{- else }}
- ports:
    - {port: 443, protocol: TCP}
    - {port: 6443, protocol: TCP}
{{- end }}
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
