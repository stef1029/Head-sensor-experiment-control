"""
Core types for the LaserLink unified laser API.

Every backend implements the ``_LaserBackend`` protocol. ``Laser`` is a
thin dispatcher that picks a backend by ``kind`` at construction and
forwards calls. Status is reported uniformly via ``LaserStatus``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class LaserStatus:
    """Snapshot of a laser's runtime state.

    All backends populate this consistently — the frontend never has to
    check ``kind`` to interpret the fields.
    """
    name: str
    kind: str
    port: str
    connected: bool
    ready: bool                     # past wait_ready / safety key armed
    output_enabled: bool            # LD on, awaiting external TTL gating
    power_mw: float                 # last commanded power
    fault: str | None = None        # vendor fault text, if any


@runtime_checkable
class _LaserBackend(Protocol):
    """Backend contract. One backend class per laser kind."""

    name: str
    kind: str
    port: str
    requires_key: bool              # True if wait_ready blocks on a physical key

    def connect(self) -> None: ...
    def wait_ready(self, timeout: float) -> None: ...
    def set_power(self, mw: float) -> None: ...
    def turn_on(self) -> None: ...
    def turn_off(self) -> None: ...
    def get_status(self) -> LaserStatus: ...
    def disconnect(self) -> None: ...


class LaserError(RuntimeError):
    """Base for all laserlink errors."""


class LaserConnectionError(LaserError):
    """Failed to open / lost comms with the laser."""


class LaserProtocolError(LaserError):
    """Vendor returned a malformed response or rejected a command."""


class LaserTimeoutError(LaserError):
    """A blocking call exceeded its timeout."""


class LaserNotReadyError(LaserError):
    """Operation requires the laser to be past wait_ready first."""
