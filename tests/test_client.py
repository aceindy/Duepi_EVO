"""Unit tests for DuepiEvoClient protocol behavior."""

from __future__ import annotations

from typing import Any

import pytest

from homeassistant.components.climate import HVACMode

from custom_components.duepi_evo import client as client_module
from custom_components.duepi_evo.client import (
    DuepiEvoClient,
    DuepiEvoProtocolError,
)


class FakeSocket:
    """Simple fake socket used to capture traffic and feed responses."""

    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.sent: list[bytes] = []
        self.connected_to: tuple[str, int] | None = None
        self.timeout: float | None = None
        self.closed = False

    def settimeout(self, timeout: float) -> None:
        self.timeout = timeout

    def connect(self, address: tuple[str, int]) -> None:
        self.connected_to = address

    def send(self, data: bytes) -> int:
        self.sent.append(data)
        return len(data)

    def recv(self, _size: int) -> bytes:
        if not self.responses:
            return b""
        return self.responses.pop(0).encode()

    def close(self) -> None:
        self.closed = True

    def __enter__(self) -> "FakeSocket":
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.close()


def _client(*, init_command: bool = False) -> DuepiEvoClient:
    return DuepiEvoClient(
        host="192.168.0.10",
        port=2000,
        min_temp=16.0,
        max_temp=30.0,
        no_feedback=16.0,
        auto_reset=False,
        init_command=init_command,
    )


def test_generate_command_checksum() -> None:
    """Command formatter should match protocol framing and checksum."""
    payload = DuepiEvoClient.generate_command("D1000")
    assert payload.startswith("\x1bRD1000")
    assert payload.endswith("&")
    assert payload == "\x1bRD100057&"


def test_set_temperature_sends_init_command_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """When init_command is enabled, init frame must be sent first."""
    created: list[FakeSocket] = []

    def fake_socket(*_args: Any, **_kwargs: Any) -> FakeSocket:
        sock = FakeSocket(["\x1b00000020&"])
        created.append(sock)
        return sock

    monkeypatch.setattr("socket.socket", fake_socket)
    monkeypatch.setattr(client_module.select, "select", lambda _read, _write, _error, _timeout: ([], [], []))

    client = _client(init_command=True)
    client.set_temperature(23)

    assert len(created) == 1
    sent_frames = created[0].sent
    assert len(sent_frames) == 2
    assert b"RDC000" in sent_frames[0]
    assert b"RF2170" in sent_frames[1]


def test_set_temperature_skips_init_command_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """When init_command is disabled, only setpoint frame is sent."""
    created: list[FakeSocket] = []

    def fake_socket(*_args: Any, **_kwargs: Any) -> FakeSocket:
        sock = FakeSocket(["\x1b00000020&"])
        created.append(sock)
        return sock

    monkeypatch.setattr("socket.socket", fake_socket)

    client = _client(init_command=False)
    client.set_temperature(23)

    assert len(created) == 1
    sent_frames = created[0].sent
    assert len(sent_frames) == 1
    assert b"RDC000" not in sent_frames[0]
    assert b"RF2170" in sent_frames[0]


def test_fetch_state_parses_protocol_frames(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fetch should decode burner, fan, temperatures, speed and error code."""
    responses = [
        "\x1b02000000&",  # status => Flame On
        "\x1b00020000&",  # power level => 2 => Low
        "\x1b00D70000&",  # ambient => 21.5 C
        "\x1b00140000&",  # pellet speed => 20
        "\x1b00C80000&",  # flugas => 200 C
        "\x1b00320000&",  # exh fan raw => 50 * 10 => 500 rpm
        "\x1b00050000&",  # error => 5 => Out of pellets
        "\x1b00170000&",  # setpoint => 23
        "\x1b002D0000&",  # pcb temp => 45 C
        "\x1b0001F400&",  # total burn time => 500 h
        "\x1b00002A00&",  # burn time since reset => 42 h
        "\x1b03000000&",  # pressure switch => pressure detected
    ]
    created: list[FakeSocket] = []

    def fake_socket(*_args: Any, **_kwargs: Any) -> FakeSocket:
        sock = FakeSocket(responses)
        created.append(sock)
        return sock

    monkeypatch.setattr("socket.socket", fake_socket)

    state = _client(init_command=False).fetch_state()
    assert state.burner_status == "Flame On"
    assert state.power_level == "Low"
    assert state.current_temp_c == 21.5
    assert state.pellet_speed == 20
    assert state.flu_gas_temp_c == 200
    assert state.exh_fan_speed_rpm == 500
    assert state.error_code == "Out of pellets"
    assert state.target_temp_c == 23.0
    assert state.pcb_temp_c == 45
    assert state.total_burn_time_h == 500
    assert state.burn_time_since_reset_h == 42
    assert state.pressure_switch_active is True
    assert state.hvac_mode == HVACMode.HEAT
    assert state.heating is True
    assert len(created) == 1
    sent_frames = b"".join(created[0].sent)
    assert b"RDF000" in sent_frames
    assert b"RED000" in sent_frames
    assert b"REE000" in sent_frames
    assert b"RC0000" in sent_frames


def test_fetch_state_keeps_snapshot_when_pressure_switch_payload_is_unknown(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Unknown pressure switch payloads should not fail the main state refresh."""
    responses = [
        "\x1b02000000&",
        "\x1b00020000&",
        "\x1b00D70000&",
        "\x1b00140000&",
        "\x1b00C80000&",
        "\x1b00320000&",
        "\x1b00000000&",
        "\x1b00170000&",
        "\x1b002D0000&",
        "\x1b0001F400&",
        "\x1b00002A00&",
        "\x1b99990000&",
    ]

    def fake_socket(*_args: Any, **_kwargs: Any) -> FakeSocket:
        return FakeSocket(responses)

    monkeypatch.setattr("socket.socket", fake_socket)
    caplog.set_level("DEBUG")

    state = _client(init_command=False).fetch_state()

    assert state.pressure_switch_active is None
    assert "Unexpected pressure switch payload" in caplog.text


@pytest.mark.parametrize(
    ("status", "expected_hvac_mode", "expected_heating"),
    [
        ("Off", HVACMode.OFF, False),
        ("Cooling down", HVACMode.HEAT, False),
        ("Flame On", HVACMode.HEAT, True),
        ("Eco idle", HVACMode.HEAT, True),
        ("Cleaning", HVACMode.HEAT, True),
    ],
)
def test_hvac_from_status_mapping(
    status: str,
    expected_hvac_mode: HVACMode,
    expected_heating: bool,
) -> None:
    """Burner status should map to the expected HVAC mode and heating flag."""
    hvac_mode, heating = DuepiEvoClient._hvac_from_status(status)

    assert hvac_mode == expected_hvac_mode
    assert heating is expected_heating


def test_fetch_state_raises_protocol_error_on_malformed_frame(monkeypatch: pytest.MonkeyPatch) -> None:
    """Short/invalid frames should raise a protocol error."""

    def fake_socket(*_args: Any, **_kwargs: Any) -> FakeSocket:
        return FakeSocket(["bad"])

    monkeypatch.setattr("socket.socket", fake_socket)

    with pytest.raises(DuepiEvoProtocolError):
        _client(init_command=False).fetch_state()
