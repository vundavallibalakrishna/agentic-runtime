"""The fresh-clone port holder keeps its listening sockets alive."""

import gc
import importlib.util
import socket
from pathlib import Path

import pytest

from ar_common.host_ports import port_in_use

ROOT = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location("hold_ports", ROOT / "scripts" / "hold_ports.py")
assert _SPEC is not None
assert _SPEC.loader is not None
hold_ports = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(hold_ports)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def test_held_port_stays_in_use_until_the_socket_closes() -> None:
    port = _free_port()
    opened = hold_ports.hold((port,))
    try:
        assert len(opened) == 1
        gc.collect()
        assert port_in_use(port)
    finally:
        for sock in opened:
            sock.close()
    assert not port_in_use(port)


def test_unreferenced_sockets_release_the_port() -> None:
    port = _free_port()
    hold_ports.hold((port,))
    gc.collect()
    assert not port_in_use(port)


def test_main_keeps_the_port_for_the_process_lifetime(monkeypatch: pytest.MonkeyPatch) -> None:
    port = _free_port()
    real_hold = hold_ports.hold

    def only_ephemeral(_ports: tuple[int, ...] = hold_ports.DEFAULTS) -> list[socket.socket]:
        return real_hold((port,))

    def stop(_seconds: float) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(hold_ports, "hold", only_ephemeral)
    monkeypatch.setattr(hold_ports.time, "sleep", stop)
    hold_ports._HELD.clear()
    try:
        with pytest.raises(KeyboardInterrupt):
            hold_ports.main()
        gc.collect()
        assert hold_ports._HELD
        assert port_in_use(port)
    finally:
        for sock in list(hold_ports._HELD):
            sock.close()
        hold_ports._HELD.clear()
    assert not port_in_use(port)
