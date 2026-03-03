# Python Interface for IMU Head Sensor System

## Overview
This Python interface provides a complete suite of tools for interacting with the IMU head sensor system, including data acquisition, real-time visualization, sensor calibration, and data storage functionality.

## Core Components

### 1. Main Data Acquisition Script
**File:** `head_sensor.py`

#### Key Features
- Real-time data collection from the IMU sensor
- Live angle visualization through a Tkinter interface
- Data saving in both JSON and HDF5 formats
- Rotation matrix application for coordinate system adjustment
- Automatic termination via external signal file
- Error handling and reliability reporting

#### Usage
```bash
python head_sensor.py --port COM24 --id MOUSE_ID --date DATE_TIME --path OUTPUT_PATH --rotation 90
```

#### Arguments
- `--port`: COM port for the head sensor (default: COM24)
- `--id`: Mouse identifier
- `--date`: Date and time for file naming
- `--path`: Output directory path
- `--rotation`: Rotation angle in degrees (default: 90)

### 2. Calibration Interface
**File:** `head_sensor_calibration_ctrl.py`

#### Features
- Three-stage calibration process:
  1. Accelerometer calibration
  2. Gyroscope calibration
  3. Advanced magnetometer calibration
- Interactive console interface
- Automatic calibration value extraction
- Arduino-ready output format

#### Usage
```bash
python head_sensor_calibration_ctrl.py
```

### 3. Magnetometer Calibration
**File:** `calibrate_magnetometer.py`

#### Features
- Real-time 3D visualization of magnetometer data
- Ellipsoid fitting for magnetic field correction
- Header-based packet synchronization
- Live data plotting
- Automatic calibration matrix generation

## Data Communication Protocol

### Serial Configuration
- Baud Rate: 57600
- Timeout: 2 seconds

### Packet Structure
- Start Boundary: 0x02 (STX)
- Message ID: 4 bytes (unsigned long)
- Data: 12 bytes (3 x 4-byte floats for yaw, pitch, roll)
- End Boundary: 0x03 (ETX)

### Control Commands
- 's': Start recording
- 'e': End recording
- 'q': Reset serial connection
- '#f': Request single frame
- '#s': Synchronization request
- '#o': Output mode control

## Real-Time Visualization
**File:** `angle_display_window.py`

### Features
- Real-time angle display in a Tkinter window
- Thread-safe update mechanism
- Color-coded angle components:
  - Yaw: Blue (#4a90e2)
  - Roll: Green (#50c878)
  - Pitch: Orange (#ff7f50)
- Always-on-top window mode
- Fixed window dimensions (800x100 pixels)

### Display Updates
- Update rate: 50ms
- Thread-safe queue implementation
- Automatic cleanup on window close

## Data Storage

### HDF5 Format
Stores the following datasets:
- message_ids
- yaw_data
- roll_data
- pitch_data
- timestamps

### JSON Format
Includes:
- Timestamp
- Message count
- Reliability statistics
- Time duration
- Messages array
- Error messages

## Calibration Process

### 1. Accelerometer Calibration
1. Enter calibration mode
2. Move sensor through all orientations
3. Record min/max values for each axis
4. Store calibration values

### 2. Gyroscope Calibration
1. Place sensor on stable surface
2. Collect data for 10 seconds
3. Calculate average offsets
4. Store offset values

### 3. Magnetometer Calibration
1. Collect 3D magnetic field samples
2. Perform ellipsoid fitting
3. Generate correction matrix
4. Store calibration parameters

## Error Handling

### Serial Communication
- Automatic reconnection attempts
- Packet integrity verification
- Buffer overflow protection
- Error message logging

### Data Validation
- Packet boundary checking
- Message length verification
- Data type validation
- Timestamp consistency checks

## Performance Considerations

### Real-time Processing
- Non-blocking serial reads
- Thread-safe display updates
- Efficient buffer management
- Minimized processing overhead

### Memory Management
- Circular buffer implementation
- Regular buffer clearing
- Efficient data structure usage
- Proper resource cleanup

## Troubleshooting

### Common Issues
1. **Serial Connection Failures**
   - Verify COM port number
   - Check baud rate settings
   - Ensure Arduino is properly connected
   - Reset serial connection with 'q' command

2. **Data Quality Issues**
   - Recalibrate sensors
   - Check for magnetic interference
   - Verify packet integrity
   - Monitor error counts

3. **Display Problems**
   - Check thread safety
   - Verify update rate
   - Monitor system resources
   - Restart visualization

## Dependencies
- numpy
- serial
- h5py
- keyboard
- tkinter
- matplotlib
- colorama
- struct

## Contributing
When modifying the system:
1. Maintain packet protocol compatibility
2. Update calibration procedures as needed
3. Document any changes to data formats
4. Test real-time performance impact
5. Verify thread safety
6. Update version history
