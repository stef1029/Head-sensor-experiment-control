"""
Laser test script — supports both 473nm (Cobolt) and 635nm (red) lasers.

Uses the board registry to resolve COM ports automatically.
Can run a simple turn-on test or a full Arduino-driven stimulation sequence.
Edit the configuration section in main() to change parameters.
"""

import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts')))

import serial
import keyboard
from colorama import init, Fore, Style
from pycobolt import Cobolt06MLD
from red_laser_control import RedLaser
from laser_control import setup_arduino, read_arduino_output, wait_for_key
from utils.board_registry import BoardRegistry

init()
exit_key = 'del'

# Default path to board registry (relative to this file)
DEFAULT_REGISTRY = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'config', 'board_registry.json'))


# ------------------------------------------------------------------
# Simple turn-on test
# ------------------------------------------------------------------

def test_473nm(registry, board_name, power_mw):
    """Turn on the 473nm Cobolt laser at the given power and wait for DELETE to stop."""
    port = registry.find_board_port(board_name)
    print(Fore.CYAN + f"473nm laser '{board_name}' resolved to {port}" + Style.RESET_ALL)

    laser = Cobolt06MLD(port=port)
    try:
        laser.clear_fault()
        laser.constant_power(power=0)
        laser.turn_on()
        time.sleep(2)

        if "Waiting for key" in laser.get_state():
            if not wait_for_key(laser):
                print(Fore.YELLOW + "Key check interrupted" + Style.RESET_ALL)
                return

        laser.constant_power(power=power_mw)
        print(Fore.GREEN + f"Laser ON at {power_mw} mW — press DELETE to turn off" + Style.RESET_ALL)

        while not keyboard.is_pressed(exit_key):
            time.sleep(0.1)

        print(Fore.YELLOW + "\nDELETE pressed — shutting down" + Style.RESET_ALL)
    finally:
        laser.constant_power(power=0)
        laser.turn_off()
        laser.disconnect()
        print(Fore.GREEN + "Laser OFF and disconnected" + Style.RESET_ALL)


def test_red(registry, board_name, power_mw):
    """Turn on the 635nm red laser at the given power and wait for DELETE to stop."""
    port = registry.find_board_port(board_name)
    baudrate = registry.get_baudrate(board_name)
    print(Fore.CYAN + f"Red laser '{board_name}' resolved to {port}" + Style.RESET_ALL)

    laser = RedLaser(port=port, baudrate=baudrate)
    laser.connect()
    try:
        laser.turn_on()
        time.sleep(0.5)
        laser.set_power(power_mw)
        print(Fore.GREEN + f"Laser ON at {power_mw} mW — press DELETE to turn off" + Style.RESET_ALL)

        while not keyboard.is_pressed(exit_key):
            time.sleep(0.1)

        print(Fore.YELLOW + "\nDELETE pressed — shutting down" + Style.RESET_ALL)
    finally:
        laser.turn_off()
        time.sleep(0.5)
        laser.disconnect()
        print(Fore.GREEN + "Laser OFF and disconnected" + Style.RESET_ALL)


# ------------------------------------------------------------------
# Full stimulation test with Arduino
# ------------------------------------------------------------------

def run_stim_test(registry, laser_type, laser_board, arduino_board,
                  powers, stim_times, num_cycles, stim_delay,
                  pulse_freq, pulse_on_time):
    """Run a full Arduino-driven stimulation sequence."""
    laser_port = registry.find_board_port(laser_board)
    arduino_port = registry.find_board_port(arduino_board)
    print(Fore.GREEN + f"Laser '{laser_board}' -> {laser_port}" + Style.RESET_ALL)
    print(Fore.GREEN + f"Arduino '{arduino_board}' -> {arduino_port}" + Style.RESET_ALL)

    laser = None
    arduino = None

    try:
        print(Fore.CYAN + "=" * 70 + Style.RESET_ALL)
        print(Fore.CYAN + "LASER STIMULATION TEST" + Style.RESET_ALL)
        print(Fore.CYAN + "=" * 70 + Style.RESET_ALL)

        print(f"\n  Laser type: {laser_type}")
        print(f"  Power levels: {powers} mW")
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
        if laser_type == '473':
            laser = Cobolt06MLD(port=laser_port)
            laser.clear_fault()
            laser.constant_power(power=0)
            laser.turn_on()
            time.sleep(2)

            if "Waiting for key" in laser.get_state():
                if not wait_for_key(laser):
                    print(Fore.YELLOW + "Key check interrupted" + Style.RESET_ALL)
                    return False

            laser.modulation_mode(power=0)
            laser.digital_modulation(1)
            time.sleep(5)
        else:
            baudrate = registry.get_baudrate(laser_board)
            laser = RedLaser(port=laser_port, baudrate=baudrate)
            laser.connect()
            laser.turn_on()
            time.sleep(0.5)
            laser.set_power(powers[0])
            time.sleep(0.5)

        # Initialize Arduino
        arduino = setup_arduino(arduino_port, stim_times, num_cycles,
                                stim_delay, pulse_freq, pulse_on_time)

        # Run through power levels
        for power in powers:
            print(Fore.CYAN + f"\n{'=' * 70}" + Style.RESET_ALL)
            print(Fore.CYAN + f"Starting sequence at {power} mW" + Style.RESET_ALL)
            print(Fore.CYAN + f"{'=' * 70}" + Style.RESET_ALL)

            if laser_type == '473':
                laser.set_modulation_power(power)
            else:
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
        cleanup(laser, arduino, laser_type)


def cleanup(laser, arduino, laser_type='473'):
    """Safe cleanup of devices"""
    try:
        if arduino:
            arduino.write(b'e')
            time.sleep(0.1)
            arduino.close()
    except Exception:
        pass

    try:
        if laser:
            if laser_type == '473':
                laser.constant_power(power=0)
                laser.turn_off()
                laser.disconnect()
            else:
                laser.turn_off()
                time.sleep(0.5)
                laser.disconnect()
    except Exception:
        pass


def main():
    # ===== CONFIGURATION — edit these to change test parameters =====
    LASER_TYPE = '473'              # '473' (Cobolt) or 'red' (635nm)
    LASER_BOARD = '473_laser_1'     # Board registry name (e.g. '473_laser_1', '473_laser_2', '635nm_laser_1')
    POWER_MW = 5.0                  # Power in mW for simple turn-on test

    # Set to True to run full Arduino stimulation test instead of simple on/off
    RUN_STIM = False
    ARDUINO_BOARD = 'laser_pulse_board'
    POWERS_MW = [5.0]               # Power levels in mW (stim mode)
    STIM_TIMES_MS = [100000]        # Stimulation durations in ms
    NUM_CYCLES = 1                  # Number of cycles per power level
    STIM_DELAY_MS = 500             # Delay between stimulations in ms
    PULSE_FREQ = 0                  # Pulse frequency in Hz (0 for solid pulse)
    PULSE_ON_TIME_MS = 10           # Pulse on time in ms
    # ================================================================

    registry = BoardRegistry(DEFAULT_REGISTRY)

    try:
        if RUN_STIM:
            success = run_stim_test(
                registry=registry,
                laser_type=LASER_TYPE,
                laser_board=LASER_BOARD,
                arduino_board=ARDUINO_BOARD,
                powers=POWERS_MW,
                stim_times=STIM_TIMES_MS,
                num_cycles=NUM_CYCLES,
                stim_delay=STIM_DELAY_MS,
                pulse_freq=PULSE_FREQ,
                pulse_on_time=PULSE_ON_TIME_MS,
            )
            sys.exit(0 if success else 1)
        else:
            if LASER_TYPE == '473':
                test_473nm(registry, LASER_BOARD, POWER_MW)
            else:
                test_red(registry, LASER_BOARD, POWER_MW)
    except Exception as e:
        print(Fore.RED + f"\nTest failed: {e}" + Style.RESET_ALL)
        sys.exit(1)


if __name__ == "__main__":
    main()
