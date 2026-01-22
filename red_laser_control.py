import argparse
import time
import sys
import serial
import keyboard
from colorama import init, Fore, Style

init()
exit_key = 'del'


def calculate_checksum(data_bytes):
    """Calculate checksum by summing bytes 0 to 7 and taking low byte"""
    return sum(data_bytes) & 0xFF


def calculate_total_duration(powers, stim_times, num_cycles, stim_delay):
    """Calculate estimated total duration in minutes based on pulses every stim_delay seconds"""
    one_cycle_time = 0

    for i in range(len(stim_times)):
        one_cycle_time += stim_delay

    one_power_time = one_cycle_time * num_cycles
    total_time_ms = one_power_time * len(powers)

    setup_time_ms = 10000
    power_change_time_ms = 2000 * (len(powers) - 1)
    total_time_ms += setup_time_ms + power_change_time_ms

    total_minutes = total_time_ms / (1000 * 60)
    return total_minutes


class RedLaser:
    """Red laser control via RS-232 protocol"""

    def __init__(self, port='COM26', baudrate=9600):
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        self.is_on = False

    def connect(self):
        """Open serial connection to laser"""
        try:
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=8,
                parity=serial.PARITY_NONE,
                stopbits=1,
                timeout=1
            )
            time.sleep(0.5)
        except serial.SerialException as e:
            raise RuntimeError(f"Failed to open laser serial connection on {self.port}: {e}") from e

    def disconnect(self):
        """Close serial connection"""
        if self.ser and self.ser.is_open:
            self.ser.close()

    def _send_command(self, cmd_bytes):
        """Send command and read response"""
        if not self.ser or not self.ser.is_open:
            raise RuntimeError("Laser not connected. Call connect() first.")

        self.ser.write(cmd_bytes)
        return self._read_response()

    def _read_response(self, timeout=1.0):
        """Read and parse response from laser"""
        start_time = time.time()
        response = b''

        while time.time() - start_time < timeout:
            if self.ser.in_waiting:
                response += self.ser.read(self.ser.in_waiting)
                if len(response) >= 7 and response[-1] == 0x0D:
                    break
            time.sleep(0.01)

        if not response:
            raise RuntimeError(f"No response from laser on {self.port} after {timeout}s timeout")

        return response

    def set_power(self, power_mw):
        """
        Set laser power in milliwatts
        Protocol: 0x53, 0x0A, 0x02, 0x01 (write), DATA1-4, CHECKSUM, 0x0D
        """
        power_value = int(power_mw)

        # Split into 4 bytes (high to low order)
        data1 = (power_value >> 24) & 0xFF
        data2 = (power_value >> 16) & 0xFF
        data3 = (power_value >> 8) & 0xFF
        data4 = power_value & 0xFF

        cmd = [
            0x53,  # START CODE for commands TO laser
            0x0A,  # FRAME SIZE
            0x02,  # CHANNEL (LD power set, mW)
            0x01,  # COMMAND (write)
            data1, data2, data3, data4
        ]

        checksum = calculate_checksum(cmd)
        cmd.extend([checksum, 0x0D])

        response = self._send_command(bytes(cmd))

        # Check for OK response (0x41 0x07 0x4F 0x4B...)
        if response and len(response) >= 4:
            if response[2:4] == b'OK':
                return True
            elif response[2:5] == b'ERR':
                raise RuntimeError(f"Laser rejected power setting of {power_mw} mW. Response: {response.hex()}")

        raise RuntimeError(f"Invalid response from laser when setting power to {power_mw} mW. Response: {response.hex() if response else 'empty'}")

    def turn_on(self):
        """
        Turn laser ON
        Protocol: 0x53, 0x0A, 0x00, 0x01 (write), 0x00, 0x00, 0x00, 0x01, CHECKSUM, 0x0D
        """
        cmd = [
            0x53,  # START CODE for commands TO laser
            0x0A,  # FRAME SIZE
            0x00,  # CHANNEL (LD switch)
            0x01,  # COMMAND (write)
            0x00, 0x00, 0x00, 0x01  # Turn ON
        ]

        checksum = calculate_checksum(cmd)
        cmd.extend([checksum, 0x0D])

        response = self._send_command(bytes(cmd))

        # Verify the command was successful
        if not response or len(response) < 4:
            raise RuntimeError(f"Invalid response when turning laser ON. Response: {response.hex() if response else 'empty'}")
        if response[2:5] == b'ERR':
            raise RuntimeError(f"Laser rejected turn ON command. Response: {response.hex()}")

        self.is_on = True

    def turn_off(self):
        """
        Turn laser OFF
        Protocol: 0x53, 0x0A, 0x00, 0x01 (write), 0x00, 0x00, 0x00, 0x00, CHECKSUM, 0x0D
        """
        cmd = [
            0x53,  # START CODE for commands TO laser
            0x0A,  # FRAME SIZE
            0x00,  # CHANNEL (LD switch)
            0x01,  # COMMAND (write)
            0x00, 0x00, 0x00, 0x00  # Turn OFF
        ]

        checksum = calculate_checksum(cmd)
        cmd.extend([checksum, 0x0D])

        response = self._send_command(bytes(cmd))

        # Verify the command was successful
        if not response or len(response) < 4:
            raise RuntimeError(f"Invalid response when turning laser OFF. Response: {response.hex() if response else 'empty'}")
        if response[2:5] == b'ERR':
            raise RuntimeError(f"Laser rejected turn OFF command. Response: {response.hex()}")

        self.is_on = False


def read_arduino_output(arduino, timeout=1):
    """Read all available output from Arduino with timeout, checking less frequently"""
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
    """Initialize Arduino and send parameters

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
    """Safe cleanup of devices"""
    try:
        if arduino:
            arduino.write(b'e')  # Emergency stop
            time.sleep(0.1)
            arduino.close()
    except Exception as e:
        print(Fore.RED + f"Warning: Failed to clean up Arduino: {e}" + Style.RESET_ALL)

    try:
        if laser:
            # Turn laser OFF for safety, then disconnect
            laser.turn_off()
            time.sleep(0.5)
            laser.disconnect()
    except Exception as e:
        print(Fore.RED + f"Warning: Failed to clean up laser: {e}" + Style.RESET_ALL)


def main():
    parser = argparse.ArgumentParser(description='Red laser stimulation coordinator')
    parser.add_argument('--laser_port', type=str, default='COM26', help='COM port for red laser')
    parser.add_argument('--arduino_port', type=str, default='COM23', help='COM port for Arduino')
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

    laser = None
    arduino = None

    try:
        # Calculate and display estimated duration
        est_duration = calculate_total_duration(args.powers, args.stim_times,
                                             args.num_cycles, args.stim_delay)
        print(Fore.GREEN + f"\nEstimated total duration: {est_duration:.1f} minutes" + Style.RESET_ALL)
        print(Fore.GREEN + "Red Laser control:" + Style.RESET_ALL + f"Running {len(args.powers)} power levels: {args.powers} mW")
        print(Fore.GREEN + "Red Laser control:" + Style.RESET_ALL + f"Each power level will run {args.num_cycles} cycles")
        if args.pulse_freq <= 0:
            print(Fore.GREEN + "Red Laser control:" + Style.RESET_ALL + "Using solid pulses (no pulse train)")
        else:
            print(Fore.GREEN + "Red Laser control:" + Style.RESET_ALL +
                  f"Pulse frequency: {args.pulse_freq} Hz, on time: {args.pulse_on_time}ms")
        print(Fore.GREEN + "Red Laser control:" + Style.RESET_ALL + f"Press DELETE at any time to stop the sequence\n")

        # Initialize laser
        print(Fore.GREEN + "Red Laser control:" + Style.RESET_ALL + "Initializing red laser...")
        laser = RedLaser(port=args.laser_port)
        laser.connect()

        # Turn laser ON first (required before setting power, Arduino will gate the output)
        print(Fore.GREEN + "Red Laser control:" + Style.RESET_ALL + "Turning laser ON (Arduino will control gating)...")
        laser.turn_on()
        time.sleep(0.5)

        # Set initial power after turning on
        print(Fore.GREEN + "Red Laser control:" + Style.RESET_ALL + f"Setting initial power to {args.powers[0]} mW...")
        laser.set_power(args.powers[0])
        time.sleep(0.5)

        # Setup Arduino
        print(Fore.GREEN + "Red Laser control:" + Style.RESET_ALL + "Initializing Arduino...")
        arduino = setup_arduino(args.arduino_port, args.stim_times,
                              args.num_cycles, args.stim_delay,
                              args.pulse_freq, args.pulse_on_time)

        # Run through power levels
        for power in args.powers:
            print(Fore.GREEN + "Red Laser control:" + Style.RESET_ALL + f"\nStarting sequence at {power} mW")
            laser.set_power(power)
            time.sleep(1)
            arduino.write(b"s")

            last_check_time = 0
            check_interval = 0.3

            while True:
                current_time = time.time()

                if keyboard.is_pressed(exit_key):
                    print(Fore.GREEN + "Red Laser control:" + Style.RESET_ALL + "\nDEL pressed - stopping stimulation")
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

        print(Fore.GREEN + "Red Laser control:" + Style.RESET_ALL + "\nSequence complete - shutting down...")
        cleanup(laser, arduino)
        return 0

    except KeyboardInterrupt:
        print(Fore.GREEN + "Red Laser control:" + Style.RESET_ALL + "\nStopping stimulation and shutting down...")
        cleanup(laser, arduino)
        return 1

    except Exception as e:
        print(Fore.RED + f"Red Laser control: Error - {str(e)}" + Style.RESET_ALL)
        cleanup(laser, arduino)
        return 1


def test_red_laser():
    """Test function to verify red laser control works correctly"""
    # Test configuration
    TEST_PORT = 'COM26'
    TEST_POWER = 5  # mW
    TEST_DURATION = 3  # seconds

    print(Fore.CYAN + "=" * 60 + Style.RESET_ALL)
    print(Fore.CYAN + "RED LASER TEST MODE" + Style.RESET_ALL)
    print(Fore.CYAN + "=" * 60 + Style.RESET_ALL)
    print(f"\nTest Configuration:")
    print(f"  Port: {TEST_PORT}")
    print(f"  Power: {TEST_POWER} mW")
    print(f"  Duration: {TEST_DURATION} seconds")
    print(Fore.CYAN + "\nStarting test...\n" + Style.RESET_ALL)

    laser = None

    try:
        # Connect to laser
        print(Fore.GREEN + "Test:" + Style.RESET_ALL + f" Connecting to laser on {TEST_PORT}...")
        laser = RedLaser(port=TEST_PORT)
        laser.connect()
        print(Fore.GREEN + "Test:" + Style.RESET_ALL + " Connected!")
        time.sleep(0.5)

        # Turn laser ON
        print(Fore.GREEN + "Test:" + Style.RESET_ALL + " Turning laser ON...")
        laser.turn_on()
        time.sleep(0.5)

        # Set power
        print(Fore.GREEN + "Test:" + Style.RESET_ALL + f" Setting power to {TEST_POWER} mW...")
        laser.set_power(TEST_POWER)
        time.sleep(0.5)

        # Wait
        print(Fore.GREEN + "Test:" + Style.RESET_ALL + f" Laser is ON at {TEST_POWER} mW. Waiting {TEST_DURATION} seconds...")
        time.sleep(TEST_DURATION)

        # Turn laser OFF
        print(Fore.GREEN + "Test:" + Style.RESET_ALL + " Turning laser OFF...")
        laser.turn_off()
        time.sleep(0.5)

        # Disconnect
        laser.disconnect()

        print(Fore.CYAN + "\n" + "=" * 60 + Style.RESET_ALL)
        print(Fore.GREEN + "Test:" + Style.RESET_ALL + " Test completed successfully!")
        print(Fore.CYAN + "=" * 60 + Style.RESET_ALL)

    except Exception as e:
        print(Fore.RED + f"\nTest failed: {str(e)}" + Style.RESET_ALL)
        if laser:
            try:
                laser.turn_off()
                laser.disconnect()
            except:
                pass
        raise


if __name__ == "__main__":
    # If run directly, execute test function
    if len(sys.argv) == 1:
        test_red_laser()
    else:
        sys.exit(main())
