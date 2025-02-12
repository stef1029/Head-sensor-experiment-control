import json
import traceback
import re
from pathlib import Path
from datetime import datetime

class Cohort_folder_openfield:
    """
    Similar to the original 'Cohort_folder' class, but adapted for a new 
    experiment in which each session folder is expected to contain 
    (at minimum) an 'ArduinoDAQ.h5' and a 'HeadSensor.h5'. 
    Additional checks/files can be added as needed.

    This class:
      1) Walks through a top-level 'cohort_directory',
      2) Finds session subfolders,
      3) Checks that the required raw data files exist,
      4) Stores that info in dictionaries,
      5) Exports final JSONs summarizing the experiment data.
    """

    def __init__(self, cohort_directory, multi=False):
        """
        Args:
            cohort_directory (str or Path): Path to the folder containing all sessions.
            multi (bool, optional): If True, indicates that the cohort folder might 
                                    contain multiple subfolders, each with session 
                                    directories.
        """
        self.cohort_directory = Path(cohort_directory)
        self.multi = multi

        # Basic directory check
        if not self.cohort_directory.exists():
            raise FileNotFoundError(f"Cohort directory '{self.cohort_directory}' does not exist.")

        # Prepare an internal data structure for the entire cohort
        self.cohort = {
            "Cohort name": self.cohort_directory.name,
            "mice": {}
        }

        # We'll also maintain a "concise" structure
        self.cohort_concise = {}

        # Main initialization steps
        self.find_mice()
        self.check_raw_data()
        self.check_for_preliminary_analysis()
        self.make_concise_cohort_logs()

        # Save the final JSONs
        self.save_cohort_info()

    def get_session(self, session_id, concise=False):
        """
        Returns the dictionary for a given session ID.
        If 'concise=True', returns the entry from self.cohort_concise
        (i.e., from 'complete_data' or 'incomplete_data'),
        otherwise returns the entry from self.cohort['mice'].

        Args:
            session_id (str): The session ID to find.
            concise (bool): If True, return from the 'concise' dictionary; otherwise return full.

        Returns:
            dict or None: The session dictionary, or None if not found.
        """
        if not concise:
            # Search the full cohort dict
            for mouse_id, mouse_data in self.cohort["mice"].items():
                for sess_id, sess_dict in mouse_data["sessions"].items():
                    if sess_id == session_id:
                        return sess_dict
            return None
        else:
            # Search the concise dict, both 'complete_data' and 'incomplete_data'
            for data_type in ["complete_data", "incomplete_data"]:
                if data_type in self.cohort_concise:
                    for mouse_id, sessions_dict in self.cohort_concise[data_type].items():
                        if session_id in sessions_dict:
                            return sessions_dict[session_id]
            return None

    def find_mice(self):
        """
        Searches for session folders within the top-level folder. 
        The identification logic is simplified for this new experiment.
        """
        print(f"Finding mice/session folders in {self.cohort_directory}")

        # Distinguish between single-level vs multi-level org
        if not self.multi:
            # Single-level: session folders are direct children
            session_folders = [
                folder for folder in self.cohort_directory.glob('*')
                if folder.is_dir() and len(folder.name) > 13 and folder.name[13] == "_"
            ]
        else:
            # Multi-level: each subfolder might contain multiple session folders
            top_folders = [
                folder for folder in self.cohort_directory.glob('*')
                if folder.is_dir() and 'OEAB_recording' not in folder.name
            ]
            session_folders = []
            for folder in top_folders:
                for sub in folder.glob('*'):
                    if sub.is_dir() and len(sub.name) > 13 and sub.name[13] == "_":
                        session_folders.append(sub)

        # Build the cohort dictionary
        for sess_folder in session_folders:
            session_id = sess_folder.name
            # For instance, parse mouse ID from session_id
            mouse_id = session_id[14:]  # e.g., "240315_123456_mouseX" => "mouseX"

            if mouse_id not in self.cohort["mice"]:
                self.cohort["mice"][mouse_id] = {"sessions": {}}

            # Each session gets an entry
            self.cohort["mice"][mouse_id]["sessions"][session_id] = {
                "directory": str(sess_folder),
                "mouse_id": mouse_id,
                "session_id": session_id
            }

    def check_raw_data(self):
        """
        For each session, check if the required raw data files exist (e.g. ArduinoDAQ.h5, HeadSensor.h5).
        Store the results in the session's dictionary.
        """
        print("Checking raw data for each session...")
        for mouse_id, mouse_data in self.cohort["mice"].items():
            for session_id, session_dict in mouse_data["sessions"].items():
                session_path = Path(session_dict["directory"])

                # Prepare a raw_data dictionary
                raw_data = {}
                required_files = {
                    "arduino_daq_h5": "ArduinoDAQ.h5",
                    "head_sensor_h5": "Head_sensor.h5",
                    "metadata_json": "metadata.json"
                }

                missing_files = []
                all_files_ok = True

                # Check for each required file
                for key, pattern in required_files.items():
                    found_file = self.find_file(session_path, pattern)
                    if found_file is None:
                        all_files_ok = False
                        missing_files.append(pattern)
                        raw_data[key] = "None"
                    else:
                        raw_data[key] = str(found_file)

                # Mark presence
                raw_data["is_all_raw_data_present?"] = all_files_ok
                raw_data["missing_files"] = missing_files

                # Attach to the session
                session_dict["raw_data"] = raw_data

    def check_for_preliminary_analysis(self):
        """
        Optional: check for any 'post-processed' files that indicate 
        preliminary analysis has been done. For example, if you produce 
        'head_sensor_synced.json' after data alignment, check for that.
        """
        print("Checking for preliminary analysis products...")
        for mouse_id, mouse_data in self.cohort["mice"].items():
            for session_id, session_dict in mouse_data["sessions"].items():
                session_path = Path(session_dict["directory"])
                processed_data = {}
                # We'll assume there's a single indicator file for now:
                # e.g. 'head_sensor_synced.json'
                indicator_file = self.find_file(session_path, 'synced_data.json')

                if indicator_file:
                    processed_data["preliminary_analysis_done?"] = True
                    processed_data["synced_data_file"] = str(indicator_file)
                else:
                    processed_data["preliminary_analysis_done?"] = False
                    processed_data["synced_data_file"] = "None"

                session_dict["processed_data"] = processed_data

    def make_concise_cohort_logs(self):
        """
        Builds a 'concise' dictionary summarizing which sessions are 
        complete vs incomplete, similar to your original script.
        """
        print("Building concise cohort logs...")
        self.cohort_concise["complete_data"] = {}
        self.cohort_concise["incomplete_data"] = {}

        for mouse_id, mouse_data in self.cohort["mice"].items():
            for session_id, session_dict in mouse_data["sessions"].items():
                raw_data_ok = session_dict["raw_data"].get("is_all_raw_data_present?", False)
                # We can store minimal info, e.g. session path, which files are missing, etc.
                session_summary = {
                    "directory": session_dict["directory"],
                    "missing_files": session_dict["raw_data"]["missing_files"],
                }
                if raw_data_ok:
                    if mouse_id not in self.cohort_concise["complete_data"]:
                        self.cohort_concise["complete_data"][mouse_id] = {}
                    self.cohort_concise["complete_data"][mouse_id][session_id] = session_summary
                else:
                    if mouse_id not in self.cohort_concise["incomplete_data"]:
                        self.cohort_concise["incomplete_data"][mouse_id] = {}
                    self.cohort_concise["incomplete_data"][mouse_id][session_id] = session_summary

    def save_cohort_info(self):
        """
        Saves the main dictionary (`cohort_info.json`) and the concise dictionary
        (`concise_cohort_info.json`) in the top-level directory.
        """
        cohort_info_path = self.cohort_directory / "cohort_info.json"
        concise_info_path = self.cohort_directory / "concise_cohort_info.json"

        try:
            with open(cohort_info_path, 'w') as f:
                json.dump(self.cohort, f, indent=4)
            print(f"Saved detailed cohort info to {cohort_info_path}")
        except Exception as e:
            print(f"Failed to save {cohort_info_path}: {e}")
            traceback.print_exc()

        try:
            with open(concise_info_path, 'w') as f:
                json.dump(self.cohort_concise, f, indent=4)
            print(f"Saved concise cohort info to {concise_info_path}")
        except Exception as e:
            print(f"Failed to save {concise_info_path}: {e}")
            traceback.print_exc()

    @staticmethod
    def find_file(directory: Path, substring: str):
        """
        Returns the first file in 'directory' whose name contains 'substring'.
        If none found, returns None.
        """
        for file in directory.glob('*'):
            if substring in file.name:
                return file
        return None

def main():
    """
    Example usage. 
    Point it to your new experiment's folder. 
    This script will create 'cohort_info.json' and 'concise_cohort_info.json' 
    summarizing the sessions found and whether the key raw files exist.
    """
    print("Starting Cohort_folder_HeadSensor...")
    test_dir = r"C:\Users\Tripodi Group\Videos\2501 - openfield experiment output"
    manager = Cohort_folder_openfield(cohort_directory=test_dir, multi=False)
    print("Finished building new experiment cohort info.")

    session_id = "250113_165159_test1"
    print(manager.get_session(session_id).keys())

if __name__ == "__main__":
    main()
