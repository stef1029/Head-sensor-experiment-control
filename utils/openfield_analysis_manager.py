import json
import numpy as np
import h5py
import traceback
from pathlib import Path
import os

# Import the NWB conversion utility
from utils.headtracker_to_nwb import headtracker_to_nwb

class Analysis_manager_openfield:
    def __init__(self, session_dict, create_nwb=True):
        """
        Initialize the analysis manager and process data.
        
        Args:
            session_dict (dict): Dictionary containing session information
            create_nwb (bool): Whether to create an NWB file after synchronization
        """
        # Basic attributes
        self.session_id = session_dict.get("session_id")
        self.session_dir = Path(session_dict.get("directory", ""))
        self.body_sensor = session_dict.get("body_sensor", False)

        # Retrieve file paths from "raw_data" dict
        raw_data = session_dict.get("raw_data", {})
        self.arduino_daq_h5 = Path(raw_data.get("arduino_daq_h5", ""))
        self.head_sensor_h5 = Path(raw_data.get("head_sensor_h5", ""))
        if self.body_sensor:
            self.body_sensor_h5 = Path(raw_data.get("body_sensor_h5", ""))
        
        # Add path for tracker data JSON
        self.tracker_json = self.session_dir / f"{self.session_id}_Tracker_data.json"

        # Run the main sync functions
        try:
            # Sync head sensor, camera frame, and laser data
            self.sync_data = self.sync_all_data()
            session_dict = self.save_synced_data(self.sync_data, session_dict)
            
            # Create NWB file if requested
            if create_nwb:
                self.create_nwb_file(session_dict)
                
        except Exception as e:
            print(f"Error processing data for {self.session_dir}: {e}")
            traceback.print_exc()

    def get_sync_pulses(self, channel_name):
        """
        Helper function to get sync pulses for a given channel from ArduinoDAQ.
        
        Args:
            channel_name (str): Name of the channel in ArduinoDAQ file
            
        Returns:
            tuple: (pulse_times, timestamps from DAQ)
        """
        with h5py.File(self.arduino_daq_h5, 'r') as daq_h5:
            channel_data = np.array(daq_h5['channel_data'][channel_name])
            daq_timestamps = np.array(daq_h5['timestamps'])

        # Detect low-to-high transitions
        pulse_indices = np.where((channel_data[:-1] == 0) & (channel_data[1:] == 1))[0]
        # The pulse occurs at index+1
        pulse_times = daq_timestamps[pulse_indices + 1]
        
        print(f"Found {len(pulse_times)} pulses in ArduinoDAQ for {channel_name} channel.")
        return pulse_times, daq_timestamps

    def get_laser_events(self, channel_name='LASER_SYNC'):
        """
        Get both rising and falling edges of laser pulses to record full events.
        
        Args:
            channel_name (str): Name of the laser channel in ArduinoDAQ file
            
        Returns:
            dict: Dictionary containing laser event data
        """
        with h5py.File(self.arduino_daq_h5, 'r') as daq_h5:
            channel_data = np.array(daq_h5['channel_data'][channel_name])
            daq_timestamps = np.array(daq_h5['timestamps'])

        # Detect both rising and falling edges
        rising_indices = np.where((channel_data[:-1] == 0) & (channel_data[1:] == 1))[0]
        falling_indices = np.where((channel_data[:-1] == 1) & (channel_data[1:] == 0))[0]
        
        # The edge occurs at index+1
        rising_times = daq_timestamps[rising_indices + 1]
        falling_times = daq_timestamps[falling_indices + 1]
        
        # Handle case where we have unequal number of rising and falling edges
        min_len = min(len(rising_times), len(falling_times))
        
        # Calculate pulse durations (if we have matching rising and falling edges)
        durations = []
        if min_len > 0:
            # If first falling edge comes before first rising edge, skip it
            if len(falling_times) > 0 and len(rising_times) > 0 and falling_times[0] < rising_times[0]:
                falling_times = falling_times[1:]
                min_len = min(len(rising_times), len(falling_times))
                
            # Calculate durations for matching edges
            if min_len > 0:
                for i in range(min_len):
                    duration = falling_times[i] - rising_times[i]
                    durations.append(duration)
        
        print(f"Found {len(rising_times)} rising and {len(falling_times)} falling edges for {channel_name}")
        
        return {
            "rising_times": rising_times.tolist(),
            "falling_times": falling_times.tolist(),
            "durations": durations,
        }

    def sync_head_sensor_data(self, pulse_times):
        """
        Sync head sensor data with DAQ pulse times.
        """
        with h5py.File(self.head_sensor_h5, 'r') as sensor_h5:
            message_ids = np.array(sensor_h5['message_ids'])
            yaw_data = np.array(sensor_h5['yaw_data'])
            roll_data = np.array(sensor_h5['roll_data'])
            pitch_data = np.array(sensor_h5['pitch_data'])
            sensor_ts = np.array(sensor_h5['timestamps'])

        # Build pulse dictionary
        pulse_dict = {i: pulse_time for i, pulse_time in enumerate(pulse_times)}

        # Print the number of head sensor messages being synced
        print(f"Syncing {len(message_ids)} head sensor messages with {len(pulse_times)} pulses...")

        # Sync timestamps
        synced_timestamps = [pulse_dict.get(msg_id, None) for msg_id in message_ids]

        return {
            "message_ids": message_ids.tolist(),
            "yaw_data": yaw_data.tolist(),
            "roll_data": roll_data.tolist(),
            "pitch_data": pitch_data.tolist(),
            "head_sensor_timestamps": sensor_ts.tolist(),
            "synced_timestamps": synced_timestamps,
        }

    def sync_camera_data(self, pulse_times):
        """
        Sync camera frame IDs with DAQ pulse times.
        """
        # Load frame IDs from tracker JSON
        try:
            with open(self.tracker_json, 'r') as f:
                tracker_data = json.load(f)
                frame_ids = np.array(tracker_data["frame_IDs"])
        except Exception as e:
            print(f"Error loading tracker data: {e}")
            return None

        # Build pulse dictionary
        pulse_dict = {i: pulse_time for i, pulse_time in enumerate(pulse_times)}

        # Print the number of camera frames being synced
        print(f"Syncing {len(frame_ids)} camera frames with {len(pulse_times)} pulses...")

        # Sync timestamps
        synced_timestamps = [pulse_dict.get(frame_id, None) for frame_id in frame_ids]

        return {
            "frame_ids": frame_ids.tolist(),
            "synced_timestamps": synced_timestamps,
        }

    def sync_all_data(self):
        """
        Sync head sensor, camera frame, and laser event data with their respective pulses.
        """
        # Get pulse times for head sensor and camera channels
        head_sensor_pulses, _ = self.get_sync_pulses('HEADSENSOR_SYNC')
        if self.body_sensor:
            body_sensor_pulses, _ = self.get_sync_pulses('BODYSENSOR_SYNC')

        camera_pulses, _ = self.get_sync_pulses('CAMERA_SYNC')
        
        # Get laser events (rising and falling edges)
        laser_events = self.get_laser_events('LASER_SYNC')

        # Sync head sensor data
        head_sensor_data = self.sync_head_sensor_data(head_sensor_pulses)
        if self.body_sensor:
            body_sensor_data = self.sync_head_sensor_data(body_sensor_pulses)
        
        # Sync camera frame data
        camera_data = self.sync_camera_data(camera_pulses)

        # Combine all synced data
        if self.body_sensor:
            synced_data = {
                "session_id": self.session_id,
                "head_sensor": {
                    "pulse_times": head_sensor_pulses.tolist(),
                    **head_sensor_data
                },
                "body_sensor": {
                    "pulse_times": body_sensor_pulses.tolist(),
                    **body_sensor_data
                },
                "camera": {
                    "pulse_times": camera_pulses.tolist(),
                    **camera_data
                } if camera_data is not None else None,
                "laser": laser_events
            }
        else:
            synced_data = {
                "session_id": self.session_id,
                "head_sensor": {
                    "pulse_times": head_sensor_pulses.tolist(),
                    **head_sensor_data
                },
                "camera": {
                    "pulse_times": camera_pulses.tolist(),
                    **camera_data
                } if camera_data is not None else None,
                "laser": laser_events
            }

        return synced_data

    def save_synced_data(self, synced_data, session_dict):
        """
        Save the synced data to JSON.
        """
        print("Saving synced data...")
        output_path = self.session_dir / f"{self.session_id}_synced_data.json"
        try:
            with open(output_path, 'w') as fp:
                json.dump(synced_data, fp, indent=4)
            print(f"Synced data saved to {output_path}")
        except Exception as e:
            print(f"Failed to save synced data: {e}")
        
        session_dict['synced_data_json'] = str(output_path)
        return session_dict
            
    def create_nwb_file(self, session_dict):
        """
        Create an NWB file from the synchronized data.
        """
        print(f"Creating NWB file for session {self.session_id}...")
        
        # Check if synced data JSON exists
        synced_data_file = Path(session_dict.get('synced_data_json', None))
        if not synced_data_file.exists():
            print(f"Synced data file not found: {synced_data_file}")
            return None
            
        # Find video file (if any)
        video_file = session_dict.get('raw_data', {}).get('video', None)
        if video_file is None:
            video_filename = None
        else:
            video_filename = Path(video_file).name
        
        try:
            # Call the NWB conversion function
            nwb_path = headtracker_to_nwb(
                session_dict=session_dict,
                session_directory=self.session_dir,
                video_filename=video_filename
            )
            
            if nwb_path:
                print(f"Successfully created NWB file: {nwb_path}")
                return nwb_path
            else:
                print(f"Failed to create NWB file for session {self.session_id}")
                return None
                
        except Exception as e:
            print(f"Error creating NWB file: {e}")
            traceback.print_exc()
            return None