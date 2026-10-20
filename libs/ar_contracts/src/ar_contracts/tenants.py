"""Tenant and plan documents. Spec: docs/03-specs/02-identity-tenancy.md §3.1 and §3.10."""

from typing import Literal

from pydantic import Field

from ar_contracts.json_api import ApiModel


class _Model(ApiModel):
    """Tenant document. Keys on the wire are camelCase."""


class RetentionSettings(_Model):
    conversations_days: int = 365
    run_events_days: int = 90
    files_days: int = 365
    audit_years: int = 7
    memory_inactive_days: int = 730
    deleted_conversation_days: int = 30


class FeatureFlags(_Model):
    custom_rego: bool = False
    teams_channel: bool = True
    email_channel: bool = True
    widget: bool = False
    web_fetch: bool = False
    guardrails: bool = False
    injection_classifier: bool = True
    pii_redaction: bool = True
    tenant_model_providers: bool = False


class ChatSettings(_Model):
    allow_sharing: bool = True


class LimitSettings(_Model):
    max_active_runs_per_user: int = 5


class BrandingSettings(_Model):
    product_name: str = ""
    logo_file_id: str | None = None
    primary_color: str = ""


class MemorySettings(_Model):
    enabled: bool = True
    extraction: bool = True


class ApprovalSettings(_Model):
    default_ttl_s: int = 86400


class SecuritySettings(_Model):
    require_step_up_for_w3: bool = True
    allow_self_review: bool = False
    allowed_upload_mime_types: list[str] = Field(
        default_factory=lambda: [
            "text/plain",
            "text/markdown",
            "text/csv",
            "application/pdf",
            "application/json",
            "image/png",
            "image/jpeg",
        ]
    )
    max_upload_mb: int = 100


class SiemSettings(_Model):
    enabled: bool = False
    webhook_id: str | None = None


class AuditSettings(_Model):
    siem: SiemSettings = Field(default_factory=SiemSettings)


class ObservabilitySettings(_Model):
    capture_content: bool = False


class GrievanceContact(_Model):
    name: str = ""
    email: str = ""


class PrivacySettings(_Model):
    notice_text_md: str = ""
    notice_version: str = "0"
    grievance_contact: GrievanceContact = Field(default_factory=GrievanceContact)


class TenantSettings(_Model):
    default_timezone: str = "Asia/Kolkata"
    default_locale: str = "en-IN"
    retention: RetentionSettings = Field(default_factory=RetentionSettings)
    egress_allowlist: list[str] = Field(default_factory=list)
    features: FeatureFlags = Field(default_factory=FeatureFlags)
    chat: ChatSettings = Field(default_factory=ChatSettings)
    limits: LimitSettings = Field(default_factory=LimitSettings)
    branding: BrandingSettings = Field(default_factory=BrandingSettings)
    memory: MemorySettings = Field(default_factory=MemorySettings)
    approvals: ApprovalSettings = Field(default_factory=ApprovalSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    audit: AuditSettings = Field(default_factory=AuditSettings)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)
    privacy: PrivacySettings = Field(default_factory=PrivacySettings)


class MaxRetention(_Model):
    conversations_days: int = 3650
    audit_years: int = 7


class PlanFeatures(_Model):
    custom_rego: bool = False
    widget: bool = False
    teams_channel: bool = True
    email_channel: bool = True
    web_fetch: bool = False
    guardrails: bool = False
    tenant_model_providers: bool = False


class PlanLimits(_Model):
    max_users: int | None = None
    max_agents: int = 200
    max_tool_servers: int | None = None
    max_collections: int | None = None
    max_knowledge_documents: int = 100_000
    max_knowledge_bytes: int = 50 * 1024 * 1024 * 1024
    max_storage_gb: int | None = None
    max_routines: int = 500
    max_concurrent_runs: int = 100
    max_concurrent_sandboxes: int = 50
    max_sandbox_cpu_millis: int = 8000
    max_sandbox_memory_mb: int = 16384
    monthly_cost_micros: int | None = None
    api_rpm: int = 6000
    unit_prices: dict[str, int] = Field(default_factory=dict)
    max_retention: MaxRetention = Field(default_factory=MaxRetention)
    features: PlanFeatures = Field(default_factory=PlanFeatures)


class NotificationPrefs(_Model):
    email: bool = True
    slack: bool = False
    teams: bool = False


class UserSettings(_Model):
    locale: str = "en-IN"
    timezone: str = "Asia/Kolkata"
    memory_enabled: bool = True
    notifications: NotificationPrefs = Field(default_factory=NotificationPrefs)
    theme: Literal["system", "light", "dark"] = "system"
