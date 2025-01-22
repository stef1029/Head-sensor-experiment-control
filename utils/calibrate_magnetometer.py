import time
import struct
import sys

import serial
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

import keyboard  # <-- Added

from utils import countdown_timer

HEADER = b'\xAA\x55'  # Our 2-byte packet header
MSG_LEN = 36          # We expect 36 bytes of data after the header -> 9 floats

def calibrate_magnetometer_header(
    ser,
    max_samples=10000,
    plot_update_interval=0.1
):
    """
    1) Opens 'port' at 'baud_rate', sends commands for raw binary output with a 2-byte header.
    2) Continuously reads from the serial port, searching for 0xAA,0x55 to delineate each 36-byte packet.
    3) Extracts magnetometer data from each packet, does live 3D scatter plotting.
    4) On exit (figure closed, ESC pressed, or Ctrl+C), performs an ellipsoid fit to compute calibration.
    
    Returns:
        center (np.ndarray of shape (3,)): Ellipsoid center offset
        transform (np.ndarray of shape (3,3)): Ellipsoid correction matrix
    """
    # ---------------------------------------------
    # 1) Open Serial Port and Configure
    # ---------------------------------------------
    ser.reset_input_buffer()

    # Send commands to the Arduino so it outputs:
    #   HEADER + 36 bytes (9 floats) per packet (ax, ay, az, mx, my, mz, gx, gy, gz)
    # Adjust to your firmware commands if needed
    ser.write(b"#osrb")  # Turn on binary sensor output with header
    ser.write(b"#o1")    # Start continuous streaming
    ser.write(b"#oe0")   # Disable error messages
    ser.write(b"s")      # (Optional) if your firmware requires 's' to "start recording"

    # ---------------------------------------------
    # 2) Set up Live 3D Plot
    # ---------------------------------------------
    plt.ion()
    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')
    ax.set_title("Live Magnetometer Data (Header-Based)")
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_zlabel("Z")

    magnetom_data = []  # list of (mx, my, mz) floats
    buffer = b""        # to accumulate incoming bytes
    last_plot_update = time.time()

    print("\nCollecting magnetometer data. Press ESC or close the plot window to stop.\n")

    # ---------------------------------------------
    # 3) Main Loop: Read, Parse, Plot
    # ---------------------------------------------
    try:
        while True:
            # Exit if ESC is pressed
            if keyboard.is_pressed('esc'):
                print("\nESC pressed. Exiting data collection.\n")
                break

            # If user closed the figure window, break
            if not plt.fignum_exists(fig.number):
                break

            # Read incoming chunk
            chunk = ser.read(1024)
            if chunk:
                buffer += chunk

                # Process buffer: look for HEADER -> next HEADER
                while True:
                    start_idx = buffer.find(HEADER)
                    if start_idx < 0:
                        # No header found -> read more
                        break

                    # Find the next header AFTER this one
                    next_idx = buffer.find(HEADER, start_idx + len(HEADER))
                    if next_idx < 0:
                        # Second header not found -> partial packet possible
                        break

                    # Extract everything between the two headers
                    message = buffer[start_idx + len(HEADER) : next_idx]
                    # Remove that portion from the buffer
                    buffer = buffer[next_idx:]

                    # Check if message is exactly 36 bytes
                    if len(message) == MSG_LEN:
                        # Parse 9 floats
                        acc_x, acc_y, acc_z, mag_x, mag_y, mag_z, gyr_x, gyr_y, gyr_z = struct.unpack('<9f', message)

                        # Store magnetometer data
                        magnetom_data.append((mag_x, mag_y, mag_z))

                        # (Optional) Print or do something with full sensor data
                        # print(f"Accel=({acc_x:.2f},{acc_y:.2f},{acc_z:.2f})  "
                        #       f"Magn=({mag_x:.2f},{mag_y:.2f},{mag_z:.2f})  "
                        #       f"Gyro=({gyr_x:.2f},{gyr_y:.2f},{gyr_z:.2f})")

                    else:
                        print(f"Discarded message of length {len(message)} (expected 36).")

            # Limit total samples
            if len(magnetom_data) >= max_samples:
                print(f"Reached {max_samples} samples. Stopping.")
                break

            # Update plot at given interval
            if (time.time() - last_plot_update) >= plot_update_interval:
                last_plot_update = time.time()
                ax.clear()
                ax.set_title("Live Magnetometer Data (Header-Based)")
                ax.set_xlabel("X")
                ax.set_ylabel("Y")
                ax.set_zlabel("Z")

                if magnetom_data:
                    xs = [p[0] for p in magnetom_data]
                    ys = [p[1] for p in magnetom_data]
                    zs = [p[2] for p in magnetom_data]
                    ax.scatter(xs, ys, zs, s=2, c='r')

                plt.draw()
                plt.pause(0.001)

    except KeyboardInterrupt:
        print("\nInterrupted by user (Ctrl+C).")

    # ---------------------------------------------
    # 4) Cleanup Serial & Plot
    # ---------------------------------------------
    try:
        # Send commands to stop streaming
        ser.write(b"e")    # Stop recording
        ser.write(b"#o0")  # Turn off continuous streaming
    except:
        pass

    plt.ioff()
    plt.close(fig)

    # If no data was collected, just return
    if not magnetom_data:
        print("No magnetometer data collected.")
        return None, None

    # ---------------------------------------------
    # 5) Ellipsoid Fit
    # ---------------------------------------------
    # Convert to NumPy array
    M = np.array(magnetom_data, dtype=np.float32)
    x = M[:, 0]
    y = M[:, 1]
    z = M[:, 2]

    # Build design matrix for ellipsoid eqn:
    # A*x^2 + B*y^2 + C*z^2 + 2Dxy + 2Exz + 2Fyz + 2Gx + 2Hy + 2Iz = 1
    D = np.column_stack([
        x*x,
        y*y,
        z*z,
        2.0*x*y,
        2.0*x*z,
        2.0*y*z,
        2.0*x,
        2.0*y,
        2.0*z
    ])

    ones = np.ones(len(M))
    lhs = D.T @ D
    rhs = D.T @ ones
    v = np.linalg.solve(lhs, rhs)  # [A,B,C,D,E,F,G,H,I]

    # Form 4x4 matrix
    A_ellip = np.array([
        [v[0], v[3], v[4], v[6]],
        [v[3], v[1], v[5], v[7]],
        [v[4], v[5], v[2], v[8]],
        [v[6], v[7], v[8], -1.0]
    ], dtype=np.float64)

    # Center = -inv(A[0:3,0:3]) * [G,H,I]
    A_3x3 = A_ellip[0:3, 0:3]
    ghi   = v[6:9]
    center = -np.linalg.inv(A_3x3) @ ghi

    # Translate
    T = np.eye(4)
    T[3, 0:3] = center
    R = T @ A_ellip @ T.T
    R_3x3 = R[0:3, 0:3] / (-R[3, 3])

    evals, evecs = np.linalg.eig(R_3x3)
    radii = np.sqrt(1.0 / evals.real)
    scale_mat = np.diag(1.0 / radii) * np.min(radii)
    comp = evecs @ scale_mat @ evecs.T

    return center, comp

# If running as a script, for example usage:
if __name__ == "__main__":
    # Example usage: open serial and run calibration
    # Make sure to adjust your port and baud rate
    port = 'COM3'          # or '/dev/ttyUSB0' on Linux
    baud_rate = 115200
    ser = serial.Serial(port, baud_rate, timeout=0.1)

    center, transform = calibrate_magnetometer_header(ser)
    if center is not None:
        print("\nCalibration complete.\n"
              f"Center = {center}\n"
              f"Transform =\n{transform}")
