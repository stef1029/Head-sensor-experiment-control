"""
Integrated test for red laser + Arduino stimulation board.
Tests the complete laser stimulation system as used in the main experiment.

Default COM ports are taken from start.py:
- Laser (red 635nm): COM20
- Arduino stim board: COM21
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from red_laser_control import RedLaser, setup_arduino, read_arduino_output
import serial
import time
import keyboard
from colorama import init, Fore, Style

init()
exit_key = 'del'


def run_integrated_test(laser_port, arduino_port, powers, stim_times, num_cycles, stim_delay, pulse_freq, pulse_on_time):
    """
    Run integrated test of laser + Arduino system

    Args:
        laser_port: COM port for red laser
        arduino_port: COM port for Arduino stim board
        powers: List of laser powers in mW
        stim_times: List of stimulation durations in ms
        num_cycles: Number of cycles per power level
        stim_delay: Delay between stimulations in ms
        pulse_freq: Pulse frequency in Hz (0 for solid pulse)
        pulse_on_time: Pulse on time in ms
    """
    laser = None
    arduino = None

    try:
        print(Fore.CYAN + "=" * 70 + Style.RESET_ALL)
        print(Fore.CYAN + "INTEGRATED LASER STIMULATION TEST" + Style.RESET_ALL)
        print(Fore.CYAN + "=" * 70 + Style.RESET_ALL)

        print(f"\nTest Configuration:")
        print(f"  Laser Port: {laser_port}")
        print(f"  Arduino Port: {arduino_port}")
        print(f"  Power levels: {powers} mW")
        print(f"  Stim times: {stim_times} ms")
        print(f"  Cycles per power: {num_cycles}")
        print(f"  Delay between stims: {stim_delay} ms")
        if pulse_freq > 0:
            print(f"  Pulse frequency: {pulse_freq} Hz")
            print(f"  Pulse on time: {pulse_on_time} ms")
        else:
            print(f"  Mode: Solid pulse")

        # Calculate estimated duration
        total_pulses = len(stim_times) * num_cycles * len(powers)
        total_time_sec = (total_pulses * stim_delay) / 1000
        print(f"\n  Total pulses: {total_pulses}")
        print(f"  Estimated duration: ~{total_time_sec:.1f} seconds")
        print(f"\n  Press DELETE at any time to stop\n")

        # Initialize laser
        print(Fore.GREEN + "Test:" + Style.RESET_ALL + " Initializing red laser...")
        laser = RedLaser(port=laser_port)
        laser.connect()
        print(Fore.GREEN + "Test:" + Style.RESET_ALL + " Laser connected!")

        # Turn laser ON first (required before setting power)
        print(Fore.GREEN + "Test:" + Style.RESET_ALL + " Turning laser ON...")
        laser.turn_on()
        time.sleep(0.5)

        # Set initial power after turning on
        print(Fore.GREEN + "Test:" + Style.RESET_ALL + f" Setting initial power to {powers[0]} mW...")
        laser.set_power(powers[0])
        time.sleep(0.5)

        # Initialize Arduino
        print(Fore.GREEN + "Test:" + Style.RESET_ALL + " Initializing Arduino stim board...")
        arduino = setup_arduino(arduino_port, stim_times, num_cycles, stim_delay, pulse_freq, pulse_on_time)
        print(Fore.GREEN + "Test:" + Style.RESET_ALL + " Arduino ready!")

        # Run through power levels
        for power in powers:
            print(Fore.CYAN + f"\n{'=' * 70}" + Style.RESET_ALL)
            print(Fore.CYAN + f"Starting sequence at {power} mW" + Style.RESET_ALL)
            print(Fore.CYAN + f"{'=' * 70}" + Style.RESET_ALL)

            laser.set_power(power)
            time.sleep(0.5)

            # Start Arduino sequence
            arduino.write(b"s")

            # Monitor Arduino output
            last_check_time = 0
            check_interval = 0.3

            while True:
                current_time = time.time()

                if keyboard.is_pressed(exit_key):
                    print(Fore.YELLOW + "\nTest:" + Style.RESET_ALL + " DELETE pressed - stopping")
                    raise KeyboardInterrupt("User stopped test")

                if current_time - last_check_time >= check_interval:
                    last_check_time = current_time
                    if arduino.in_waiting:
                        try:
                            response = arduino.readline().decode().strip()
                            print(Fore.YELLOW + "Arduino:" + Style.RESET_ALL + f" {response}")
                            if response == 'e':
                                print(Fore.GREEN + "Test:" + Style.RESET_ALL + f" Completed power level {power} mW")
                                break
                        except UnicodeDecodeError:
                            pass

                time.sleep(0.1)

        # Turn laser OFF
        print(Fore.GREEN + "\nTest:" + Style.RESET_ALL + " Turning laser OFF...")
        laser.turn_off()
        time.sleep(0.5)

        # Cleanup
        arduino.close()
        laser.disconnect()

        print(Fore.CYAN + "\n" + "=" * 70 + Style.RESET_ALL)
        print(Fore.GREEN + "Test:" + Style.RESET_ALL + " All sequences completed successfully!")
        print(Fore.CYAN + "=" * 70 + Style.RESET_ALL)

        return True

    except KeyboardInterrupt:
        print(Fore.YELLOW + "\nTest:" + Style.RESET_ALL + " Test interrupted by user")
        cleanup(laser, arduino)
        return False

    except Exception as e:
        print(Fore.RED + f"\nTest:" + Style.RESET_ALL + f" Error: {str(e)}")
        cleanup(laser, arduino)
        raise


def cleanup(laser, arduino):
    """Safe cleanup of devices"""
    try:
        if arduino:
            arduino.write(b'e')  # Emergency stop
            time.sleep(0.1)
            arduino.close()
            print(Fore.GREEN + "Test:" + Style.RESET_ALL + " Arduino closed")
    except Exception as e:
        print(Fore.RED + f"Warning: Failed to clean up Arduino: {e}" + Style.RESET_ALL)

    try:
        if laser:
            laser.turn_off()
            time.sleep(0.5)
            laser.disconnect()
            print(Fore.GREEN + "Test:" + Style.RESET_ALL + " Laser disconnected")
    except Exception as e:
        print(Fore.RED + f"Warning: Failed to clean up laser: {e}" + Style.RESET_ALL)


def main():
    # ===== TEST CONFIGURATION =====
    # Default COM ports from start.py
    LASER_PORT = 'COM26'      # Red laser port (635nm) - laser_port_635nm from start.py
    ARDUINO_PORT = 'COM21'    # Arduino stim board - stim_port from start.py

    # Quick test parameters
    POWERS_MW = [10.0]           # 2 power levels
    STIM_TIMES_MS = [10000]        # 2 stim durations
    NUM_CYCLES = 1                     # 3 cycles per power
    STIM_DELAY_MS = 500               # 1 second between stims
    PULSE_FREQ = 0                     # Solid pulse (set to 30 for pulse train)
    PULSE_ON_TIME_MS = 10              # 10ms on time (ignored if solid pulse)
    # ==============================

    try:
        success = run_integrated_test(
            laser_port=LASER_PORT,
            arduino_port=ARDUINO_PORT,
            powers=POWERS_MW,
            stim_times=STIM_TIMES_MS,
            num_cycles=NUM_CYCLES,
            stim_delay=STIM_DELAY_MS,
            pulse_freq=PULSE_FREQ,
            pulse_on_time=PULSE_ON_TIME_MS
        )

        if success:
            sys.exit(0)
        else:
            sys.exit(1)

    except Exception as e:
        print(Fore.RED + f"\nTest failed with error: {str(e)}" + Style.RESET_ALL)
        sys.exit(1)


if __name__ == "__main__":
    main()
