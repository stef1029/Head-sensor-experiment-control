#!/usr/bin/env python3
"""
Install or uninstall a Windows Explorer context-menu entry for .h5 files.

This installer requires the user to specify:
- the Python interpreter path
- the ArduinoDAQ viewer script path

On install, it:
1. validates the supplied paths
2. writes a CMD runner script
3. registers a right-click menu entry for .h5 files

On uninstall, it:
1. removes the registry entries
2. optionally removes the generated CMD runner script

Usage
-----
Install:
    python install_h5_context_menu.py install ^
        --python "C:\\Path\\To\\python.exe" ^
        --viewer "C:\\Path\\To\\plot_arduino_daq_channels.py"

Uninstall:
    python install_h5_context_menu.py uninstall

Optional:
    --runner "C:\\Path\\To\\run_plot_arduino_daq_channels.cmd"

If --runner is not supplied during install, the runner is created in the same
directory as this installer script.
"""

from __future__ import annotations

import argparse
import sys
import winreg
from pathlib import Path


MENU_KEY_PATH = r"Software\Classes\SystemFileAssociations\.h5\shell\ViewArduinoDAQChannels"
COMMAND_KEY_PATH = MENU_KEY_PATH + r"\command"

MENU_TEXT = "Plot ArduinoDAQ channels"
ICON_VALUE = r"C:\Windows\System32\shell32.dll,70"
DEFAULT_RUNNER_NAME = "run_plot_arduino_daq_channels.cmd"


def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments.

    Returns
    -------
    argparse.Namespace
        Parsed CLI arguments.
    """
    parser = argparse.ArgumentParser(
        description="Install or uninstall an Explorer right-click menu entry for .h5 files."
    )
    parser.add_argument(
        "action",
        choices=["install", "uninstall"],
        help="Whether to install or uninstall the context-menu entry.",
    )
    parser.add_argument(
        "--python",
        dest="python_path",
        help="Full path to python.exe. Required for install.",
    )
    parser.add_argument(
        "--viewer",
        dest="viewer_path",
        help="Full path to the ArduinoDAQ viewer Python script. Required for install.",
    )
    parser.add_argument(
        "--runner",
        dest="runner_path",
        help=(
            "Full path for the generated CMD runner script. "
            "If omitted, it will be created next to this installer."
        ),
    )
    parser.add_argument(
        "--remove-runner",
        action="store_true",
        help="When uninstalling, also delete the generated CMD runner if it exists.",
    )
    return parser.parse_args()


def validate_file_exists(path: Path, description: str) -> Path:
    """
    Validate that a path exists and is a file.

    Parameters
    ----------
    path
        Path to validate.
    description
        Human-readable description for error messages.

    Returns
    -------
    Path
        Resolved path.

    Raises
    ------
    FileNotFoundError
        If the path does not exist.
    ValueError
        If the path exists but is not a file.
    """
    resolved = path.expanduser().resolve()

    if not resolved.exists():
        raise FileNotFoundError(f"{description} not found: {resolved}")

    if not resolved.is_file():
        raise ValueError(f"{description} is not a file: {resolved}")

    return resolved


def choose_runner_path(runner_arg: str | None) -> Path:
    """
    Determine where to write the CMD runner script.

    Parameters
    ----------
    runner_arg
        Optional user-supplied runner path.

    Returns
    -------
    Path
        Resolved runner path.
    """
    if runner_arg:
        return Path(runner_arg).expanduser().resolve()

    return (Path(__file__).resolve().parent / DEFAULT_RUNNER_NAME).resolve()


def write_runner_script(runner_path: Path, python_path: Path, viewer_path: Path) -> None:
    """
    Write the CMD runner script that Explorer will call.

    Parameters
    ----------
    runner_path
        Output path for the CMD runner.
    python_path
        Full path to python.exe.
    viewer_path
        Full path to the ArduinoDAQ viewer script.
    """
    runner_contents = f"""@echo off
setlocal

set "PYTHON_EXE={python_path}"
set "SCRIPT_PATH={viewer_path}"

if "%~1"=="" (
    "%PYTHON_EXE%" "%SCRIPT_PATH%"
) else (
    "%PYTHON_EXE%" "%SCRIPT_PATH%" "%~1"
)

endlocal
"""

    runner_path.parent.mkdir(parents=True, exist_ok=True)
    runner_path.write_text(runner_contents, encoding="utf-8", newline="\r\n")


def set_reg_string(root: int, subkey: str, name: str | None, value: str) -> None:
    """
    Create or open a registry key and set a string value.

    Parameters
    ----------
    root
        Registry root.
    subkey
        Registry subkey path.
    name
        Value name, or None / empty string for the default value.
    value
        String value to set.
    """
    with winreg.CreateKey(root, subkey) as key:
        winreg.SetValueEx(key, name or "", 0, winreg.REG_SZ, value)


def delete_tree(root: int, subkey: str) -> None:
    """
    Recursively delete a registry subtree if it exists.

    Parameters
    ----------
    root
        Registry root.
    subkey
        Registry subkey path.
    """
    try:
        with winreg.OpenKey(root, subkey, 0, winreg.KEY_READ | winreg.KEY_WRITE) as key:
            while True:
                try:
                    child_name = winreg.EnumKey(key, 0)
                    delete_tree(root, f"{subkey}\\{child_name}")
                except OSError:
                    break
    except FileNotFoundError:
        return

    winreg.DeleteKey(root, subkey)


def install_context_menu(runner_path: Path) -> None:
    """
    Install the Explorer context-menu entry.

    Parameters
    ----------
    runner_path
        Full path to the CMD runner script.
    """
    command = f'"{runner_path}" "%1"'

    set_reg_string(winreg.HKEY_CURRENT_USER, MENU_KEY_PATH, None, MENU_TEXT)
    set_reg_string(winreg.HKEY_CURRENT_USER, MENU_KEY_PATH, "Icon", ICON_VALUE)
    set_reg_string(winreg.HKEY_CURRENT_USER, COMMAND_KEY_PATH, None, command)


def uninstall_context_menu() -> None:
    """
    Remove the Explorer context-menu entry.
    """
    delete_tree(winreg.HKEY_CURRENT_USER, COMMAND_KEY_PATH)
    delete_tree(winreg.HKEY_CURRENT_USER, MENU_KEY_PATH)


def install(python_path_str: str | None, viewer_path_str: str | None, runner_path_str: str | None) -> None:
    """
    Perform installation.

    Parameters
    ----------
    python_path_str
        String path to python.exe.
    viewer_path_str
        String path to the viewer script.
    runner_path_str
        Optional path where the CMD runner should be written.

    Raises
    ------
    ValueError
        If required arguments are missing.
    """
    if not python_path_str:
        raise ValueError("You must specify --python with the full path to python.exe.")

    if not viewer_path_str:
        raise ValueError("You must specify --viewer with the full path to the ArduinoDAQ viewer script.")

    python_path = validate_file_exists(Path(python_path_str), "Python executable")
    viewer_path = validate_file_exists(Path(viewer_path_str), "Viewer script")
    runner_path = choose_runner_path(runner_path_str)

    write_runner_script(runner_path, python_path, viewer_path)
    install_context_menu(runner_path)

    print("Installed context-menu entry successfully.")
    print(f"Menu text   : {MENU_TEXT}")
    print(f"Python path : {python_path}")
    print(f"Viewer path : {viewer_path}")
    print(f"Runner path : {runner_path}")
    print("Applies to  : .h5 files")


def uninstall(runner_path_str: str | None, remove_runner: bool) -> None:
    """
    Perform uninstallation.

    Parameters
    ----------
    runner_path_str
        Optional runner path.
    remove_runner
        Whether to delete the runner script file.
    """
    uninstall_context_menu()
    print("Removed context-menu registry entries.")

    if remove_runner:
        runner_path = choose_runner_path(runner_path_str)
        if runner_path.exists():
            runner_path.unlink()
            print(f"Deleted runner script: {runner_path}")
        else:
            print(f"Runner script not found, nothing to delete: {runner_path}")


def main() -> int:
    """
    Entry point.

    Returns
    -------
    int
        Exit code.
    """
    args = parse_args()

    try:
        if args.action == "install":
            install(args.python_path, args.viewer_path, args.runner_path)
        else:
            uninstall(args.runner_path, args.remove_runner)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())