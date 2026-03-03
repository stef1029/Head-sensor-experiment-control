import h5py

def read_h5_file(file_path):
    data_dict = {}
    with h5py.File(file_path, 'r') as f:
        for key in f.keys():
            data_dict[key] = f[key][:]
    return data_dict

def print_data_summary(data_dict):
    for key, value in data_dict.items():
        print(f"{key}: {value[:5]}...")  # Print the first 5 elements of each array for a quick summary

if __name__ == "__main__":
    # Replace 'sensor_data.h5' with the path to your HDF5 file
    file_path = r'C:\Users\Stefan R Coltman\OneDrive - University of Cambridge\01 - PhD at LMB\Coding projects\240520 - IMU python\240521_160723_NoID\240521_160723_NoID-Head_sensor.h5'
    data = read_h5_file(file_path)
    
    # Print a summary of the data
    print_data_summary(data)
    
    # Example of how to access specific datasets
    message_ids = data['message_ids']
    yaw_data = data['yaw_data']
    roll_data = data['roll_data']
    pitch_data = data['pitch_data']
    timestamps = data['timestamps']

    print("\nExample data access:")
    print(f"Message IDs: {message_ids[:5]}")
    print(f"Yaw Data: {yaw_data[:5]}")
    print(f"Roll Data: {roll_data[:5]}")
    print(f"Pitch Data: {pitch_data[:5]}")
    print(f"Timestamps: {timestamps[:5]}")
