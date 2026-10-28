"""The GRC pack stays installed in the repo and off in the default workspace."""

from ar_pack_grc.install import _dev_install, grc_pack_enabled


def test_pack_is_parked_unless_the_flag_is_on(monkeypatch) -> None:
    monkeypatch.delenv("AR_GRC_PACK_ENABLED", raising=False)
    assert grc_pack_enabled() is False
    monkeypatch.setenv("AR_GRC_PACK_ENABLED", "true")
    assert grc_pack_enabled() is True
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setenv("AR_ENV", "dev")
    assert _dev_install() is True
    monkeypatch.setenv("AR_GRC_PACK_ENABLED", "false")
    assert _dev_install() is False
