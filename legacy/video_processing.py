import cv2 as cv
import os
import multiprocessing as mp
import struct
import subprocess

def bmp_to_avi_MP(prefix, data_folder_path, framerate = 30, num_processes = 8):
    # Get all the bmp files in the folder
    bmp_files = [f for f in os.listdir(data_folder_path) if f.endswith('.bmp') and f.startswith(prefix)]

    # Sort the files by name
    bmp_files.sort()

    # Get the first file to use as a template for the video writer
    first_file = cv.imread(os.path.join(data_folder_path, bmp_files[0]))
    height, width, channels = first_file.shape
    dims = (width, height)
    FPS = framerate

    temp_video_dir = data_folder_path / 'temp_videos'
    os.makedirs(temp_video_dir, exist_ok=True)

    # Divide your list of bmp frame files into chunks according to the number of available CPUs
    chunk_size = len(bmp_files) // num_processes
    chunks = [bmp_files[i:i + chunk_size] for i in range(0, len(bmp_files), chunk_size)]

    # Use multiprocessing to process each chunk
    with mp.Pool(num_processes) as p:
        p.starmap(process_video_chunk_MP, [(chunks[i], i, temp_video_dir, FPS, dims, data_folder_path) for i in range(num_processes)])

    # Concatenate all chunks into a single video
    output_path = data_folder_path / f"{data_folder_path.stem}_{prefix}_MP.avi"
    concatenate_videos(temp_video_dir, output_path)

    # Clean up the temporary directory
    os.rmdir(temp_video_dir)

def get_dims(frame_path):
    with open(frame_path, 'rb') as bmp:
        bmp.read(18)  # Skip over the size and reserved fields.

        # Read width and height.
        width = struct.unpack('I', bmp.read(4))[0]
        height = struct.unpack('I', bmp.read(4))[0]

    return (width, height)

def concatenate_videos(temp_video_dir, output_path):
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

def clear_BMP_files(data_folder_path):
    # Get all the bmp files in the folder
    bmp_files = [f for f in os.listdir(data_folder_path) if f.endswith('.bmp')]

    # Sort the files by name
    bmp_files.sort()

    for bmp_file in bmp_files:
        bmp_path = os.path.join(data_folder_path, bmp_file)
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