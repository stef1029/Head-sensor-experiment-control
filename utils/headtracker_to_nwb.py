"""
headtracker_to_nwb.py - Conversion utilities for head tracking data to NWB format

This script provides functions to convert head sensor data, camera data, and laser pulses to the 
Neurodata Without Borders (NWB) format, making it compatible with neuroscience data analysis tools.

Important: This converter specifically uses the synchronized timestamps from the post-processing
pipeline rather than raw pulse data. It relies on the "*_synced_data.json" file generated 
by the Analysis_manager_openfield class.
"""

from pynwb import NWBHDF5IO, NWBFile, TimeSeries
from pynwb.behavior import SpatialSeries
from pynwb.file import Subject
from pynwb.image import ImageSeries
from hdmf.utils import docval, get_docval, popargs

from datetime import datetime
from dateutil import tz
from uuid import uuid4
import numpy as np
from pathlib import Path
import json
import h5py
import os

def detect_rising_edges(signal, timestamps, threshold=0.5):
    """
    Identify the indices of rising edges (TTL pulses) in the given signal.
    
    Args:
        signal (array): The signal array (0s and 1s)
        timestamps (array): Timestamps corresponding to the signal array
        threshold (float): Threshold for detecting edges (default 0.5)
        
    Returns:
        array: Indices of rising edges in the signal
    """
    signal = np.asarray(signal)
    if len(signal) == 0:
        return np.array([])

    above_thresh = signal >= threshold
    rising = (above_thresh[1:] == True) & (above_thresh[:-1] == False)
    edge_indices = np.where(rising)[0] + 1  # +1 offset because we shifted by 1
    return edge_indices

def detect_falling_edges(signal, timestamps, threshold=0.5):
    """
    Identify the indices of falling edges (TTL pulses) in the given signal.
    
    Args:
        signal (array): The signal array (0s and 1s)
        timestamps (array): Timestamps corresponding to the signal array
        threshold (float): Threshold for detecting edges (default 0.5)
        
    Returns:
        array: Indices of falling edges in the signal
    """
    signal = np.asarray(signal)
    if len(signal) == 0:
        return np.array([])

    above_thresh = signal >= threshold
    falling = (above_thresh[1:] == False) & (above_thresh[:-1] == True)
    edge_indices = np.where(falling)[0] + 1  # +1 offset because we shifted by 1
    return edge_indices

def extract_pulse_durations(signal, timestamps, threshold=0.5, min_duration_ms=0.01):
    """
    Extract start times and durations of pulses from a binary signal.
    
    Args:
        signal (array): The binary signal (0s and 1s)
        timestamps (array): Timestamps corresponding to the signal
        threshold (float): Threshold for detecting pulses (default 0.5)
        min_duration_ms (float): Minimum pulse duration in milliseconds (default 0.01ms)
        
    Returns:
        tuple: (start_times, durations) - arrays of pulse start times and durations in seconds
    """
    # Find rising and falling edges
    rise_indices = detect_rising_edges(signal, timestamps, threshold)
    fall_indices = detect_falling_edges(signal, timestamps, threshold)
    
    # Ensure we have matching pairs (if signal starts high, discard first falling edge)
    if len(fall_indices) > 0 and (len(rise_indices) == 0 or fall_indices[0] < rise_indices[0]):
        fall_indices = fall_indices[1:]
        
    # Ensure we have matching pairs (if signal ends high, discard last rising edge)
    if len(rise_indices) > len(fall_indices):
        rise_indices = rise_indices[:len(fall_indices)]
    
    # Calculate start times and durations
    start_times = timestamps[rise_indices]
    end_times = timestamps[fall_indices]
    
    # Calculate durations in seconds
    durations = end_times - start_times
    
    # Filter out very short pulses if needed
    if min_duration_ms > 0:
        valid_mask = durations >= (min_duration_ms / 1000.0)  # Convert ms to seconds
        start_times = start_times[valid_mask]
        durations = durations[valid_mask]
    
    return start_times, durations

def timeseries_to_intervals(timestamps, signal, HIGH=1, filter_short=False, min_duration_ms=50):
    """
    Convert timestamps and on/off signal to NWB intervals.
    
    Args:
        timestamps (array): Signal timestamps
        signal (array): The binary signal (0s and 1s)
        HIGH (int): Value representing the ON state (default 1)
        filter_short (bool): Whether to filter out short events (default False)
        min_duration_ms (int): Minimum duration in milliseconds to keep an event (default 50ms)
        
    Returns:
        tuple: (intervals array, interval timestamps array)
    """
    timestamps = np.array(timestamps)
    signal = np.array(signal)

    if HIGH == 0:
        HIGH = -1

    # Calculate state changes
    diff = HIGH * np.diff(signal, prepend=0)
    
    # Find indices of on and off times
    change_indices = np.where(diff != 0)[0]
    
    if len(change_indices) == 0:
        return np.array([]), np.array([])
        
    # Ensure even number of changes (start and end for each event)
    if len(change_indices) % 2 != 0:
        change_indices = np.append(change_indices, len(signal) - 1)

    if filter_short:
        # Calculate event durations
        start_indices = change_indices[::2]
        end_indices = change_indices[1::2]
        
        # Convert to milliseconds for comparison
        durations_sec = timestamps[end_indices] - timestamps[start_indices]
        durations_ms = durations_sec * 1000.0
        
        # Filter events based on duration
        long_event_mask = durations_ms >= min_duration_ms
        filtered_start_indices = start_indices[long_event_mask]
        filtered_end_indices = end_indices[long_event_mask]
        
        # Create intervals and timestamps
        interval_timestamps = np.concatenate((
            timestamps[filtered_start_indices],
            timestamps[filtered_end_indices]
        ))
        
        intervals = np.concatenate((
            HIGH * np.ones_like(filtered_start_indices),
            -HIGH * np.ones_like(filtered_end_indices)
        ))
    else:
        # Create intervals and timestamps for all events
        interval_timestamps = timestamps[change_indices]
        intervals = diff[change_indices]
    
    # Sort by timestamp to maintain chronological order
    sort_indices = np.argsort(interval_timestamps)
    interval_timestamps = interval_timestamps[sort_indices]
    intervals = intervals[sort_indices]
    
    return intervals, interval_timestamps

def headtracker_to_nwb(
    session_dict,
    session_metadata=None,
    experimenter="",
    institution="",
    lab="",
    subject_species="Mouse",
    session_description="Head tracking experiment with laser pulses",
):
    """
    Convert head sensor data and Arduino DAQ data to NWB format,
    using synchronized timestamps from the post-processing pipeline.
    
    Args:
        session_directory (Path or str): Path to the session directory
        output_directory (Path or str, optional): Directory to save the NWB file (defaults to session_directory)
        session_metadata (dict, optional): Additional metadata about the session
        experimenter (str): Name of the experimenter
        institution (str): Institution where the experiment was conducted
        lab (str): Laboratory where the experiment was conducted
        subject_species (str): Species of the subject
        session_description (str): Description of the session
        video_filename (str, optional): Name of video file if available
        
    Returns:
        Path: Path to the created NWB file
    """
    # Convert to Path objects
    session_directory = Path(session_dict.get("directory", None))
    
    # Make sure output directory exists
    session_directory.mkdir(parents=True, exist_ok=True)
    
    # Extract session info from directory name
    session_id = session_directory.name
    
    # Extract mouse ID from session ID (format: YYMMDD_HHMMSS_mouseID)
    mouse_id = session_dict.get("mouse_id", "unknown_mouse")
    body_sensor = session_dict.get("body_sensor", False)
    
    # Look for required files
    synced_data_file = session_dict.get("synced_data_json", None)
    head_sensor_h5_file = session_dict.get("raw_data", {}).get("head_sensor_h5", None)
    body_sensor_h5_file = session_dict.get("raw_data", {}).get("body_sensor_h5", None)
    arduino_daq_h5_file = session_dict.get("raw_data", {}).get("arduino_daq_h5", None)
    session_metadata_path = session_dict.get("raw_data", {}).get("metadata", None)
    session_video = session_dict.get("raw_data", {}).get("video", None)
    
    # Check if we have all necessary files
    if not synced_data_file:
        raise FileNotFoundError(f"No synced data file found in {session_directory}")
    
    if not head_sensor_h5_file:
        raise FileNotFoundError(f"No head sensor HDF5 file found in {session_directory}")
    
    if not arduino_daq_h5_file:
        raise FileNotFoundError(f"No Arduino DAQ HDF5 file found in {session_directory}")
    
    if body_sensor and not body_sensor_h5_file:
        raise FileNotFoundError(f"Body sensor indicated but no body sensor HDF5 file found in {session_directory}")
    
    # Load synced data
    with open(synced_data_file, 'r') as f:
        synced_data = json.load(f)

    # Load session metadata
    with open(session_metadata_path, 'r') as f:
        session_metadata = json.load(f)
    
    # Get experiment parameters from metadata or use defaults
    head_sensor_rotation_angle = session_metadata.get("head_sensor_rotation_angle", 0)
    if body_sensor:
        body_sensor_rotation_angle = session_metadata.get("body_sensor_rotation_angle", 0)
    else:
        body_sensor_rotation_angle = None
    stim_times_ms = session_metadata.get("stim_times_ms", [])
    num_cycles = session_metadata.get("num_cycles", 0)
    brain_laser_power_mW = session_metadata.get("brain_laser_power_mW", 0)
    set_laser_power_mW = session_metadata.get("set_laser_power_mW", 0)
    notes = session_metadata.get("notes", "")
    
    # Parse session start time from session ID (format: YYMMDD_HHMMSS_mouseID)
    try:
        session_start = datetime.strptime(session_id[:13], '%y%m%d_%H%M%S')
        session_start = session_start.replace(tzinfo=tz.gettz('Europe/London'))
    except ValueError:
        # Fallback to current time if parsing fails
        session_start = datetime.now(tz.gettz('Europe/London'))
    
    # Create NWB file with metadata
    nwbfile = NWBFile(
        session_description=session_description,
        identifier=str(uuid4()),
        session_start_time=session_start,
        experimenter=experimenter,
        institution=institution,
        lab=lab,
        experiment_description=(
            f"Head tracking experiment - " 
            f"Head sensor rotation angle: {head_sensor_rotation_angle}°, "
            f"Body sensor rotation angle: {body_sensor_rotation_angle}°, "
            f"Stim times (ms): {stim_times_ms}, "
            f"Num cycles: {num_cycles}, "
            f"Brain laser power: {brain_laser_power_mW}mW, "
            f"Set laser power: {set_laser_power_mW}mW, "
            f"Notes: {notes}"
        )
    )
    
    # Add subject information
    nwbfile.subject = Subject(
        subject_id=mouse_id,
        species=subject_species
    )
    
    # --------------------------------------------------------------------------
    # Load head sensor data and add with synced timestamps
    # --------------------------------------------------------------------------
    # First, load raw head sensor data
    with h5py.File(head_sensor_h5_file, 'r') as h5f:
        message_ids = np.array(h5f['message_ids'])
        yaw_data = np.array(h5f['yaw_data'])
        roll_data = np.array(h5f['roll_data'])
        pitch_data = np.array(h5f['pitch_data'])
    
    # Extract synchronized head sensor data from synced_data
    if 'head_sensor' in synced_data and synced_data['head_sensor']:
        head_synced_timestamps = np.array(synced_data['head_sensor'].get('synced_timestamps', []))
        
        # Filter out None/null values from synced timestamps (keep only valid entries)
        valid_indices = [i for i, val in enumerate(head_synced_timestamps) if val is not None]
        if valid_indices:
            # Create synchronized arrays
            synced_yaw = np.array([yaw_data[i] for i in valid_indices])
            synced_roll = np.array([roll_data[i] for i in valid_indices])
            synced_pitch = np.array([pitch_data[i] for i in valid_indices])
            synced_timestamps = np.array([head_synced_timestamps[i] for i in valid_indices])

            print(f"Syncing {len(message_ids)} head sensor messages with {len(synced_timestamps)} pulses...")
            
            # Create a behavioral module for head tracking data
            behavior_module = nwbfile.create_processing_module(
                name='head_sensor_data',
                description='Head orientation tracking data'
            )
            
            # Create and add yaw spatial series
            yaw_series = SpatialSeries(
                name='yaw',
                description='Yaw (horizontal rotation, left/right movement) of the head in degrees',
                data=synced_yaw,
                timestamps=synced_timestamps,
                reference_frame='Initial head position at recording start',
                unit='degrees',
                conversion=1.0
            )
            behavior_module.add_data_interface(yaw_series)
            
            # Create and add pitch spatial series
            pitch_series = SpatialSeries(
                name='pitch',
                description='Pitch (vertical rotation, up/down movement) of the head in degrees',
                data=synced_pitch,
                timestamps=synced_timestamps,
                reference_frame='Initial head position at recording start',
                unit='degrees',
                conversion=1.0
            )
            behavior_module.add_data_interface(pitch_series)
            
            # Create and add roll spatial series
            roll_series = SpatialSeries(
                name='roll',
                description='Roll (rotation around long axis, tilting) of the head in degrees',
                data=synced_roll,
                timestamps=synced_timestamps,
                reference_frame='Initial head position at recording start',
                unit='degrees',
                conversion=1.0
            )
            behavior_module.add_data_interface(roll_series)
        else:
            print("Warning: No valid synchronized timestamps found for head sensor data")
    else:
        print("Warning: No head sensor data found in synced_data.json")

    print("Head sensor data added to NWB file")
    # --------------------------------------------------------------------------
    # If present, load body sensor data and add with synced timestamps
    # --------------------------------------------------------------------------
    # Load raw body sensor data
    if body_sensor and body_sensor_h5_file:
        with h5py.File(body_sensor_h5_file, 'r') as h5f:
            message_ids = np.array(h5f['message_ids'])
            yaw_data = np.array(h5f['yaw_data'])
            roll_data = np.array(h5f['roll_data'])
            pitch_data = np.array(h5f['pitch_data'])
        
        # Extract synchronized head sensor data from synced_data
        if 'body_sensor' in synced_data and synced_data['body_sensor']:
            body_synced_timestamps = np.array(synced_data['body_sensor'].get('synced_timestamps', []))
            
            # Filter out None/null values from synced timestamps (keep only valid entries)
            valid_indices = [i for i, val in enumerate(body_synced_timestamps) if val is not None]
            if valid_indices:
                # Create synchronized arrays
                synced_yaw = np.array([yaw_data[i] for i in valid_indices])
                synced_roll = np.array([roll_data[i] for i in valid_indices])
                synced_pitch = np.array([pitch_data[i] for i in valid_indices])
                synced_timestamps = np.array([body_synced_timestamps[i] for i in valid_indices])

                print(f"Syncing {len(message_ids)} body sensor messages with {len(synced_timestamps)} pulses...")
                
                # Create a behavioral module for body tracking data
                behavior_module = nwbfile.create_processing_module(
                    name='body_sensor_data',
                    description='Body orientation tracking data'
                )
                
                # Create and add yaw spatial series
                yaw_series = SpatialSeries(
                    name='yaw',
                    description='Yaw (horizontal rotation, left/right movement) of the body in degrees',
                    data=synced_yaw,
                    timestamps=synced_timestamps,
                    reference_frame='Initial head position at recording start',
                    unit='degrees',
                    conversion=1.0
                )
                behavior_module.add_data_interface(yaw_series)
                
                # Create and add pitch spatial series
                pitch_series = SpatialSeries(
                    name='pitch',
                    description='Pitch (vertical rotation, up/down movement) of the body in degrees',
                    data=synced_pitch,
                    timestamps=synced_timestamps,
                    reference_frame='Initial head position at recording start',
                    unit='degrees',
                    conversion=1.0
                )
                behavior_module.add_data_interface(pitch_series)
                
                # Create and add roll spatial series
                roll_series = SpatialSeries(
                    name='roll',
                    description='Roll (rotation around long axis, tilting) of the body in degrees',
                    data=synced_roll,
                    timestamps=synced_timestamps,
                    reference_frame='Initial head position at recording start',
                    unit='degrees',
                    conversion=1.0
                )
                behavior_module.add_data_interface(roll_series)
            else:
                print("Warning: No valid synchronized timestamps found for body sensor data")
        else:
            print("Warning: No body sensor data found in synced_data.json")
    
    # --------------------------------------------------------------------------
    # Process stimulation data from the Arduino DAQ channels
    # --------------------------------------------------------------------------
    # Load the Arduino DAQ data to get channel information
    with h5py.File(arduino_daq_h5_file, 'r') as h5f:
        daq_timestamps = np.array(h5f['timestamps'])
        
        # Get list of available channels
        available_channels = list(h5f['channel_data'].keys())
        
        # Get channel data (we'll use this for event extraction, not for direct timestamps)
        channel_data = {}
        for channel_name in available_channels:
            channel_data[channel_name] = np.array(h5f['channel_data'][channel_name])
    
    # --------------------------------------------------------------------------
    # Add LASER channel events with accurate durations
    # --------------------------------------------------------------------------
    if 'LASER_SYNC' in channel_data:
        # Extract pulse start times and durations using the improved method
        laser_start_times, laser_durations = extract_pulse_durations(
            channel_data['LASER_SYNC'], 
            daq_timestamps,
            min_duration_ms=0.01  # Very low minimum to capture all pulses
        )
        
        if len(laser_start_times) > 0:
            # Create a TimeSeries for the laser stimulation events with actual durations
            laser_ts = TimeSeries(
                name='laser_stimulation',
                description='Laser stimulation events with accurate pulse durations',
                data=laser_durations,  # Now using actual durations instead of just 1s
                timestamps=laser_start_times,
                unit='seconds',
                comments=(f"Laser power: {brain_laser_power_mW}mW, {len(laser_start_times)} events detected. "
                          f"Data values represent actual pulse durations in seconds.")
            )
            nwbfile.add_stimulus(laser_ts)
            
            # Show distribution of durations (quantiles)
            percentiles = [0, 10, 25, 50, 75, 90, 100]
            duration_percentiles = np.percentile(laser_durations, percentiles)
            print("  Duration distribution (seconds):")
            for p, val in zip(percentiles, duration_percentiles):
                print(f"    {p}th percentile: {val:.6f}s")
            
            # Try to identify typical pulse durations (clusters)
            from scipy.cluster.vq import kmeans, vq
            
            # Use k-means to find the main duration clusters (if scipy is available)
            try:
                # Only use k-means if we have enough unique durations
                unique_durations = np.unique(laser_durations)
                if len(unique_durations) >= 2:
                    # Estimate k (number of clusters) based on expected stim durations from metadata
                    k = len(stim_times_ms) if stim_times_ms else min(5, len(unique_durations))
                    k = max(2, min(k, len(unique_durations)))  # At least 2, at most unique values
                    
                    # Run k-means clustering on durations
                    centroids, _ = kmeans(laser_durations.reshape(-1, 1), k)
                    centroids = centroids.flatten()
                    centroids.sort()
                    
                    # Assign each duration to a cluster
                    idx, _ = vq(laser_durations.reshape(-1, 1), centroids.reshape(-1, 1))
                    
                    # Count pulses in each cluster
                    print("  Identified pulse duration patterns:")
                    for i, centroid in enumerate(centroids):
                        count = np.sum(idx == i)
                        print(f"    ~{centroid*1000:.2f}ms: {count} pulses ({count/len(laser_durations)*100:.1f}%)")
            except (ImportError, Exception) as e:
                # Skip clustering if scipy is not available or other error occurs
                pass
    else:
        print("Warning: No LASER_SYNC channel found in Arduino DAQ data")
    
    # --------------------------------------------------------------------------
    # Add video data if available
    # --------------------------------------------------------------------------
    if 'camera' in synced_data and synced_data['camera']:
        camera_synced_timestamps = synced_data['camera'].get('synced_timestamps', [])
        
        # Find valid timestamps (not None/null)
        valid_indices = [i for i, val in enumerate(camera_synced_timestamps) if val is not None]
        
        if valid_indices and session_video:            
            # Get valid timestamps
            valid_timestamps = [camera_synced_timestamps[i] for i in valid_indices]
            
            # Create ImageSeries for video
            video_series = ImageSeries(
                name='behavior_video',
                description='Behavior tracking video',
                external_file=[f'./{session_video}'],
                format='external',
                starting_frame=[0],
                timestamps=valid_timestamps,
                unit='n.a.'
            )
            nwbfile.add_acquisition(video_series)
    
    # Create output filename from session ID
    output_filename = f"{session_id}_headtracker.nwb"
    output_path = session_directory / output_filename
    
    # Write the NWB file
    with NWBHDF5IO(output_path, 'w') as io:
        io.write(nwbfile)
    
    print(f"Created NWB file: {output_path}")
    return output_path
