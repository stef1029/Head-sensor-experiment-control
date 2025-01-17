import time
import serial
import struct
import numpy as np
import argparse
from datetime import datetime
import os
import keyboard
import h5py
import json
import sys
from utils import create_end_signal
import asyncio
import threading
from colorama import init, Fore, Back, Style
init()

import angle_display_window as adw

head_sensor_port = 'COM24'
baud_rate = 57600
timeout = 2

exit_key = 'esc'

# Boundary bytes
START_BOUNDARY = b'\x02'
END_BOUNDARY = b'\x03'

UP = "\033[1A"; CLEAR = '\x1b[2K'

# Buffers for storing data
message_ids = []
yaw_data = []
roll_data = []
pitch_data = []
timestamps = []

# Define the rotation angle (in degrees)

rotation_angle_degrees = 135  # Example: 45 degrees

rotation_angle = np.radians(rotation_angle_degrees)  # Convert to radians

# Function to create a rotation matrix based on the specified axis
def create_rotation_matrix(axis, angle):
    if axis == 'yaw':
        return np.array([
            [np.cos(angle), -np.sin(angle), 0],
            [np.sin(angle), np.cos(angle), 0],
            [0, 0, 1]
        ])
    elif axis == 'pitch':
        return np.array([
            [np.cos(angle), 0, np.sin(angle)],
            [0, 1, 0],
            [-np.sin(angle), 0, np.cos(angle)]
        ])
    elif axis == 'roll':
        return np.array([
            [1, 0, 0],
            [0, np.cos(angle), -np.sin(angle)],
            [0, np.sin(angle), np.cos(angle)]
        ])
    else:
        raise ValueError("Axis must be 'yaw', 'pitch', or 'roll'")

# Specify the axis for rotation ('yaw', 'pitch', or 'roll')
rotation_axis = 'roll'  # Example: rotate around the yaw-axis

# Create the rotation matrix
rotation_matrix = create_rotation_matrix(rotation_axis, rotation_angle)

def parse_binary_message(message):
    try:
        if len(message) == 16:  # 1 unsigned long (4 bytes) + 3 floats (4 bytes each)
            message_id = struct.unpack('L', message[0:4])[0]
            ypr = struct.unpack('fff', message[4:16])
            return message_id, ypr[0], ypr[1], ypr[2]  # yaw, roll, pitch order
    except struct.error as e:
        print(Fore.BLUE + "Head Sensor:" + Style.RESET_ALL + f"Error parsing binary message: {e}, message: {message}")
    return None, None, None, None

def apply_rotation(yaw, roll, pitch, rotation_matrix):
    """Apply the specified axis rotation matrix to YRP values."""
    # Convert YRP to a 3x1 vector (order adjusted to yaw, roll, pitch)
    ypr_vector = np.array([yaw, roll, pitch])
    # Apply the rotation matrix
    ypr_rotated = rotation_matrix @ ypr_vector
    return ypr_rotated[0], ypr_rotated[1], ypr_rotated[2]


def zero_values(timeout=1):
    print(Fore.BLUE + "Head Sensor:" + Style.RESET_ALL + "Zeroing initial values...")
    start_time = time.time()
    final_values = None
    global head_sensor

    while time.time() - start_time < timeout:
        try:
            # Read until start boundary is found
            if head_sensor.read() == START_BOUNDARY:
                message = bytearray()
                while True:
                    byte = head_sensor.read(1)
                    if byte == END_BOUNDARY:
                        break
                    message.extend(byte)

                if len(message) == 16:
                    message_id, yaw, roll, pitch = parse_binary_message(message)
                    if message_id is not None and yaw is not None and roll is not None and pitch is not None:
                        final_values = (yaw, roll, pitch)
        except serial.SerialException as e:
            print(Fore.BLUE + "Head Sensor:" + Style.RESET_ALL + f"Serial error: {e}, skipping message")
        except UnicodeDecodeError as e:
            print(Fore.BLUE + "Head Sensor:" + Style.RESET_ALL + f"Decoding error: {e}, skipping line")

    return final_values

async def check_stim_signal(file_path, stop_event):
    def esc_key_monitor():
        keyboard.wait('esc')
        if not stop_event.is_set():
            stop_event.set()

    # Start a separate thread to monitor for the ESC key press
    esc_thread = threading.Thread(target=esc_key_monitor, daemon=True)
    esc_thread.start()

    try:
        while not stop_event.is_set():
            if os.path.exists(file_path):
                stop_event.set()
                head_sensor.write(b'e')
                break
            await asyncio.sleep(1)  # Check every second
    finally:
        keyboard.unhook_all()

def read_sensor(initial_yaw, initial_roll, initial_pitch, angle_display):
    print(Fore.BLUE + "Head Sensor:" + Style.RESET_ALL + "Reading sensor data...")

    # Set up counters & buffers
    start_time = time.time()
    message_count = 0
    full_messages = 0
    error_messages = []
    packet_buffer = bytearray()
    DELIMITER = b'\x03\x02'

    # Create event loop and stop event
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    stop_event = asyncio.Event()

    # Start signal file check task
    stim_signal_path = os.path.join(output_path, "stim_complete.signal")
    loop.create_task(check_stim_signal(stim_signal_path, stop_event))

    while not stop_event.is_set():
        try:
            chunk = head_sensor.read(1)
            if not chunk:
                continue

            packet_buffer.extend(chunk)
            idx = packet_buffer.find(DELIMITER)
            
            while idx != -1:
                frame = packet_buffer[:idx]
                del packet_buffer[:idx + len(DELIMITER)]

                if len(frame) == 16:
                    message_id, yaw, roll, pitch = parse_binary_message(frame)
                    if (message_id is not None and yaw is not None 
                        and roll is not None and pitch is not None):
                        yaw -= initial_yaw
                        roll -= initial_roll
                        pitch -= initial_pitch

                        yaw, roll, pitch = apply_rotation(yaw, roll, pitch, rotation_matrix)

                        current_time = time.time() - start_time
                        message_ids.append(message_id)
                        yaw_data.append(yaw)
                        roll_data.append(roll)
                        pitch_data.append(pitch)
                        timestamps.append(current_time)

                        adw.update_display_safe(angle_display, yaw, roll, pitch)

                        message_count += 1
                        full_messages += 1
                else:
                    error_messages.append([message_count, str(frame)])

                idx = packet_buffer.find(DELIMITER)

        except serial.SerialException as e:
            print(Fore.BLUE + "Head Sensor:" + Style.RESET_ALL + f"Serial error: {e}, skipping message")
            error_messages.append([message_count, f"SerialException: {e}"])
        except UnicodeDecodeError as e:
            print(Fore.BLUE + "Head Sensor:" + Style.RESET_ALL + f"Decoding error: {e}, skipping message")
            error_messages.append([message_count, f"UnicodeError: {e}"])

        # Check for manual stop
        if keyboard.is_pressed(exit_key):
            head_sensor.write(b'e')
            break

        loop.run_until_complete(asyncio.sleep(0))

    # After the loop ends, compute stats
    end_time = time.time()
    duration = end_time - start_time
    message_rate = message_count / duration if duration > 0 else 0

    print(Fore.BLUE + "Head Sensor:" + Style.RESET_ALL + f"Message counter: {message_count}")
    print(Fore.BLUE + "Head Sensor:" + Style.RESET_ALL + f"Full messages: {full_messages}, reliability: "
          f"{(full_messages/message_count)*100 if message_count > 0 else 0:.2f}%")
    print(Fore.BLUE + "Head Sensor:" + Style.RESET_ALL + f"Time taken: {duration:.2f}s, rate: {message_rate:.2f} messages/s")

    create_end_signal(output_path)

    # Save everything
    save_data(
        message_ids, yaw_data, roll_data, pitch_data, timestamps,
        full_messages, message_count, duration, error_messages
    )
    
    angle_display.close()
    head_sensor.close()

def save_data(message_ids, yaw_data, roll_data, pitch_data, timestamps, full_messages, message_count, duration, error_messages):
    data_to_save = {
        "time": str(datetime.now()),
        "No. of messages": message_count,
        "reliability": (full_messages/message_count)*100 if message_count > 0 else 0,
        "time taken": duration,
        "messages per second": message_count / duration if duration > 0 else 0,
        "messages": list(zip(message_ids, yaw_data, roll_data, pitch_data)),
        "error messages": error_messages
    }

    output_file = os.path.join(output_path, save_file_name + ".json")
    with open(output_file, "w") as f:
        json.dump(data_to_save, f, indent=4)

    # Save the data in HDF5 format
    hdf5_file = os.path.join(output_path, save_file_name + ".h5")
    with h5py.File(hdf5_file, 'w') as f:
        f.create_dataset('message_ids', data=message_ids)
        f.create_dataset('yaw_data', data=yaw_data)
        f.create_dataset('roll_data', data=roll_data)
        f.create_dataset('pitch_data', data=pitch_data)
        f.create_dataset('timestamps', data=timestamps)
        print(Fore.BLUE + "Head Sensor:" + Style.RESET_ALL + "Data saved to HDF5 file")


def calibrate():

    head_sensor = serial.Serial(head_sensor_port, baud_rate, timeout=timeout)
    time.sleep(2)  # Give some time for the connection to settle
    head_sensor.reset_input_buffer()

    accelerometer_values = ""
    magnetometer_values = ""
    gyroscope_values = ""

    # Send start command to Arduino
    head_sensor.write(b's')
    head_sensor.flush()  # Ensure the command is transmitted
    head_sensor.write(b'#oc')  # Send the command to calibrate the sensor

    input("Calibration mode. Hold sensor still in hand and press Enter to start.")
    print("""Accelerometer calibration values. Very gently move sensor so that all axes are pointing up at one point.\n
          Press 'Q' to freeze values and move onto next step.\n""")
    head_sensor.write(b'#oc')  # Send the command to calibrate the sensor
    # head_sensor.flush()
    head_sensor.reset_input_buffer()
    while True:
        if head_sensor.in_waiting > 0:
            message = head_sensor.readline().decode('utf-8').strip()
            print(UP, end = CLEAR)
            print(message)
            accelerometer_values = message
        if keyboard.is_pressed('q'):
            head_sensor.write(b'#on')
            break
    
    # input("")
    

    input("Lay sensor still on the table and do not touch. Then press Enter to start gyroscope calibration.")
    print("""Gyroscope calibration values. Do not touch sensor. Press 'Q' to freeze values and finish calibration.\n""")

    head_sensor.write(b'#on')
    start_time = time.perf_counter()
    calibration_time = 10
    while True:
        if head_sensor.in_waiting > 0:
            message = head_sensor.readline().decode('utf-8').strip()
            try:
                values = [float(value.split(' ')[0]) for value in message.split('/')[2:]]
                print(UP, end = CLEAR)
                print(f"Time remaining: {round((start_time + calibration_time) - time.perf_counter(), 1)}, Values: {values}")
                gyroscope_values = values
            except ValueError:
                print(f"Error parsing message: {message}")
                continue

        if time.perf_counter() - start_time > calibration_time:
            for i in range(3):
                head_sensor.write(b'#ot')
                head_sensor.write(b'e')
            break
        if keyboard.is_pressed('q'):
            for i in range(3):
                head_sensor.write(b'#ot')
                head_sensor.write(b'e')
            break

    print("Calibration complete.")
    print("Now go to globals.h and input these values into the ACCEL_X_MIN and GYRO_AVERAGE_OFFSET_X bits.")
    print(f"Accelerometer values: {accelerometer_values}")
    print(f"Gyroscope values: X: '{gyroscope_values[0]}', Y: '{gyroscope_values[1]}', Z: '{gyroscope_values[2]}'")

    head_sensor.close()

def retry_connection():

    head_sensor.close()
    head_sensor = serial.Serial(head_sensor_port, baud_rate, timeout=timeout)
    time.sleep(2)  # Give some time for the connection to settle
    head_sensor.reset_input_buffer()

    # Send start command to Arduino
    head_sensor.write(b's')
    head_sensor.flush()  # Ensure the command is transmitted
    return head_sensor


def main():

    angle_display = adw.AngleDisplay()

    # Create and start the display thread
    def run_display():
        try:
            angle_display.root.mainloop()
        except Exception as e:
            print(f"Display error: {e}")
            
    display_thread = threading.Thread(target=run_display, daemon=True)
    display_thread.start()

    parser = argparse.ArgumentParser(description='Listen to serial port and save data.')
    
    parser.add_argument('--id', type=str, help='mouse ID')
    parser.add_argument('--date', type=str, help='date_time')
    parser.add_argument('--path', type=str, help='path')
    args = parser.parse_args()

    # Only run code below if run from command line with args:
    if len(sys.argv) > 1:

        global output_path
        if args.id is not None:
            mouse_ID = args.id
        else:
            mouse_ID = "NoID"
        
        if args.date is not None:
            date_time = args.date
        else:
            date_time = f"{datetime.now():%y%m%d_%H%M%S}"
        
        foldername = f"{date_time}_{mouse_ID}"
        if args.path is not None:
            output_path = args.path
        else:
            output_path = os.path.join(os.getcwd(), foldername)
            os.mkdir(output_path)

        global save_file_name
        save_file_name = f"{foldername}-Head_sensor"

        # Initialize serial connections
        global head_sensor
        try:
            head_sensor = serial.Serial(head_sensor_port, baud_rate, timeout=timeout)
        except serial.SerialException as e:
            print(Fore.BLUE + "Head Sensor:" + Style.RESET_ALL + f"Serial error: {e}, retrying connection")
            time.sleep(1)
            head_sensor = serial.Serial(head_sensor_port, baud_rate, timeout=timeout)
        time.sleep(2)  # Give some time for the connection to settle
        head_sensor.reset_input_buffer()

        # Send start command to Arduino
        head_sensor.write(b's')
        head_sensor.flush()  # Ensure the command is transmitted

        # Zero the initial values
        initial_yaw, initial_roll, initial_pitch = zero_values()
        if np.isnan(initial_yaw):
            print(Fore.BLUE + "Head Sensor:" + Style.RESET_ALL + "Sensor startup failed, trying again...")
            head_sensor.close()
            time.sleep(2)
            head_sensor = serial.Serial(head_sensor_port, baud_rate, timeout=timeout)
            time.sleep(2)  # Give some time for the connection to settle
            head_sensor.reset_input_buffer()

            # Send start command to Arduino
            head_sensor.write(b's')
            head_sensor.flush()  # Ensure the command is transmitted
            initial_yaw, initial_roll, initial_pitch = zero_values()

            if np.isnan(initial_yaw):
                print(Fore.BLUE + "Head Sensor:" + Style.RESET_ALL + "Sensor startup failed again, trying again again...")
                head_sensor.close()
                time.sleep(2)
                head_sensor = serial.Serial(head_sensor_port, baud_rate, timeout=timeout)
                time.sleep(2)  # Give some time for the connection to settle
                head_sensor.reset_input_buffer()

                # Send start command to Arduino
                head_sensor.write(b's')
                head_sensor.flush()  # Ensure the command is transmitted
                initial_yaw, initial_roll, initial_pitch = zero_values()

        # initial_yaw, initial_roll, initial_pitch = 0, 0, 0

        def sensor_thread():
            read_sensor(initial_yaw, initial_roll, initial_pitch, angle_display)

        # Start sensor reading in a separate thread
        sensor_thread = threading.Thread(target=sensor_thread, daemon=True)
        sensor_thread.start()
        
        # Run Tkinter main loop in the main thread
        try:
            angle_display.root.mainloop()
        except:
            pass
    else:
        calibrate()


if __name__ == "__main__":
    # calibrate()
    main()
    print(Fore.BLUE + "Head Sensor: " + Style.RESET_ALL + "Head sensor stopped.")
