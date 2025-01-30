import argparse
from pycobolt import Cobolt06MLD
import time
import sys
import serial
import keyboard
from colorama import init, Fore, Style
init()

def calculate_total_duration(powers, stim_times, num_cycles, stim_delay):
    """Calculate estimated total duration in minutes"""
    # Time for one complete cycle of all stim durations
    one_cycle_time = sum(stim_times) + (len(stim_times) * stim_delay)
    
    # Total time for all cycles at one power level
    one_power_time = one_cycle_time * num_cycles
    
    # Total time for all power levels
    total_time_ms = one_power_time * len(powers)
    
    # Add setup time estimates (laser init, power changes, etc)
    setup_time_ms = 10000  # 10 seconds for initial setup
    power_change_time_ms = 2000 * (len(powers) - 1)  # 2 seconds per power change
    
    total_time_ms += setup_time_ms + power_change_time_ms
    
    # Convert to minutes
    total_minutes = total_time_ms / (1000 * 60)
    
    return total_minutes

def wait_for_key(laser, timeout=30):
    """Wait for the key to be turned, with timeout in seconds"""
    print(Fore.GREEN + "Laser control:" + Style.RESET_ALL + Fore.BLUE + "\nWaiting for laser key. Toggle key on box to continue..." + Style.RESET_ALL)
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        if keyboard.is_pressed('esc'):
            return False
        state = laser.get_state()
        if state != "1 - Waiting for key":
            return True
        time.sleep(1)
    return False

def read_arduino_output(arduino, timeout=1):
    """Read all available output from Arduino with timeout"""
    start_time = time.time()
    response = ""
    while (time.time() - start_time) < timeout:
        if keyboard.is_pressed('esc'):
            return "esc_pressed"
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
    arduino = serial.Serial(arduino_port, 57600, timeout=5)
    time.sleep(2)
    arduino.reset_input_buffer()
    
    # Calculate pulse timing
    if pulse_freq <= 0:
        # For non-pulsing mode, set timing to ensure solid pulse
        print(Fore.GREEN + "Debug:" + Style.RESET_ALL + " Setting up solid pulse mode")
        pulse_off_time = 0
    else:
        # Calculate period and validate pulse timing
        print(Fore.GREEN + "Debug:" + Style.RESET_ALL + " Setting up pulse train mode")
        pulse_period_ms = int(1000 / pulse_freq)  # Convert Hz to ms period
        if pulse_on_time >= pulse_period_ms:
            raise ValueError(f"Pulse on time ({pulse_on_time}ms) must be less than pulse period ({pulse_period_ms}ms) at {pulse_freq}Hz")
        pulse_off_time = pulse_period_ms - pulse_on_time
    
    # Format: numDurations#duration1,duration2,...,numCycles,stimDelay,pulseOnTime,pulseOffTime
    params = f"{len(stim_times)}#{','.join(map(str, stim_times))},{num_cycles},{stim_delay},{pulse_on_time},{pulse_off_time}\n"
    print(Fore.GREEN + "Debug:" + Style.RESET_ALL + f" Sending parameters: {params.strip()}")
    arduino.write(b'p')
    time.sleep(0.01)
    
    for char in params:
        arduino.write(char.encode())
        time.sleep(0.001)
    
    response = read_arduino_output(arduino)
    if response == "esc_pressed":
        arduino.close()
        raise KeyboardInterrupt("ESC pressed")
    if "params_received" not in response:
        raise RuntimeError("Failed to initialize Arduino")
    
    return arduino

def cleanup(laser, arduino):
    """Safe cleanup of devices"""
    try:
        if arduino:
            arduino.write(b'e')  # Emergency stop
            time.sleep(0.1)
            arduino.close()
    except:
        pass
    
    try:
        if laser:
            laser.constant_power(power=0)
            laser.turn_off()
            laser.disconnect()
    except:
        pass

def main():
    parser = argparse.ArgumentParser(description='Laser stimulation coordinator')
    parser.add_argument('--laser_port', type=str, default='COM11', help='COM port for laser')
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
        print(Fore.GREEN + "Laser control:" + Style.RESET_ALL + f"Running {len(args.powers)} power levels: {args.powers} mW")
        print(Fore.GREEN + "Laser control:" + Style.RESET_ALL + f"Each power level will run {args.num_cycles} cycles")
        if args.pulse_freq <= 0:
            print(Fore.GREEN + "Laser control:" + Style.RESET_ALL + "Using solid pulses (no pulse train)")
        else:
            print(Fore.GREEN + "Laser control:" + Style.RESET_ALL + 
                  f"Pulse frequency: {args.pulse_freq} Hz, on time: {args.pulse_on_time}ms")
        print(Fore.GREEN + "Laser control:" + Style.RESET_ALL + f"Press ESC at any time to stop the sequence\n")

        # Initialize laser
        print(Fore.GREEN + "Laser control:" + Style.RESET_ALL + "Initializing laser...")
        laser = Cobolt06MLD(port=args.laser_port)
        laser.clear_fault()
        laser.constant_power(power=0)
        laser.turn_on()
        time.sleep(2)
        
        if "Waiting for key" in laser.get_state():
            if not wait_for_key(laser):
                print(Fore.GREEN + "Laser control:" + Style.RESET_ALL + "Laser key check interrupted")
                return 1
        
        print(Fore.GREEN + "Laser control:" + Style.RESET_ALL + "Setting up modulation mode...")
        laser.modulation_mode(power=0)
        laser.digital_modulation(1)
        time.sleep(5)
        
        # Setup Arduino
        print(Fore.GREEN + "Laser control:" + Style.RESET_ALL + "Initializing Arduino...")
        arduino = setup_arduino(args.arduino_port, args.stim_times, 
                              args.num_cycles, args.stim_delay,
                              args.pulse_freq, args.pulse_on_time)
        
        # Run through power levels
        for power in args.powers:
            print(Fore.GREEN + "Laser control:" + Style.RESET_ALL + f"\nStarting sequence at {power} mW")
            laser.set_modulation_power(power)
            time.sleep(1)
            arduino.write(b"s")
            
            while True:
                if keyboard.is_pressed('esc'):
                    print(Fore.GREEN + "Laser control:" + Style.RESET_ALL + "\nESC pressed - stopping stimulation")
                    raise KeyboardInterrupt("ESC pressed")
                
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
        
    except Exception as e:
        print(Fore.GREEN + "Laser control:" + Style.RESET_ALL + f"\nError: {str(e)}")
        cleanup(laser, arduino)
        return 1

if __name__ == "__main__":
    sys.exit(main())