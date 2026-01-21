import serial
import time
import keyboard
from colorama import init, Fore, Style

init()
exit_key = 'del'


def read_arduino_output(arduino, timeout=1):
    """Read all available output from Arduino with timeout"""
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
    print(Fore.CYAN + "Arduino Test:" + Style.RESET_ALL + f" Connecting to Arduino on {arduino_port}...")
    arduino = serial.Serial(arduino_port, 57600, timeout=5)
    time.sleep(2)
    arduino.reset_input_buffer()

    # Calculate pulse timing
    if pulse_freq <= 0:
        print(Fore.CYAN + "Arduino Test:" + Style.RESET_ALL + " Setting up solid pulse mode")
        pulse_off_time = 0
    else:
        print(Fore.CYAN + "Arduino Test:" + Style.RESET_ALL + " Setting up pulse train mode")
        pulse_period_ms = int(1000 / pulse_freq)
        if pulse_on_time >= pulse_period_ms:
            raise ValueError(f"Pulse on time ({pulse_on_time}ms) must be less than pulse period ({pulse_period_ms}ms) at {pulse_freq}Hz")
        pulse_off_time = pulse_period_ms - pulse_on_time

    # Format: numDurations#duration1,duration2,...,numCycles,stimDelay,pulseOnTime,pulseOffTime
    params = f"{len(stim_times)}#{','.join(map(str, stim_times))},{num_cycles},{stim_delay},{pulse_on_time},{pulse_off_time}\n"
    print(Fore.CYAN + "Arduino Test:" + Style.RESET_ALL + f" Sending parameters: {params.strip()}")
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
        raise RuntimeError("Failed to initialize Arduino")

    print(Fore.GREEN + "Arduino Test:" + Style.RESET_ALL + " Parameters accepted by Arduino")
    return arduino


def run_test_sequence(arduino):
    """Run a test pulse sequence"""
    print(Fore.CYAN + "\nArduino Test:" + Style.RESET_ALL + " Starting test pulse sequence...")
    print(Fore.CYAN + "Arduino Test:" + Style.RESET_ALL + " Press DELETE to stop\n")

    arduino.write(b"s")

    last_check_time = 0
    check_interval = 0.3

    while True:
        current_time = time.time()

        if keyboard.is_pressed(exit_key):
            print(Fore.CYAN + "\nArduino Test:" + Style.RESET_ALL + " DELETE pressed - stopping")
            arduino.write(b'e')  # Emergency stop
            return False

        if current_time - last_check_time >= check_interval:
            last_check_time = current_time
            if arduino.in_waiting:
                try:
                    response = arduino.readline().decode().strip()
                    print(Fore.YELLOW + "Arduino:" + Style.RESET_ALL + f" {response}")
                    if response == 'e':
                        print(Fore.GREEN + "\nArduino Test:" + Style.RESET_ALL + " Sequence completed!")
                        return True
                except UnicodeDecodeError:
                    pass

        time.sleep(0.1)


def main():
    # ===== TEST CONFIGURATION =====
    ARDUINO_PORT = 'COM21'  # From start.py stim_port

    # Short test sequence: 3 different pulse durations, 2 cycles each, 1 second delay
    STIM_TIMES_MS = [1000]  # 3 different pulse durations
    NUM_CYCLES = 5                    # 2 cycles of each duration
    STIM_DELAY_MS = 500             # 1 second between pulses
    PULSE_FREQ = 0                   # Solid pulse mode
    PULSE_ON_TIME_MS = 10            # 10ms on time per pulse
    # ==============================

    print(Fore.CYAN + "=" * 70 + Style.RESET_ALL)
    print(Fore.CYAN + "ARDUINO LASER CONTROL BOARD TEST" + Style.RESET_ALL)
    print(Fore.CYAN + "=" * 70 + Style.RESET_ALL)
    print(f"\nTest Configuration:")
    print(f"  Arduino Port: {ARDUINO_PORT}")
    print(f"  Pulse Durations: {STIM_TIMES_MS} ms")
    print(f"  Cycles per duration: {NUM_CYCLES}")
    print(f"  Delay between pulses: {STIM_DELAY_MS} ms")
    if PULSE_FREQ > 0:
        print(f"  Pulse frequency: {PULSE_FREQ} Hz")
        print(f"  Pulse on time: {PULSE_ON_TIME_MS} ms")
    else:
        print(f"  Mode: Solid pulse (no pulse train)")

    # Calculate total expected time
    total_pulses = len(STIM_TIMES_MS) * NUM_CYCLES
    total_time_sec = (total_pulses * STIM_DELAY_MS) / 1000
    print(f"\n  Total pulses: {total_pulses}")
    print(f"  Estimated duration: ~{total_time_sec:.1f} seconds")

    print(Fore.CYAN + "\nStarting test...\n" + Style.RESET_ALL)

    arduino = None

    try:
        # Setup Arduino
        arduino = setup_arduino(
            ARDUINO_PORT,
            STIM_TIMES_MS,
            NUM_CYCLES,
            STIM_DELAY_MS,
            PULSE_FREQ,
            PULSE_ON_TIME_MS
        )

        # Run test sequence
        success = run_test_sequence(arduino)

        # Cleanup
        time.sleep(0.1)
        arduino.close()

        print(Fore.CYAN + "\n" + "=" * 70 + Style.RESET_ALL)
        if success:
            print(Fore.GREEN + "Arduino Test:" + Style.RESET_ALL + " Test completed successfully!")
        else:
            print(Fore.YELLOW + "Arduino Test:" + Style.RESET_ALL + " Test stopped by user")
        print(Fore.CYAN + "=" * 70 + Style.RESET_ALL)

    except KeyboardInterrupt:
        print(Fore.YELLOW + "\nArduino Test:" + Style.RESET_ALL + " Interrupted by user")
        if arduino:
            try:
                arduino.write(b'e')
                time.sleep(0.1)
                arduino.close()
            except:
                pass

    except Exception as e:
        print(Fore.RED + f"\nArduino Test:" + Style.RESET_ALL + f" Error: {str(e)}")
        if arduino:
            try:
                arduino.write(b'e')
                time.sleep(0.1)
                arduino.close()
            except:
                pass
        raise


if __name__ == "__main__":
    main()
