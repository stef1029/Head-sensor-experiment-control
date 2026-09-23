r"""
RS-232 protocol helpers for CNI diode lasers.

Frame layout (host -> laser, 10 bytes total):

    [0x53] [0x0A] [channel] [cmd] [d1] [d2] [d3] [d4] [chk] [0x0D]
       |     |       |       |    \________ 4-byte payload
       |     |       |       \__ command (0x01 = write)
       |     |       \__ channel (0x00 = LD switch, 0x02 = LD power mW)
       |     \__ frame size (10)
       \__ start code

Checksum = sum(bytes[0:8]) & 0xFF.
Response checked by callers: bytes 2..4 == b"OK" on success, b"ERR" on rejection.
"""

from __future__ import annotations

from .base import LaserProtocolError


START_CODE = 0x53
FRAME_SIZE = 0x0A
TERMINATOR = 0x0D
CMD_WRITE = 0x01

CHANNEL_LD_SWITCH = 0x00
CHANNEL_LD_POWER_MW = 0x02

DATA_OFF = b"\x00\x00\x00\x00"
DATA_ON = b"\x00\x00\x00\x01"


def calculate_checksum(payload: bytes) -> int:
    """Sum bytes and return the low byte.

    Reference: head-sensor red_laser_control.py calculate_checksum.
    Used over the first 8 bytes of the frame (start..d4).
    """
    return sum(payload) & 0xFF


def build_frame(channel: int, data4: bytes, cmd: int = CMD_WRITE) -> bytes:
    """Build a 10-byte RS-232 frame.

    Args:
        channel: 0x00 (LD switch) or 0x02 (LD power mW).
        data4:   Exactly 4 bytes of payload (big-endian for power; 0/1 for switch).
        cmd:     0x01 = write (only command in use today).
    """
    if len(data4) != 4:
        raise ValueError(f"data4 must be exactly 4 bytes, got {len(data4)}")
    head = bytes([START_CODE, FRAME_SIZE, channel, cmd]) + data4
    chk = calculate_checksum(head)
    return head + bytes([chk, TERMINATOR])


def build_power_frame(power_mw: float) -> bytes:
    """Frame to set the LD power, in mW.

    Power is rounded to the nearest int and serialised as a 4-byte
    big-endian unsigned integer. The laser firmware handles range
    checking; we don't second-guess it here.
    """
    value = max(0, int(round(power_mw)))
    return build_frame(CHANNEL_LD_POWER_MW, value.to_bytes(4, "big"))


def build_on_frame() -> bytes:
    return build_frame(CHANNEL_LD_SWITCH, DATA_ON)


def build_off_frame() -> bytes:
    return build_frame(CHANNEL_LD_SWITCH, DATA_OFF)


def parse_response(response: bytes) -> bool:
    """Return True if the laser acknowledged the command.

    Raises ``LaserProtocolError`` on an explicit ERR response or a
    malformed reply. The caller has already done the read with a timeout
    and confirmed at least one byte arrived.
    """
    if not response or len(response) < 4:
        raise LaserProtocolError(
            f"Short response from laser: {response.hex() if response else 'empty'}"
        )
    if response[2:5] == b"ERR":
        raise LaserProtocolError(f"Laser rejected command. Response: {response.hex()}")
    if response[2:4] == b"OK":
        return True
    raise LaserProtocolError(
        f"Unrecognised response from laser: {response.hex()}"
    )
