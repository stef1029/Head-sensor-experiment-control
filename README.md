# Head Sensor System User Manual

## Quick Start Guide

1. Open `start.py` in your preferred editor
2. Set your mouse ID and fiber transmission efficiency (TE)
3. Configure your experiment parameters
4. Run the script

## System Setup

### Required Hardware
- Arduino Due (DAQ board)
- Arduino Uno/Nano (Stimulation control)
- IMU head sensor
- Cobolt laser
- Behavior camera
- Computer with appropriate COM ports

### COM Port Configuration
Default settings (adjust in script if needed):
```python
stim_port = 'COM23'    # Stimulation board
head_port = 'COM24'    # Head sensor
daq_port = 'COM16'     # Arduino DAQ
```

## Configuring Your Experiment

### 1. Mouse Information
```python
mouse_id = "mtaq15-1a"    # Your mouse identifier
fiber_TE = 94             # Fiber transmission efficiency (%)
patch_cord_TE = 66        # Patch cord transmission efficiency (%)
```

### 2. Experiment Parameters
```python
# Output location
output_folder = r"D:\2701_Pitx2_opto_excite_headsensor"

# Stimulation parameters
at_brain_power_levels = [0.1, 0.5, 1, 3, 5, 10]  # Power at brain (mW)
stim_times_ms = [50, 100, 250, 500, 1000, 2000]  # Stimulation durations
num_cycles = 20                                   # Repetitions
stim_delay = 5000                                # Inter-stim interval (ms)
pulse_freq = 10                                  # Pulse frequency (Hz)
pulse_on_time = 10                               # Pulse width (ms)

# Head sensor orientation
rotation_angle = 90                              # Sensor rotation correction
```

### 3. System Components Control
Enable/disable specific components:
```python
run_head_sensor = True    # IMU tracking
run_camera = True         # Behavior camera
run_arduino_daq = True    # Data acquisition
run_stim_board = True     # Laser stimulation
```

## Running an Experiment

1. **Preparation**
   - Ensure all hardware is connected
   - Verify COM ports are correct
   - Check laser is in modulation mode with 'Digital' enabled

2. **Starting the Experiment**
   - Run `start.py`
   - System will initialize in this order:
     1. Timer display
     2. Arduino DAQ
     3. Camera tracking
     4. Head sensor
     5. Laser control

3. **During the Experiment**
   - Real-time displays show:
     - Head orientation angles
     - Timer countdown
     - Camera feed
   - Press 'ESC' at any time to stop

4. **Experiment Completion**
   - System automatically stops when:
     - All stimulation cycles complete
     - All components signal completion
   - Data saved automatically

## Data Output Structure

Your experiment folder will contain:
```
YYMMDD_HHMMSS_mouseID/
├── ArduinoDAQ files (.h5, .json)
├── Head sensor data (.h5, .json)
├── Camera recordings
├── Metadata.json
└── Various signal files
```

## How It Works (Background)

### 1. Coordination System
- ExperimentControl class manages all components
- Asynchronous communication via signal files
- Automatic power calculations based on transmission efficiencies

### 2. Data Collection
- Head sensor: 3-axis orientation at 50Hz
- Arduino DAQ: 35 digital inputs monitoring
- Camera: Behavior tracking
- All data timestamped and synchronized

### 3. Stimulation Protocol
```
For each power level:
    For each cycle:
        For each stimulation duration:
            1. Set laser power
            2. Generate stimulus
            3. Wait delay period
```

### 4. Synchronization
- Hardware sync pulses between components
- Software sync via signal files
- Timestamps aligned across all data streams

## Troubleshooting

### COM Port Issues
1. Check Device Manager for correct ports
2. Update ports in script
3. Ensure no other software is using ports
4. Try disconnecting/reconnecting devices

### Laser Control
1. Verify modulation mode is active
2. Check 'Digital' box is ticked
3. Confirm power calculations
4. Test with lower powers first

### Data Recording
1. Check available disk space
2. Verify write permissions
3. Monitor real-time displays
4. Check output files during recording

### Common Error Messages
- "COM port not found": Check connections
- "Laser key check interrupted": Insert/turn key
- "Signal file timeout": Check component status

## Best Practices

1. **Before Starting**
   - Calibrate head sensor if needed
   - Verify laser power at fiber tip
   - Test all components individually
   - Create backup of settings

2. **During Experiment**
   - Monitor real-time displays
   - Watch for error messages
   - Keep notes of any issues
   - Avoid unnecessary computer use

3. **After Experiment**
   - Check all data files present
   - Verify metadata accuracy
   - Backup data promptly
   - Document any anomalies

## Maintenance

### Regular Checks
- Head sensor calibration
- Laser power calibration
- COM port connections
- Disk space availability

### File Management
- Regular data backups
- Clear old signal files
- Archive completed experiments
- Update configuration files

## Support and Resources

### Configuration Files
- Located at: `C:\dev\projects\head_sensor_config.json`
- Contains paths and settings
- Update when changing computers
- Backup before modifying

### Documentation
- See individual component READMEs
- Check code comments for details
- Refer to hardware manuals
- Keep notes of custom modifications

