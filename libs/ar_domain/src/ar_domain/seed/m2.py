"""Dev catalogue for models and the assistant. Spec: docs/09-plan/M02-first-chat.md.

Idempotent. Platform rows use ``tenant_id`` NULL. The assistant is published v1.
"""

from typing import TYPE_CHECKING

from sqlalchemy import select

from ar_common.host_ports import fake_llm_base_url
from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.agents.logic import assistant_definition, definition_hash
from ar_domain.agents.tables import Agent, AgentVersion
from ar_domain.agents.templates import builder_definition, helpdesk_definition
from ar_domain.identity.seed import ensure_everyone_team
from ar_domain.models.tables import Model, ModelAlias, ModelProvider

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


async def apply(session: AsyncSession, tenant_id: uuid.UUID, admin_id: uuid.UUID) -> None:
    """Insert fake-llm, standard aliases, team ``everyone`` and ``assistant``."""
    provider = await session.scalar(
        select(ModelProvider).where(
            ModelProvider.tenant_id.is_(None), ModelProvider.name == "fake-llm"
        )
    )
    if provider is None:
        provider = ModelProvider(
            id=new_id(),
            tenant_id=None,
            name="fake-llm",
            kind="fake",
            base_url=fake_llm_base_url(),
        )
        session.add(provider)
        await session.flush()
    chat = await _model(session, provider.id, "fake-chat", "chat")
    embed = await _model(session, provider.id, "fake-embed", "embedding")
    rerank = await _model(session, provider.id, "fake-rerank", "rerank")
    await _alias(session, "reasoning", "chat", chat.id)
    await _alias(session, "fast", "chat", chat.id)
    await _alias(session, "vision", "chat", chat.id)
    await _alias(session, "embed", "embedding", embed.id)
    await _alias(session, "rerank", "rerank", rerank.id)
    await ensure_everyone_team(session, tenant_id, admin_id)
    await _published(
        session,
        tenant_id,
        admin_id,
        slug="assistant",
        name="Assistant",
        description="Default assistant",
        definition=assistant_definition(),
    )
    await _published(
        session,
        tenant_id,
        admin_id,
        slug="helpdesk",
        name="Helpdesk",
        description="Answers common requests.",
        definition=helpdesk_definition(),
    )
    await _published(
        session,
        tenant_id,
        admin_id,
        slug="builder",
        name="Builder",
        description="Drafts an agent from a sentence. It does not publish.",
        definition=builder_definition(),
    )


async def _published(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    admin_id: uuid.UUID,
    *,
    slug: str,
    name: str,
    description: str,
    definition: dict[str, object],
) -> None:
    agent = await session.scalar(
        select(Agent).where(Agent.tenant_id == tenant_id, Agent.slug == slug)
    )
    if agent is not None:
        return
    agent_id = new_id()
    version_id = new_id()
    now = utcnow()
    session.add(
        Agent(
            id=agent_id,
            tenant_id=tenant_id,
            slug=slug,
            name=name,
            description=description,
            owner_user_id=admin_id,
            visibility="tenant",
            status="published",
            risk_tier="low",
        )
    )
    await session.flush()
    session.add(
        AgentVersion(
            id=version_id,
            tenant_id=tenant_id,
            agent_id=agent_id,
            version=1,
            state="published",
            definition=definition,
            definition_hash=definition_hash(definition),
            change_note="seed",
            created_by=admin_id,
            published_at=now,
            published_by=admin_id,
        )
    )
    await session.flush()
    stored = await session.get(Agent, agent_id)
    if stored is not None:
        stored.published_version_id = version_id


async def _model(session: AsyncSession, provider_id: uuid.UUID, name: str, kind: str) -> Model:
    row = await session.scalar(select(Model).where(Model.tenant_id.is_(None), Model.name == name))
    if row is None:
        row = Model(
            id=new_id(),
            tenant_id=None,
            provider_id=provider_id,
            name=name,
            upstream_model=name,
            kind=kind,
            capabilities=["streaming"],
        )
        session.add(row)
        await session.flush()
    return row


async def _alias(session: AsyncSession, alias: str, kind: str, model_id: uuid.UUID) -> None:
    row = await session.scalar(
        select(ModelAlias).where(ModelAlias.tenant_id.is_(None), ModelAlias.alias == alias)
    )
    if row is None:
        session.add(
            ModelAlias(
                id=new_id(),
                tenant_id=None,
                alias=alias,
                kind=kind,
                primary_model_id=model_id,
                default_params={"temperature": 0.2},
            )
        )
