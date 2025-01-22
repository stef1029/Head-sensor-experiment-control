
import re
import time
import serial
import keyboard

from utils.calibrate_magnetometer import calibrate_magnetometer_header


UP = "\033[A"
CLEAR = "\033[K"

def calibrate(port, baud_rate=57600, timeout=0.1):
    """
    Performs:
      1) Accelerometer calibration (sensor=0)
      2) Skips the built-in magnetometer calibration by sending #on twice
      3) Performs gyroscope calibration (sensor=2)
      4) Closes the serial connection
      5) Calls 'calibrate_magnetometer_header' for the mag calibration
    """
    head_sensor = serial.Serial(port, baud_rate, timeout=timeout)
    time.sleep(2)  # Give some time for the connection to settle
    head_sensor.reset_input_buffer()

    # Containers to store final calibration strings / values
    accelerometer_values = ""
    gyroscope_values = ""

    # 1) Start overall recording on the Arduino
    head_sensor.write(b's')  # 's' => start recording
    head_sensor.flush()

    # 2) Enter calibration mode (sets sensor=0 => Accelerometer)
    head_sensor.write(b'#oc')  # "#o"+"c" => calibrate sensors (sensor=0)
    head_sensor.flush()
    head_sensor.reset_input_buffer()

    # ------------------------------------------------------
    # ACCELEROMETER CALIBRATION (curr_calibration_sensor=0)
    # ------------------------------------------------------
    input(
        "ACCELEROMETER CALIBRATION.\n"
        "Gently move the sensor so all axes point up/down at some moment.\n"
        "Press Enter to begin collecting calibration data.\n"
        "When satisfied, press 'Esc' to finalize accelerometer calibration.\n"
    )

    while True:
        # Read lines from Arduino, display them so user sees min/max
        if head_sensor.in_waiting > 0:
            message = head_sensor.readline().decode('utf-8', errors='replace').strip()
            accelerometer_values = message  # Store the last line we got
            print(UP + CLEAR + message)
            
        # Check if user pressed 'ESC'
        if keyboard.is_pressed('esc'):
            # Move to the next sensor => #on => sensor=1
            head_sensor.write(b'#on')
            head_sensor.flush()
            # Move again => #on => sensor=2 (this effectively "skips" magnetometer)
            head_sensor.write(b'#on')
            head_sensor.flush()
            break

    # ------------------------------------------------------
    # GYROSCOPE CALIBRATION (curr_calibration_sensor=2)
    # ------------------------------------------------------
    # Now the Arduino is in sensor=2 (gyro) calibration mode
    input(
        "\nGYROSCOPE CALIBRATION.\n"
        "Place the sensor on a stable surface. DO NOT touch it.\n"
        "Press Enter to begin collecting calibration data.\n"
        "Press 'Esc' to finish early (otherwise it runs for 10s).\n"
    )

    head_sensor.reset_input_buffer()
    start_time = time.perf_counter()
    calibration_time = 10.0  # seconds

    while True:
        # Calculate time left
        elapsed = time.perf_counter() - start_time
        time_left = calibration_time - elapsed
        if time_left < 0:
            time_left = 0

        # If there's any new message from the Arduino, read it
        if head_sensor.in_waiting > 0:
            message = head_sensor.readline().decode("utf-8", errors="replace").strip()
            gyroscope_values = message

            # Clear the previous console lines, then print the new message
            # followed by a line showing the countdown
            print(UP + CLEAR + f"Time remaining: {time_left:.1f}s -- {message}")

        # Check if we've exceeded 10s or user pressed ESC
        if elapsed >= calibration_time or keyboard.is_pressed('esc'):
            # Finalize: send any commands to revert to angles, stop, etc.
            for _ in range(3):
                head_sensor.write(b'#ot')
                head_sensor.write(b'e')
                head_sensor.flush()
            break

        # Optional small sleep to avoid busy-wait hammering the CPU
        time.sleep(0.01)

    # ------------------------------------------------------
    # 3) DONE WITH ACC & GYRO CALIBRATION
    # ------------------------------------------------------
    print("\nACC + GYRO CALIBRATION complete.")
    print("Accelerometer final min/max line read:")
    print(f"  => {accelerometer_values}")
    print("Gyroscope final offset/average line read:")
    print(f"  => {gyroscope_values}")

    # --- Parse the final accelerometer line for min/max ---
    # Example line looks like:
    #   accel x,y,z (min/max) = -37.00/8.00  -271.00/-225.00  -147.00/-102.00
    #
    # We'll do a simple parse:
    ax_min = ax_max = ay_min = ay_max = az_min = az_max = 0.0
    # Use a regex or manual splitting:
    match_acc = re.search(
        r"accel x,y,z \(min/max\)\s*=\s*(.*?)\s*$",
        accelerometer_values
    )
    if match_acc:
        # e.g. "-37.00/8.00  -271.00/-225.00  -147.00/-102.00"
        xyz_str = match_acc.group(1).strip()
        parts = xyz_str.split()
        # Expect 3 parts: X, Y, Z
        try:
            x_part, y_part, z_part = parts
            ax_min_str, ax_max_str = x_part.split('/')
            ay_min_str, ay_max_str = y_part.split('/')
            az_min_str, az_max_str = z_part.split('/')
            ax_min = float(ax_min_str)
            ax_max = float(ax_max_str)
            ay_min = float(ay_min_str)
            ay_max = float(ay_max_str)
            az_min = float(az_min_str)
            az_max = float(az_max_str)
        except:
            pass

    # --- Parse the final gyroscope line for average offsets ---
    # Example line:
    #   gyro x,y,z (current/average) = 2.00/2.48  24.00/23.46  -16.00/-15.91
    gx_offset = gy_offset = gz_offset = 0.0
    match_gyro = re.search(
        r"gyro x,y,z \(current/average\)\s*=\s*(.*?)\s*$",
        gyroscope_values
    )
    if match_gyro:
        xyz_gyro_str = match_gyro.group(1).strip()  # "2.00/2.48 24.00/23.46 -16.00/-15.91"
        gyro_parts = xyz_gyro_str.split()
        # Expect 3 parts again
        try:
            gx_part, gy_part, gz_part = gyro_parts
            # For each "A/B", we want B => the average offset
            gx_current_str, gx_avg_str = gx_part.split('/')
            gy_current_str, gy_avg_str = gy_part.split('/')
            gz_current_str, gz_avg_str = gz_part.split('/')
            gx_offset = float(gx_avg_str)
            gy_offset = float(gy_avg_str)
            gz_offset = float(gz_avg_str)
        except:
            pass

    # 4) Stop recording prior to starting magnetometer
    head_sensor.write(b'e')
    head_sensor.flush()

    # ------------------------------------------------------
    # 5) RUN THE NEW MAGNETOMETER CALIBRATION FUNCTION
    # ------------------------------------------------------
    print("\nNow starting the advanced magnetometer calibration...")
    center, transform = calibrate_magnetometer_header(
        head_sensor,
        max_samples=10000,
        plot_update_interval=0.1
    )

    # Close the Arduino serial so the mag calibration can do its own streaming if needed
    head_sensor.close()

    # ------------------------------------------------------
    # PRINT THE RESULTS IN ARDUINO-FRIENDLY FORMAT
    # ------------------------------------------------------
    print("\nFull Calibration Process Done.")
    print("=== Copy-Paste Below into your Arduino Code ===\n")

    print("// Accelerometer calibration values:")
    print(f"#define ACCEL_X_MIN ((float) {ax_min:.2f})")
    print(f"#define ACCEL_X_MAX ((float) {ax_max:.2f})")
    print(f"#define ACCEL_Y_MIN ((float) {ay_min:.2f})")
    print(f"#define ACCEL_Y_MAX ((float) {ay_max:.2f})")
    print(f"#define ACCEL_Z_MIN ((float) {az_min:.2f})")
    print(f"#define ACCEL_Z_MAX ((float) {az_max:.2f})")

    print("\n// Gyroscope average offsets:")
    print(f"#define GYRO_AVERAGE_OFFSET_X ((float) {gx_offset:.2f})")
    print(f"#define GYRO_AVERAGE_OFFSET_Y ((float) {gy_offset:.2f})")
    print(f"#define GYRO_AVERAGE_OFFSET_Z ((float) {gz_offset:.2f})")

    print("\n// Magnetometer calibration parameters:")
    print("#define CALIBRATION__MAGN_USE_EXTENDED true")
    print("const float magn_ellipsoid_center[3] = {")
    print(f"    {center[0]:.8f}, {center[1]:.8f}, {center[2]:.8f}")
    print("};")
    print("const float magn_ellipsoid_transform[3][3] = {")
    for row in transform:
        print(f"    {{{row[0]:.8f}, {row[1]:.8f}, {row[2]:.8f}}},")
    print("};")

if __name__ == "__main__":
    # Change this to the correct COM port
    port = "COM24"
    calibrate(port)