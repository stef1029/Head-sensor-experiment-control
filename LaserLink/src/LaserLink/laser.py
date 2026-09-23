"""
Unified Laser frontend — picks a backend by ``kind`` and forwards calls.

Adding a new laser type is one entry in ``_BACKENDS`` plus a backend
module that satisfies ``_LaserBackend``.
"""

from __future__ import annotations

from .base import LaserError, LaserStatus, _LaserBackend
from .cni_laser import _CniLaserBackend
from .cobolt_06mld import _Cobolt06mldBackend
from .mock import _MockBackend


_BACKENDS: dict[str, type] = {
    "cni_laser": _CniLaserBackend,
    "cobolt_06mld": _Cobolt06mldBackend,
}


def known_kinds() -> list[str]:
    """Return the laser kind codes registered in this build."""
    return sorted(_BACKENDS.keys())


def is_known_kind(kind: str) -> bool:
    return kind in _BACKENDS


class Laser:
    """One class, one API across all supported laser kinds.

    Args:
        name: Human-readable identifier — used in logs and ``LaserStatus``.
        kind: Laser-kind code (see ``known_kinds()``).
        port: OS-level port string (e.g. ``"COM26"``). LaserLink does not
            resolve names from board registries — pass the resolved string.
        mock: If True, returns a mock backend that tracks state without
            touching hardware. Honoured for any kind.
        **vendor_kwargs: Forwarded to the backend constructor (e.g.
            ``baudrate=9600`` for the CNI laser).
    """

    def __init__(
        self,
        name: str,
        kind: str,
        port: str,
        *,
        mock: bool = False,
        **vendor_kwargs,
    ) -> None:
        self.name = name
        self.kind = kind
        self.port = port

        if mock:
            self._backend: _LaserBackend = _MockBackend(name=name, kind=kind, port=port)
        else:
            cls = _BACKENDS.get(kind)
            if cls is None:
                raise LaserError(
                    f"Unknown laser kind: {kind!r}. Known: {known_kinds()}"
                )
            self._backend = cls(name=name, port=port, **vendor_kwargs)

    @property
    def requires_key(self) -> bool:
        return self._backend.requires_key

    def connect(self) -> None:
        self._backend.connect()

    def wait_ready(self, timeout: float = 30.0) -> None:
        self._backend.wait_ready(timeout)

    def set_power(self, mw: float) -> None:
        self._backend.set_power(mw)

    def turn_on(self) -> None:
        self._backend.turn_on()

    def turn_off(self) -> None:
        self._backend.turn_off()

    def disconnect(self) -> None:
        self._backend.disconnect()

    def get_status(self) -> LaserStatus:
        return self._backend.get_status()

    # Convenience for `with Laser(...) as laser:` — connect on enter,
    # turn_off + disconnect on exit. wait_ready / set_power / turn_on
    # remain explicit since their ordering is the user's responsibility.
    def __enter__(self) -> "Laser":
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        try:
            self.turn_off()
        finally:
            self.disconnect()
