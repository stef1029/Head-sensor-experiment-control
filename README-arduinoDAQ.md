# ArduinoDAQ System Documentation

## Overview
The ArduinoDAQ system is a high-speed data acquisition system that monitors multiple digital inputs and efficiently transmits state changes to a host computer. It consists of a Python host interface and an Arduino firmware component, designed for behavioral experiment monitoring with support for multiple sensors, actuators, and synchronization signals.

## Hardware Requirements

### Arduino Setup
- Arduino Due (recommended for high-speed USB communication)
- 35 monitored digital pins including:
  - 6 Spotlights (SPOT1-6)
  - 6 Sensors (SENSOR1-6)
  - 6 Buzzers (BUZZER1-6)
  - 6 LEDs (LED_1-6)
  - 6 Valves (VALVE1-6)
  - Cue signals (GO_CUE, NOGO_CUE)
  - Synchronization pins (CAMERA_SYNC, HEADSENSOR_SYNC, LASER_SYNC)

## Communication Protocol

### Serial Configuration
- Baud Rate: 115200
- Message Format: Binary
- Frame Structure: 11 bytes per message

### Message Format
```
Byte  0:     Start marker (0x01)
Bytes 1-9:   Interleaved message number (4 bytes) and state data (5 bytes)
Byte  10:    End marker (0x02)
```

### State Data Encoding
- 35-bit state vector (packed into 5 bytes)
- Each bit represents one digital input
- Messages sent only on state changes
- Message counter increments with every read

## Python Interface (ArduinoDAQ.py)

### Features
1. Real-time data acquisition
2. Automatic file management
3. Multi-format data storage (HDF5, JSON, CSV backup)
4. Experiment synchronization
5. Error handling and reliability tracking

### Usage
```bash
python arduino_daq_2_listen.py --id MOUSE_ID --date DATE_TIME --path OUTPUT_PATH --port COM_PORT
```

### Parameters
```python
--id:   Mouse identifier
--date: Timestamp (format: YYMMDD_HHMMSS)
--path: Output directory
--port: Serial port (default: COM2)
```

### Data Storage

#### HDF5 Format
```python
Root
├── Attributes
│   ├── mouse_ID
│   ├── date_time
│   ├── reliability
│   └── statistics
├── message_ids
├── timestamps
└── channel_data
    ├── SPOT1-6
    ├── SENSOR1-6
    ├── BUZZER1-6
    ├── LED_1-6
    ├── VALVE1-6
    └── SYNC signals
```

#### JSON Format
```json
{
    "mouse_ID": string,
    "date_time": string,
    "No_of_messages": int,
    "reliability": float,
    "time_taken": float,
    "messages_per_second": float,
    "message_ids": [],
    "timestamps": [],
    "channel_data_raw": [],
    "error_messages": []
}
```

### Synchronization
- Monitors signal files from:
  - Behavior control
  - Camera system
  - Head sensor
- Automatic termination when all signals received

## Arduino Firmware (ArduinoDAQ2_Due.cpp)
Code found in repo 'ArduinoDAQ2_Due'

### Pin Configuration
```cpp
// Input Pins
SPOT1-6:    7, 8, 9, 10, 11, 12
SENSOR1-6:  24, 25, 26, 27, 28, 29
BUZZER1-6:  30, 31, 32, 33, 34, 35
LED_1-6:    36, 37, 38, 39, 40, 41
VALVE1-6:   42, 43, 44, 45, 46, 47
GO_CUE:     48
NOGO_CUE:   50
SYNC Pins:  62, 63, 53
```

### Main Features
1. High-speed digital input monitoring
2. Change-based transmission
3. Synchronization pulse generation
4. Configurable sampling rate
5. Error detection

### Operation Sequence

1. **Initialization**
   ```cpp
   - Configure all pins as inputs
   - Initialize serial communication
   - Wait for start command ('s')
   ```

2. **Main Loop**
   ```cpp
   - Read all input states
   - Generate sync pulse
   - Check for state changes
   - Build and send messages if changed
   - Check for end command ('e')
   ```

3. **Message Building**
   ```cpp
   - Create 11-byte message packet
   - Interleave message ID and state data
   - Add start/end markers
   ```

### Performance Optimizations
1. State change detection
2. Efficient bit manipulation
3. Minimal delay between readings
4. Optimized USB communication
5. Sync pulse timing

## Error Handling

### Python Side
1. Serial Connection
   - Automatic reconnection
   - Buffer management
   - Timeout handling

2. Data Validation
   - Message integrity checks
   - Sequence verification
   - Backup storage

3. File Operations
   - Automatic backup creation
   - Error logging
   - Resource cleanup

### Arduino Side
1. Communication
   - Start/end byte verification
   - State validation
   - Buffer overflow prevention

2. Hardware
   - Pin state monitoring
   - Sync pulse timing
   - USB communication checks

## Troubleshooting

### Common Issues

1. **Communication Errors**
   - Verify COM port settings
   - Check USB connection
   - Monitor error messages
   - Verify baud rate

2. **Data Quality**
   - Check reliability percentage
   - Monitor message rate
   - Verify pin connections
   - Check sync signals

3. **Synchronization**
   - Verify signal files
   - Check file permissions
   - Monitor timing alignment
   - Validate sync pulses

## Performance Considerations

1. **Timing**
   - Minimize processing in main loop
   - Optimize state change detection
   - Efficient message building
   - USB buffer management

2. **Data Management**
   - Regular backups
   - Efficient storage formats
   - Memory usage optimization
   - Buffer size tuning

## Dependencies
- Python:
  - pyserial
  - h5py
  - numpy
  - asyncio
  - keyboard
  - colorama

- Arduino:
  - Standard Arduino libraries

## Development Guidelines

When modifying the system:
1. Maintain message protocol compatibility
2. Test timing critical operations
3. Verify data integrity
4. Update documentation
5. Test synchronization
6. Validate backup systems
