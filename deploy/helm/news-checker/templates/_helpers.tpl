{{- define "news-checker.fullname" -}}
{{ .Release.Name }}-news-checker
{{- end -}}

{{- define "news-checker.labels" -}}
app.kubernetes.io/name: news-checker
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}
