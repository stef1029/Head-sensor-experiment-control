from easypyspin import VideoCapture
import cv2 as cv
import numpy as np
from datetime import datetime
import csv
import json
import time
import os
import argparse
import keyboard
import multiprocessing
import subprocess

global global_FPS
global global_DIMS
global_FPS = 0
global_DIMS = (0, 0)

class Tracker:
    def __init__(self, new_mouse_ID=None, new_date_time=None, new_path=None, cam=None, FPS=30):

        if new_mouse_ID is None:
            self.mouse_ID = input(r"Enter mouse ID (no '.'s): ")
        else:
            self.mouse_ID = new_mouse_ID

        if new_date_time is None:
            self.start_time = f"{datetime.now():%y%m%d_%H%M%S}"
        else:
            self.start_time = new_date_time
        
        self.foldername = f"{self.start_time}_{self.mouse_ID}"
        if new_path is None:
            self.path = os.path.join(os.getcwd(), self.foldername)
            os.mkdir(self.path)
        else:
            self.path = new_path

        if cam is None:
            self.cam = 0
            self.cam_no = 0
        else:
            if cam == 1:
                self.cam = '23606054'
                self.cam_no = 1
            else:
                self.cam = 0
                self.cam_no = 0

        self.angles_list = []
        self.data_list = []

        self.cap = VideoCapture(self.cam) 

        if not self.cap.isOpened():
            print("Camera can't open\nexit")
            return -1
        self.cap.set(cv.CAP_PROP_EXPOSURE, -1)
        self.cap.set(cv.CAP_PROP_GAIN, -1)
        self.FPS = FPS
        global global_FPS
        global_FPS = self.FPS
        self.cap.set(cv.CAP_PROP_FPS, self.FPS)

        self.dims = (
                int(self.cap.get(cv.CAP_PROP_FRAME_WIDTH)),
                int(self.cap.get(cv.CAP_PROP_FRAME_HEIGHT))
            )
        global global_DIMS
        global_DIMS = self.dims

    def timer(self):
        start_time = self.timer_start_time
        return time.perf_counter() - start_time

    def tracker(self, show_frame=False, save_video=True, save_to_avi=True):
        try:
            self.previous_point_1 = self.previous_point_2 = None
            self.previous_angle = None
            self.frame_count = 0

            self.timer_start_time = time.perf_counter()

            self.frame_IDs = []

            while True:
                ret, self.frame, frame_ID = self.cap.read()

                if not ret:
                    continue
                
                self.frame_IDs.append(frame_ID)

                if save_video:
                    filename = os.path.join(self.path, fr"raw_temp{self.frame_count:08}.bmp")
                    cv.imwrite(filename, self.frame)

                # calculate time since last frame and display as true fps value on frame:
                if self.frame_count == 0:
                    self.fps_start_time = time.perf_counter()
                fps = 1 / (time.perf_counter() - self.fps_start_time)
                self.fps_start_time = time.perf_counter()
                cv.putText(self.frame, str(round(fps)), (10, 30), cv.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

                if show_frame:
                    scale = 0.7
                    self.img_show = cv.resize(self.frame, None, fx=scale, fy=scale)
                    cv.imshow(f"Rig {self.cam_no}. Press M to quit", self.img_show)

                self.frame_count += 1

                if cv.waitKey(5) == ord("m"):
                    break

                if keyboard.is_pressed("m"):
                    break
        except Exception as e:
            print(e)
        
        finally:
            self.cap.release()
            cv.destroyAllWindows()

            self.end_time = f"{datetime.now():%y%m%d_%H%M%S}"
            self.save_data()
            print("Tracker data saved")

            if save_to_avi:
                start_time = time.perf_counter()
                print("Saving video... ")
                self.bmp_to_avi_MP("raw")
                # self.bmp_to_avi_MP("overlay")

                # check if file ending in .avi exists, if so, delete all the bmp files:
                avi_files = [f for f in os.listdir(self.path) if f.endswith('.avi')]
                if len(avi_files) > 0:
                    self.clear_BMP_files()
                    
                print("Video saved!")
                # time taken in minutes and seconds:
                print(f"Time taken: {round((time.perf_counter() - start_time) / 60)} minutes {round((time.perf_counter() - start_time) % 60)} seconds")

    
    def save_data(self):
        # make file name the date and time:
        file_name = f"{self.foldername}_Camera_data.json"

        data = {}

        data["frame_rate"] = self.FPS
        data["start_time"] = self.start_time
        data["end_time"] = self.end_time
        data["height"] = self.dims[1]
        data["width"] = self.dims[0]
        data["frame_IDs"] = self.frame_IDs

        # save data to json file:
        
        with open(f'{os.path.join(self.path, f"{file_name}")}', "w") as f:
            json.dump(data, f, indent=4)


    def bmp_to_avi_MP(self, prefix, framerate = 30):
        # Get all the bmp files in the folder
        bmp_files = [f for f in os.listdir(self.path) if f.endswith('.bmp') and f.startswith(prefix)]

        # Sort the files by name
        bmp_files.sort()

        # Get the first file to use as a template for the video writer
        first_file = cv.imread(os.path.join(self.path, bmp_files[0]))
        height, width, channels = first_file.shape

        temp_video_dir = os.path.join(self.path, 'temp_videos')
        os.makedirs(temp_video_dir, exist_ok=True)

        # Divide your list of bmp frame files into chunks according to the number of available CPUs
        num_processes = multiprocessing.cpu_count()
        chunk_size = len(bmp_files) // num_processes
        chunks = [bmp_files[i:i + chunk_size] for i in range(0, len(bmp_files), chunk_size)]

        global global_FPS
        global global_DIMS
        # Use multiprocessing to process each chunk
        with multiprocessing.Pool(num_processes) as p:
            p.starmap(process_video_chunk_MP, [(chunks[i], i, temp_video_dir, self.FPS, self.dims, self.path) for i in range(num_processes)])

        # Concatenate all chunks into a single video
        output_path = os.path.join(self.path, f"{self.foldername}_{prefix}_MP.avi")
        self.concatenate_videos(temp_video_dir, output_path)

        # Clean up the temporary directory
        os.rmdir(temp_video_dir)
    
    def concatenate_videos(self, temp_video_dir, output_path):
        # Determine the list of all chunk video files
        chunk_files = sorted([os.path.join(temp_video_dir, f) for f in os.listdir(temp_video_dir) if f.endswith('.avi')])
        # Create a temporary text file containing the list of video files for ffmpeg
        list_path = os.path.join(temp_video_dir, 'video_list.txt')
        with open(list_path, 'w') as f:
            for chunk_file in chunk_files:
                f.write(f"file '{chunk_file}'\n")

        # Run ffmpeg command to concatenate all the videos
        ffmpeg_cmd = ['ffmpeg', '-f', 'concat', '-safe', '0', '-i', list_path, '-c', 'copy', output_path]
        subprocess.run(ffmpeg_cmd)

        # Clean up the temporary chunk video files and text file
        for file_path in chunk_files:
            os.remove(file_path)
        os.remove(list_path)

    def clear_BMP_files(self):
        # Get all the bmp files in the folder
        bmp_files = [f for f in os.listdir(self.path) if f.endswith('.bmp')]

        # Sort the files by name
        bmp_files.sort()

        for bmp_file in bmp_files:
            bmp_path = os.path.join(self.path, bmp_file)
            os.remove(bmp_path)

def process_video_chunk_MP(chunk, chunk_index, temp_video_dir, FPS, DIMS, path):
    fourcc = cv.VideoWriter_fourcc(*'MJPG')
    # Each process will create its own output file
    temp_video_path = os.path.join(temp_video_dir, f"chunk_{chunk_index}.avi")
    video_writer = cv.VideoWriter(temp_video_path, fourcc, FPS, DIMS)

    for bmp_file in chunk:
        bmp_path = os.path.join(path, bmp_file)
        frame = cv.imread(bmp_path)
        video_writer.write(frame)

    video_writer.release()

def main():

    parser = argparse.ArgumentParser()
    parser.add_argument("--id", type=str, help="Mouse ID")
    parser.add_argument("--date", type=str, help="Date and time")
    parser.add_argument("--path", type=str, help="Path to save data to")
    args = parser.parse_args()
    
    if args.id is not None:
        mouse_ID = args.id
    else:
        mouse_ID = "NoID"
    
    if args.date is not None:
        date_time = args.date
    else:
        date_time = f"{datetime.now():%y%m%d_%H%M%S}"
    
    foldername = f"{date_time}_{mouse_ID}"
    if args.path is not None:
        path = args.path

    else:
        test_path = r"C:\Users\Tripodi Group\Videos\Test video"
        # path = os.path.join(os.getcwd(), foldername)
        path = os.path.join(test_path, foldername)
        os.mkdir(path)


    camera = Tracker(new_mouse_ID=mouse_ID, new_date_time=date_time, new_path=path, cam=1)
    camera.tracker(show_frame=True, save_video=True, save_to_avi=False)

if __name__ == "__main__":
    main()