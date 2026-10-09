{{- define "sample.identity" -}}
{{- printf "%s/%s/%s" .Release.Namespace .Chart.Name .Release.Name | sha256sum | trunc 16 -}}
{{- end -}}
{{- define "sample.name" -}}
{{- printf "%s-%s-%s" (.Chart.Name | trunc 20) (.Release.Name | trunc 15 | trimSuffix "-") (include "sample.identity" .) -}}
{{- end -}}
{{- define "sample.selector" -}}
app.kubernetes.io/name: {{ .Chart.Name | quote }}
app.kubernetes.io/instance: {{ .Release.Name | quote }}
samples.coco.io/identity: {{ include "sample.identity" . | quote }}
{{- end -}}
{{- define "sample.labels" -}}
{{ include "sample.selector" . }}
app.kubernetes.io/managed-by: {{ .Release.Service | quote }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | quote }}
{{- with .Values.resourceLabels }}
{{ toYaml . }}
{{- end }}
{{- end -}}
{{- define "sample.account" -}}
{{- if .Values.serviceAccount.create -}}
{{- include "sample.name" . -}}
{{- else -}}
{{- required "serviceAccount.name is required when create=false" .Values.serviceAccount.name -}}
{{- end -}}
{{- end -}}
{{- define "sample.annotations" -}}
io.katacontainers.config.hypervisor.default_memory: "2048"
io.katacontainers.config.runtime.create_container_timeout: {{ max 900 (add (int .Values.startup.timeoutSeconds) 30) | quote }}
{{- if eq .Values.initdata.mode "configMap" }}
coco.io/initdata-configmap: {{ .Values.initdata.configMapName | quote }}
{{- else if eq .Values.initdata.mode "inline" }}
io.katacontainers.config.hypervisor.cc_init_data: {{ .Values.initdata.encoded | quote }}
{{- end }}
{{- with .Values.podAnnotations }}
{{ toYaml . }}
{{- end }}
{{- end -}}
{{- define "sample.validate" -}}
{{- if and (ne .Values.initdata.mode "inline") .Values.initdata.encoded }}{{ fail "initdata.encoded requires mode=inline; it is never silently ignored" }}{{ end -}}
{{- if and .Values.serviceAccount.create .Values.serviceAccount.name }}{{ fail "name is an existing-account reference only; set create=false" }}{{ end -}}
{{- if and (hasKey .Values "keyDelivery") (ne .Chart.Name "block-storage-encrypted") }}{{ fail "keyDelivery is only supported by the encrypted chart" }}{{ end -}}
{{- if and (hasKey .Values "nfs") (ne .Chart.Name "nfs-direct") }}{{ fail "nfs values are only supported by the direct NFS chart" }}{{ end -}}
{{- range $reserved := list "/proc" "/sys" "/dev" "/etc" "/run" "/usr" "/bin" "/sbin" "/lib" "/lib64" "/boot" "/root" "/opt/sample" }}
{{- if or (eq $.Values.storage.mountPath $reserved) (hasPrefix (printf "%s/" $reserved) $.Values.storage.mountPath) }}{{ fail "storage path overlaps reserved runtime paths" }}{{ end -}}
{{- end }}
{{- range $name, $resources := .Values.resources }}
  {{- range $field := list "requests" "limits" }}
    {{- $map := index $resources $field }}
    {{- if or (not (hasKey $map "cpu")) (not (hasKey $map "memory")) }}{{ fail "every role requires CPU and memory requests and limits" }}{{ end }}
  {{- end }}
  {{- $requested := include "sample.memoryBytes" $resources.requests.memory | float64 }}
  {{- $limited := include "sample.memoryBytes" $resources.limits.memory | float64 }}
  {{- if or (le $requested 0.0) (lt $limited $requested) }}{{ fail "memory limits must cover positive requests" }}{{ end }}
  {{- if and (eq $name "application") (lt $requested 2684354560.0) }}{{ fail "application memory must reserve at least 2560Mi for guest RAM and overhead" }}{{ end }}
  {{- $cpuRequest := include "sample.cpuMilli" $resources.requests.cpu | float64 }}
  {{- $cpuLimit := include "sample.cpuMilli" $resources.limits.cpu | float64 }}
  {{- if or (lt $cpuRequest 1.0) (lt $cpuLimit $cpuRequest) }}{{ fail "CPU limits must cover requests of at least 1m" }}{{ end }}
{{- end }}
{{- range $image := .Values.images }}
  {{- if regexMatch ":(latest|stable|main|master|nightly|edge|dev|canary)$" $image }}{{ fail "floating image aliases are not supported" }}{{ end }}
{{- end }}
{{- if gt (int .Values.startup.pollSeconds) (int .Values.startup.timeoutSeconds) }}{{ fail "startup polling must not exceed timeout" }}{{ end -}}
{{- if eq (include "sample.account" .) "default" }}{{ fail "the default service account is not supported" }}{{ end -}}
{{- range $map := list .Values.podLabels .Values.resourceLabels }}
  {{- range $key, $_ := $map }}
    {{- if or (hasPrefix "app.kubernetes.io/" $key) (hasPrefix "samples.coco.io/" $key) (eq $key "helm.sh/chart") (eq $key "coco.io/skip-initdata") }}{{ fail "reserved label cannot be customized" }}{{ end }}
  {{- end }}
{{- end }}
{{- range $map := list .Values.podAnnotations .Values.resourceAnnotations }}
  {{- range $key, $_ := $map }}
    {{- if or (hasPrefix "meta.helm.sh/" $key) (hasPrefix "helm.sh/" $key) (hasPrefix "io.katacontainers." $key) (eq $key "coco.io/initdata-configmap") (eq $key "checksum/scripts") }}{{ fail "reserved annotation cannot be customized" }}{{ end }}
  {{- end }}
{{- end }}
{{- if eq .Chart.Name "block-storage-encrypted" }}
  {{- $key := .Values.keyDelivery }}
  {{- $external := $key.sealed.existingSecret.name }}
  {{- $envelope := $key.sealed.envelope }}
  {{- if eq $key.mode "sealed" }}
    {{- if eq (not (empty $external)) (not (empty $envelope)) }}{{ fail "sealed mode requires exactly one envelope source" }}{{ end }}
    {{- if and $envelope (not (regexMatch "^sealed\\.[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]+$" $envelope)) }}{{ fail "a genuine signed CoCo sealed token is required" }}{{ end }}
    {{- if $envelope }}
      {{- $parts := splitList "." $envelope }}
      {{- $header := include "sample.decodeSegment" (index $parts 1) | fromJson }}
      {{- $payload := include "sample.decodeSegment" (index $parts 2) | fromJson }}
      {{- if or (ne (get $header "alg") "ES256") (not (regexMatch "^[A-Za-z0-9_-]+$" (default "" (get $header "kid")))) }}{{ fail "sealed header requires ES256 and a safe guest-local signing-key identifier" }}{{ end }}
      {{- if or (ne (get $payload "type") "vault") (ne (get $payload "version") "0.1.0") (ne (get $payload "provider") "kbs") (ne (get $payload "name") (printf "kbs:///%s" $key.kbs.resourcePath)) }}{{ fail "sealed vault metadata must identify the configured single KBS resource" }}{{ end }}
    {{- end }}
    {{- if $key.insecureSecret.name }}{{ fail "insecure source conflicts with sealed mode" }}{{ end }}
  {{- else if eq $key.mode "insecureSecret" }}
    {{- if not $key.insecureSecret.name }}{{ fail "insecureSecret.name is required" }}{{ end }}
    {{- if or $external $envelope }}{{ fail "sealed source conflicts with insecure mode" }}{{ end }}
  {{- else }}
    {{- if or $external $envelope $key.insecureSecret.name }}{{ fail "curl mode cannot use another source" }}{{ end }}
  {{- end }}
{{- end }}
{{- end -}}

{{- define "sample.decodeSegment" -}}
{{- $encoded := replace "_" "/" (replace "-" "+" .) -}}
{{- $padding := mod (sub 4 (mod (len $encoded) 4)) 4 | int -}}
{{- printf "%s%s" $encoded (repeat $padding "=") | b64dec -}}
{{- end -}}

{{- define "sample.memoryBytes" -}}
{{- if not (regexMatch "^[0-9]+([.][0-9]+)?(Ki|Mi|Gi|Ti|K|M|G|T)?$" .) }}{{ fail "memory must be a supported positive byte/SI quantity" }}{{ end -}}
{{- $number := regexFind "^[0-9]+([.][0-9]+)?" . -}}
{{- $suffix := trimPrefix $number . -}}
{{- $units := dict "" 1.0 "Ki" 1024.0 "Mi" 1048576.0 "Gi" 1073741824.0 "Ti" 1099511627776.0 "K" 1000.0 "M" 1000000.0 "G" 1000000000.0 "T" 1000000000000.0 -}}
{{- mulf (float64 $number) (float64 (get $units $suffix)) -}}
{{- end -}}

{{- define "sample.cpuMilli" -}}
{{- if not (regexMatch "^[0-9]+([.][0-9]+)?m?$" .) }}{{ fail "CPU must be a supported core/millicore quantity" }}{{ end -}}
{{- if hasSuffix "m" . }}{{ trimSuffix "m" . | float64 }}{{ else }}{{ mulf (float64 .) 1000.0 }}{{ end -}}
{{- end -}}

{{- define "sample.nfsSource" -}}
{{- if contains ":" .Values.nfs.server -}}
{{- printf "[%s]:%s" .Values.nfs.server .Values.nfs.exportPath -}}
{{- else -}}
{{- printf "%s:%s" .Values.nfs.server .Values.nfs.exportPath -}}
{{- end -}}
{{- end -}}
