"""
CNI laser backend — raw RS-232 (no upstream library).

Protocol bytes are owned by ``cni_laser_protocol``. The hardware is a
CNI diode laser fronted by a Prolific PL2303GT USB-serial adapter at
9600 8N1. Emission is gated externally by a TTL line into the laser's
shutter input — this code never pulses output itself.

Ported from ``Head-sensor-experiment-control/scripts/red_laser_control.py``.
"""

from __future__ import annotations

import logging
import time

import serial

from .base import (
    LaserConnectionError,
    LaserNotReadyError,
    LaserProtocolError,
    LaserStatus,
    LaserTimeoutError,
)
from .cni_laser_protocol import (
    build_off_frame,
    build_on_frame,
    build_power_frame,
    parse_response,
)

logger = logging.getLogger(__name__)

_TERMINATOR = 0x0D
_RESPONSE_TIMEOUT_S = 1.0
_CONNECT_SETTLE_S = 0.5
# Firmware ACKs each command quickly but isn't ready for the next one
# for ~hundreds of ms. Back-to-back commands get dropped silently —
# every command-issuing method sleeps after sending so callers don't
# have to know about it.
_POST_COMMAND_SETTLE_S = 0.5
# Smallest valid reply is 7 bytes (0x41 0x07 + payload + 0x0D). A
# shorter "complete" buffer means a stray 0x0D from a half-flushed
# driver buffer; keep waiting.
_MIN_RESPONSE_LEN = 7


class _CniLaserBackend:
    """RS-232 backend for CNI diode lasers."""

    kind = "cni_laser"
    requires_key = False

    def __init__(self, name: str, port: str, *, baudrate: int = 9600) -> None:
        self.name = name
        self.port = port
        self._baudrate = baudrate
        self._ser: serial.Serial | None = None
        # Firmware doesn't expose readback; mirror commanded state.
        self._output_enabled = False
        self._power_mw = 0.0
        self._fault: str | None = None

    # ----- lifecycle -----

    def connect(self) -> None:
        if self._ser is not None and self._ser.is_open:
            return
        try:
            self._ser = serial.Serial(
                port=self.port,
                baudrate=self._baudrate,
                bytesize=8,
                parity=serial.PARITY_NONE,
                stopbits=1,
                timeout=_RESPONSE_TIMEOUT_S,
            )
        except serial.SerialException as e:
            raise LaserConnectionError(
                f"Failed to open CNI laser '{self.name}' on {self.port}: {e}"
            ) from e
        time.sleep(_CONNECT_SETTLE_S)

        try:
            # Drain stale bytes left over from a previous session.
            self._ser.reset_input_buffer()
            # Firmware requires LD-enable before set_power is accepted.
            self._send(build_on_frame())
        except Exception:
            self._close_serial()
            raise
        self._output_enabled = True
        time.sleep(_POST_COMMAND_SETTLE_S)
        self._fault = None
        logger.info(
            "[laser:%s] connected on %s (LD enabled, awaiting TTL)",
            self.name, self.port,
        )

    def wait_ready(self, timeout: float) -> None:
        # No safety key on this device — connect() already left it ready.
        del timeout

    def set_power(self, mw: float) -> None:
        self._send(build_power_frame(mw))
        self._power_mw = float(mw)
        time.sleep(_POST_COMMAND_SETTLE_S)
        logger.info("[laser:%s] set_power %.2f mW", self.name, mw)

    def turn_on(self) -> None:
        # Idempotent — firmware silently drops a redundant LD-enable
        # (no ACK -> 1s timeout), and connect() already enabled it.
        if self._output_enabled:
            return
        self._send(build_on_frame())
        self._output_enabled = True
        time.sleep(_POST_COMMAND_SETTLE_S)
        logger.info("[laser:%s] turn_on", self.name)

    def turn_off(self) -> None:
        if not self._output_enabled:
            return
        self._send(build_off_frame())
        self._output_enabled = False
        time.sleep(_POST_COMMAND_SETTLE_S)
        logger.info("[laser:%s] turn_off", self.name)

    def disconnect(self) -> None:
        if self._ser is None:
            return
        self._close_serial()
        logger.info("[laser:%s] disconnected", self.name)

    def get_status(self) -> LaserStatus:
        connected = self._ser is not None and self._ser.is_open
        return LaserStatus(
            name=self.name,
            kind=self.kind,
            port=self.port,
            connected=connected,
            ready=connected,
            output_enabled=self._output_enabled,
            power_mw=self._power_mw,
            fault=self._fault,
        )

    # ----- internals -----

    def _close_serial(self) -> None:
        """Close the port (best-effort) and reset state. Idempotent."""
        if self._ser is None:
            return
        try:
            if self._ser.is_open:
                self._ser.close()
        except Exception:  # noqa: BLE001 — cleanup must not raise
            pass
        self._ser = None
        self._output_enabled = False

    def _send(self, frame: bytes) -> None:
        if self._ser is None or not self._ser.is_open:
            raise LaserNotReadyError(
                f"CNI laser '{self.name}' not connected — call connect() first."
            )
        logger.debug("[laser:%s] -> %s", self.name, frame.hex())
        try:
            self._ser.write(frame)
        except serial.SerialException as e:
            raise LaserConnectionError(
                f"Write to CNI laser '{self.name}' failed: {e}"
            ) from e

        response = self._read_until_terminator()
        logger.debug("[laser:%s] <- %s", self.name, response.hex())
        try:
            parse_response(response)
        except LaserProtocolError as e:
            self._fault = str(e)
            raise

    def _read_until_terminator(self) -> bytes:
        """Drain bytes until a complete reply or the timeout elapses."""
        assert self._ser is not None
        deadline = time.monotonic() + _RESPONSE_TIMEOUT_S
        buf = bytearray()
        while time.monotonic() < deadline:
            if self._ser.in_waiting:
                buf.extend(self._ser.read(self._ser.in_waiting))
                if len(buf) >= _MIN_RESPONSE_LEN and buf[-1] == _TERMINATOR:
                    return bytes(buf)
            time.sleep(0.01)
        if not buf:
            raise LaserTimeoutError(
                f"No response from CNI laser '{self.name}' on {self.port} "
                f"within {_RESPONSE_TIMEOUT_S}s"
            )
        return bytes(buf)
