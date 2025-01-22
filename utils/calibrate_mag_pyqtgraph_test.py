import sys
import struct
import time

import serial
import numpy as np

import pyqtgraph as pg
import pyqtgraph.opengl as gl
from pyqtgraph.Qt import QtCore, QtWidgets

HEADER = b'\xAA\x55'  # 2-byte packet header
MSG_LEN = 36          # Expect 36 bytes => 9 floats


def calibrate_magnetometer_header(ser,
                                  max_samples=10000,
                                  plot_update_interval=0.1):
    """
    Reads binary magnetometer data from 'ser', plots in 3D with PyQtGraph,
    includes a GLAxisItem, and handles 'Esc' key to stop.
    Performs ellipsoid calibration afterward.

    Returns:
        center (np.ndarray, shape(3,)): Ellipsoid center offset
        transform (np.ndarray, shape(3,3)): Ellipsoid correction matrix
    """

    # -------------------------
    # 1) Configure Serial Port
    # -------------------------
    ser.reset_input_buffer()
    ser.write(b"#osrb")  # Turn on binary output with 2-byte header
    ser.write(b"#o1")    # Start continuous streaming
    ser.write(b"#oe0")   # Disable error messages
    ser.write(b"s")      # (Optional) depends on your firmware

    # -----------------------------
    # 2) Custom GLViewWidget Class
    # -----------------------------
    # Subclass GLViewWidget so we can intercept the Esc key press
    class MyGLViewWidget(gl.GLViewWidget):
        def keyPressEvent(self, ev):
            # Check if 'Esc' is pressed
            if ev.key() == QtCore.Qt.Key_Escape:
                cleanup_and_close()
            else:
                # Pass other keys to the default handler
                super().keyPressEvent(ev)

    # ---------------------------
    # 3) Create PyQt Application
    # ---------------------------
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(sys.argv)

    # Use the custom GLViewWidget
    view = MyGLViewWidget()
    view.setWindowTitle('Live Magnetometer Data (PyQtGraph)')
    view.opts['distance'] = 1000  # Adjust based on your data range
    view.show()

    # Add a 3D axis
    axis = gl.GLAxisItem()
    axis.setSize(x=500, y=500, z=500)
    view.addItem(axis)

    # (Optional) Label the axes if your PyQtGraph supports GLTextItem
    try:
        from pyqtgraph.opengl import GLTextItem
        label_x = GLTextItem(pos=(50, 0, 0), text='X', color=(1,1,1,1))
        label_y = GLTextItem(pos=(0, 50, 0), text='Y', color=(1,1,1,1))
        label_z = GLTextItem(pos=(0, 0, 50), text='Z', color=(1,1,1,1))
        view.addItem(label_x)
        view.addItem(label_y)
        view.addItem(label_z)
    except ImportError:
        print("GLTextItem not available. Axis labels won't be shown.")

    # Create a 3D scatter for magnetometer data
    scatter = gl.GLScatterPlotItem()
    scatter.setGLOptions('additive')  # or 'translucent', etc.
    view.addItem(scatter)

    # Data storage
    magnetom_data = []
    buffer = b""
    last_plot_update = time.time()
    stopped = False

    # --------------------------
    # 4) Timer-based update loop
    # --------------------------
    def update_data():
        nonlocal buffer, last_plot_update, stopped

        if stopped:
            return

        # Read serial data
        chunk = ser.read(1024)
        if chunk:
            buffer += chunk

            # Parse packets
            while True:
                start_idx = buffer.find(HEADER)
                if start_idx < 0:
                    break

                next_idx = buffer.find(HEADER, start_idx + len(HEADER))
                if next_idx < 0:
                    break

                message = buffer[start_idx + len(HEADER): next_idx]
                buffer = buffer[next_idx:]

                if len(message) == MSG_LEN:
                    data_tuple = struct.unpack('<9f', message)
                    # (ax, ay, az, mx, my, mz, gx, gy, gz)
                    mag_x, mag_y, mag_z = data_tuple[3:6]
                    magnetom_data.append((mag_x, mag_y, mag_z))
                else:
                    print(f"Discarded partial message of length {len(message)}")

        # Check max samples
        if len(magnetom_data) >= max_samples:
            print(f"Reached {max_samples} samples. Stopping.")
            cleanup_and_close()
            return

        # Update plot at limited intervals
        now = time.time()
        if (now - last_plot_update) >= plot_update_interval:
            last_plot_update = now
            if magnetom_data:
                arr = np.array(magnetom_data, dtype=np.float32)
                scatter.setData(pos=arr,
                                color=(1, 0, 0, 1),
                                size=2)

    # -----------------------
    # 5) Cleanup & Close
    # -----------------------
    def cleanup_and_close():
        nonlocal stopped
        stopped = True
        timer.stop()
        try:
            ser.write(b"e")    # stop recording
            ser.write(b"#o0")  # turn off continuous streaming
        except:
            pass
        ser.close()

        # Close the PyQt window
        view.close()
        # Quit the application
        QtWidgets.QApplication.quit()

    # -------------------------
    # 6) QTimer to call update
    # -------------------------
    timer = QtCore.QTimer()
    timer.timeout.connect(update_data)
    timer.start(10)  # 10ms => up to 100 fps

    # -------------------------
    # 7) Run the GUI event loop
    # -------------------------
    try:
        app.exec_()
    except KeyboardInterrupt:
        cleanup_and_close()

    # If no data collected, return
    if not magnetom_data:
        print("No magnetometer data collected.")
        return None, None

    # -------------------------
    # 8) Ellipsoid Calibration
    # -------------------------
    M = np.array(magnetom_data, dtype=np.float32)
    x = M[:, 0]
    y = M[:, 1]
    z = M[:, 2]

    # Build design matrix for ellipsoid eqn:
    D = np.column_stack([
        x*x, y*y, z*z,
        2.0*x*y, 2.0*x*z, 2.0*y*z,
        2.0*x, 2.0*y, 2.0*z
    ])
    ones = np.ones(len(M))
    lhs = D.T @ D
    rhs = D.T @ ones
    v = np.linalg.solve(lhs, rhs)  # [A,B,C,D,E,F,G,H,I]

    A_ellip = np.array([
        [v[0], v[3], v[4], v[6]],
        [v[3], v[1], v[5], v[7]],
        [v[4], v[5], v[2], v[8]],
        [v[6], v[7], v[8], -1.0]
    ], dtype=np.float64)

    A_3x3 = A_ellip[0:3, 0:3]
    ghi = v[6:9]
    center = -np.linalg.inv(A_3x3) @ ghi

    T = np.eye(4)
    T[3, 0:3] = center
    R = T @ A_ellip @ T.T
    R_3x3 = R[0:3, 0:3] / (-R[3, 3])

    evals, evecs = np.linalg.eig(R_3x3)
    radii = np.sqrt(1.0 / evals.real)
    scale_mat = np.diag(1.0 / radii) * np.min(radii)
    transform = evecs @ scale_mat @ evecs.T

    return center, transform


# ----------------------------------------------------------------------------
# Example usage:
# ----------------------------------------------------------------------------
if __name__ == "__main__":
    class FakeSerial:
        def reset_input_buffer(self): pass
        def write(self, x): pass
        def close(self): pass
        def read(self, n): return b''

    ser = FakeSerial()

    center, transform = calibrate_magnetometer_header(ser)
    print("center:", center)
    print("transform:\n", transform)
