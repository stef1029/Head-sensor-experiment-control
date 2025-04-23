import multiprocessing as mp
from pathlib import Path
import json
import os
from datetime import datetime

def process_cohort_videos(cohort_directory: str | Path, num_processes: int = None):
    """
    Process all videos in a cohort directory. Skips already processed videos.
    
    Args:
        cohort_directory (str | Path): Root directory containing all session folders
        num_processes (int, optional): Number of processes for multiprocessing. Defaults to CPU count.
    """
    cohort_directory = Path(cohort_directory)
    processed_count = 0
    skipped_count = 0
    error_count = 0
    
    # Find all session directories (assuming they contain binary video files)
    session_dirs = [d for d in cohort_directory.glob("**/") if list(d.glob("*binary_video*"))]
    
    if not session_dirs:
        print("No sessions with binary video files found.")
        return
    
    print(f"Found {len(session_dirs)} sessions with binary video files")
    
    # Process each session
    for session_dir in session_dirs:
        try:
            processor = VideoProcessor(session_dir, num_processes)
            result = processor.process_session()
            
            if result == "processed":
                processed_count += 1
            elif result == "skipped":
                skipped_count += 1
                
        except Exception as e:
            print(f"Error processing session {session_dir}: {e}")
            error_count += 1
    
    print(f"\nProcessing complete:")
    print(f"Successfully processed: {processed_count} sessions")
    print(f"Skipped (already processed): {skipped_count} sessions")
    print(f"Errors encountered: {error_count} sessions")

class VideoProcessor:
    def __init__(self, session_directory: Path, num_processes: int = None):
        """
        Initialize the video processor for a session directory.
        
        Args:
            session_directory (Path): Directory containing the session data
            num_processes (int, optional): Number of processes for multiprocessing. Defaults to CPU count.
        """
        self.session_directory = Path(session_directory)
        self.num_processes = num_processes or mp.cpu_count()

    def process_session(self):
        """
        Process video data in the session directory.
        Detects binary video files and processes them using the binary conversion method.
        Skips processing if video already exists.
        
        Returns:
            str: "processed" if video was processed, "skipped" if already processed, None if error
        """
        # Find binary video files in the session directory
        binary_files = list(self.session_directory.glob('*binary_video*'))
        
        if not binary_files:
            print(f"No binary video files found in {self.session_directory}. Skipping...")
            return None

        if len(binary_files) > 1:
            print(f"Multiple binary video files found in {self.session_directory}. Using the first one.")

        binary_file = binary_files[0]
        metadata_file = self.session_directory / f"{self.session_directory.name}_Tracker_data.json"

        if not binary_file.exists():
            print(f"Binary file {binary_file} not found. Skipping...")
            return None

        if not metadata_file.exists():
            print(f"Metadata file {metadata_file} not found. Skipping...")
            return None
            
        # Check if video already exists (look for any .avi files)
        video_files = list(self.session_directory.glob('*.avi'))
        if video_files:
            print(f"Video file already exists in {self.session_directory}. Skipping conversion...")
            return "skipped"

        # Process the video
        print(f"Processing video in {self.session_directory}...")
        try:
            convert_binary_to_video(
                str(binary_file),
                str(metadata_file),
                self.session_directory
            )
            print(f"Successfully processed video in {self.session_directory}")

            # Check if the video was created successfully
            new_video_files = list(self.session_directory.glob("*_output.avi"))
            if new_video_files:
                latest_video = max(new_video_files, key=lambda x: x.stat().st_mtime)
                if latest_video.exists() and latest_video.stat().st_size > 0:
                    # Remove the binary video file
                    binary_file.unlink()
                    print(f"Successfully processed video and removed binary file in {self.session_directory}")
                    return "processed"
                else:
                    print(f"Video conversion completed but output file not found or empty in {self.session_directory}")
                    return None
            else:
                print(f"No output video file found in {self.session_directory}")
                return None
                
        except Exception as e:
            print(f"Error processing video in {self.session_directory}: {e}")
            return None


def convert_binary_to_video(binary_filename, json_filename, output_directory):
    # Load metadata from JSON file
    try:
        with open(json_filename, 'r') as json_file:
            metadata = json.load(json_file)
    except Exception as e:
        print(f"Error reading JSON file: {e}")
        return

    # Extract metadata
    try:
        image_width = metadata['image_width']
        image_height = metadata['image_height']
        frame_rate = metadata['frame_rate']
        frame_IDs = metadata.get('frame_IDs', [])

        if not frame_IDs:
            print("Error: 'frame_IDs' not found or empty in JSON file.")
            return

        number_of_images = len(frame_IDs)

        # Since images are always Mono8, set bytes_per_pixel accordingly
        bytes_per_pixel = 1

        # Generate output video filename
        date_time = f"{datetime.now():%y%m%d_%H%M%S}"
        video_filename = output_directory / f"{date_time}_output.avi"

    except KeyError as e:
        print(f"Missing key in JSON file: {e}")
        return

    # Calculate image size
    image_size = image_width * image_height * bytes_per_pixel

    # Determine the number of CPU cores
    num_cores = mp.cpu_count()
    # num_cores = 4  # You can set this manually if desired
    print(f"Number of CPU cores available: {num_cores}")

    # Calculate chunk size
    chunk_size = max(number_of_images // num_cores, 1)

    # Split frame indices into chunks
    chunks = [frame_IDs[i:i + chunk_size] for i in range(0, number_of_images, chunk_size)]

    # Create a temporary directory for intermediate video chunks
    temp_video_dir = output_directory / 'temp_videos'
    temp_video_dir.mkdir(parents=True, exist_ok=True)

    # Prepare arguments for multiprocessing
    args = []
    for idx, chunk in enumerate(chunks):
        args.append((binary_filename, image_size, image_width, image_height,
                     chunk, idx, temp_video_dir, bytes_per_pixel, frame_rate))

    # Use multiprocessing to process chunks in parallel
    with mp.Pool(processes=min(num_cores, len(chunks))) as pool:
        pool.starmap(process_video_chunk, args)

    # Concatenate all chunked videos into one final video
    concatenate_videos(temp_video_dir, video_filename)

    # Clean up temporary directory
    for temp_file in temp_video_dir.glob('*'):
        temp_file.unlink()
    temp_video_dir.rmdir()

    print(f"Video saved as {video_filename}")

def process_video_chunk(binary_filename, image_size, image_width, image_height,
                        frame_IDs_chunk, chunk_index, temp_video_dir, bytes_per_pixel, frame_rate):
    """
    Processes a chunk of images and writes them to a temporary video file.
    """
    import numpy as np
    import cv2

    # Open binary file
    try:
        with open(binary_filename, 'rb') as binary_file:
            # Calculate the position to start reading from
            start_frame = frame_IDs_chunk[0]
            start_pos = start_frame * image_size
            binary_file.seek(start_pos)

            # Set up VideoWriter for grayscale images
            is_color = False  # Mono8 images are grayscale
            fourcc = cv2.VideoWriter_fourcc(*'MJPG')  # Change codec if needed
            temp_video_filename = temp_video_dir / f"chunk_{chunk_index:03}.avi"
            video_writer = cv2.VideoWriter(
                str(temp_video_filename),
                fourcc,
                frame_rate,  # Use the correct frame rate
                (image_width, image_height),
                isColor=is_color
            )

            if not video_writer.isOpened():
                print(f"Error: Could not open temporary video file for writing: {temp_video_filename}")
                return

            # Process images in the chunk
            for _ in frame_IDs_chunk:
                buffer = binary_file.read(image_size)
                if not buffer:
                    print(f"Error: End of file reached unexpectedly in chunk {chunk_index}")
                    break
                elif len(buffer) < image_size:
                    print(f"Error: Incomplete image data in chunk {chunk_index}")
                    break

                # Convert buffer to NumPy array
                image = np.frombuffer(buffer, dtype=np.uint8)

                # Reshape the image to 2D array
                image = image.reshape((image_height, image_width))

                # Write frame to video
                video_writer.write(image)

            # Clean up
            video_writer.release()

    except Exception as e:
        print(f"Error processing chunk {chunk_index}: {e}")
        return

def concatenate_videos(temp_video_dir, output_filename):
    """
    Concatenates temporary video chunks into a single video using ffmpeg.
    """
    import subprocess

    # Get list of chunk video files
    chunk_files = sorted(temp_video_dir.glob('chunk_*.avi'))

    if not chunk_files:
        print(f"No chunk files found in {temp_video_dir}. Skipping concatenation.")
        return

    # Create a text file listing all the chunk files
    list_file = temp_video_dir / 'video_list.txt'
    with open(list_file, 'w') as f:
        for chunk_file in chunk_files:
            f.write(f"file '{chunk_file.as_posix()}'\n")

    # Build ffmpeg command
    ffmpeg_cmd = [
        'ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', str(list_file.as_posix()),
        '-c', 'copy', str(output_filename)
    ]

    # Run ffmpeg to concatenate videos
    result = subprocess.run(
        ffmpeg_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    if result.returncode != 0:
        print(f"ffmpeg error (concatenate_videos):\n{result.stderr}")
        return

    # Remove the list file
    list_file.unlink()

if __name__ == "__main__":
    # Define the paths
    binary_filename = r"E:\bin_test\241128_151903_test1_binary_video.bin"
    json_filename = r"E:\bin_test\241128_151903_test1_Tracker_data.json"
    output_directory = Path(r"E:\bin_test")

    # Convert binary to video with multiprocessing
    convert_binary_to_video(binary_filename, json_filename, output_directory)