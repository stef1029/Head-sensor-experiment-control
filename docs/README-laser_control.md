# Laser Stimulation Control System

## Overview
This system coordinates between a Python controller and an Arduino to deliver precise laser stimulation patterns. The Python script manages a Cobolt laser device while the Arduino handles the precise timing of stimulation pulses.

## System Components

### Hardware Requirements
- Cobolt06MLD laser
- Arduino (with digital output pins)
- Laser control pin (Arduino pin 7)
- Status LED (Arduino pin 13)

### Software Components
1. Python Control Script (`laser_control.py`)
2. Arduino Firmware (`laser_timing.ino`)
3. Cobolt Laser SDK (`pycobolt`)

## Communication Protocol

### Serial Configuration
- Baud Rate: 57600
- Hardware Flow Control: None
- Protocol: ASCII-based commands

### Command Structure
1. Parameter Setup ('p')
   ```
   Format: p{numDurations}#{duration1},{duration2},...,{numCycles},{stimDelay},{pulseOnTime},{pulseOffTime}\n
   Example: p3#50,100,250,20,5000,50,50\n
   ```

2. Control Commands
   - 's': Start stimulation sequence
   - 'e': Emergency stop/end sequence
   - 'p': Parameter configuration

3. Arduino Responses
   - "params_received": Confirmation of parameter setup
   - "e": Sequence completion signal

## Parameter Configuration

### Python-side Parameters
```python
--laser_port: COM port for laser (default: COM11)
--arduino_port: COM port for Arduino (default: COM23)
--powers: List of power levels in mW [5.0, 10.0, 15.0]
--stim_times: Stimulation durations in ms [50, 100, 250, 500, 1000, 2000]
--num_cycles: Repetitions per power level (default: 20)
--stim_delay: Inter-stimulus interval in ms (default: 5000)
--pulse_freq: Pulse frequency in Hz (default: 10.0)
--pulse_on_time: Pulse width in ms (default: 50)
```

### Arduino Parameters
```cpp
MAX_DURATIONS: Maximum number of different durations (10)
LASER_PIN: Digital output for laser control (7)
LED_PIN: Status LED output (13)
```

## Operation Sequence

1. **Initialization Phase**
   ```
   Python:
   1. Initialize laser device
   2. Wait for laser key
   3. Configure modulation mode
   4. Setup Arduino parameters
   
   Arduino:
   1. Configure pin modes
   2. Wait for parameters
   ```

2. **Parameter Configuration**
   ```
   Python → Arduino:
   1. Send 'p' command
   2. Send parameter string
   
   Arduino:
   1. Parse parameter string
   2. Store parameters
   3. Send "params_received"
   ```

3. **Stimulation Sequence**
   ```
   For each power level:
       Python:
       1. Set laser power
       2. Send 's' command
       3. Wait for completion
       
       Arduino:
       1. For each cycle:
           2. For each duration:
               3. Generate pulse pattern
               4. Wait interval
       5. Send "e" when complete
   ```

## Pulse Generation Modes

### Solid Pulse Mode (pulseOffTime = 0)
```
     ┌────────┐
     │        │
─────┘        └─────
     <duration>
```

### Pulse Train Mode (pulseOffTime > 0)
```
     ┌─┐ ┌─┐ ┌─┐
     │ │ │ │ │ │
─────┘ └─┘ └─┘ └───
     <--duration-->
```

## Error Handling

### Python-side
1. Laser Key Check
   - Timeout after 30 seconds
   - ESC key monitoring
   - State verification

2. Communication Errors
   - Serial timeout handling
   - Parameter validation
   - Arduino response verification

3. Emergency Stop
   - ESC key monitoring
   - Safe shutdown sequence
   - Resource cleanup

### Arduino-side
1. Parameter Validation
   - Duration count limits
   - Timing parameter checks
   - Command validation

2. Pulse Timing
   - Overflow prevention
   - Duration tracking
   - Sequence verification

## Safety Features

1. **Hardware Safety**
   - Laser key requirement
   - Default-off pin states
   - LED status indication

2. **Software Safety**
   - Power ramping
   - Emergency stop handling
   - Parameter bounds checking
   - Resource cleanup on exit

3. **Timing Safety**
   - Pulse width verification
   - Interval validation
   - Sequence completion checks

## Troubleshooting

### Common Issues

1. **Communication Errors**
   - Verify COM port settings
   - Check baud rate configuration
   - Confirm cable connections
   - Reset Arduino if needed

2. **Timing Issues**
   - Verify pulse parameters
   - Check for timing overflows
   - Monitor LED for pulse verification
   - Validate interval settings

3. **Laser Control**
   - Check key position
   - Verify power settings
   - Monitor modulation mode
   - Confirm Arduino control signals

## Performance Considerations

1. **Timing Accuracy**
   - Arduino handles critical timing
   - Minimize serial communication during pulses
   - Use hardware-timed pulses when possible
   - Account for serial latency

2. **Resource Management**
   - Proper cleanup on exit
   - Buffer management
   - Status monitoring
   - Error recovery

## Code Maintenance

When modifying the system:
1. Maintain command protocol compatibility
2. Test timing accuracy
3. Verify safety features
4. Document parameter changes
5. Update error handling
6. Test emergency stops
7. Validate pulse patterns

## Dependencies
- Python:
  - pycobolt
  - pyserial
  - keyboard
  - colorama
  - argparse

- Arduino:
  - Standard Arduino libraries
