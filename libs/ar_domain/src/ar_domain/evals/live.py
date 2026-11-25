"""Live model switch. A key on its own does not call the provider."""

from __future__ import annotations

import os
import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

    from ar_domain.chat.service import ChatService

LIVE_FLAG = "AR_EVAL_GYM_LIVE"
LIVE_KEY = "AR_CERT_LLM_API_KEY"
LIVE_URL = "AR_CERT_LLM_BASE_URL"
LIVE_MODEL = "AR_CERT_LLM_MODEL"


class LiveConfigError(RuntimeError):
    """The live switch is on and the key, the address or the model name is missing."""


def live_requested(environ: Mapping[str, str] | None = None) -> bool:
    """True only when the operator set the live flag. A key alone stays offline."""
    env = os.environ if environ is None else environ
    return env.get(LIVE_FLAG, "").strip() == "1"


def cert_key(environ: Mapping[str, str] | None = None) -> str:
    """Return the cert key. Callers must not log or persist it."""
    env = os.environ if environ is None else environ
    return env.get(LIVE_KEY, "").strip()


def install_live(
    store: ChatService,
    tenant_id: uuid.UUID,
    *,
    key: str,
    base_url: str,
    model: str,
) -> None:
    """Point the tenant reasoning alias at an OpenAI-compatible chat endpoint.

    The endpoint and the model are the caller's: nothing here names a vendor.
    """
    if not key:
        raise LiveConfigError(f"{LIVE_FLAG}=1 requires {LIVE_KEY}")
    if not base_url.strip() or not model.strip():
        raise LiveConfigError(f"set {LIVE_URL} and {LIVE_MODEL}: the endpoint and the model")
    provider_id = uuid.uuid4()
    model_id = uuid.uuid4()
    alias_id = uuid.uuid4()
    store.providers[provider_id] = {
        "id": provider_id,
        "tenant_id": tenant_id,
        "kind": "openai",
        "name": "Gym live",
        "base_url": base_url.rstrip("/"),
        "api_key": key,
        "timeout_s": 120,
        "status": "active",
    }
    store.models[model_id] = {
        "id": model_id,
        "tenant_id": tenant_id,
        "provider_id": provider_id,
        "upstream_model": model,
        "name": model,
    }
    store.aliases[alias_id] = {
        "id": alias_id,
        "tenant_id": tenant_id,
        "alias": "reasoning",
        "status": "active",
        "primary_model_id": model_id,
    }


def live_settings(environ: Mapping[str, str] | None = None) -> tuple[str, str, str]:
    """Key, base URL and model name. Raises when any of the three is not set."""
    env = os.environ if environ is None else environ
    key = cert_key(env)
    if not key:
        raise LiveConfigError(f"{LIVE_FLAG}=1 requires {LIVE_KEY}")
    url = env.get(LIVE_URL, "").strip()
    model = env.get(LIVE_MODEL, "").strip()
    if not url or not model:
        raise LiveConfigError(
            f"set {LIVE_URL} and {LIVE_MODEL}: the address of an OpenAI-compatible endpoint "
            "and the name of the model to ask"
        )
    return key, url, model
