import serial
import json
import csv
import datetime
import keyboard
import time
from datetime import datetime
import os
import argparse
from pathlib import Path
import h5py
import numpy as np
import asyncio
from collections import deque
import traceback
import threading
import tkinter as tk
from colorama import init, Fore, Style
init()

exit_key = "del"
test = False

async def check_signal_files(output_path, stop_event):
    if test:
        def esc_key_monitor():
            keyboard.wait('esc')
            if not stop_event.is_set():
                stop_event.set()
        esc_thread = threading.Thread(target=esc_key_monitor, daemon=True)
        esc_thread.start()

    behaviour_signal = False
    camera_signal = False
    head_sensor_signal = False
    
    while not stop_event.is_set():
        if os.path.exists(output_path / "end_signal_behaviour_control.signal"):
            behaviour_signal = True
            print(Fore.YELLOW + "ArduinoDAQ:" + Style.RESET_ALL + "Received behaviour control end signal.")
        camera_signal_path = output_path / "rig_openfield_camera_finished.signal"
        if os.path.exists(camera_signal_path):
            camera_signal = True
            print(Fore.YELLOW + "ArduinoDAQ:" + Style.RESET_ALL + "Received camera end signal.")
        head_sensor_signal_path = output_path / "end_signal_head_sensor.signal"
        if os.path.exists(head_sensor_signal_path):
            head_sensor_signal = True
            print(Fore.YELLOW + "ArduinoDAQ:" + Style.RESET_ALL + "Received head sensor end signal.")
        if behaviour_signal and camera_signal and head_sensor_signal:
            stop_event.set()
            break
        await asyncio.sleep(1)

    if test:
        keyboard.unhook_all()

async def listen(channel_names, new_mouse_ID=None, new_date_time=None, new_path=None, port=None):
    messages_from_arduino = deque()
    backup_buffer = deque()
    
    # Create a backup worker thread and queue for non-blocking file operations
    from queue import Queue
    backup_queue = Queue()
    
    def backup_worker():
        while True:
            item = backup_queue.get()
            if item is None:  # Exit signal
                break
            path, data = item
            try:
                with open(path, 'a', newline='') as csvfile:
                    csv_writer = csv.writer(csvfile)
                    csv_writer.writerows(data)
            except Exception as e:
                print(f"Error in backup thread: {e}")
            finally:
                backup_queue.task_done()
    
    # Start the backup thread as a daemon (will auto-terminate when main program exits)
    backup_thread = threading.Thread(target=backup_worker, daemon=True)
    backup_thread.start()
    
    if new_mouse_ID is None:
        mouse_ID = input(r"Enter mouse ID: ")
    else:
        mouse_ID = new_mouse_ID

    if new_date_time is None:
        date_time = f"{datetime.now():%y%m%d_%H%M%S}"
    else:
        date_time = new_date_time

    foldername = f"{date_time}_{mouse_ID}"

    if new_path is None:
        output_path = Path(os.path.join(os.getcwd(), foldername))
        os.mkdir(output_path)
    else:
        output_path = Path(new_path)

    backup_csv_path = output_path / f"{foldername}-backup.csv"
    COM_PORT = port
    
    try:
        ser = serial.Serial(COM_PORT, 115200, timeout=1)
        time.sleep(3)
    except serial.SerialException:
        print("Serial-listen connection not found, trying again...")
        ser = serial.Serial(COM_PORT, 115200, timeout=1)
        time.sleep(3)

    ser.write("s".encode("utf-8"))
    ser.reset_input_buffer()
    ser.read_until(b"s")

    # Create a signal file indicating DAQ has started
    daq_signal_file = output_path / "daq_started.signal"
    with open(daq_signal_file, 'w') as sf:
        sf.write("DAQ started successfully")

    start = time.perf_counter()
    message_counter = 0
    full_messages = 0
    error_messages = []
    stop_event = asyncio.Event()

    try:
        asyncio.create_task(check_signal_files(output_path, stop_event))
    except Exception as e:
        print(f"Error while starting signal file check task: {e}")

    backup_interval = 5
    last_backup_time = time.perf_counter()

    # Read messages until a stop condition is triggered
    while not stop_event.is_set():
        if ser.in_waiting >= 7:
            current_time = time.perf_counter() - start
            message = ser.read(7)
            if len(message) == 7 and message[0] == 0x01 and message[6] == 0x02:
                msgNum = (
                    (message[1] << 24) |
                    (message[2] << 16) |
                    (message[3] << 8)  |
                    (message[4])
                )
                state = message[5]
                messages_from_arduino.append([msgNum, state, current_time])
                backup_buffer.append([msgNum, state, current_time])
                full_messages += 1
            else:
                error_messages.append([message_counter, message.hex(), current_time])
            message_counter += 1

        # Replace the synchronous backup with the non-blocking queue-based approach
        now = time.perf_counter()
        # if now - last_backup_time >= backup_interval:
        #     last_backup_time = now
        #     if len(backup_buffer) > 0:  # Only queue if there's data to back up
        #         backup_queue.put((backup_csv_path, list(backup_buffer)))
        #         backup_buffer.clear()  # Clear buffer immediately

        await asyncio.sleep(0)

    end = time.perf_counter()

    # Process any remaining backup data
    # if len(backup_buffer) > 0:
    #     backup_queue.put((backup_csv_path, list(backup_buffer)))
    
    # Optional: Wait for all backup operations to complete
    # backup_queue.join()

    for _ in range(3):
        ser.write(b"e")

    save_to_hdf5_and_json(
        foldername=foldername,
        output_path=output_path,
        mouse_ID=mouse_ID,
        date_time=date_time,
        messages_from_arduino=list(messages_from_arduino),
        message_counter=message_counter,
        full_messages=full_messages,
        start=start,
        end=end,
        error_messages=error_messages,
        channel_names=channel_names
    )

    ser.close()



def save_to_hdf5_and_json(foldername, output_path, mouse_ID, date_time, messages_from_arduino,
                          message_counter, full_messages, start, end, error_messages,
                          channel_names):
    message_ids = np.array([m[0] for m in messages_from_arduino], dtype=np.uint32)
    states = np.array([m[1] for m in messages_from_arduino], dtype=np.uint8)
    timestamps = np.array([m[2] for m in messages_from_arduino], dtype=np.float64)

    num_channels = len(channel_names)
    num_messages = len(states)
    channel_data_array = np.zeros((num_messages, num_channels), dtype=np.uint8)
    
    for i, state in enumerate(states):
        # If you want the first channel name in the list to be the highest bit:
        for bit_index in range(num_channels):
            msb_aligned_bit = num_channels - 1 - bit_index
            channel_data_array[i, bit_index] = (state >> msb_aligned_bit) & 1

    save_file_name = f"{foldername}-ArduinoDAQ.h5"
    output_file = output_path / save_file_name
    json_file_name = f"{foldername}-ArduinoDAQ.json"
    json_output_file = output_path / json_file_name

    try:
        reliability = (full_messages / message_counter) * 100
    except ZeroDivisionError:
        reliability = 0

    binary_list = [''.join(str(bit) for bit in row) for row in channel_data_array]

    data_to_save = {
        "mouse_ID": mouse_ID,
        "date_time": date_time,
        "time": str(datetime.now()),
        "No_of_messages": num_messages,
        "reliability": reliability,
        "time_taken": end - start,
        "messages_per_second": (num_messages / (end - start)) if (end - start) else 0,
        "message_ids": message_ids.tolist(),
        "timestamps": timestamps.tolist(),
        "channel_data_raw": binary_list,
        "error_messages": error_messages,
        "channel_names": channel_names
    }

    with open(json_output_file, 'w') as json_file:
        json.dump(data_to_save, json_file, indent=4)

    with h5py.File(output_file, 'w') as h5f:
        h5f.attrs['mouse_ID'] = mouse_ID
        h5f.attrs['date_time'] = date_time
        h5f.attrs['time'] = str(datetime.now())
        h5f.attrs['No_of_messages'] = num_messages
        h5f.attrs['reliability'] = reliability
        h5f.attrs['time_taken'] = end - start
        h5f.attrs['messages_per_second'] = (num_messages / (end - start)) if (end - start) else 0

        h5f.create_dataset('message_ids', data=message_ids, compression='gzip')
        h5f.create_dataset('timestamps', data=timestamps, compression='gzip')

        channel_group = h5f.create_group('channel_data')
        for ch_index, ch_name in enumerate(channel_names):
            channel_group.create_dataset(ch_name, data=channel_data_array[:, ch_index], compression='gzip')

        if error_messages:
            error_messages_str = [str(err_msg) for err_msg in error_messages]
            error_messages_np = np.array(error_messages_str, dtype=object)
            h5f.create_dataset('error_messages', data=error_messages_np,
                               compression='gzip', dtype=h5py.string_dtype())

def save_to_backup_csv(backup_csv_path, backup_buffer):
    try:
        with open(backup_csv_path, 'a', newline='') as csvfile:
            csv_writer = csv.writer(csvfile)
            csv_writer.writerows(backup_buffer)
        return True
    except Exception as e:
        print(f"Error while saving to backup CSV: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Listen to serial port and save data.')
    parser.add_argument('--id', type=str, help='mouse ID')
    parser.add_argument('--date', type=str, help='date_time')
    parser.add_argument('--path', type=str, help='path')
    parser.add_argument('--port', type=str, default='COM2', help='COM port')
    parser.add_argument(
        '--channels',
        type=str,
        help="Comma-separated list of 8 channel names (e.g. 'IN3V3_2_camera,IN3V3_3,IN3V3_4,IN3V3_5,IN5V_6_head_sensor,IN5V_7_laser,IN5V_8,IN5V_9')"
    )
    args = parser.parse_args()

    if not args.channels:
        print("Error: You must provide exactly 8 channel names via --channels.")
        exit(1)

    channel_names = [ch.strip() for ch in args.channels.split(',')]
    if len(channel_names) != 8:
        print("Error: You must provide exactly 8 channel names.")
        exit(1)

    mouse_ID = args.id if args.id else "NoID"
    date_time = args.date if args.date else f"{datetime.now():%y%m%d_%H%M%S}"
    path = args.path if args.path else os.path.join(os.getcwd(), f"{date_time}_{mouse_ID}")
    if args.path is None and not os.path.exists(path):
        os.mkdir(path)

    try:
        asyncio.run(
            listen(
                channel_names=channel_names,
                new_mouse_ID=mouse_ID,
                new_date_time=date_time,
                new_path=path,
                port=args.port
            )
        )
    except Exception:
        print("Error in main function")
        traceback.print_exc()

    print(Fore.YELLOW + "ArduinoDAQ:" + Style.RESET_ALL + "ArduinoDAQ finished.")

if __name__ == '__main__':
    main()
