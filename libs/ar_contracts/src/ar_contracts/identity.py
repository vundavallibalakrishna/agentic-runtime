"""Identity documents stored as JSON. Spec: docs/03-specs/02-identity-tenancy.md §3.2."""

from datetime import datetime
from typing import Literal

from pydantic import Field

from ar_contracts.api_model import ApiModel


class _Model(ApiModel):
    """Identity document. Keys on the wire are camelCase."""


class AttributeMappings(_Model):
    department: str | None = None
    location: str | None = None


class OidcIdpConfig(_Model):
    kind: Literal["oidc"] = "oidc"
    issuer: str
    client_id: str
    scopes: list[str] = Field(default_factory=lambda: ["openid", "email", "profile"])
    groups_claim: str | None = "groups"
    attribute_mappings: AttributeMappings = Field(default_factory=AttributeMappings)


class SamlIdpConfig(_Model):
    kind: Literal["saml"] = "saml"
    metadata_url: str | None = None
    metadata_xml: str | None = None
    entity_id: str
    name_id_format: str = "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress"
    attribute_mappings: AttributeMappings = Field(default_factory=AttributeMappings)


IdpConfig = OidcIdpConfig | SamlIdpConfig


class Me(ApiModel):
    """Authenticated caller. Role and permission values stay catalogue tokens."""

    id: str
    email: str | None = None
    display_name: str | None = None
    created_at: datetime | None = None
    roles: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    teams: list[dict[str, object]] = Field(default_factory=list)
    groups: list[dict[str, object]] = Field(default_factory=list)
    settings: dict[str, object] = Field(default_factory=dict)
