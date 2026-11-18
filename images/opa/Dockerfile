# OPA cannot compute the install HMAC. The forwarder beside it signs each
# bundle fetch. The binary is the upstream static build.
FROM openpolicyagent/opa:1.21.3-static AS opa
FROM python:3.12-slim
COPY --from=opa /opa /usr/local/bin/opa
COPY deploy/compose/opa/forward.py /usr/local/bin/ar-opa-forward.py
EXPOSE 8181
ENTRYPOINT ["python", "/usr/local/bin/ar-opa-forward.py"]
