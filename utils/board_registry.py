#!/usr/bin/env python3
"""
Board Registry Library

Provides functions to look up board connection info by human-readable name
and resolve the current COM port for a registered board.

The registry JSON path is loaded from the project config JSON
(key: "BOARD_REGISTRY"), or can be specified directly.

Usage:
    from utils.board_registry import BoardRegistry

    registry = BoardRegistry("path/to/board_registry.json")
    port = registry.find_board_port("head_imu")

    # Or with the project config:
    registry = BoardRegistry.from_config("path/to/head_sensor_config.json")
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from serial.tools import list_ports


@dataclass
class BoardInfo:
    """Information about a registered board."""
    name: str
    description: str
    vid: Optional[int]
    pid: Optional[int]
    serial_number: Optional[str]
    baudrate: int


class BoardNotFoundError(RuntimeError):
    """Raised when a board cannot be found in the registry or on the system."""


class BoardRegistry:
    """
    Manages a registry of known boards and provides methods to find them.
    """

    def __init__(self, registry_path: Path | str):
        self.registry_path = Path(registry_path)
        self._boards: dict[str, BoardInfo] = {}
        self._load_registry()

    @classmethod
    def from_config(cls, config_path: Path | str) -> "BoardRegistry":
        """
        Create a BoardRegistry using the path stored in the project config JSON.

        The config JSON must contain a "BOARD_REGISTRY" key pointing to the
        board_registry.json file.
        """
        with open(config_path, "r") as f:
            config = json.load(f)
        registry_path = config.get("BOARD_REGISTRY")
        if not registry_path:
            raise FileNotFoundError(
                f"Config '{config_path}' does not contain a 'BOARD_REGISTRY' key."
            )
        return cls(registry_path)

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def _load_registry(self) -> None:
        """Load the board registry from the JSON file."""
        if not self.registry_path.exists():
            raise FileNotFoundError(f"Board registry not found: {self.registry_path}")

        with open(self.registry_path, "r") as f:
            data = json.load(f)

        self._boards.clear()
        for name, info in data.get("boards", {}).items():
            vid_raw = info.get("vid")
            pid_raw = info.get("pid")

            if vid_raw is None or vid_raw == "null":
                vid = None
            elif isinstance(vid_raw, str):
                vid = int(vid_raw, 16)
            else:
                vid = vid_raw

            if pid_raw is None or pid_raw == "null":
                pid = None
            elif isinstance(pid_raw, str):
                pid = int(pid_raw, 16)
            else:
                pid = pid_raw

            self._boards[name] = BoardInfo(
                name=name,
                description=info.get("description", ""),
                vid=vid,
                pid=pid,
                serial_number=info.get("serial_number"),
                baudrate=info.get("baudrate", 115200),
            )

    def reload(self) -> None:
        """Reload the registry from disk."""
        self._load_registry()

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def list_boards(self) -> list[str]:
        """Return a list of all registered board names."""
        return list(self._boards.keys())

    def get_board_info(self, name: str) -> BoardInfo:
        """
        Get information about a registered board.

        Raises:
            BoardNotFoundError: If the board name is not in the registry.
        """
        if name not in self._boards:
            available = ", ".join(self._boards.keys()) or "(none)"
            raise BoardNotFoundError(
                f"Board '{name}' not found in registry. Available: {available}"
            )
        return self._boards[name]

    def find_board_port(self, name: str) -> str:
        """
        Find the current COM port for a registered board.

        Returns:
            COM port string (e.g. "COM3").

        Raises:
            BoardNotFoundError: If the board is not connected or not in registry.
        """
        info = self.get_board_info(name)

        for port in list_ports.comports():
            vid_match = info.vid is None or port.vid == info.vid
            pid_match = info.pid is None or port.pid == info.pid

            if vid_match and pid_match:
                if info.serial_number is None or port.serial_number == info.serial_number:
                    return port.device

        vid_str = hex(info.vid) if info.vid is not None else "None"
        pid_str = hex(info.pid) if info.pid is not None else "None"
        raise BoardNotFoundError(
            f"Board '{name}' (VID={vid_str}, PID={pid_str}, "
            f"serial={info.serial_number!r}) not found on any COM port."
        )

    def get_baudrate(self, name: str) -> int:
        """Return the configured default baud rate for a board."""
        return self.get_board_info(name).baudrate


def main():
    """List all currently connected USB serial devices and their identifiers."""
    from colorama import Fore, Style, init
    init()

    ports = list_ports.comports()
    if not ports:
        print("No serial devices found.")
        return

    print(f"\n  {len(ports)} device(s) found. Copy any entry below into board_registry.json:\n")

    for p in sorted(ports, key=lambda x: x.device):
        vid_str = f'"0x{p.vid:04x}"' if p.vid is not None else "null"
        pid_str = f'"0x{p.pid:04x}"' if p.pid is not None else "null"
        sn_str = f'"{p.serial_number}"' if p.serial_number else "null"

        print(Fore.CYAN + f"        \"{p.device}_RENAME_ME\"" + Style.RESET_ALL + ": {")
        print(f'            "description": "{p.description}",')
        print(f'            "vid": {vid_str},')
        print(f'            "pid": {pid_str},')
        print(f'            "serial_number": {sn_str},')
        print(f'            "baudrate": 115200')
        print("        },\n")


if __name__ == "__main__":
    main()
