import json
import sys
from pathlib import Path

def print_section_lengths(data, section_name):
    """
    Print lengths of arrays in a specific section of the JSON data.
    
    Args:
        data (dict): Section of JSON data containing arrays
        section_name (str): Name of the section being processed
    """
    if data is None:
        print(f"{section_name} data not found or is None")
        return
        
    print(f"\n{section_name} Data:")
    print("-" * 40)
    
    for key, value in data.items():
        if isinstance(value, list):
            print(f"{key:25} length: {len(value)}")
        elif isinstance(value, dict):
            # Handle nested dictionaries if they exist
            for sub_key, sub_value in value.items():
                if isinstance(sub_value, list):
                    print(f"{key}.{sub_key:20} length: {len(sub_value)}")

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

    print(f"Reading from: {json_file}")
    
    # Print session ID
    print(f"Session ID: {data.get('session_id', 'Not found')}")
    
    # Print lengths for head sensor data
    print_section_lengths(data.get('head_sensor'), "Head Sensor")
    
    # Print lengths for camera data
    print_section_lengths(data.get('camera'), "Camera")

if __name__ == "__main__":
    # Check if a file path was provided as command line argument
    if len(sys.argv) > 1:
        output_json = sys.argv[1]
    else:
        # Default path if none provided
        output_json = r"C:\Users\Tripodi Group\Videos\2501 - openfield experiment output\250116_174334_test1\250116_174334_test1_synced_data.json"
    
    demo_print_lengths(output_json)