# System context and containers

Product: **Agentic Runtime**, a web platform where companies define agents (persona, instructions, model, tools, knowledge, memory, policies, routines, skills, channels, sandboxes) and their people chat with them. Agents plan, call tools, run code, browse, create files, remember, delegate to subagents and run unattended routines, all on the company's infrastructure and models. Names of deployables are canonical in [service-decomposition.md](service-decomposition.md).

## 1. System context

```mermaid
flowchart TB
  EU[End user<br/>browser, Slack, Teams, email]
  BU[Agent builder / tool owner]
  AD[Tenant admin / approver / auditor]
  PA[Platform operator<br/>SaaS or install owner]
  DEV[Developer systems<br/>REST API, SDKs, webhooks]
  subgraph AR[Agentic Runtime]
    P[Web app + API + workers + gateways]
  end
  IDP[Company IdP<br/>OIDC / SAML / SCIM]
  LLM[Company model servers<br/>vLLM, TEI, OpenAI-compatible]
  TOOLS[Company tools<br/>MCP servers, internal APIs, databases]
  SRC[Knowledge sources<br/>SharePoint, Confluence, Drive, S3, web]
  CH[Slack / Teams / mail servers]
  SIEM[SIEM / monitoring]
  EU --> P
  BU --> P
  AD --> P
  PA --> P
  DEV --> P
  P --> IDP
  P --> LLM
  P --> TOOLS
  P --> SRC
  P <--> CH
  P --> SIEM
```

Trust boundaries: (1) internet/corporate network → ingress (TLS, WAF optional); (2) platform services ↔ data stores (mTLS optional, NetworkPolicies); (3) platform → sandboxes (untrusted code; egress via proxy only); (4) platform → tool servers and model servers (credentials minted per call); (5) tenant ↔ tenant (RLS, payload filters, namespaces). Threats per boundary: [threat-model](../06-security/threat-model.md).

## 2. Containers

```mermaid
flowchart LR
  subgraph edge[Ingress]
    ING[Envoy Gateway<br/>TLS, routing]
  end
  subgraph app[Platform deployables]
    WEB[web<br/>Next.js]
    API[api<br/>FastAPI BFF + REST + SSE]
    RT[runtime-worker<br/>AgentRunWorkflow]
    SYS[system-worker<br/>routines, outbox, retention, evals]
    ING2[ingest-worker<br/>knowledge + file processing]
    MG[model-gateway]
    MCPG[mcp-gateway<br/>tool choke point + built-ins]
    SBM[sandbox-manager]
    CHN[channels<br/>Slack, Teams, email]
    SQL[mcp-sql]
    OAPI[mcp-openapi]
    OPA[opa]
  end
  subgraph data[Stateful services]
    PG[(Postgres 18 + pgvector)]
    VK[(Valkey)]
    TMP[(Temporal)]
    QD[(Qdrant, optional)]
    S3[(S3 store)]
    KC[Keycloak]
    BAO[OpenBao / Vault]
  end
  subgraph sbx[Sandbox namespace]
    SA[sandbox pods<br/>sandbox-agent]
    SQ[Squid egress proxy]
  end
  ING --> WEB & API & CHN
  WEB --> API
  API --> PG & VK & TMP & S3 & KC & BAO & MG & MCPG & SBM & OPA
  RT --> PG & VK & TMP & MG & MCPG & OPA
  SYS --> PG & VK & TMP & S3 & MG & SBM & CHN
  ING2 --> PG & TMP & S3 & MG
  ING2 -.->|optional adapter| QD
  MCPG --> PG & VK & OPA & S3 & SBM & SA & SQL & OAPI & CHN
  MCPG -.->|optional adapter| QD
  SBM --> PG & S3 & SA
  SA --> SQ
  CHN --> API & VK
  MG --> LLMs[(model servers)]
  MCPG --> EXT[(remote MCP servers)]
  SQL --> DBS[(company databases)]
  OAPI --> APIS[(internal APIs)]
```

Observability sidecars are omitted: every deployable exports OTLP to the OpenTelemetry Collector ([spec 18](../03-specs/18-observability-eval.md)).

## 3. Key properties

| Property | How |
|---|---|
| Durability | Every run is a Temporal workflow; activities idempotent ([ADR-0003](adr/ADR-0003-temporal-durable-runs.md)). |
| Single enforcement point for tools | `mcp-gateway` ([ADR-0006](adr/ADR-0006-mcp-tool-protocol.md)). |
| Tenant isolation | RLS (including knowledge vectors in `chunk_embeddings`) + mandatory tenant filters in every `RetrievalStore` query + per-tenant object prefixes + sandbox network isolation ([tenancy-isolation](tenancy-isolation.md)). |
| Company-hosted models | `model-gateway` only calls registered providers; no internet egress from the model namespace. |
| Two deployment modes | Same images; `AR_DEPLOYMENT_MODE` ([deployment-modes](../00-overview/deployment-modes.md)). |

Request-level sequences: [request-flows.md](request-flows.md).
