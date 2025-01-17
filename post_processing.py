import os
import json
import numpy as np
import h5py
import traceback
from pathlib import Path

from video_processor import process_cohort_videos
from cohort_folder_openfield import Cohort_folder_openfield
from openfield_analysis_manager import Analysis_manager_openfield


def main():
    """
    Example main function: 
    - Create session_info 
    - Run the sync.
    """
    cohort_folder_path = r"C:\Users\Tripodi Group\Videos\2501 - openfield experiment output"


    cohort_folder = Cohort_folder_openfield(cohort_folder_path)
    cohort_info = cohort_folder.cohort

    process_cohort_videos(cohort_folder_path)

    sessions_to_process = []
    for mouse, mouse_data in cohort_info["mice"].items():
        for session in mouse_data["sessions"]:
            session_info = cohort_folder.get_session(session)
            sessions_to_process.append(session_info)

    print("Starting main function...")
    # Run processing
    for session in sessions_to_process:
        processor = Analysis_manager_openfield(session)
        
    print("Processing complete.")

if __name__ == "__main__":
    main()