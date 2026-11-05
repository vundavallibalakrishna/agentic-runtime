cd /Users/balakrishnavundavalli/working/talentfino/cura/agentic_runtime
export AR_CERT_LLM_API_KEY="$(cat .secrets/deepinfra_api_key)"
AR_MG_PORT=18101 nohup uv run ar-model-gateway > /tmp/grc-logs/gateway.log 2>&1 &
AR_PORT=18131 AR_TEMPORAL_ADDRESS=127.0.0.1:1 AR_MODEL_GATEWAY_URL=http://127.0.0.1:18101 AR_PUBLIC_URL=http://127.0.0.1:18132 AR_WEB_HOST_PORT=18132 nohup uv run ar-api > /tmp/grc-logs/api.log 2>&1 &
cd apps/web && API_PROXY_URL=http://127.0.0.1:18131 AR_NEXT_DIST=.next-fresh nohup pnpm exec next start --port 18132 > /tmp/grc-logs/web.log 2>&1 &
