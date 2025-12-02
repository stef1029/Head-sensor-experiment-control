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
from utils.cohort_folder_openfield import Cohort_folder
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

def find_sessions_to_process(cohort_directory, refresh=False):
    """
    Given a cohort directory info dict, return a list of sessions that need processing
    (where raw data is present but preliminary analysis not yet done).
    
    Args:
        cohort_directory (dict): Dictionary containing cohort directory information
        refresh (bool): If True, include sessions that have already been processed for reprocessing
        
    Returns:
        list: List of session information dictionaries to process
    """
    print(f"\nExamining directory: {cohort_directory['local']}")

    cohort_folder = Cohort_folder(cohort_directory['local'])
    cohort_info = cohort_folder.cohort
    
    sessions_to_process = []
    for mouse, mouse_data in cohort_info["mice"].items():
        for session in mouse_data["sessions"]:
            session_info = cohort_folder.get_session(session)
            
            raw_data_present = session_info["raw_data"].get("is_all_raw_data_present?", False)
            analysis_done = session_info["processed_data"].get("preliminary_analysis_done?", False)
            
            if raw_data_present:
                if not analysis_done or refresh:
                    # Include session if:
                    # - It hasn't been processed yet, OR
                    # - refresh is True (reprocess even if already done)
                    sessions_to_process.append(session_info)
                    
                    if analysis_done and refresh:
                        print(f"  Reprocessing session: {session} for mouse {mouse} (refresh requested)")
                    else:
                        print(f"  Found unprocessed session: {session} for mouse {mouse}")
                else:
                    print(f"  Skipping session {session} for mouse {mouse} - Already processed")
            else:
                print(f"  Skipping session {session} for mouse {mouse} - Missing raw data")
    
    return sessions_to_process

def run_postprocessing_for_sessions(sessions_to_process):
    """
    For each session in sessions_to_process, run the analysis logic.
    """
    print(f"Starting processing of {len(sessions_to_process)} sessions...")
    for session_info in sessions_to_process:
        Analysis_manager_openfield(session_info)

def main():
    """
    Main function to process multiple cohort directories and sync with CephFS.
    We have three cohorts defined. The first two will be processed
    using the "video-compress-then-postprocess-then-rsync" sequence
    in one big block, while the third continues with the original logic.
    """
    # Define cohort directories with both local and remote paths using Windows paths
    cohort_directories = []

    # 1) 2501_Pitx2_opto_inhib_headsensor
    # cohort_directory_1 = {
    #     'local': Path(r"D:\2501_Pitx2_opto_inhib_headsensor"),
    #     'cephfs_mapped': Path(r"W:\2501_IMU_experiments_data\2501_Pitx2_opto_inhib_headsensor_Stefan"),
    #     'cephfs_hal': r"/cephfs2/srogers/2501_IMU_experiments_data/2501_Pitx2_opto_inhib_headsensor_Stefan",
    #     'rsync_local': r"/cygdrive/d/2501_Pitx2_opto_inhib_headsensor",
    #     'rsync_cephfs_mapped': r"/cygdrive/w/2501_IMU_experiments_data/2501_Pitx2_opto_inhib_headsensor_Stefan"
    # }
    # cohort_directories.append(cohort_directory_1)

    # 2) 2701_Pitx2_opto_excite_headsensor
    # cohort_directory_2 = {
    #     'local': Path(r"D:\2701_Pitx2_opto_excite_headsensor"),
    #     'cephfs_mapped': Path(r"W:\2501_IMU_experiments_data\2501_Pitx2_opto_excite_headsensor_Lynn"),
    #     'cephfs_hal': r"/cephfs2/srogers/2501_IMU_experiments_data/2501_Pitx2_opto_excite_headsensor_Lynn",
    #     'rsync_local': r"/cygdrive/d/2701_Pitx2_opto_excite_headsensor",
    #     'rsync_cephfs_mapped': r"/cygdrive/w/2501_IMU_experiments_data/2501_Pitx2_opto_excite_headsensor_Lynn"
    # }
    # cohort_directories.append(cohort_directory_2)

    # 3) 1102_VM_opto_excite_headsensor
    # cohort_directory_3 = {
    #     'local': Path(r"D:\1102_VM_opto_excite_headsensor"),
    #     'cephfs_mapped': Path(r"W:\2501_IMU_experiments_data\1102_VM-opto-excite-headsensor_Dan"),
    #     'cephfs_hal': r"/cephfs2/srogers/2501_IMU_experiments_data/1102_VM-opto-excite-headsensor_Dan",
    #     'rsync_local': r"/cygdrive/d/1102_VM_opto_excite_headsensor",
    #     'rsync_cephfs_mapped': r"/cygdrive/w/2501_IMU_experiments_data/1102_VM-opto-excite-headsensor_Dan"
    # }
    # cohort_directories.append(cohort_directory_3)

    # 4) 20250303_Pitx2_opto_excite_headsensor
    # cohort_directory_4 = {
    #     'local': Path(r"d:\20250303_Pitx2_opto_excite_headsensor"),
    #     'cephfs_mapped': Path(r"W:\2501_IMU_experiments_data\2501_Pitx2_opto_excite_headsensor_Lynn"),
    #     'cephfs_hal': r"/cephfs2/srogers/2501_IMU_experiments_data/2501_Pitx2_opto_excite_headsensor_Lynn",
    #     'rsync_local': r"/cygdrive/d/2701_Pitx2_opto_excite_headsensor",
    #     'rsync_cephfs_mapped': r"/cygdrive/w/2501_IMU_experiments_data/2501_Pitx2_opto_excite_headsensor_Lynn"
    # } 
    # cohort_directories.append(cohort_directory_4)
    
    
    # # 5) 20250405_Pitx2_opto_excite_headsensor
    # cohort_directory_5 = {
    #     'local': Path(r"c:\20250405_Pitx2_opto_excite_headsensor"),
    #     # 'cephfs_mapped': Path(r"W:\2501_IMU_experiments_data\2501_Pitx2_opto_excite_headsensor_Lynn"),
    #     # 'cephfs_hal': r"/cephfs2/srogers/2501_IMU_experiments_data/2501_Pitx2_opto_excite_headsensor_Lynn",
    #     # 'rsync_local': r"/cygdrive/d/2701_Pitx2_opto_excite_headsensor",
    #     # 'rsync_cephfs_mapped': r"/cygdrive/w/2501_IMU_experiments_data/2501_Pitx2_opto_excite_headsensor_Lynn"
    # } 
    # cohort_directories.append(cohort_directory_5)

    # cohort_directory_5 = {
    #     'local': Path(r"c:\DATA\250806_Pitx2_cFOS_opt"),
    #     # 'cephfs_mapped': Path(r"W:\2501_IMU_experiments_data\2501_Pitx2_opto_excite_headsensor_Lynn"),
    #     # 'cephfs_hal': r"/cephfs2/srogers/2501_I  MU_experiments_data/2501_Pitx2_opto_excite_headsensor_Lynn",
    #     # 'rsync_local': r"/cygdrive/d/2701_Pitx2_opto_excite_headsensor",
    #     # 'rsync_cephfs_mapped': r"/cygdrive/w/2501_IMU_experiments_data/2501_Pitx2_opto_excite_headsensor_Lynn"
    # } 
    # cohort_directories.append(cohort_directory_5)

    # cohort_directory = {
    #     'local': Path(r"C:\DATA\250416_pitx2_stim_check"),
    #     # 'cephfs_mapped': Path(r"W:\2501_IMU_experiments_data\2501_Pitx2_opto_excite_headsensor_Lynn"),
    #     # 'cephfs_hal': r"/cephfs2/srogers/2501_IMU_experiments_data/2501_Pitx2_opto_excite_headsensor_Lynn",
    #     # 'rsync_local': r"/cygdrive/c/DATA/250416_pitx2_stim_check",
    #     # 'rsync_cephfs_mapped': r"/cygdrive/w/2501_IMU_experiments_data/2501_Pitx2_opto_excite_headsensor_Lynn"
    # } 
    # cohort_directories.append(cohort_directory)

    # cohort_directory = {
    #     'local': Path(r"D:\250421_VM_opto_excite_headsensor"),
    #     # 'cephfs_mapped': Path(r"W:\2501_IMU_experiments_data\2501_Pitx2_opto_excite_headsensor_Lynn"),
    #     # 'cephfs_hal': r"/cephfs2/srogers/2501_IMU_experiments_data/2501_Pitx2_opto_excite_headsensor_Lynn",
    #     # 'rsync_local': r"/cygdrive/c/DATA/250416_pitx2_stim_check",
    #     # 'rsync_cephfs_mapped': r"/cygdrive/w/2501_IMU_experiments_data/2501_Pitx2_opto_excite_headsensor_Lynn"
    # } 
    # cohort_directories.append(cohort_directory)

    # cohort_directory = {
    #     'local': Path(r"C:\DATA\250423_opto_inhibition_SC_bilateral"),
    #     # 'cephfs_mapped': Path(r"W:\2501_IMU_experiments_data\2501_Pitx2_opto_excite_headsensor_Lynn"),
    #     # 'cephfs_hal': r"/cephfs2/srogers/2501_IMU_experiments_data/2501_Pitx2_opto_excite_headsensor_Lynn",
    #     # 'rsync_local': r"/cygdrive/c/DATA/250416_pitx2_stim_check",
    #     # 'rsync_cephfs_mapped': r"/cygdrive/w/2501_IMU_experiments_data/2501_Pitx2_opto_excite_headsensor_Lynn"
    # } 
    # cohort_directories.append(cohort_directory)

    # cohort_directory = {
    #     'local': Path(r"C:\DATA\250603_opto_excite_SC_sst"),
    #     # 'cephfs_mapped': Path(r"W:\2501_IMU_experiments_data\2501_Pitx2_opto_excite_headsensor_Lynn"),
    #     # 'cephfs_hal': r"/cephfs2/srogers/2501_IMU_experiments_data/2501_Pitx2_opto_excite_headsensor_Lynn",
    #     # 'rsync_local': r"/cygdrive/c/DATA/250416_pitx2_stim_check",
    #     # 'rsync_cephfs_mapped': r"/cygdrive/w/2501_IMU_experiments_data/2501_Pitx2_opto_excite_headsensor_Lynn"
    # } 
    # cohort_directories.append(cohort_directory)

    # cohort_directory = {
    #     'local': Path(r"C:\DATA\250515_opto_excite_Pitx2_VM"),
    #     # 'cephfs_mapped': Path(r"W:\2501_IMU_experiments_data\2501_Pitx2_opto_excite_headsensor_Lynn"),
    #     # 'cephfs_hal': r"/cephfs2/srogers/2501_IMU_experiments_data/2501_Pitx2_opto_excite_headsensor_Lynn",
    #     # 'rsync_local': r"/cygdrive/c/DATA/250416_pitx2_stim_check",
    #     # 'rsync_cephfs_mapped': r"/cygdrive/w/2501_IMU_experiments_data/2501_Pitx2_opto_excite_headsensor_Lynn"
    # } 
    # cohort_directories.append(cohort_directory)

    # cohort_directory = {
    #     'local': Path(r"C:\DATA\Pitx2_Chemo_Baseline_Movements"),
    #     # 'cephfs_mapped': Path(r"W:\2501_IMU_experiments_data\2501_Pitx2_opto_excite_headsensor_Lynn"),
    #     # 'cephfs_hal': r"/cephfs2/srogers/2501_IMU_experiments_data/2501_Pitx2_opto_excite_headsensor_Lynn",
    #     # 'rsync_local': r"/cygdrive/c/DATA/250416_pitx2_stim_check",
    #     # 'rsync_cephfs_mapped': r"/cygdrive/w/2501_IMU_experiments_data/2501_Pitx2_opto_excite_headsensor_Lynn"
    # } 
    # cohort_directories.append(cohort_directory)

    # cohort_directory = {
    #     'local': Path(r"c:\DATA\250806_Pitx2_cFOS_opt"),
    #     # 'cephfs_mapped': Path(r"W:\2501_IMU_experiments_data\2501_Pitx2_opto_excite_headsensor_Lynn"),
    #     # 'cephfs_hal': r"/cephfs2/srogers/2501_IMU_experiments_data/2501_Pitx2_opto_excite_headsensor_Lynn",
    #     # 'rsync_local': r"/cygdrive/c/DATA/250416_pitx2_stim_check",
    #     # 'rsync_cephfs_mapped': r"/cygdrive/w/2501_IMU_experiments_data/2501_Pitx2_opto_excite_headsensor_Lynn"
    # } 
    # cohort_directories.append(cohort_directory)

    # cohort_directory = {
    #     'local': Path(r"C:\DATA\251008_Pitx2-Catch-Array"),
    #     # 'cephfs_mapped': Path(r"W:\2501_IMU_experiments_data\2501_Pitx2_opto_excite_headsensor_Lynn"),
    #     # 'cephfs_hal': r"/cephfs2/srogers/2501_IMU_experiments_data/2501_Pitx2_opto_excite_headsensor_Lynn",
    #     # 'rsync_local': r"/cygdrive/c/DATA/250416_pitx2_stim_check",
    #     # 'rsync_cephfs_mapped': r"/cygdrive/w/2501_IMU_experiments_data/2501_Pitx2_opto_excite_headsensor_Lynn"
    # } 
    # cohort_directories.append(cohort_directory)

    # cohort_directory = {
    #     'local': Path(r"C:\DATA\251031_opto_Pitx2_excite_medulla"),
    #     # 'cephfs_mapped': Path(r"W:\2501_IMU_experiments_data\2501_Pitx2_opto_excite_headsensor_Lynn"),
    #     # 'cephfs_hal': r"/cephfs2/srogers/2501_IMU_experiments_data/2501_Pitx2_opto_excite_headsensor_Lynn",
    #     # 'rsync_local': r"/cygdrive/c/DATA/250416_pitx2_stim_check",
    #     # 'rsync_cephfs_mapped': r"/cygdrive/w/2501_IMU_experiments_data/2501_Pitx2_opto_excite_headsensor_Lynn"
    # } 
    # cohort_directories.append(cohort_directory)

    cohort_directory = {
        'local': Path(r"D:\Pitx2_Inhib_DTx\Baseline_movements\Saline")} 
    cohort_directories.append(cohort_directory)

    cohort_directory = {
        'local': Path(r"D:\Pitx2_Inhib_DTx\Baseline_movements\DCZ")} 
    cohort_directories.append(cohort_directory)

    # cohort_directory = {
    #     'local': Path(r"D:\test_output")} 
    # cohort_directories.append(cohort_directory)
 
    print("Starting main processing of multiple directories...")

    # Optional: Wait until after work hours (e.g., 10 PM) before starting
    # wait_until_time(22)  # Uncomment to enable waiting until 10 PM

    # ------------------------------------------------------------------
    # PART A: For the cohorts, do the "three-phase" approach:
    #   1) Gather sessions, compress all videos first
    #   2) Post-process all sessions
    #   3) Then rsync
    # ------------------------------------------------------------------
    # Store the sessions that need processing for the cohorts
    sessions_map = {}

    refresh = False  # Set to True to reprocess already processed sessions

    # Phase 1: Gather sessions, compress videos for each
    print("\n=== PHASE 1: Gathering sessions & compressing videos ===")
    for cd in cohort_directories:
        sessions_to_process = find_sessions_to_process(cd, refresh=refresh)
        sessions_map[cd['local']] = sessions_to_process
        if sessions_to_process:
            print(f"\nFound {len(sessions_to_process)} sessions needing processing in {cd['local']}. Compressing videos...")
            process_cohort_videos(cd['local'])
        else:
            print(f"No sessions to process in {cd['local']}. Skipping compression.")

    # Phase 2: Post-process all sessions
    print("\n=== PHASE 2: Post-processing sessions ===")
    for cd in cohort_directories:
        sessions_to_process = sessions_map[cd['local']]
        if sessions_to_process:
            run_postprocessing_for_sessions(sessions_to_process)
        else:
            print(f"No sessions to post-process in {cd['local']}.")

    # Phase 3: Rsync
    # print("\n=== PHASE 3: Syncing changes ===")
    # for cd in cohort_directories:
    #     print(f"Syncing {cd['rsync_local']} to {cd['rsync_cephfs_mapped']}...")
    #     sync_with_cephfs(cd['rsync_local'], cd['rsync_cephfs_mapped'])
    print("\n=== PHASE 3: Syncing switched off. Move files manually. ===")

    print("\nAll requested directories have been processed and synced successfully.")

if __name__ == "__main__":
    main()
