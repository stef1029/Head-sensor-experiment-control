import serial
import matplotlib.pyplot as plt
import time

# Serial port configuration
serial_port = 'COM3'  # Use the correct COM port for your Arduino
baud_rate = 57600

# Initialize serial connection
ser = serial.Serial(serial_port, baud_rate, timeout=1)

# Give the Arduino time to reset
time.sleep(2)

# Initialize data storage
roll_data = []
pitch_data = []
yaw_data = []
timestamps = []

# Record data for 10 seconds
start_time = time.time()
while time.time() - start_time < 15:
    try:
        line = ser.readline().decode('utf-8').strip()
        if line:
            try:
                if '#YPR=' in line:
                    _, data = line.split('#YPR=')
                    roll, pitch, yaw = map(float, data.split(','))

                    # Store the data with the receipt timestamp
                    current_time = time.time() - start_time
                    roll_data.append(roll)
                    pitch_data.append(pitch)
                    yaw_data.append(yaw)
                    timestamps.append(current_time)

                    print(f"Timestamp: {current_time:.2f} s, Roll: {roll:.2f}, Pitch: {pitch:.2f}, Yaw: {yaw:.2f}")
            except ValueError as e:
                print(f"Error parsing line: {e}")
    except UnicodeDecodeError as e:
        print(f"Decoding error: {e}, skipping line")

# Close serial connection
ser.close()

# Calculate the frequency of readings
if len(timestamps) > 1:
    total_time = timestamps[-1] - timestamps[0]  # Total time from first to last reading
    num_readings = len(timestamps)
    frequency_hz = num_readings / total_time
    print(f"Frequency of readings: {frequency_hz:.2f} Hz")
else:
    print("Not enough data to calculate frequency")

# Plot the recorded data
plt.figure(figsize=(10, 8))

plt.subplot(3, 1, 1)
plt.plot(timestamps, roll_data, 'r-', label='Roll')
plt.title('Roll')
plt.xlabel('Time (s)')
plt.ylabel('Degrees')
plt.legend()

plt.subplot(3, 1, 2)
plt.plot(timestamps, pitch_data, 'g-', label='Pitch')
plt.title('Pitch')
plt.xlabel('Time (s)')
plt.ylabel('Degrees')
plt.legend()

plt.subplot(3, 1, 3)
plt.plot(timestamps, yaw_data, 'b-', label='Yaw')
plt.title('Yaw')
plt.xlabel('Time (s)')
plt.ylabel('Degrees')
plt.legend()

plt.tight_layout()
plt.show()
