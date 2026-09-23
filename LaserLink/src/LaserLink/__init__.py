"""
LaserLink — unified laser control library.

Public surface: ``Laser`` (the dispatcher class), ``LaserStatus`` (status
snapshots), and the ``LaserError`` hierarchy.

Adding a new laser kind: add a backend module satisfying the
``_LaserBackend`` Protocol in ``base.py``, then register it in the
``_BACKENDS`` dict in ``laser.py``.
"""

from .base import (
    LaserConnectionError,
    LaserError,
    LaserNotReadyError,
    LaserProtocolError,
    LaserStatus,
    LaserTimeoutError,
)
from .laser import Laser, is_known_kind, known_kinds

__all__ = [
    "Laser",
    "LaserStatus",
    "LaserError",
    "LaserConnectionError",
    "LaserProtocolError",
    "LaserTimeoutError",
    "LaserNotReadyError",
    "known_kinds",
    "is_known_kind",
]
