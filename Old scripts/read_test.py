import time
import serial
import struct

# Replace 'COM3' with the appropriate port for your system
arduino_port = 'COM3'
baud_rate = 57600
timeout = 2

# Boundary bytes
START_BOUNDARY = b'\x02'
END_BOUNDARY = b'\x03'

# Buffers for storing data
message_ids = []
roll_data = []
pitch_data = []
yaw_data = []
timestamps = []

def parse_binary_message(message):
    try:
        if len(message) == 16:  # 1 unsigned long (4 bytes) + 3 floats (4 bytes each)
            message_id = struct.unpack('L', message[0:4])[0]
            ypr = [struct.unpack('f', message[i:i+4])[0] for i in range(4, 16, 4)]
            return message_id, ypr[0], ypr[1], ypr[2]
    except struct.error as e:
        print(f"Error parsing binary message: {e}, message: {message}")
    return None, None, None, None

def sync_timing():
    with serial.Serial(arduino_port, baud_rate, timeout=timeout) as ser:
        # time.sleep(2)  # Give some time for the connection to settle
        
        # Flush the input buffer to clear any old data
        ser.reset_input_buffer()

        # Measure 10 seconds on Python clock
        start_time = time.time()
        message_count = 0
        while time.time() - start_time < 10:
            try:
                # Read until start boundary is found
                while ser.read() != START_BOUNDARY:
                    pass
                
                # Read the fixed size of the message (16 bytes)
                message = ser.read(16)

                # Read until end boundary is found
                if ser.read() == END_BOUNDARY:
                    message_id, roll, pitch, yaw = parse_binary_message(message)

                    if message_id is not None and roll is not None and pitch is not None and yaw is not None:
                        # Store the data with the receipt timestamp
                        current_time = time.time() - start_time
                        message_ids.append(message_id)
                        roll_data.append(roll)
                        pitch_data.append(pitch)
                        yaw_data.append(yaw)
                        timestamps.append(current_time)
                        message_count += 1

                        print(f"Timestamp: {current_time:.2f} s, Message ID: {message_id}, Roll: {roll:.2f}, Pitch: {pitch:.2f}, Yaw: {yaw:.2f}")

            except serial.SerialException as e:
                print(f"Serial error: {e}, skipping message")
            except UnicodeDecodeError as e:
                print(f"Decoding error: {e}, skipping line")

        # Calculate and print the rate of messages in Hz
        end_time = time.time()
        duration = end_time - start_time
        if duration > 0:
            message_rate = message_count / duration
            print(f"Message rate: {message_rate:.2f} Hz")

if __name__ == "__main__":
    sync_timing()
