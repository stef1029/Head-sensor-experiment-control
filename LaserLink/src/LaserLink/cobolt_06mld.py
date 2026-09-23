"""
Cobolt 06MLD backend — wraps ``pycobolt.Cobolt06MLD``.

The Cobolt's TTL-gated mode requires a multi-step setup that is hidden
behind the unified API: ``connect`` brings the LD on at 0 mW so we can
read the safety-key state, ``wait_ready`` polls for the key turn and
then switches the laser into modulation + digital-modulation mode,
``set_power`` writes the modulation power, ``turn_off`` drops digital
modulation and zeroes power. Sequence ported from
``Head-sensor-experiment-control/scripts/laser_control.py``.

``pycobolt`` import is deferred to construction time so the rest of
LaserLink (and its tests) doesn't require the package on machines that
only run the red laser.
"""

from __future__ import annotations

import logging
import time

from .base import (
    LaserConnectionError,
    LaserNotReadyError,
    LaserStatus,
    LaserTimeoutError,
)

logger = logging.getLogger(__name__)


# Vendor recommends ~2s after turn_on before reading state (LD warm-up)
# and ~5s after switching into modulation mode before commanding power.
_POST_TURN_ON_S = 2.0
_POST_MODULATION_SETTLE_S = 5.0
_KEY_POLL_INTERVAL_S = 0.3
_KEY_WAITING_TOKEN = "Waiting for key"


class _Cobolt06mldBackend:
    """Wraps pycobolt.Cobolt06MLD and adapts it to LaserLink's contract."""

    kind = "cobolt_06mld"
    requires_key = True

    def __init__(self, name: str, port: str) -> None:
        self.name = name
        self.port = port
        self._dev = None  # type: ignore[var-annotated]
        self._ready = False
        self._output_enabled = False
        self._power_mw = 0.0
        self._fault: str | None = None

    # ----- lifecycle -----

    def connect(self) -> None:
        try:
            from pycobolt import Cobolt06MLD
        except ImportError as e:
            raise LaserConnectionError(
                "pycobolt not installed — install it to use the cobolt_06mld backend"
            ) from e

        try:
            self._dev = Cobolt06MLD(port=self.port)
            self._dev.clear_fault()
            self._dev.constant_power(power=0)
            # LD must be on for the controller to report key state.
            self._dev.turn_on()
        except Exception as e:  # vendor lib raises a mix of exception types
            self._dev = None
            raise LaserConnectionError(
                f"Failed to connect to Cobolt 06MLD '{self.name}' on {self.port}: {e}"
            ) from e

        time.sleep(_POST_TURN_ON_S)
        self._ready = False
        self._output_enabled = False
        self._power_mw = 0.0
        self._fault = None
        logger.info("[laser:%s] connected on %s (Cobolt 06MLD)", self.name, self.port)

    def wait_ready(self, timeout: float) -> None:
        if self._dev is None:
            raise LaserNotReadyError(
                f"Cobolt '{self.name}' not connected — call connect() first."
            )

        deadline = time.monotonic() + timeout
        announced = False
        while time.monotonic() < deadline:
            try:
                state = str(self._dev.get_state())
            except Exception as e:
                self._fault = f"get_state failed: {e}"
                raise LaserConnectionError(
                    f"Lost comms with Cobolt '{self.name}' while waiting for key: {e}"
                ) from e
            if _KEY_WAITING_TOKEN not in state:
                # Key turned — switch into TTL-modulated mode.
                self._enter_modulation_mode()
                self._ready = True
                logger.info("[laser:%s] ready (state=%r)", self.name, state)
                return
            if not announced:
                logger.info(
                    "[laser:%s] waiting for safety key (state=%r)...",
                    self.name, state,
                )
                announced = True
            time.sleep(_KEY_POLL_INTERVAL_S)

        raise LaserTimeoutError(
            f"Cobolt '{self.name}' key not turned within {timeout:.0f}s"
        )

    def _enter_modulation_mode(self) -> None:
        assert self._dev is not None
        # 0 mW baseline so flipping into modulation never emits unexpectedly.
        self._dev.modulation_mode(power=0)
        self._dev.digital_modulation(1)
        time.sleep(_POST_MODULATION_SETTLE_S)

    def set_power(self, mw: float) -> None:
        if self._dev is None or not self._ready:
            raise LaserNotReadyError(
                f"Cobolt '{self.name}' not ready — call wait_ready() first."
            )
        try:
            self._dev.set_modulation_power(mw)
        except Exception as e:
            self._fault = f"set_modulation_power failed: {e}"
            raise LaserConnectionError(
                f"set_power on Cobolt '{self.name}' failed: {e}"
            ) from e
        self._power_mw = float(mw)
        logger.info("[laser:%s] set_power %.2f mW", self.name, mw)

    def turn_on(self) -> None:
        if self._dev is None or not self._ready:
            raise LaserNotReadyError(
                f"Cobolt '{self.name}' not ready — call wait_ready() first."
            )
        # Modulation is already on after wait_ready; this is an idempotent
        # safety re-assert. Output is gated by the TTL line into the
        # Cobolt's digital modulation input from this point.
        try:
            self._dev.digital_modulation(1)
        except Exception as e:
            self._fault = f"digital_modulation(1) failed: {e}"
            raise LaserConnectionError(
                f"turn_on on Cobolt '{self.name}' failed: {e}"
            ) from e
        self._output_enabled = True
        logger.info("[laser:%s] turn_on (digital modulation enabled)", self.name)

    def turn_off(self) -> None:
        if self._dev is None:
            return
        # Modulation off + 0 mW = guaranteed no emission regardless of TTL.
        try:
            self._dev.digital_modulation(0)
            self._dev.set_modulation_power(0)
        except Exception as e:
            # Don't raise on shutdown paths — just record the fault.
            self._fault = f"turn_off failed: {e}"
            logger.warning("[laser:%s] turn_off error: %s", self.name, e)
        self._output_enabled = False
        self._power_mw = 0.0
        logger.info("[laser:%s] turn_off", self.name)

    def disconnect(self) -> None:
        if self._dev is None:
            return
        try:
            try:
                self._dev.constant_power(power=0)
                self._dev.turn_off()
            except Exception as e:
                logger.warning("[laser:%s] error during disconnect cleanup: %s", self.name, e)
            try:
                self._dev.disconnect()
            except Exception as e:
                logger.warning("[laser:%s] error closing Cobolt connection: %s", self.name, e)
        finally:
            self._dev = None
            self._ready = False
            self._output_enabled = False
            self._power_mw = 0.0
            logger.info("[laser:%s] disconnected", self.name)

    def get_status(self) -> LaserStatus:
        connected = self._dev is not None
        return LaserStatus(
            name=self.name,
            kind=self.kind,
            port=self.port,
            connected=connected,
            ready=self._ready,
            output_enabled=self._output_enabled,
            power_mw=self._power_mw,
            fault=self._fault,
        )
