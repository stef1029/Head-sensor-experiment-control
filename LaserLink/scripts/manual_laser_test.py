"""
Hand-edit hardware test for LaserLink.

Edit the LASERS list and timing knobs in main(), then run:

    uv run python LaserLink/scripts/manual_laser_test.py

Connects each laser, sets power, turns it on, holds for HOLD_SECONDS
while you drive your TTL lines, then turns off and disconnects. Set
DEBUG_BYTES = True to see every TX/RX frame as hex.
"""

import logging
import time

from LaserLink import Laser


def main() -> int:
    # Each entry is one laser. Comment out the ones you don't want.
    #   kind:  "cni_laser" or "cobolt_06mld"
    #   mock:  True = no hardware, walks the lifecycle in memory
    LASERS = [
        {"name": "rig1_red", "kind": "cni_laser", "port": "COM31",
         "power_mw": 50.0, "mock": False},
        # {"name": "rig1_blue", "kind": "cobolt_06mld", "port": "COM20",
        #  "power_mw": 5.0, "mock": False},
    ]

    HOLD_SECONDS = 5.0
    KEY_TIMEOUT_S = 30.0          # only used by Cobolt
    DEBUG_BYTES = False           # True to dump TX/RX frame hex

    logging.basicConfig(
        level=logging.DEBUG if DEBUG_BYTES else logging.INFO,
        format="%(asctime)s.%(msecs)03d %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    armed: list[Laser] = []
    try:
        for spec in LASERS:
            laser = Laser(
                name=spec["name"], kind=spec["kind"],
                port=spec["port"], mock=spec.get("mock", False),
            )
            laser.connect()
            if laser.requires_key:
                print(f"[{laser.name}] turn the safety key now "
                      f"(timeout {KEY_TIMEOUT_S:.0f}s)")
            laser.wait_ready(timeout=KEY_TIMEOUT_S)
            laser.set_power(spec["power_mw"])
            laser.turn_on()
            armed.append(laser)
            print(f"[{laser.name}] armed at {spec['power_mw']:.2f} mW")

        print(f"\nHolding for {HOLD_SECONDS:.1f}s — drive TTL lines now. Ctrl+C to stop early.")
        time.sleep(HOLD_SECONDS)

    except KeyboardInterrupt:
        print("\nInterrupted.")
    except Exception as e:  # noqa: BLE001
        print(f"\nERROR: {e!r}")
        return 1
    finally:
        for laser in reversed(armed):
            try:
                laser.turn_off()
                laser.disconnect()
            except Exception as e:  # noqa: BLE001
                print(f"[{laser.name}] shutdown error: {e!r}")

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
