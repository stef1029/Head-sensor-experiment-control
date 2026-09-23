"""
Interactive probe for the blue CNI laser on COM31.

Goal: send hand-built RS-232 frames at the blue laser and see what comes
back, without needing the vendor .exe in the loop. Starts from the red
635nm protocol's frame builder as a baseline (the blue is a cousin) and
lets you diverge from there as you learn what's different.

Run from the LaserLink/ directory:

    uv run python tests/blue_laser_hacking/probe.py

REPL commands (type `help` once inside):
    on / off            red-protocol LD enable / disable frame
    pow <mw>            red-protocol power frame, e.g. `pow 50`
    raw <hex>           send arbitrary bytes verbatim
    cs <hex>            send hex with checksum + 0x0d auto-appended
    show <on|off|pow N> print the red-protocol frame without sending
    listen <secs>       just read for N seconds, no transmit
    drain               read whatever's in the input buffer right now
    wait <secs>         pause N seconds before next prompt
    quit                close port and exit
"""

from __future__ import annotations

import time

import serial

from LaserLink.cni_laser_protocol import (
    build_off_frame,
    build_on_frame,
    build_power_frame,
    calculate_checksum,
)


PORT = "COM31"
BAUD = 9600
READ_TIMEOUT_S = 1.0
POST_TX_WAIT_S = 0.3


def hexd(b: bytes) -> str:
    return " ".join(f"{x:02x}" for x in b)


def parse_hex(arg: str) -> bytes:
    cleaned = arg.replace(" ", "").replace(",", "").replace("0x", "")
    if len(cleaned) % 2:
        raise ValueError("hex string must have even number of nibbles")
    return bytes.fromhex(cleaned)


def send(ser: serial.Serial, frame: bytes,
         post_wait: float = POST_TX_WAIT_S) -> bytes:
    """Write frame, then collect anything that comes back within post_wait."""
    print(f"  TX ({len(frame):2d}): {hexd(frame)}")
    ser.reset_input_buffer()
    ser.write(frame)
    ser.flush()
    deadline = time.monotonic() + post_wait
    buf = bytearray()
    while time.monotonic() < deadline:
        if ser.in_waiting:
            buf.extend(ser.read(ser.in_waiting))
        else:
            time.sleep(0.01)
    if ser.in_waiting:
        buf.extend(ser.read(ser.in_waiting))
    if buf:
        print(f"  RX ({len(buf):2d}): {hexd(bytes(buf))}")
        ascii_view = "".join(chr(c) if 32 <= c < 127 else "." for c in buf)
        print(f"  RX ascii: {ascii_view}")
    else:
        print("  RX  -- (no response)")
    return bytes(buf)


HELP = """\
on                send red-protocol LD enable frame
off               send red-protocol LD disable frame
pow <mw>          send red-protocol power frame, e.g. `pow 50`
raw <hex>         send arbitrary bytes verbatim
                  e.g. `raw 53 0a 00 01 00 00 00 01 5e 0d`
cs <hex>          send hex with checksum + 0x0d auto-appended
                  e.g. `cs 53 0a 00 01 00 00 00 01`
show on|off|pow N print the red-protocol frame without sending
listen <secs>     just read for N seconds, no transmit
drain             read whatever's in the input buffer right now
wait <secs>       pause N seconds before next prompt
help              show this
quit              close port and exit
"""


def show_frame(arg: str) -> None:
    arg = arg.strip().lower()
    if arg == "on":
        f = build_on_frame()
    elif arg == "off":
        f = build_off_frame()
    elif arg.startswith("pow"):
        _, _, mw_s = arg.partition(" ")
        f = build_power_frame(float(mw_s))
    else:
        print(f"  show: unknown {arg!r}. Try `show on`, `show off`, `show pow 50`.")
        return
    print(f"  {arg}: {hexd(f)}")


def repl(ser: serial.Serial) -> None:
    print(HELP)
    print(f"connected to {ser.port} at {ser.baudrate} 8N1\n")
    while True:
        try:
            line = input("blue> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not line:
            continue
        cmd, _, arg = line.partition(" ")
        cmd = cmd.lower()
        try:
            if cmd in ("quit", "exit", "q"):
                return
            elif cmd in ("help", "?"):
                print(HELP)
            elif cmd == "on":
                send(ser, build_on_frame())
            elif cmd == "off":
                send(ser, build_off_frame())
            elif cmd == "pow":
                send(ser, build_power_frame(float(arg)))
            elif cmd == "raw":
                send(ser, parse_hex(arg))
            elif cmd == "cs":
                head = parse_hex(arg)
                frame = head + bytes([calculate_checksum(head), 0x0D])
                send(ser, frame)
            elif cmd == "show":
                show_frame(arg)
            elif cmd == "listen":
                secs = float(arg) if arg else 1.0
                deadline = time.monotonic() + secs
                got_any = False
                print(f"  listening {secs:.1f}s ...")
                while time.monotonic() < deadline:
                    if ser.in_waiting:
                        chunk = ser.read(ser.in_waiting)
                        got_any = True
                        print(f"  RX +{len(chunk):2d}: {hexd(chunk)}")
                    else:
                        time.sleep(0.02)
                if not got_any:
                    print("  (silence)")
            elif cmd == "drain":
                n = ser.in_waiting
                if n:
                    chunk = ser.read(n)
                    print(f"  RX ({len(chunk):2d}): {hexd(chunk)}")
                else:
                    print("  (buffer empty)")
            elif cmd == "wait":
                time.sleep(float(arg) if arg else 1.0)
            else:
                print(f"  unknown command {cmd!r}. Type `help`.")
        except Exception as e:  # noqa: BLE001
            print(f"  ! {type(e).__name__}: {e}")


def main() -> int:
    print(f"opening {PORT} at {BAUD} 8N1, timeout={READ_TIMEOUT_S}s ...")
    try:
        ser = serial.Serial(
            port=PORT, baudrate=BAUD, bytesize=8,
            parity=serial.PARITY_NONE, stopbits=1,
            timeout=READ_TIMEOUT_S,
        )
    except serial.SerialException as e:
        print(f"failed to open {PORT}: {e}")
        return 1

    try:
        time.sleep(0.5)  # let the chip settle after open
        n = ser.in_waiting
        if n:
            print(f"flushed leftover bytes: {hexd(ser.read(n))}")
        repl(ser)
    finally:
        try:
            ser.close()
        except Exception:  # noqa: BLE001
            pass
        print("port closed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
