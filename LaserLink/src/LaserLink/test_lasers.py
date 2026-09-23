"""
Standalone CLI test harness for LaserLink.

Usage:

    laserlink-test --kind cni_laser --port COM26 --power 5 --hold-seconds 5
    laserlink-test --kind cobolt_06mld --port COM27 --power 5 --hold-seconds 5
    laserlink-test --kind cni_laser --port COM_FAKE --mock --power 10 --hold-seconds 1
    laserlink-test --config lasers.toml --hold-seconds 10

Equivalent: ``python -m LaserLink.test_lasers ...``.

For each laser, the harness runs:
    connect -> wait_ready -> set_power -> turn_on -> hold -> turn_off -> disconnect

and prints a status table after the hold. Exit 0 on success, non-zero
on the first failure (with a one-line summary of which laser failed at
which step).

This script is the Phase-1 sign-off proof: if it works against the real
hardware, the library is good.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from dataclasses import dataclass

# Python 3.11+ ships tomllib; on 3.10 the workspace already pulls
# something usable, but fall back gracefully if the env is older.
try:
    import tomllib  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - 3.10 fallback
    import tomli as tomllib  # type: ignore[import-not-found,no-redef]

from .laser import Laser, known_kinds


@dataclass
class _LaserPlan:
    name: str
    kind: str
    port: str
    power_mw: float
    mock: bool


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="laserlink-test",
        description="Run a connect/arm/hold/stop cycle on one or more lasers.",
    )
    p.add_argument("--config", type=str,
                   help="Path to a TOML file with a [[lasers]] array.")
    p.add_argument("--kind", type=str, choices=known_kinds(),
                   help="Laser kind (single-laser mode).")
    p.add_argument("--port", type=str,
                   help="Port string e.g. COM26 (single-laser mode).")
    p.add_argument("--name", type=str, default="cli",
                   help="Human-readable name for logs (single-laser mode).")
    p.add_argument("--power", type=float, default=0.0,
                   help="Power in mW (single-laser mode).")
    p.add_argument("--mock", action="store_true",
                   help="Use the mock backend (no hardware).")
    p.add_argument("--hold-seconds", type=float, default=5.0,
                   help="How long to keep the lasers turned_on before stopping.")
    p.add_argument("--key-timeout", type=float, default=30.0,
                   help="wait_ready timeout passed to each laser, in seconds.")
    p.add_argument("-v", "--verbose", action="store_true",
                   help="Verbose logging.")
    return p.parse_args(argv)


def _plans_from_args(args: argparse.Namespace) -> list[_LaserPlan]:
    if args.config:
        with open(args.config, "rb") as f:
            data = tomllib.load(f)
        lasers = data.get("lasers", [])
        if not lasers:
            raise SystemExit(f"No [[lasers]] entries in {args.config}")
        plans: list[_LaserPlan] = []
        for i, entry in enumerate(lasers):
            try:
                plans.append(_LaserPlan(
                    name=entry["name"],
                    kind=entry["kind"],
                    port=entry["port"],
                    power_mw=float(entry.get("power_mw", 0.0)),
                    mock=bool(entry.get("mock", args.mock)),
                ))
            except KeyError as e:
                raise SystemExit(
                    f"Laser entry {i} in {args.config} missing key: {e}"
                ) from None
        return plans

    if not args.kind or not args.port:
        raise SystemExit(
            "Provide either --config FILE, or both --kind and --port. "
            "See --help."
        )
    return [_LaserPlan(
        name=args.name, kind=args.kind, port=args.port,
        power_mw=args.power, mock=args.mock,
    )]


def _print_status_table(lasers: list[Laser]) -> None:
    headers = ("name", "kind", "port", "ready", "output", "power_mw", "fault")
    rows = [headers]
    for laser in lasers:
        s = laser.get_status()
        rows.append((
            s.name, s.kind, s.port,
            "yes" if s.ready else "no",
            "on" if s.output_enabled else "off",
            f"{s.power_mw:.2f}",
            "" if s.fault is None else s.fault,
        ))
    widths = [max(len(str(r[c])) for r in rows) for c in range(len(headers))]
    for r in rows:
        print("  ".join(str(r[c]).ljust(widths[c]) for c in range(len(headers))))


def _arm_one(plan: _LaserPlan, key_timeout: float) -> Laser:
    laser = Laser(name=plan.name, kind=plan.kind, port=plan.port, mock=plan.mock)
    print(f"[{plan.name}] connecting on {plan.port} (kind={plan.kind}, mock={plan.mock})")
    laser.connect()
    if laser.requires_key:
        print(f"[{plan.name}] waiting for safety key (timeout {key_timeout:.0f}s) — turn the key now if needed...")
    laser.wait_ready(timeout=key_timeout)
    print(f"[{plan.name}] ready")
    laser.set_power(plan.power_mw)
    print(f"[{plan.name}] set_power {plan.power_mw:.2f} mW")
    laser.turn_on()
    print(f"[{plan.name}] turn_on (LD enabled, awaiting TTL)")
    return laser


def _stop_one(laser: Laser) -> None:
    try:
        laser.turn_off()
    finally:
        laser.disconnect()


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )

    plans = _plans_from_args(args)
    armed: list[Laser] = []
    failed_at: tuple[str, str] | None = None

    try:
        for plan in plans:
            try:
                armed.append(_arm_one(plan, args.key_timeout))
            except Exception as e:
                failed_at = (plan.name, f"arm: {e}")
                raise

        print()
        print("All lasers armed:")
        _print_status_table(armed)
        print()
        print(f"Holding for {args.hold_seconds:.1f}s. Drive your TTL lines now.")
        time.sleep(args.hold_seconds)

    except KeyboardInterrupt:
        print("\nInterrupted — stopping lasers...")
    except Exception as e:
        print(f"\nERROR: {e}")
        if failed_at is None:
            failed_at = ("?", str(e))
    finally:
        for laser in reversed(armed):
            try:
                _stop_one(laser)
                print(f"[{laser.name}] turn_off + disconnect ok")
            except Exception as e:
                print(f"[{laser.name}] STOP ERROR: {e}")

    if failed_at is not None:
        name, step = failed_at
        print(f"\nFAIL — laser {name!r} failed at {step}")
        return 1

    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
