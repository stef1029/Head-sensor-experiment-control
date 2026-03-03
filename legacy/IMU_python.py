"""                                                                                                                                                                                                                                                                                                                 
Created on Mon Feb 27 14:11:48 2023

@author: Marco Tripodi
 """

import serial                                                                                                                                                                                            
 
import threading
import time 
import sys                    
            
# set here the duration of the experiment, in seconds!
expduration = 10                
         
        
# Initialize serial connections with Arduinos11                                                                                                                                                                                        
try:
    ser = serial.Serial('COM21', timeout=1, baudrate=57600) # Replace 'COM5' with your serial port and put the right baud rate as on your Arduino script, 57600 is correct for the Razor AHRS DCM
except serial.SerialException as e:
    print("Error opening first serial port: ", e)
    sys.exit(1)

try:
    ser2 = serial.Serial('COM22', timeout=1, baudrate=57600) # Replace 'COM6' with your second serial port, the one you use to command the trigger Arduino board
except serial.SerialException as e:
    print("Error opening second serial port: ", e)
    ser.close()
    sys.exit(1)


time.sleep(0.1)

# Set buffer sizes
ser.buffersize = 4096
ser2.buffersize = 4096


# Send 'a' to the second serial port
ser.flushInput()
ser2.flushInput()

time.sleep(1) 
ser2.write(b'a')


# Initialize output files
try:
    output_file_ser = open('imu.txt', 'w')
except IOError as e:
    print("Error opening output file: ", e)
    ser.close()
    ser2.close()
    sys.exit(1)

# Define a function to stop the program after N seconds
def stop_program():
    time.sleep(expduration) #This defines the duration of the experiment based on the value assigned to the variable expduration at the top of the code
    print("N seconds have elapsed, stopping program...")
    sys.exit()

# Start thread to stop the program after 15 seconds
stop_thread = threading.Thread(target=stop_program)
stop_thread.start()

try:
    while True:
        # Check if 15 seconds have elapsed
        if not stop_thread.is_alive():
            break

        # Read data from serial port 1 (ser) the stream strat time is ~146ms which can be considered 0
        try:
            line1 = ser.readline().decode('utf-8', 'replace').rstrip()
        except serial.SerialException as e:
            print("Error occurred while reading from serial port 1: ", e)
            continue

        # Print and write data from serial port 1 to console and file, remove the # from print(line1) if you want to see the YPR values in console
        #print(line1)
        output_file_ser.write(line1 + '\n')


except Exception as e:
    print("Error occurred: ", e)

finally:
    # Stop stop_thread
    stop_thread.join()
    ser.flushInput()
    ser2.flushInput()
    time.sleep(0.5) 
    ser.close()
    ser2.close()
    output_file_ser.close()


# REformat output file for antelope to include comma before "#YPR"

with open('imu.txt', 'r') as f:
    lines = f.readlines()
    
with open('imu_reformatted.txt', 'w') as f:
    for line in lines:  
        line = line.replace('#YPR=',',#YPR=')
        f.write(line)
    
