import serial
import time


def calculate_checksum(data_bytes):
    """Calculate checksum by summing bytes 0 to 7 and taking low byte"""
    return sum(data_bytes) & 0xFF


def create_power_command(power_mw):
    """
    Create command to set laser power
    Protocol: 0x53, 0x0A, 0x02, 0x01 (write), DATA1-4, CHECKSUM, 0x0D
    Power range: 0 to max power (bytes written high-order to low-order)
    """
    # Power value in mW - protocol says "from 0 to max power"
    # The documentation shows bytes are written from high-order byte to low-order byte
    power_value = int(power_mw)  # Keep as mW (integer)

    # Split into 4 bytes (high to low order)
    data1 = (power_value >> 24) & 0xFF
    data2 = (power_value >> 16) & 0xFF
    data3 = (power_value >> 8) & 0xFF
    data4 = power_value & 0xFF

    # Build command
    cmd = [
        0x53,  # START CODE
        0x0A,  # FRAME SIZE (10 bytes)
        0x02,  # CHANNEL (LD power set, mW)
        0x01,  # COMMAND (write)
        data1, # DATA1 (high byte)
        data2, # DATA2
        data3, # DATA3
        data4  # DATA4 (low byte)
    ]

    # Calculate checksum on bytes 0-7
    checksum = calculate_checksum(cmd)

    # Add checksum and end code
    cmd.append(checksum)
    cmd.append(0x0D)  # END CODE

    return bytes(cmd)


def create_read_command(channel):
    """
    Create command to read laser status
    Protocol: 0x53, 0x0A, CHANNEL, 0x00 (read), DATA1-4, CHECKSUM, 0x0D
    """
    cmd = [
        0x53,  # START CODE
        0x0A,  # FRAME SIZE (10 bytes)
        channel,  # CHANNEL
        0x00,  # COMMAND (read)
        0x00,  # DATA1
        0x00,  # DATA2
        0x00,  # DATA3
        0x00   # DATA4
    ]

    # Calculate checksum on bytes 0-7
    checksum = calculate_checksum(cmd)

    # Add checksum and end code
    cmd.append(checksum)
    cmd.append(0x0D)  # END CODE

    return bytes(cmd)


def create_switch_command(turn_on=True):
    """
    Create command to turn laser on/off
    Protocol: 0x53, 0x0A, 0x00, 0x01 (write), DATA1-4, CHECKSUM, 0x0D
    LD switch: 0-OFF, 1-ON
    """
    data1 = 0x00
    data2 = 0x00
    data3 = 0x00
    data4 = 0x01 if turn_on else 0x00

    # Build command
    cmd = [
        0x53,  # START CODE
        0x0A,  # FRAME SIZE (10 bytes)
        0x00,  # CHANNEL (LD switch set)
        0x01,  # COMMAND (write)
        data1, # DATA1
        data2, # DATA2
        data3, # DATA3
        data4  # DATA4
    ]

    # Calculate checksum on bytes 0-7
    checksum = calculate_checksum(cmd)

    # Add checksum and end code
    cmd.append(checksum)
    cmd.append(0x0D)  # END CODE

    return bytes(cmd)


def read_response(ser, timeout=1.0):
    """Read and parse response from laser"""
    start_time = time.time()
    response = b''

    while time.time() - start_time < timeout:
        if ser.in_waiting:
            response += ser.read(ser.in_waiting)
            # Check if we have a complete response (should be 7 bytes for success, 10 for read response)
            if len(response) >= 7 and response[-1] == 0x0D:
                break
        time.sleep(0.01)

    if response:
        print(f"Response: {' '.join(f'0x{b:02X}' for b in response)}")
        return response
    else:
        print("No response received")
        return None


def main():
    # ===== CONFIGURATION =====
    COM_PORT = 'COM26'
    BAUD_RATE = 9600
    POWER_MW = 5  # 5 mW
    ON_DURATION = 10  # 10 seconds
    # ========================

    print(f"Connecting to laser on {COM_PORT}...")

    try:
        # Open serial connection
        ser = serial.Serial(
            port=COM_PORT,
            baudrate=BAUD_RATE,
            bytesize=8,
            parity=serial.PARITY_NONE,
            stopbits=1,
            timeout=1
        )

        print("Connected!")
        time.sleep(0.5)  # Give it a moment to stabilize

        # First, try reading the current switch state
        print("\nReading current laser state...")
        read_cmd = create_read_command(0x00)  # Read LD switch state
        print(f"Sending: {' '.join(f'0x{b:02X}' for b in read_cmd)}")
        ser.write(read_cmd)
        read_response(ser)
        time.sleep(0.5)

        # Turn laser ON first
        print("\nTurning laser ON...")
        on_cmd = create_switch_command(turn_on=True)
        print(f"Sending: {' '.join(f'0x{b:02X}' for b in on_cmd)}")
        ser.write(on_cmd)
        read_response(ser)
        time.sleep(0.5)

        # Then set power
        print(f"\nSetting power to {POWER_MW} mW...")
        power_cmd = create_power_command(POWER_MW)
        print(f"Sending: {' '.join(f'0x{b:02X}' for b in power_cmd)}")
        ser.write(power_cmd)
        read_response(ser)
        time.sleep(0.5)

        # Wait for specified duration
        print(f"\nLaser is ON. Waiting {ON_DURATION} seconds...")
        time.sleep(ON_DURATION)

        # Turn laser OFF
        print("\nTurning laser OFF...")
        off_cmd = create_switch_command(turn_on=False)
        print(f"Sending: {' '.join(f'0x{b:02X}' for b in off_cmd)}")
        ser.write(off_cmd)
        read_response(ser)

        print("\nTest complete!")

        # Close connection
        ser.close()
        print("Connection closed.")

    except serial.SerialException as e:
        print(f"Serial port error: {e}")
    except Exception as e:
        print(f"Error: {e}")
        raise


if __name__ == "__main__":
    main()
