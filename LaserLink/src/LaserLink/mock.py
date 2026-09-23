"""
Mock backend — kind-agnostic, no hardware.

Selected via ``Laser(..., mock=True)``. Tracks state in memory so a
caller can drive the same lifecycle the real lasers expose, useful for
GUI dev and CI without serial hardware.
"""

from __future__ import annotations

import logging

from .base import LaserNotReadyError, LaserStatus

logger = logging.getLogger("laserlink.mock")


class _MockBackend:
    """Stand-in for any laser kind. Logs every call; never opens a port."""

    def __init__(self, name: str, kind: str, port: str) -> None:
        self.name = name
        self.kind = kind
        self.port = port
        # Cobolt-flavoured kinds advertise key handling; mock honours that
        # bit for completeness even though wait_ready is a no-op here.
        self.requires_key = kind == "cobolt_06mld"
        self._connected = False
        self._ready = False
        self._output_enabled = False
        self._power_mw = 0.0

    def connect(self) -> None:
        self._connected = True
        logger.info("[mock:%s/%s] connect on %s", self.name, self.kind, self.port)

    def wait_ready(self, timeout: float) -> None:
        del timeout
        if not self._connected:
            raise LaserNotReadyError(
                f"Mock laser '{self.name}' not connected — call connect() first."
            )
        self._ready = True
        logger.info("[mock:%s] wait_ready -> ready", self.name)

    def set_power(self, mw: float) -> None:
        if not self._ready:
            raise LaserNotReadyError(
                f"Mock laser '{self.name}' not ready — call wait_ready() first."
            )
        self._power_mw = float(mw)
        logger.info("[mock:%s] set_power %.2f mW", self.name, mw)

    def turn_on(self) -> None:
        if not self._ready:
            raise LaserNotReadyError(
                f"Mock laser '{self.name}' not ready — call wait_ready() first."
            )
        self._output_enabled = True
        logger.info("[mock:%s] turn_on", self.name)

    def turn_off(self) -> None:
        self._output_enabled = False
        self._power_mw = 0.0
        logger.info("[mock:%s] turn_off", self.name)

    def disconnect(self) -> None:
        self._connected = False
        self._ready = False
        self._output_enabled = False
        self._power_mw = 0.0
        logger.info("[mock:%s] disconnect", self.name)

    def get_status(self) -> LaserStatus:
        return LaserStatus(
            name=self.name,
            kind=self.kind,
            port=self.port,
            connected=self._connected,
            ready=self._ready,
            output_enabled=self._output_enabled,
            power_mw=self._power_mw,
            fault=None,
        )
