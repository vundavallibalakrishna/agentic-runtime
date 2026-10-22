"""Declarative definitions. Spec: docs/05-contracts/definition-schema.md."""

from typing import Annotated, Literal

from pydantic import ConfigDict, Field, JsonValue

from ar_contracts.api_model import ApiModel
from ar_contracts.budget import RunBudget

_SLUG = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"


class _Model(ApiModel):
    model_config = ConfigDict(frozen=True)


class Metadata(_Model):
    slug: str | None = Field(default=None, pattern=_SLUG)
    name: str | None = None
    description: str | None = None
    visibility: Literal["private", "team", "tenant"] | None = None
    owner_team: str | None = None
    risk_tier: Literal["low", "medium", "high"] | None = None
    alias: str | None = None


class Persona(_Model):
    display_name: str = Field(min_length=1, max_length=80)
    greeting: str = Field(default="", max_length=500)
    avatar_file: str | None = None


class ModelParams(_Model):
    temperature: float = Field(default=0.2, ge=0, le=2)
    top_p: float = Field(default=1, ge=0, le=1)
    max_output_tokens: int = Field(default=4096, ge=1)
    reasoning_effort: Literal["low", "medium", "high"] | None = None


class ModelSpec(_Model):
    alias: str
    fast_alias: str = "fast"
    vision_alias: str | None = None
    params: ModelParams = ModelParams()
    degrade_to_fast: bool = True


class ToolOverride(_Model):
    require_approval: Literal["always", "policy"] | None = None
    pinned: bool = False


class ToolBinding(_Model):
    server: str
    version: str = "*"
    include: list[str] = Field(default_factory=lambda: ["*"])
    overrides: dict[str, ToolOverride] = Field(default_factory=dict)


class ToolSearch(_Model):
    mode: Literal["auto", "on", "off"] = "auto"
    top_k: int = Field(default=12, ge=4, le=32)


class KnowledgeSpec(_Model):
    collections: list[str] = Field(default_factory=list, max_length=20)
    auto_retrieve: bool = False
    top_k: int = Field(default=8, ge=1)
    min_score: float = Field(default=0.3, ge=0, le=1)


def _default_read_scopes() -> list[Literal["user", "agent", "team", "agent_user"]]:
    return ["user", "agent"]


class MemorySpec(_Model):
    enabled: bool = True
    read_scopes: list[Literal["user", "agent", "team", "agent_user"]] = Field(
        default_factory=_default_read_scopes
    )
    user_writes: Literal["auto", "explicit_only", "off"] = "auto"
    agent_writes: Literal["review", "off"] = "review"
    recall_top_k: int = Field(default=8, ge=1)


class SubagentSpec(_Model):
    allowed: list[str] = Field(default_factory=list)
    allow_self_clone: bool = False
    max_depth: int = Field(default=1, ge=1, le=3)
    max_parallel: int = Field(default=3, ge=1)


class SandboxSpec(_Model):
    enabled: bool = False
    template: str = "default"
    scope: Literal["conversation", "agent_user", "agent"] = "conversation"
    extra_egress_allowlist: list[str] = Field(default_factory=list)


class ContextSpec(_Model):
    compaction_threshold: float = Field(default=0.7, ge=0.4, le=0.9)
    tool_result_max_tokens: int = Field(default=4000, ge=1)
    history_max_messages: int = Field(default=40, ge=1)


class OutputSpec(_Model):
    citations: Literal["required", "preferred", "off"] = "preferred"
    show_reasoning: bool = False
    grounding: Literal["off", "preferred", "strict"] = "off"


class AssuranceSpec(_Model):
    record_mode: Literal["off", "on"] = "off"


class SafetySpec(_Model):
    pii_masking: bool = False
    injection_classifier: bool = True


class ChannelFlags(_Model):
    web: bool = True
    slack: bool = False
    teams: bool = False
    email: bool = False
    api: bool = True
    widget: bool = False


class AgentDefinition(_Model):
    """Versioned body stored in ``agent_versions.definition``."""

    persona: Persona
    instructions: str = Field(min_length=1, max_length=32_000)
    starter_prompts: list[str] = Field(default_factory=list, max_length=6)
    model: ModelSpec
    tools: list[ToolBinding] = Field(default_factory=list)
    tool_search: ToolSearch = ToolSearch()
    knowledge: KnowledgeSpec = KnowledgeSpec()
    skills: list[str] = Field(default_factory=list, max_length=50)
    memory: MemorySpec = MemorySpec()
    subagents: SubagentSpec = SubagentSpec()
    sandbox: SandboxSpec = SandboxSpec()
    budget: RunBudget
    context: ContextSpec = ContextSpec()
    output: OutputSpec = OutputSpec()
    assurance: AssuranceSpec = AssuranceSpec()
    safety: SafetySpec = SafetySpec()
    channels: ChannelFlags = ChannelFlags()


class ToolAuth(_Model):
    mode: Literal["none", "static_secret", "user_oauth", "token_exchange", "internal_jwt"] = "none"
    credential_provider: str | None = None
    secret: str | None = None


class ToolGovernance(_Model):
    risk_class: Literal["R0", "W1", "W2", "W3"] | None = None
    data_classification: str | None = None
    timeout_s: int | None = None
    rate_limit_per_minute: int | None = None


class RemoteMcp(_Model):
    url: str
    headers: dict[str, str] = Field(default_factory=dict)


class OpenApiSpec(_Model):
    spec_file: str
    base_url: str
    operations: list[str] = Field(default_factory=list)


class SqlSpec(_Model):
    data_connection: str


class ToolServerDefinition(_Model):
    kind: Literal["remote_mcp", "openapi", "sql"]
    version: str
    description: str = ""
    remote_mcp: RemoteMcp | None = None
    openapi: OpenApiSpec | None = None
    sql: SqlSpec | None = None
    auth: ToolAuth = ToolAuth()
    tools: dict[str, ToolGovernance] = Field(default_factory=dict)
    allowed_tools: list[str] = Field(default_factory=lambda: ["*"])


class DataConnectionDefinition(_Model):
    engine: Literal["postgres"] = "postgres"
    dsn_secret: str
    identity_mode: Literal["service", "per_user_mapped", "passthrough"] = "service"
    allowlist_schemas: list[str] = Field(default_factory=list)
    allowlist_tables: list[str] = Field(default_factory=list)
    columns_deny: list[str] = Field(default_factory=list)
    row_limit: int = Field(default=1000, ge=1)
    statement_timeout_s: int = Field(default=30, ge=1)
    classification: str = "internal"
    schema_notes: str = ""


class KnowledgeSource(_Model):
    name: str
    kind: Literal[
        "upload",
        "web",
        "s3",
        "sharepoint",
        "confluence",
        "google_drive",
        "database",
        "mcp_resource",
    ]
    secret: str | None = None
    sync_schedule: str | None = None
    acl_sync_schedule: str | None = None
    config: dict[str, str] = Field(default_factory=dict)


class KnowledgeCollectionDefinition(_Model):
    description: str = ""
    visibility: Literal["private", "team", "tenant"] = "tenant"
    acl_mode: Literal["source", "collection"] = "source"
    sensitivity: Literal["normal", "high"] = "normal"
    classification: str = "internal"
    embedding_alias: str = "embed"
    text_search_config: Literal["simple", "english"] = "simple"
    chunk_target_tokens: int = Field(default=512, ge=64)
    chunk_overlap_pct: int = Field(default=12, ge=0, le=50)
    contextual: bool = False
    sources: list[KnowledgeSource] = Field(default_factory=list)


class RoutineTrigger(_Model):
    type: Literal[
        "schedule", "webhook", "channel_event", "email", "file_arrival", "db_change", "manual"
    ]
    cron: str | None = None
    timezone: str | None = None
    jitter_s: int = Field(default=0, ge=0, le=3600)
    catchup_window_s: int = Field(default=0, ge=0, le=86400)
    config: dict[str, str] = Field(default_factory=dict)


class DeliveryTarget(_Model):
    type: Literal["conversation", "slack", "teams", "email", "webhook", "file"]
    integration: str | None = None
    channel: str | None = None
    pre_approved: bool = False
    config: dict[str, str] = Field(default_factory=dict)


class RoutineDefinition(_Model):
    description: str = ""
    agent: str
    agent_version: str | None = None
    run_as: Literal["owner", "service_account"] = "owner"
    service_account: str | None = None
    instructions: str
    trigger: RoutineTrigger
    event_filter: str | None = None
    delivery: list[DeliveryTarget] = Field(default_factory=list)
    budget: RunBudget
    max_runs_per_day: int = Field(default=4, ge=1)
    concurrency_policy: Literal["skip", "buffer_one", "allow"] = "skip"


class PolicyMatch(_Model):
    tools: list[str] = Field(default_factory=list)
    risk_classes: list[str] = Field(default_factory=list)
    agents: list[str] = Field(default_factory=list)
    triggers: list[str] = Field(default_factory=list)
    channels: list[str] = Field(default_factory=list)
    user_groups: list[str] = Field(default_factory=list)


class PolicyRule(_Model):
    id: str
    effect: Literal["allow", "deny", "require_approval"]
    match: PolicyMatch = PolicyMatch()
    message: str = ""


class PolicyDefinition(_Model):
    description: str = ""
    status: Literal["active", "disabled"] = "active"
    priority: int = 100
    rules: list[PolicyRule] = Field(default_factory=list)


class SkillAsset(_Model):
    path: str
    file: str


class SkillDefinition(_Model):
    description: str
    visibility: Literal["private", "team", "tenant"] = "tenant"
    required_tools: list[str] = Field(default_factory=list)
    instructions_md: str
    assets: list[SkillAsset] = Field(default_factory=list)


class ModelAliasDefinition(_Model):
    kind: Literal["chat", "embed", "rerank"]
    primary_model: str
    fallback_models: list[str] = Field(default_factory=list)


class SandboxTemplateDefinition(_Model):
    image_ref: str
    runtime_class: Literal["gvisor", "kata"] = "gvisor"
    cpu_millis: int = Field(ge=1)
    memory_mb: int = Field(ge=1)
    disk_gb: int = Field(ge=1)
    allow_browser: bool = False
    egress_allowlist: list[str] = Field(default_factory=list)
    max_classification: str = "internal"
    idle_suspend_s: int = Field(default=900, ge=1)
    max_lifetime_s: int = Field(default=86400, ge=1)
    exec_timeout_s: int = Field(default=300, ge=1)
    retention_days: int = Field(default=7, ge=1)


class ChannelIntegrationDefinition(_Model):
    kind: Literal["slack", "teams", "email", "widget"]
    secret: str
    default_agent: str
    config: dict[str, str] = Field(default_factory=dict)


class AgentResource(_Model):
    kind: Literal["Agent"]
    metadata: Metadata
    spec: AgentDefinition


class ToolServerResource(_Model):
    kind: Literal["ToolServer"]
    metadata: Metadata
    spec: ToolServerDefinition


class DataConnectionResource(_Model):
    kind: Literal["DataConnection"]
    metadata: Metadata
    spec: DataConnectionDefinition


class KnowledgeCollectionResource(_Model):
    kind: Literal["KnowledgeCollection"]
    metadata: Metadata
    spec: KnowledgeCollectionDefinition


class RoutineResource(_Model):
    kind: Literal["Routine"]
    metadata: Metadata
    spec: RoutineDefinition


class PolicyResource(_Model):
    kind: Literal["Policy"]
    metadata: Metadata
    spec: PolicyDefinition


class SkillResource(_Model):
    kind: Literal["Skill"]
    metadata: Metadata
    spec: SkillDefinition


class ModelAliasResource(_Model):
    kind: Literal["ModelAlias"]
    metadata: Metadata
    spec: ModelAliasDefinition


class SandboxTemplateResource(_Model):
    kind: Literal["SandboxTemplate"]
    metadata: Metadata
    spec: SandboxTemplateDefinition


class ChannelIntegrationResource(_Model):
    kind: Literal["ChannelIntegration"]
    metadata: Metadata
    spec: ChannelIntegrationDefinition


class PackMetadata(_Model):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,40}$")
    version: str
    name: str
    min_platform: str = "1.0.0"


class PackExtension(_Model):
    """Optional pack code. Present only when the manifest is not declarative."""

    schema_name: str = Field(alias="schema", default="")
    alembic: str = ""
    api_mount: str = ""
    web_slot: str = ""
    config_schema: dict[str, JsonValue] = Field(default_factory=dict)
    ui: dict[str, JsonValue] = Field(default_factory=dict)
    permissions: list[str] = Field(default_factory=list)
    audit_actions: list[str] = Field(default_factory=list)
    mcp_server: str = ""


class ContentPackSpec(_Model):
    resources: list[dict[str, JsonValue]] = Field(default_factory=list)
    extension: PackExtension | None = None


class ContentPack(_Model):
    """Signed manifest. ``spec.resources`` uses the same documents as a bundle."""

    api_version: Literal["agentic-runtime.dev/v1"] = Field(alias="apiVersion")
    kind: Literal["ContentPack"]
    metadata: PackMetadata
    spec: ContentPackSpec = ContentPackSpec()


DefinitionResource = Annotated[
    AgentResource
    | ToolServerResource
    | DataConnectionResource
    | KnowledgeCollectionResource
    | RoutineResource
    | PolicyResource
    | SkillResource
    | ModelAliasResource
    | SandboxTemplateResource
    | ChannelIntegrationResource,
    Field(discriminator="kind"),
]


class Bundle(_Model):
    api_version: Literal["agentic-runtime.dev/v1"] = Field(alias="apiVersion")
    kind: Literal["Bundle"]
    metadata: Metadata
    resources: list[DefinitionResource]


SCHEMA_MODELS: dict[str, type[ApiModel]] = {
    "Agent": AgentDefinition,
    "ToolServer": ToolServerDefinition,
    "DataConnection": DataConnectionDefinition,
    "KnowledgeCollection": KnowledgeCollectionDefinition,
    "Routine": RoutineDefinition,
    "Policy": PolicyDefinition,
    "Skill": SkillDefinition,
    "ModelAlias": ModelAliasDefinition,
    "SandboxTemplate": SandboxTemplateDefinition,
    "ChannelIntegration": ChannelIntegrationDefinition,
    "Bundle": Bundle,
    "ContentPack": ContentPack,
}
