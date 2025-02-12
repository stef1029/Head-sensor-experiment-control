import os
import json
import numpy as np
import h5py
import traceback
import subprocess
from pathlib import Path
from datetime import datetime
import time
import sys
import re

from utils.video_processor import process_cohort_videos
from utils.cohort_folder_openfield import Cohort_folder_openfield
from utils.openfield_analysis_manager import Analysis_manager_openfield

def sync_with_cephfs(local_dir, remote_dir):
    """
    Synchronizes local directory with remote CephFS directory using rsync via Cygwin's bash.
    """
    # Ensure trailing slashes for directories
    if not local_dir.endswith('/'):
        local_dir += '/'
    if not remote_dir.endswith('/'):
        remote_dir += '/'
    
    # Full path to Cygwin's bash executable
    bash_path = r"C:\cygwin64\bin\bash.exe"
    
    # Build the rsync command (the paths are in Cygwin format)
    rsync_cmd = (
        f'rsync -avz --no-group --progress --info=progress2 --stats --partial --delete '
        f'"{local_dir}" "{remote_dir}"'
    )
    
    # Build the full shell command, using single quotes outside to preserve inner double quotes
    shell_command = f'"{bash_path}" -l -c \'{rsync_cmd}\''
    
    print(f"Executing command: {shell_command}")
    print(f"Source path: {local_dir}")
    print(f"Destination path: {remote_dir}")
    
    try:
        process = subprocess.Popen(
            shell_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            shell=True
        )
        
        while True:
            stdout_line = process.stdout.readline()
            stderr_line = process.stderr.readline()
            
            if stdout_line == '' and stderr_line == '' and process.poll() is not None:
                break
                
            if stdout_line:
                print(stdout_line.strip())
            if stderr_line:
                print(f"ERROR: {stderr_line.strip()}", file=sys.stderr)
        
        process.wait()
        
        if process.returncode == 0:
            print("\nSync completed successfully.\n")
        else:
            print(f"\nError occurred during rsync: Return code {process.returncode}")
            _, stderr = process.communicate()
            if stderr:
                print(f"Error details:\n{stderr}")
            
    except FileNotFoundError:
        print("Error: rsync command not found. Please ensure rsync is installed and in your PATH.")
    except Exception as e:
        print(f"Unexpected error occurred during rsync: {e}")
        print(f"Error details:\n{traceback.format_exc()}")

def wait_until_time(target_hour):
    """
    Waits until a specific hour before proceeding.
    
    Args:
        target_hour (int): Hour to wait for (24-hour format)
    """
    while True:
        current_time = datetime.now()
        if current_time.hour >= target_hour:
            print(f"Current time {current_time.strftime('%H:%M:%S')} - Proceeding with the script...")
            break
        else:
            remaining_time = target_hour - current_time.hour
            print(f"Waiting for {remaining_time} more hour(s) until {target_hour}:00. Current time: {current_time.strftime('%H:%M:%S')}")
            time.sleep(60)

def process_directory(cohort_directory):
    """
    Processes a single cohort directory and syncs with CephFS.
    Only processes sessions where preliminary analysis hasn't been done yet.
    
    Args:
        cohort_directory (dict): Dictionary containing local and remote paths
    """
    print(f"\nProcessing directory: {cohort_directory['local']}")
    
    # Initialize the cohort folder
    cohort_folder = Cohort_folder_openfield(cohort_directory['local'])    
    cohort_info = cohort_folder.cohort

    # Gather sessions that need processing (preliminary analysis not done yet)
    sessions_to_process = []
    for mouse, mouse_data in cohort_info["mice"].items():
        for session in mouse_data["sessions"]:
            session_info = cohort_folder.get_session(session)
            
            # Check if raw data is present and preliminary analysis hasn't been done
            raw_data_present = session_info["raw_data"].get("is_all_raw_data_present?", False)
            analysis_done = session_info["processed_data"].get("preliminary_analysis_done?", False)
            
            if raw_data_present and not analysis_done:
                sessions_to_process.append(session_info)
                print(f"Found unprocessed session: {session} for mouse {mouse}")
            elif not raw_data_present:
                print(f"Skipping session {session} for mouse {mouse} - Missing raw data")
            elif analysis_done:
                print(f"Skipping session {session} for mouse {mouse} - Already processed")

    if sessions_to_process:
        print(f"\nFound {len(sessions_to_process)} sessions that need processing...")
        process_cohort_videos(cohort_directory['local'])

    print("Starting processing sessions...")
    
    # Run processing for each session
    for session in sessions_to_process:
        processor = Analysis_manager_openfield(session)
        # Add your analysis execution here
        # processor.run_analysis()
    
    # Sync to CephFS after processing
    print(f"\nSyncing {cohort_directory['rsync_local']} with CephFS server...\n")
    sync_with_cephfs(cohort_directory['rsync_local'], cohort_directory['rsync_cephfs_mapped'])
    
    print(f"Processing and sync complete for directory: {cohort_directory['local']}")

def main():
    """
    Main function to process multiple cohort directories and sync with CephFS.
    """
    # Define cohort directories with both local and remote paths using Windows paths
    cohort_directories = []

    cohort_directory = {'local': Path(r"D:\2501_Pitx2_opto_inhib_headsensor"),
                    'cephfs_mapped': Path(r"W:\2501_IMU_experiments_data\2501_Pitx2_opto_inhib_headsensor_Stefan"),
                    'cephfs_hal': r"/cephfs2/srogers/2501_IMU_experiments_data/2501_Pitx2_opto_inhib_headsensor_Stefan",
                    'rsync_local': r"/cygdrive/d/2501_Pitx2_opto_inhib_headsensor",
                    'rsync_cephfs_mapped': r"/cygdrive/w/2501_IMU_experiments_data/2501_Pitx2_opto_inhib_headsensor_Stefan"}
    cohort_directories.append(cohort_directory)

    cohort_directory = {'local': Path(r"D:\2701_Pitx2_opto_excite_headsensor"),
                    'cephfs_mapped': Path(r"W:\2501_IMU_experiments_data\2501_Pitx2_opto_excite_headsensor_Lynn"),
                    'cephfs_hal': r"/cephfs2/srogers/2501_IMU_experiments_data/2501_Pitx2_opto_excite_headsensor_Lynn",
                    'rsync_local': r"/cygdrive/d/2701_Pitx2_opto_excite_headsensor",
                    'rsync_cephfs_mapped': r"/cygdrive/w/2501_IMU_experiments_data/2501_Pitx2_opto_excite_headsensor_Lynn"}
    cohort_directories.append(cohort_directory)

    cohort_directory = {'local': Path(r"D:\1102_VM_opto_excite_headsensor"),
                    'cephfs_mapped': Path(r"W:\2501_IMU_experiments_data\1102_VM-opto-excite-headsensor_Dan"),
                    'cephfs_hal': r"/cephfs2/srogers/2501_IMU_experiments_data/1102_VM-opto-excite-headsensor_Dan",
                    'rsync_local': r"/cygdrive/d/2701_Pitx2_opto_excite_headsensor",
                    'rsync_cephfs_mapped': r"/cygdrive/w/2501_IMU_experiments_data/1102_VM-opto-excite-headsensor_Dan"}
    cohort_directories.append(cohort_directory)

    print("Starting main processing of multiple directories...")
    
    # Optional: Wait until after work hours (e.g., 10 PM) before starting
    # wait_until_time(22)  # Uncomment to enable waiting until 10 PM
    
    # Process each directory and sync
    for cohort_directory in cohort_directories:
        process_directory(cohort_directory)

    print("All directories have been processed and synced successfully.")

if __name__ == "__main__":
    main()