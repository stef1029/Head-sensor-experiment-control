# LaserLink

Unified laser control library. One `Laser` class, one API, dispatches to a per-vendor backend chosen by a `kind` code at init.

Supported kinds:

| Kind             | Hardware                          | Notes                                                  |
| ---------------- | --------------------------------- | ------------------------------------------------------ |
| `cni_laser`      | CNI diode laser, RS-232 (9600 8N1) | Raw protocol owned by this package; no upstream lib.   |
| `cobolt_06mld`   | Cobolt 06MLD (e.g. 473 nm blue)   | Wraps `pycobolt.Cobolt06MLD`; requires safety key.     |

LaserLink does not know about board registries, COM-port discovery, or rigs. The caller resolves the port string and passes it in.

## Installation

Inside the hex-behav workspace, this is a workspace member — `uv sync` from `hex_behav_control/` picks it up. Stand-alone:

```bash
pip install -e .
```

## Usage

```python
from LaserLink import Laser

laser = Laser(name="rig1_red", kind="cni_laser", port="COM26")

laser.connect()                  # open pyserial / pycobolt session
laser.wait_ready(timeout=30)     # NO-OP for red; blocks on Cobolt key + interlock
laser.set_power(10.0)            # mW
laser.turn_on()                  # enable LD output (TTL-gated downstream)

status = laser.get_status()      # LaserStatus dataclass
print(status)

laser.turn_off()
laser.disconnect()
```

`mock=True` skips all hardware:

```python
laser = Laser(name="dev", kind="cni_laser", port="COM_FAKE", mock=True)
laser.connect(); laser.wait_ready(); laser.set_power(5); laser.turn_on()
```

## CLI test script

`laserlink-test` (installed as a console script) runs the full lifecycle against one or more lasers:

```bash
# Single laser
laserlink-test --kind cni_laser --port COM26 --power 5 --hold-seconds 5
laserlink-test --kind cobolt_06mld --port COM27 --power 5 --hold-seconds 5

# Mock mode (no hardware)
laserlink-test --kind cni_laser --port COM_FAKE --mock --power 10 --hold-seconds 1

# Multiple lasers from a TOML config
laserlink-test --config lasers.toml
```

Equivalent: `python -m LaserLink.test_lasers ...`.

`lasers.toml` example:

```toml
[[lasers]]
name = "rig1_red"
kind = "cni_laser"
port = "COM26"
power_mw = 10.0

[[lasers]]
name = "rig2_blue"
kind = "cobolt_06mld"
port = "COM27"
power_mw = 5.0
```

## Adding a new laser kind

1. Add `my_laser.py` with a `_MyLaserBackend` class implementing the `_LaserBackend` Protocol from `base.py`.
2. Register it in `laser.py`'s `_BACKENDS` dict: `"my_kind": _MyLaserBackend`.
3. Add tests under `tests/`. Wire the new kind into `_MockBackend` if it needs vendor-specific mock behaviour (the default mock works for any kind).

## Lifecycle contract

The unified API hides vendor-specific quirks. Backends must satisfy:

| Method                | Behaviour                                                            |
| --------------------- | -------------------------------------------------------------------- |
| `connect()`           | Open comms. After return: laser is reachable, no emission yet.       |
| `wait_ready(timeout)` | Block until safe to enable emission (key check, interlocks, faults). |
| `set_power(mw)`       | Set the active power in mW.                                          |
| `turn_on()`           | Enable emission-ready state (TTL-gated downstream).                  |
| `turn_off()`          | Disable emission. Idempotent.                                        |
| `get_status()`        | Return `LaserStatus` snapshot. Should never raise.                   |
| `disconnect()`        | Close comms. Should leave hardware in a non-emitting state.          |

Errors raise `LaserError` or one of its subclasses (`LaserConnectionError`, `LaserProtocolError`, `LaserTimeoutError`, `LaserNotReadyError`).
