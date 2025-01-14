import json
import sys
from pathlib import Path

def demo_print_lengths(json_file):
    """
    Reads the synced JSON file and prints out the lengths
    of each relevant array inside it.
    """
    json_file = Path(json_file)

    if not json_file.exists():
        print(f"File does not exist: {json_file}")
        return

    # Load the JSON
    with open(json_file, 'r') as f:
        data = json.load(f)

    # List of keys in the JSON that store arrays.
    # Modify these as needed for your actual JSON structure.
    array_keys = [
        "pulse_times",
        "message_ids",
        "yaw_data",
        "roll_data",
        "pitch_data",
        "head_sensor_timestamps",
        "synced_timestamps"
    ]

    # Print lengths for each key found
    print(f"Reading from: {json_file}")
    for key in array_keys:
        if key in data:
            print(f"{key} length: {len(data[key])}")
        else:
            print(f"{key} not found in the JSON.")

if __name__ == "__main__":
    output_json = r"C:\Users\Tripodi Group\Videos\2501 - openfield experiment output\250114_161030_test1\250114_161030_test1_head_sensor_synced.json"
    demo_print_lengths(output_json)