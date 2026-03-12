"""Low-level Duepi EVO protocol client."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import select
import socket

from homeassistant.components.climate import HVACMode

from .const import (
    FAN_MODE_MAP,
    FAN_MODE_MAP_REV,
    GET_BURN_TIME,
    GET_ERRORSTATE,
    GET_EXHFANSPEED,
    GET_FLUGASTEMP,
    GET_INITCOMMAND,
    GET_PCBTEMP,
    GET_PELLETSPEED,
    GET_PRESSURE_SWITCH,
    GET_POWERLEVEL,
    GET_SETPOINT,
    GET_STATUS,
    GET_TEMPERATURE,
    GET_TOTAL_BURN_TIME,
    PRESSURE_SWITCH_OK,
    PRESSURE_SWITCH_PRESSURE,
    REMOTE_RESET,
    SET_POWERLEVEL,
    SET_TEMPERATURE,
    STATE_ACK,
    STATE_CLEAN,
    STATE_COOL,
    STATE_ECO,
    STATE_OFF,
    STATE_ON,
    STATE_START,
)

_LOGGER = logging.getLogger(__name__)


class DuepiEvoClientError(Exception):
    """Base client exception."""


class DuepiEvoTimeoutError(DuepiEvoClientError):
    """Timeout while communicating with the stove."""


class DuepiEvoProtocolError(DuepiEvoClientError):
    """Protocol parse/validation error."""


@dataclass(slots=True)
class DuepiEvoState:
    """Normalized stove state returned by the client."""

    burner_status: str
    error_code: str
    exh_fan_speed_rpm: int | None
    flu_gas_temp_c: int | None
    pellet_speed: int | None
    power_level: str
    pcb_temp_c: int | None
    total_burn_time_h: int | None
    burn_time_since_reset_h: int | None
    pressure_switch_active: bool | None
    current_temp_c: float | None
    target_temp_c: float | None
    hvac_mode: HVACMode
    heating: bool


class DuepiEvoClient:
    """Client that talks to the Duepi EVO serial bridge."""

    def __init__(
        self,
        host: str,
        port: int,
        min_temp: float,
        max_temp: float,
        no_feedback: float,
        auto_reset: bool,
        init_command: bool,
        timeout: float = 3.0,
    ) -> None:
        self.host = host
        self.port = port
        self.min_temp = min_temp
        self.max_temp = max_temp
        self.no_feedback = no_feedback
        self.auto_reset = auto_reset
        self.init_command = init_command
        self.timeout = timeout
        self._error_code_map = {
            0: "All OK",
            1: "Ignition failure",
            2: "Defective suction",
            3: "Insufficient air intake",
            4: "Water temperature",
            5: "Out of pellets",
            6: "Defective pressure switch",
            7: "Unknown",
            8: "No current",
            9: "Exhaust motor failure",
            10: "Card surge",
            11: "Date expired",
            12: "Unknown",
            13: "Suction regulating sensor error",
            14: "Overheating",
        }

    @staticmethod
    def generate_command(command: str) -> str:
        """Format command with protocol prefix and checksum."""
        formatted_cmd = "R" + command
        checksum = sum(ord(char) for char in formatted_cmd) & 0xFF
        return "\x1b" + formatted_cmd + f"{checksum:02X}" + "&"

    def _open_socket(self) -> socket.socket:
        """Open and connect a TCP socket."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        sock.connect((self.host, self.port))
        return sock

    def _send_init_if_needed(self, sock: socket.socket) -> None:
        """Send optional init command and consume optional immediate response frame."""
        if not self.init_command:
            return

        sock.send(self.generate_command(GET_INITCOMMAND).encode())

        try:
            ready_to_read, _, _ = select.select([sock], [], [], 0.2)
        except OSError:
            return

        if not ready_to_read:
            return

        try:
            init_response = sock.recv(10).decode(errors="ignore")
            if init_response:
                _LOGGER.debug("init_command response consumed: %s", init_response)
        except (TimeoutError, socket.timeout, OSError):
            return

    def _send(self, sock: socket.socket, command: str) -> None:
        """Send one protocol command."""
        sock.send(self.generate_command(command).encode())

    def _recv(self, sock: socket.socket) -> str:
        """Receive one protocol response frame."""
        response = sock.recv(10).decode(errors="ignore")
        if len(response) < 9:
            raise DuepiEvoProtocolError(f"Malformed response from {self.host}:{self.port}: {response!r}")
        return response

    def _send_and_recv(self, sock: socket.socket, command: str) -> str:
        """Send command and return response frame."""
        self._send(sock, command)
        return self._recv(sock)

    def _send_and_expect_ack(self, sock: socket.socket, command: str) -> None:
        """Send command and validate ACK flag."""
        response = self._send_and_recv(sock, command)
        current_state = int(response[1:9], 16)
        if not (STATE_ACK & current_state):
            raise DuepiEvoProtocolError(f"No ACK for command {command}, response={response!r}")

    @staticmethod
    def _read_hex_value(response: str, digits: int) -> int:
        """Parse a hex field from the start of a response payload."""
        return int(response[1 : 1 + digits], 16)

    def _optional_read(
        self,
        sock: socket.socket,
        command: str,
        *,
        description: str,
        parser,
    ):
        """Read optional telemetry without failing the main snapshot."""
        try:
            response = self._send_and_recv(sock, command)
            return parser(response)
        except (DuepiEvoProtocolError, TimeoutError, socket.timeout, ValueError) as err:
            _LOGGER.debug(
                "Optional %s read failed for %s:%s: %s",
                description,
                self.host,
                self.port,
                err,
            )
            return None

    @staticmethod
    def _decode_status(current_state: int) -> str:
        """Decode burner status flags."""
        if STATE_START & current_state:
            return "Ignition starting"
        if STATE_ON & current_state:
            return "Flame On"
        if STATE_CLEAN & current_state:
            return "Cleaning"
        if STATE_ECO & current_state:
            return "Eco idle"
        if STATE_COOL & current_state:
            return "Cooling down"
        if STATE_OFF & current_state:
            return "Off"
        return "Unknown state"

    @staticmethod
    def _hvac_from_status(status: str) -> tuple[HVACMode, bool]:
        """Return HVAC mode and heating flag from burner status."""
        if status == "Off":
            return HVACMode.OFF, False
        if status == "Cooling down":
            return HVACMode.HEAT, False
        return HVACMode.HEAT, True

    def _decode_pressure_switch(self, response: str) -> bool | None:
        """Decode the pressure switch status returned by RC0000."""
        pressure_state = self._read_hex_value(response, 4)
        if pressure_state == PRESSURE_SWITCH_OK:
            return False
        if pressure_state == PRESSURE_SWITCH_PRESSURE:
            return True

        _LOGGER.debug(
            "Unexpected pressure switch payload from %s:%s: %s",
            self.host,
            self.port,
            response,
        )
        return None

    def fetch_state(self) -> DuepiEvoState:
        """Fetch and parse a full stove state snapshot."""
        try:
            with self._open_socket() as sock:
                self._send_init_if_needed(sock)

                status_response = self._send_and_recv(sock, GET_STATUS)
                burner_state = int(status_response[1:9], 16)
                burner_status = self._decode_status(burner_state)

                if burner_status == "Off":
                    power_level_code = FAN_MODE_MAP["Off"]
                else:
                    power_response = self._send_and_recv(sock, GET_POWERLEVEL)
                    power_level_code = self._read_hex_value(power_response, 4)
                power_level = FAN_MODE_MAP_REV.get(power_level_code)
                if power_level is None:
                    power_level = "Off"
                    _LOGGER.warning(
                        "Unknown fan mode value received: %s. Falling back to %s",
                        power_level_code,
                        power_level,
                    )

                ambient_response = self._send_and_recv(sock, GET_TEMPERATURE)
                current_temperature = self._read_hex_value(ambient_response, 4) / 10.0

                pellet_response = self._send_and_recv(sock, GET_PELLETSPEED)
                pellet_speed = self._read_hex_value(pellet_response, 4)

                flugass_response = self._send_and_recv(sock, GET_FLUGASTEMP)
                flu_gas_temp = self._read_hex_value(flugass_response, 4)

                exhaust_response = self._send_and_recv(sock, GET_EXHFANSPEED)
                exh_fan_speed = self._read_hex_value(exhaust_response, 4) * 10

                error_response = self._send_and_recv(sock, GET_ERRORSTATE)
                error_code_decimal = self._read_hex_value(error_response, 4)
                error_code = self._error_code_map.get(error_code_decimal, str(error_code_decimal))

                setpoint_response = self._send_and_recv(sock, GET_SETPOINT)
                setpoint_raw = self._read_hex_value(setpoint_response, 4)
                target_temperature = None
                if setpoint_raw != 0 and self.min_temp < setpoint_raw < self.max_temp:
                    target_temperature = float(setpoint_raw)

                pcb_temp = self._optional_read(
                    sock,
                    GET_PCBTEMP,
                    description="PCB temperature",
                    parser=lambda response: self._read_hex_value(response, 4),
                )
                total_burn_time = self._optional_read(
                    sock,
                    GET_TOTAL_BURN_TIME,
                    description="total burn time",
                    parser=lambda response: self._read_hex_value(response, 6),
                )
                burn_time_since_reset = self._optional_read(
                    sock,
                    GET_BURN_TIME,
                    description="burn time since reset",
                    parser=lambda response: self._read_hex_value(response, 6),
                )
                pressure_switch_active = self._optional_read(
                    sock,
                    GET_PRESSURE_SWITCH,
                    description="pressure switch",
                    parser=self._decode_pressure_switch,
                )

                hvac_mode, heating = self._hvac_from_status(burner_status)

                return DuepiEvoState(
                    burner_status=burner_status,
                    error_code=error_code,
                    exh_fan_speed_rpm=exh_fan_speed,
                    flu_gas_temp_c=flu_gas_temp,
                    pellet_speed=pellet_speed,
                    power_level=power_level,
                    pcb_temp_c=pcb_temp,
                    total_burn_time_h=total_burn_time,
                    burn_time_since_reset_h=burn_time_since_reset,
                    pressure_switch_active=pressure_switch_active,
                    current_temp_c=current_temperature,
                    target_temp_c=target_temperature,
                    hvac_mode=hvac_mode,
                    heating=heating,
                )
        except (TimeoutError, socket.timeout) as err:
            raise DuepiEvoTimeoutError(f"Time-out while polling host: {self.host}") from err
        except OSError as err:
            raise DuepiEvoClientError(f"Connection error to {self.host}:{self.port}: {err}") from err
        except ValueError as err:
            raise DuepiEvoProtocolError(f"Invalid numeric payload from {self.host}:{self.port}: {err}") from err

    def set_fan_mode(self, fan_mode: str) -> None:
        """Set stove fan mode by name."""
        if fan_mode not in FAN_MODE_MAP:
            raise DuepiEvoClientError(f"Unsupported fan mode: {fan_mode}")

        power_level_hex = hex(FAN_MODE_MAP[fan_mode])[2:3]
        command = SET_POWERLEVEL.replace("x", power_level_hex)

        try:
            with self._open_socket() as sock:
                self._send_init_if_needed(sock)
                self._send_and_expect_ack(sock, command)
        except (TimeoutError, socket.timeout) as err:
            raise DuepiEvoTimeoutError(f"Time-out while setting fan mode on host: {self.host}") from err
        except OSError as err:
            raise DuepiEvoClientError(f"Connection error to {self.host}:{self.port}: {err}") from err

    def set_temperature(self, target_temperature: float) -> None:
        """Set target temperature."""
        set_point_int = int(target_temperature)
        set_point_hex = f"{set_point_int:02X}"
        command = SET_TEMPERATURE.replace("xx", set_point_hex)

        try:
            with self._open_socket() as sock:
                self._send_init_if_needed(sock)
                self._send_and_expect_ack(sock, command)
        except (TimeoutError, socket.timeout) as err:
            raise DuepiEvoTimeoutError(f"Time-out while setting temperature on host: {self.host}") from err
        except OSError as err:
            raise DuepiEvoClientError(f"Connection error to {self.host}:{self.port}: {err}") from err

    def set_hvac_mode(self, hvac_mode: HVACMode | str) -> None:
        """Set HVAC mode by mapping to Duepi power level."""
        mode = hvac_mode.value if isinstance(hvac_mode, HVACMode) else str(hvac_mode)
        if mode == HVACMode.OFF.value:
            self.set_fan_mode("Off")
            return
        if mode == HVACMode.HEAT.value:
            self.set_fan_mode("Min")
            return
        raise DuepiEvoClientError(f"Unsupported HVAC mode: {mode}")

    def remote_reset(self, _reason: str | None = None) -> None:
        """Send remote reset command."""
        try:
            with self._open_socket() as sock:
                self._send_init_if_needed(sock)
                self._send_and_expect_ack(sock, REMOTE_RESET)
        except (TimeoutError, socket.timeout) as err:
            raise DuepiEvoTimeoutError(f"Time-out while resetting host: {self.host}") from err
        except OSError as err:
            raise DuepiEvoClientError(f"Connection error to {self.host}:{self.port}: {err}") from err
