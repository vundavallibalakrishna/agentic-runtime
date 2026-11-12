"""Production-cert defect 7: a by-hand staging seed is not blocked by the writer guard.

In staging the read-model guard refuses the in-memory `ChatService` unless the caller is
the declared bootstrap writer (`AR_BOOTSTRAP_WRITER=1`, which only the Helm job set). The
bootstrap is that writer, so `provision_defaults` now declares itself and a by-hand seed
gets past the guard. Proof: unit (no database needed).
"""

import asyncio
import os

import pytest

import ar_domain.readmodel.boot as boot
from ar_domain.bootstrap import provision_defaults
from ar_domain.chat.service import ChatService
from ar_domain.readmodel.boot import MemoryStoreRefusedError


def test_provision_defaults_declares_the_bootstrap_writer_in_staging(monkeypatch) -> None:
    # Make the process look like staging and start without the flag.
    monkeypatch.setattr(boot, "uses_shared_process_state", lambda _env: True)
    monkeypatch.delenv("AR_BOOTSTRAP_WRITER", raising=False)

    # The guard is active: a bare ChatService is refused in staging.
    with pytest.raises(MemoryStoreRefusedError):
        ChatService(fake_models_allowed=False)

    # bind_store is where the database would be reached; return None so the call fails
    # *after* the guard, proving provision_defaults got past it.
    async def _no_database(*_args, **_kwargs):
        return None

    monkeypatch.setattr("ar_domain.durable.bind.bind_store", _no_database)
    with pytest.raises(SystemExit, match="database stopped answering"):
        asyncio.run(provision_defaults("acme", "ada@acme.example"))

    # The declaration is scoped: it is removed again afterwards.
    assert "AR_BOOTSTRAP_WRITER" not in os.environ


def test_provision_defaults_restores_a_prior_writer_value(monkeypatch) -> None:
    monkeypatch.setattr(boot, "uses_shared_process_state", lambda _env: True)
    monkeypatch.setenv("AR_BOOTSTRAP_WRITER", "keep-me")

    async def _no_database(*_args, **_kwargs):
        return None

    monkeypatch.setattr("ar_domain.durable.bind.bind_store", _no_database)
    with pytest.raises(SystemExit):
        asyncio.run(provision_defaults("acme", "ada@acme.example"))

    assert os.environ["AR_BOOTSTRAP_WRITER"] == "keep-me"
