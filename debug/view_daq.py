#!/usr/bin/env python3
"""
Plot selected ArduinoDAQ channels from an HDF5 file.

Supports:
1. Command-line usage with an explicit file path
2. Fallback usage with a default internal path

If the selected file is not a valid ArduinoDAQ HDF5 file, a Windows popup
error message is shown.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

import h5py
import matplotlib.pyplot as plt
import numpy as np


DEFAULT_H5_PATH = Path(r"E:\test_output\260318_165903_test\260318_165903_test-ArduinoDAQ.h5")

DEFAULT_CHANNEL_NAMES = [
    "CAMERA_SYNC",
    "HEADSENSOR_SYNC",
    "LASER_SYNC",
    "BODYSENSOR_SYNC",
]


def show_error_popup(title: str, message: str) -> None:
    """
    Show a modal error popup.

    Parameters
    ----------
    title
        Popup window title.
    message
        Popup message text.
    """
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    messagebox.showerror(title, message, parent=root)
    root.destroy()


def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments.

    Returns
    -------
    argparse.Namespace
        Parsed command-line arguments.
    """
    parser = argparse.ArgumentParser(
        description="Plot selected channels from an ArduinoDAQ HDF5 file."
    )
    parser.add_argument(
        "h5_path",
        nargs="?",
        help="Path to the ArduinoDAQ .h5 file. If omitted, DEFAULT_H5_PATH is used.",
    )
    parser.add_argument(
        "--channels",
        nargs="+",
        default=DEFAULT_CHANNEL_NAMES,
        help="Channel names to plot.",
    )
    return parser.parse_args()


def resolve_h5_path(cli_path: str | None) -> Path:
    """
    Resolve the HDF5 file path.

    Parameters
    ----------
    cli_path
        File path passed on the command line, or None.

    Returns
    -------
    Path
        Resolved path to the HDF5 file.

    Raises
    ------
    FileNotFoundError
        If the file does not exist.
    """
    path = Path(cli_path).expanduser() if cli_path else DEFAULT_H5_PATH

    if not path.exists():
        raise FileNotFoundError(f"File does not exist:\n{path}")

    if not path.is_file():
        raise FileNotFoundError(f"Path is not a file:\n{path}")

    return path


def validate_arduino_daq_file(h5_file: h5py.File, required_channels: list[str]) -> None:
    """
    Validate that the HDF5 file looks like an ArduinoDAQ file with the required channels.

    Parameters
    ----------
    h5_file
        Open HDF5 file handle.
    required_channels
        List of channel names that must exist under channel_data.

    Raises
    ------
    ValueError
        If the file is missing required datasets/groups/channels.
    """
    missing_top_level = [name for name in ("timestamps", "channel_data") if name not in h5_file]
    if missing_top_level:
        raise ValueError(
            "This file is not a valid ArduinoDAQ HDF5 file.\n\n"
            f"Missing required item(s): {', '.join(missing_top_level)}"
        )

    channel_group = h5_file["channel_data"]
    missing_channels = [ch for ch in required_channels if ch not in channel_group]
    if missing_channels:
        raise ValueError(
            "This file does not contain the required ArduinoDAQ channels.\n\n"
            f"Missing channel(s): {', '.join(missing_channels)}"
        )


def plot_multiple_channels(arduino_daq_h5_path: Path, channel_names: list[str]) -> None:
    """
    Plot multiple channels from the ArduinoDAQ HDF5 file as separate subplots.

    Parameters
    ----------
    arduino_daq_h5_path
        Path to the ArduinoDAQ HDF5 file.
    channel_names
        Channel names to plot.
    """
    with h5py.File(arduino_daq_h5_path, "r") as daq_h5:
        validate_arduino_daq_file(daq_h5, channel_names)

        daq_timestamps = np.asarray(daq_h5["timestamps"])

        fig, axes = plt.subplots(
            len(channel_names),
            1,
            figsize=(12, 3 * len(channel_names)),
            squeeze=False,
        )
        axes = axes.flatten()

        for ax, channel in zip(axes, channel_names):
            channel_data = np.asarray(daq_h5["channel_data"][channel])
            ax.plot(daq_timestamps, channel_data, label=channel)
            ax.set_ylabel("Signal")
            ax.legend(loc="upper right")

        axes[-1].set_xlabel("Time (s)")
        fig.suptitle(f"ArduinoDAQ Signals\n{arduino_daq_h5_path.name}")
        fig.tight_layout(rect=(0, 0, 1, 0.96))
        plt.show()


def main() -> int:
    """
    Script entry point.

    Returns
    -------
    int
        Exit code.
    """
    args = parse_args()

    try:
        h5_path = resolve_h5_path(args.h5_path)
        plot_multiple_channels(h5_path, args.channels)
        return 0

    except Exception as exc:
        message = str(exc)

        # Show a popup for file-format / wrong-file problems as requested
        show_error_popup("Wrong file", message)

        # Also print to stderr for debugging from terminal
        print(f"Error: {message}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())