"""
Unified laser stimulation coordinator (LaserLink-backed).

Replaces the old laser_control.py (Cobolt) and red_laser_control.py (CNI)
scripts with a single coordinator. The laser protocol is selected by
``kind`` — resolved per-board from board_registry.json (the "kind" field)
or overridden with ``--laser_kind`` — so a CNI blue laser is driven by
naming a board whose kind is ``cni_laser``, independent of wavelength.

The Arduino still gates emission via a TTL line; this script only sets
power levels and lets the Arduino pulse the laser. Operationally it
behaves the same as the scripts it replaces: same CLI, same Arduino
handshake, same DELETE-to-stop loop.

Usage:
    python scripts/laser_stim.py --registry config/board_registry.json \
        --laser_board CNI_473_laser_1 --arduino_board laser_pulse_board \
        --powers 5 10 15 --stim_times 50 100 250 --num_cycles 20 \
        --stim_delay 5000 --pulse_freq 10 --pulse_on_time 50
"""

import argparse
import time
import sys
import os

import serial
import keyboard
from colorama import init, Fore, Style

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from LaserLink import Laser, LaserError

init()
exit_key = 'del'


def calculate_total_duration(powers, stim_times, num_cycles, stim_delay):
    """Estimate total run time in minutes (one pulse every stim_delay ms)."""
    one_cycle_time = stim_delay * len(stim_times)
    one_power_time = one_cycle_time * num_cycles
    total_time_ms = one_power_time * len(powers)

    setup_time_ms = 10000
    power_change_time_ms = 2000 * (len(powers) - 1)
    total_time_ms += setup_time_ms + power_change_time_ms

    return total_time_ms / (1000 * 60)


def read_arduino_output(arduino, timeout=1):
    """Read available Arduino output until timeout; honour the exit key."""
    start_time = time.time()
    response = ""
    last_check_time = 0
    check_interval = 0.3

    while (time.time() - start_time) < timeout:
        current_time = time.time()

        if keyboard.is_pressed(exit_key):
            return "exit_key_pressed"

        if current_time - last_check_time >= check_interval:
            last_check_time = current_time
            if arduino.in_waiting:
                try:
                    new_data = arduino.readline().decode().strip()
                    print(Fore.YELLOW + "Arduino:" + Style.RESET_ALL + f" {new_data}")
                    if new_data == "params_received" or new_data == "e":
                        response = new_data
                except UnicodeDecodeError:
                    pass
        else:
            time.sleep(0.1)

    return response


def setup_arduino(arduino_port, stim_times, num_cycles, stim_delay, pulse_freq, pulse_on_time):
    """Initialize the Arduino and send the stim parameters.

    Args:
        pulse_freq: Frequency in Hz (0 for solid pulse)
        pulse_on_time: On time in milliseconds for each pulse
    """
    try:
        arduino = serial.Serial(arduino_port, 57600, timeout=5)
    except serial.SerialException as e:
        raise RuntimeError(f"Failed to open Arduino serial connection on {arduino_port}: {e}") from e

    time.sleep(2)
    arduino.reset_input_buffer()

    if pulse_freq <= 0:
        print(Fore.GREEN + "Debug:" + Style.RESET_ALL + " Setting up solid pulse mode")
        pulse_off_time = 0
    else:
        print(Fore.GREEN + "Debug:" + Style.RESET_ALL + " Setting up pulse train mode")
        pulse_period_ms = int(1000 / pulse_freq)
        if pulse_on_time >= pulse_period_ms:
            raise ValueError(f"Pulse on time ({pulse_on_time}ms) must be less than pulse period ({pulse_period_ms}ms) at {pulse_freq}Hz")
        pulse_off_time = pulse_period_ms - pulse_on_time

    params = f"{len(stim_times)}#{','.join(map(str, stim_times))},{num_cycles},{stim_delay},{pulse_on_time},{pulse_off_time}\n"
    print(Fore.GREEN + "Debug:" + Style.RESET_ALL + f" Sending parameters: {params.strip()}")
    arduino.write(b'p')
    time.sleep(0.01)

    for char in params:
        arduino.write(char.encode())
        time.sleep(0.001)

    response = read_arduino_output(arduino)
    if response == "exit_key_pressed":
        arduino.close()
        raise KeyboardInterrupt("Exit key pressed")
    if "params_received" not in response:
        raise RuntimeError(f"Failed to initialize Arduino on {arduino_port}. Expected 'params_received', got: '{response}'")

    return arduino


def cleanup(laser, arduino):
    """Safe shutdown of devices — never raises."""
    try:
        if arduino:
            arduino.write(b'e')  # Emergency stop
            time.sleep(0.1)
            arduino.close()
    except Exception as e:
        print(Fore.RED + f"Warning: Failed to clean up Arduino: {e}" + Style.RESET_ALL)

    try:
        if laser:
            laser.turn_off()
            laser.disconnect()
    except Exception as e:
        print(Fore.RED + f"Warning: Failed to clean up laser: {e}" + Style.RESET_ALL)


def build_laser(registry, board, kind_override=None):
    """Resolve port/kind/baud from the registry and build a LaserLink Laser."""
    port = registry.find_board_port(board)
    kind = kind_override or registry.get_kind(board)
    if not kind:
        raise RuntimeError(
            f"No laser kind for board '{board}'. Add a \"kind\" field "
            f"(e.g. \"cni_laser\" or \"cobolt_06mld\") to board_registry.json, "
            f"or pass --laser_kind."
        )

    # The CNI backend takes a baudrate; the Cobolt backend (pycobolt) does not.
    vendor_kwargs = {}
    if kind == "cni_laser":
        vendor_kwargs["baudrate"] = registry.get_baudrate(board)

    print(Fore.GREEN + "Laser control:" + Style.RESET_ALL +
          f" Laser '{board}' -> {port} (kind={kind})")
    return Laser(name=board, kind=kind, port=port, **vendor_kwargs)


def main():
    parser = argparse.ArgumentParser(description='Laser stimulation coordinator (LaserLink)')
    parser.add_argument('--registry', type=str, required=True, help='Path to board_registry.json')
    parser.add_argument('--laser_board', type=str, default='473_laser_1', help='Board tag for the laser')
    parser.add_argument('--laser_kind', type=str, default=None,
                        help='Override the laser kind (cni_laser / cobolt_06mld); '
                             'default reads "kind" from the registry')
    parser.add_argument('--arduino_board', type=str, default='laser_pulse_board', help='Board tag for the Arduino')
    parser.add_argument('--powers', type=float, nargs='+', default=[5.0, 10.0, 15.0],
                        help='List of powers (mW) to cycle through')
    parser.add_argument('--stim_times', type=int, nargs='+',
                        default=[50, 100, 250, 500, 1000, 2000],
                        help='List of stimulation times in milliseconds')
    parser.add_argument('--num_cycles', type=int, default=20,
                        help='Number of cycles for each power level')
    parser.add_argument('--stim_delay', type=int, default=5000,
                        help='Delay between stimulations in milliseconds')
    parser.add_argument('--pulse_freq', type=float, default=10.0,
                        help='Pulse frequency in Hz')
    parser.add_argument('--pulse_on_time', type=int, default=50,
                        help='Pulse on time in milliseconds (0 for solid pulse)')
    args = parser.parse_args()

    # Resolve board tags to COM ports
    from utils.board_registry import BoardRegistry
    registry = BoardRegistry(args.registry)
    arduino_port = registry.find_board_port(args.arduino_board)

    laser = None
    arduino = None

    try:
        # Calculate and display estimated duration
        est_duration = calculate_total_duration(args.powers, args.stim_times,
                                                 args.num_cycles, args.stim_delay)
        print(Fore.GREEN + f"\nEstimated total duration: {est_duration:.1f} minutes" + Style.RESET_ALL)
        print(Fore.GREEN + "Laser control:" + Style.RESET_ALL + f" Running {len(args.powers)} power levels: {args.powers} mW")
        print(Fore.GREEN + "Laser control:" + Style.RESET_ALL + f" Each power level will run {args.num_cycles} cycles")
        if args.pulse_freq <= 0:
            print(Fore.GREEN + "Laser control:" + Style.RESET_ALL + " Using solid pulses (no pulse train)")
        else:
            print(Fore.GREEN + "Laser control:" + Style.RESET_ALL +
                  f" Pulse frequency: {args.pulse_freq} Hz, on time: {args.pulse_on_time}ms")
        print(Fore.GREEN + "Laser control:" + Style.RESET_ALL + f" Arduino '{args.arduino_board}' -> {arduino_port}")
        print(Fore.GREEN + "Laser control:" + Style.RESET_ALL + " Press DELETE at any time to stop the sequence\n")

        # Initialize laser via LaserLink
        print(Fore.GREEN + "Laser control:" + Style.RESET_ALL + " Initializing laser...")
        laser = build_laser(registry, args.laser_board, args.laser_kind)
        laser.connect()
        if laser.requires_key:
            print(Fore.BLUE + "Laser control: Turn the laser safety key on the box now..." + Style.RESET_ALL)
        laser.wait_ready(timeout=30.0)

        # Turn the laser on at the first power level; the Arduino gates emission.
        laser.set_power(args.powers[0])
        laser.turn_on()
        time.sleep(0.5)

        # Setup Arduino
        print(Fore.GREEN + "Laser control:" + Style.RESET_ALL + " Initializing Arduino...")
        arduino = setup_arduino(arduino_port, args.stim_times,
                                args.num_cycles, args.stim_delay,
                                args.pulse_freq, args.pulse_on_time)

        # Run through power levels
        for power in args.powers:
            print(Fore.GREEN + "Laser control:" + Style.RESET_ALL + f"\nStarting sequence at {power} mW")
            laser.set_power(power)
            time.sleep(1)
            arduino.write(b"s")

            last_check_time = 0
            check_interval = 0.3

            while True:
                current_time = time.time()

                if keyboard.is_pressed(exit_key):
                    print(Fore.GREEN + "Laser control:" + Style.RESET_ALL + "\nDEL pressed - stopping stimulation")
                    raise KeyboardInterrupt("DEL pressed")

                if current_time - last_check_time >= check_interval:
                    last_check_time = current_time
                    if arduino.in_waiting:
                        try:
                            response = arduino.readline().decode().strip()
                            print(Fore.YELLOW + "Arduino:" + Style.RESET_ALL + f" {response}")
                            if response == 'e':
                                break
                        except UnicodeDecodeError:
                            pass

                time.sleep(0.1)

        print(Fore.GREEN + "Laser control:" + Style.RESET_ALL + "\nSequence complete - shutting down...")
        cleanup(laser, arduino)
        return 0

    except KeyboardInterrupt:
        print(Fore.GREEN + "Laser control:" + Style.RESET_ALL + "\nStopping stimulation and shutting down...")
        cleanup(laser, arduino)
        return 1

    except (LaserError, Exception) as e:
        print(Fore.RED + f"Laser control: Error - {str(e)}" + Style.RESET_ALL)
        cleanup(laser, arduino)
        return 1


if __name__ == "__main__":
    sys.exit(main())
