"""
Laser test script (LaserLink-backed).

Works for any laser in the board registry — CNI (cni_laser) or Cobolt
(cobolt_06mld) — because the protocol is resolved from each board's
"kind" field. Can run a simple turn-on test or a full Arduino-driven
stimulation sequence. Edit the configuration section in main().
"""

import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts')))

import keyboard
from colorama import init, Fore, Style

from LaserLink import Laser
from laser_stim import setup_arduino
from utils.board_registry import BoardRegistry

init()
exit_key = 'del'

# Default path to board registry (relative to this file)
DEFAULT_REGISTRY = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'config', 'board_registry.json'))


def build_laser(registry, board_name, kind_override=None):
    """Resolve port/kind/baud from the registry and build a LaserLink Laser."""
    port = registry.find_board_port(board_name)
    kind = kind_override or registry.get_kind(board_name)
    if not kind:
        raise RuntimeError(
            f"No laser kind for board '{board_name}'. Add a \"kind\" field to "
            f"board_registry.json, or pass kind_override."
        )
    vendor_kwargs = {}
    if kind == "cni_laser":
        vendor_kwargs["baudrate"] = registry.get_baudrate(board_name)
    print(Fore.CYAN + f"Laser '{board_name}' -> {port} (kind={kind})" + Style.RESET_ALL)
    return Laser(name=board_name, kind=kind, port=port, **vendor_kwargs)


# ------------------------------------------------------------------
# Simple turn-on test
# ------------------------------------------------------------------

def test_simple(registry, board_name, power_mw, kind_override=None):
    """Turn the laser on at the given power and wait for DELETE to stop."""
    laser = build_laser(registry, board_name, kind_override)
    laser.connect()
    try:
        if laser.requires_key:
            print(Fore.BLUE + "Turn the laser safety key on the box now..." + Style.RESET_ALL)
        laser.wait_ready(timeout=30.0)
        laser.set_power(power_mw)
        laser.turn_on()
        print(Fore.GREEN + f"Laser ON at {power_mw} mW — press DELETE to turn off" + Style.RESET_ALL)

        while not keyboard.is_pressed(exit_key):
            time.sleep(0.1)

        print(Fore.YELLOW + "\nDELETE pressed — shutting down" + Style.RESET_ALL)
    finally:
        laser.turn_off()
        laser.disconnect()
        print(Fore.GREEN + "Laser OFF and disconnected" + Style.RESET_ALL)


# ------------------------------------------------------------------
# Full stimulation test with Arduino
# ------------------------------------------------------------------

def run_stim_test(registry, laser_board, arduino_board, powers, stim_times,
                  num_cycles, stim_delay, pulse_freq, pulse_on_time, kind_override=None):
    """Run a full Arduino-driven stimulation sequence."""
    arduino_port = registry.find_board_port(arduino_board)
    print(Fore.GREEN + f"Arduino '{arduino_board}' -> {arduino_port}" + Style.RESET_ALL)

    laser = None
    arduino = None

    try:
        print(Fore.CYAN + "=" * 70 + Style.RESET_ALL)
        print(Fore.CYAN + "LASER STIMULATION TEST" + Style.RESET_ALL)
        print(Fore.CYAN + "=" * 70 + Style.RESET_ALL)

        print(f"\n  Power levels: {powers} mW")
        print(f"  Stim times: {stim_times} ms")
        print(f"  Cycles per power: {num_cycles}")
        print(f"  Delay between stims: {stim_delay} ms")
        if pulse_freq > 0:
            print(f"  Pulse frequency: {pulse_freq} Hz")
            print(f"  Pulse on time: {pulse_on_time} ms")
        else:
            print(f"  Mode: Solid pulse")
        print(f"\n  Press DELETE at any time to stop\n")

        # Initialize laser
        laser = build_laser(registry, laser_board, kind_override)
        laser.connect()
        if laser.requires_key:
            print(Fore.BLUE + "Turn the laser safety key on the box now..." + Style.RESET_ALL)
        laser.wait_ready(timeout=30.0)
        laser.set_power(powers[0])
        laser.turn_on()
        time.sleep(0.5)

        # Initialize Arduino
        arduino = setup_arduino(arduino_port, stim_times, num_cycles,
                                stim_delay, pulse_freq, pulse_on_time)

        # Run through power levels
        for power in powers:
            print(Fore.CYAN + f"\n{'=' * 70}" + Style.RESET_ALL)
            print(Fore.CYAN + f"Starting sequence at {power} mW" + Style.RESET_ALL)
            print(Fore.CYAN + f"{'=' * 70}" + Style.RESET_ALL)

            laser.set_power(power)
            time.sleep(1)

            arduino.write(b"s")

            last_check_time = 0
            check_interval = 0.3

            while True:
                current_time = time.time()

                if keyboard.is_pressed(exit_key):
                    print(Fore.YELLOW + "\nDELETE pressed — stopping" + Style.RESET_ALL)
                    raise KeyboardInterrupt("User stopped test")

                if current_time - last_check_time >= check_interval:
                    last_check_time = current_time
                    if arduino.in_waiting:
                        try:
                            response = arduino.readline().decode().strip()
                            print(Fore.YELLOW + "Arduino:" + Style.RESET_ALL + f" {response}")
                            if response == 'e':
                                print(Fore.GREEN + f"Completed {power} mW" + Style.RESET_ALL)
                                break
                        except UnicodeDecodeError:
                            pass

                time.sleep(0.1)

        print(Fore.CYAN + "\n" + "=" * 70 + Style.RESET_ALL)
        print(Fore.GREEN + "All sequences completed!" + Style.RESET_ALL)
        print(Fore.CYAN + "=" * 70 + Style.RESET_ALL)
        return True

    except KeyboardInterrupt:
        print(Fore.YELLOW + "\nTest interrupted" + Style.RESET_ALL)
        return False

    except Exception as e:
        print(Fore.RED + f"\nError: {e}" + Style.RESET_ALL)
        raise

    finally:
        cleanup(laser, arduino)


def cleanup(laser, arduino):
    """Safe cleanup of devices."""
    try:
        if arduino:
            arduino.write(b'e')
            time.sleep(0.1)
            arduino.close()
    except Exception:
        pass

    try:
        if laser:
            laser.turn_off()
            laser.disconnect()
    except Exception:
        pass


def main():
    # ===== CONFIGURATION — edit these to change test parameters =====
    LASER_BOARD = 'CNI_473_laser_2'  # Board registry name (CNI or Cobolt — protocol from registry "kind")
    LASER_KIND = None                # Override registry kind, e.g. 'cni_laser' / 'cobolt_06mld'; None = use registry
    POWER_MW = 10.0                  # Power in mW for simple turn-on test
    # Set to True to run full Arduino stimulation test instead of simple on/off
    RUN_STIM = True
    ARDUINO_BOARD = 'laser_pulse_board'
    POWERS_MW = [10.0]               # Power levels in mW (stim mode)
    STIM_TIMES_MS = [100000]         # Stimulation durations in ms
    NUM_CYCLES = 1                   # Number of cycles per power level
    STIM_DELAY_MS = 500              # Delay between stimulations in ms
    PULSE_FREQ = 0                   # Pulse frequency in Hz (0 for solid pulse)
    PULSE_ON_TIME_MS = 10            # Pulse on time in ms
    # ================================================================

    registry = BoardRegistry(DEFAULT_REGISTRY)
    try:
        if RUN_STIM:
            success = run_stim_test(
                registry=registry,
                laser_board=LASER_BOARD,
                arduino_board=ARDUINO_BOARD,
                powers=POWERS_MW,
                stim_times=STIM_TIMES_MS,
                num_cycles=NUM_CYCLES,
                stim_delay=STIM_DELAY_MS,
                pulse_freq=PULSE_FREQ,
                pulse_on_time=PULSE_ON_TIME_MS,
                kind_override=LASER_KIND,
            )
            sys.exit(0 if success else 1)
        else:
            test_simple(registry, LASER_BOARD, POWER_MW, kind_override=LASER_KIND)
    except Exception as e:
        print(Fore.RED + f"\nTest failed: {e}" + Style.RESET_ALL)
        sys.exit(1)


if __name__ == "__main__":
    main()
