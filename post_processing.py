import os
import json
import numpy as np
import h5py
import traceback
from pathlib import Path

from utils.video_processor import process_cohort_videos
from utils.cohort_folder_openfield import Cohort_folder_openfield
from utils.openfield_analysis_manager import Analysis_manager_openfield


def process_directory(cohort_folder_path):
    """
    Processes a single cohort directory:
    - Creates session_info
    - Runs the sync
    """
    print(f"\nProcessing directory: {cohort_folder_path}")
    
    # Initialize the cohort folder
    cohort_folder = Cohort_folder_openfield(cohort_folder_path)    
    cohort_info = cohort_folder.cohort

    # Process cohort videos
    process_cohort_videos(cohort_folder_path)

    # Gather all sessions to process
    sessions_to_process = []
    for mouse, mouse_data in cohort_info["mice"].items():
        for session in mouse_data["sessions"]:
            session_info = cohort_folder.get_session(session)
            sessions_to_process.append(session_info)

    print("Starting processing sessions...")
    
    # Run processing for each session
    for session in sessions_to_process:
        processor = Analysis_manager_openfield(session)
        # If Analysis_manager_openfield has a method to execute the analysis, call it here
        # For example:
        # processor.run_analysis()
    
    print(f"Processing complete for directory: {cohort_folder_path}")

def main():
    """
    Main function to process multiple cohort directories.
    """
    # Define a list of cohort folder paths
    cohort_folder_paths = [
        r"D:\2501-Pitx2_opto_inhib_headsensor",
        r"D:\2701_Pitx2_opto_excite_headsensor",
        # Add more directories as needed
    ]

    print("Starting main processing of multiple directories...")
    
    # Iterate through each directory and process
    for cohort_folder_path in cohort_folder_paths:
        process_directory(cohort_folder_path)

    print("All directories have been processed successfully.")

if __name__ == "__main__":
    main()