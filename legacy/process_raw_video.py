"""
Adapted from the raw video processor in analysis_manager.py - 24th May 2024 SRC
"""
from pathlib import Path
import multiprocessing as mp
import Analysis_scripts.video_processing as vp



def main():
    cohort_folder = r"C:\Users\Tripodi Group\Videos\Head_sensor_output"

    sessions_to_video_process = []

    # for each folder in cohort_folder, find which ones have .bmp files still and then add them to this list: (using pathlib functions)

    for folder in Path(cohort_folder).iterdir():
        if folder.is_dir():
            # print(folder)
            for file in folder.iterdir():
                if file.is_file() and file.suffix == ".bmp":
                    sessions_to_video_process.append(folder)
                    break


    print(len(sessions_to_video_process))


    # processes = 112
    processes = mp.cpu_count()

    for video in sessions_to_video_process:
        print(f"Processing {video}...")
        vp.bmp_to_avi_MP("raw", video, framerate = 30, num_processes = processes)
        # clear bmp files:
        print(f"Clearing {video}...")
        vp.clear_BMP_files(video)
        
if __name__ == "__main__":
    main()