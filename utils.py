import time
import keyboard
import os
from colorama import init, Fore, Back, Style
init()

# Terminal control sequences (to move cursor up and clear the line)
UP = "\033[1A"
CLEAR = "\x1b[2K"

def countdown_timer(seconds, message="Time remaining", break_on_key=None, print_message=True):
    """
    Displays a countdown timer in the command line.

    Args:
        seconds (int): The countdown duration in seconds.
        message (str): The message to display before the countdown.
        break_on_key (str, optional): A key to break the countdown early (e.g., 'q'). Defaults to None.
    """
    start_time = time.perf_counter()
    
    while True:
        elapsed_time = time.perf_counter() - start_time
        remaining_time = seconds - elapsed_time

        # If time is up, exit the loop
        if remaining_time <= 0:
            if print_message:
                print(UP, end=CLEAR)
                print(f"{message}: 0.0 seconds")
            break

        # Display the countdown timer
        if print_message:
            print(UP, end=CLEAR)
            print(Fore.CYAN + f"{message}: " + Style.RESET_ALL + f"{round(remaining_time, 1)} seconds")

        # If break_on_key is specified and pressed, exit the countdown
        if break_on_key and keyboard.is_pressed(break_on_key):
            print(f"Exiting countdown early because '{break_on_key}' was pressed.")
            break

        # Sleep briefly to make the countdown smoother
        time.sleep(0.1)

def create_end_signal(output_path):
    """
    Create an empty file in the specified output path to signal the end of the experiment.

    Args:
        output_path (str): The path to the output directory.
    """
    end_signal_path = os.path.join(output_path, "end_signal.signal")
    # Create an empty file
    open(end_signal_path, 'w').close()

def check_for_signal_file(output_path):
    """
    Check if any file with a .signal extension exists in the output path.

    Args:
        output_path (str): The path to the directory to check.

    Returns:
        bool: True if a .signal file exists, False otherwise.
    """
    for file_name in os.listdir(output_path):
        if file_name.endswith(".signal"):
            return True
    return False

def delete_signal_files(output_path):
    """
    Delete all files with a .signal extension in the output path.

    Args:
        output_path (str): The path to the directory to check.
    """
    for file_name in os.listdir(output_path):
        if file_name.endswith(".signal"):
            os.remove(os.path.join(output_path, file_name))