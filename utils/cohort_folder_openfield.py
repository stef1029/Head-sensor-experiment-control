import json
import traceback
import re
from pathlib import Path
from datetime import datetime

class Cohort_folder:
    """
    Class for managing experiment cohorts, checking raw and processed data files,
    and providing access to session information.
    
    This updated version checks for NWB files and includes them as processing requirements.
    """

    def __init__(self, cohort_directory):
        """
        Args:
            cohort_directory (str or Path): Path to the folder containing all sessions.
        """
        self.cohort_directory = Path(cohort_directory)

        # Basic directory check
        if not self.cohort_directory.exists():
            raise FileNotFoundError(f"Cohort directory '{self.cohort_directory}' does not exist.")

        # Prepare an internal data structure for the entire cohort
        self.cohort = {
            "Cohort name": self.cohort_directory.name,
            "mice": {}
        }

        # Main initialization steps
        self.find_mice()
        self.check_raw_data()
        self.check_for_processed_data()

        # Save the final JSONs
        self.save_cohort_info()

    def get_session(self, session_id):
        """
        Returns the dictionary for a given session ID.
        
        Args:
            session_id (str): The session ID to find.
            concise (bool): If True, return from the 'concise' dictionary; otherwise return full.

        Returns:
            dict or None: The session dictionary, or None if not found.
        """
        # Search the full cohort dict
        for _, mouse_data in self.cohort["mice"].items():
            for sess_id, sess_dict in mouse_data["sessions"].items():
                if sess_id == session_id:
                    return sess_dict
        return None

    def find_mice(self):
        """
        Searches for session folders within the top-level folder.
        """
        print(f"Finding mice/session folders in {self.cohort_directory}")

        session_folders = [
            folder for folder in self.cohort_directory.glob('*')
            if folder.is_dir() and len(folder.name) > 13 and folder.name[13] == "_"
        ]

        # Build the cohort dictionary
        for sess_folder in session_folders:
            session_id = sess_folder.name
            # Parse mouse ID from session_id
            mouse_id = session_id[14:]  # e.g., "250225_175234_mtaq14-1c" => "mtaq14-1c"

            if mouse_id not in self.cohort["mice"]:
                self.cohort["mice"][mouse_id] = {"sessions": {}}

            # Each session gets an entry
            self.cohort["mice"][mouse_id]["sessions"][session_id] = {
                "directory": str(sess_folder),
                "mouse_id": mouse_id,
                "session_id": session_id,
                "portable": True,  # Add portable flag for session class
            }

    def check_raw_data(self):
        """
        For each session, check if raw data files exist (both required and optional).
        Store the results in the session's dictionary.
        """
        print("Checking raw data for each session...")
        for _, mouse_data in self.cohort["mice"].items():
            for _, session_dict in mouse_data["sessions"].items():
                session_path = Path(session_dict["directory"])

                # Prepare a raw_data dictionary
                raw_data = {}

                self.body_sensor = False
                # check if body sensor session:
                if self.find_file(session_path, "Body_sensor.h5"):
                    self.body_sensor = True
                
                session_dict["body_sensor"] = self.body_sensor

                # Define files with their requirement status
                # Format: "key": (filename_pattern, is_required)
                files_to_check = {
                    "arduino_daq_h5": ("ArduinoDAQ.h5", True),
                    "head_sensor_h5": ("Head_sensor.h5", True),
                    "metadata_json": ("metadata.json", True),
                    # Add optional files here
                    "video": ("output.avi", False),
                    "metadata": ("metadata.json", False),
                }
                if self.body_sensor:
                    files_to_check["body_sensor_h5"] = ("Body_sensor.h5", True)

                missing_required_files = []
                missing_optional_files = []
                all_required_files_ok = True

                # Check for each file
                for key, (pattern, is_required) in files_to_check.items():
                    found_file = self.find_file(session_path, pattern)
                    
                    if found_file is None:
                        raw_data[key] = "None"
                        # Track missing files separately based on requirement status
                        if is_required:
                            all_required_files_ok = False
                            missing_required_files.append(pattern)
                        else:
                            missing_optional_files.append(pattern)
                    else:
                        raw_data[key] = str(found_file)

                # Mark presence of required files (ignoring optional ones)
                raw_data["is_all_raw_data_present?"] = all_required_files_ok
                raw_data["missing_required_files"] = missing_required_files
                raw_data["missing_optional_files"] = missing_optional_files

                # Attach to the session
                session_dict["raw_data"] = raw_data

    def check_for_processed_data(self):
        """
        Check for processed data files that indicate analysis has been done,
        including NWB files.
        """
        print("Checking for processed data files...")
        for _, mouse_data in self.cohort["mice"].items():
            for _, session_dict in mouse_data["sessions"].items():
                session_path = Path(session_dict["directory"])
                processed_data = {}
                
                # Check for synced data file
                synced_data_file = self.find_file(session_path, 'synced_data.json')
                if synced_data_file:
                    processed_data["synced_data_file"] = str(synced_data_file)
                else:
                    processed_data["synced_data_file"] = "None"
                
                # Check for NWB file (now looking for headtracker.nwb pattern)
                nwb_file = self.find_file(session_path, 'headtracker.nwb')
                if nwb_file:
                    processed_data["NWB_file"] = str(nwb_file)
                    processed_data["processed_data_present?"] = True
                else:
                    processed_data["NWB_file"] = "None"
                    processed_data["processed_data_present?"] = False
                
                # Attach to the session
                session_dict["processed_data"] = processed_data

    def save_cohort_info(self):
        """
        Saves the main dictionary (`cohort_info.json`) and the concise dictionary
        (`concise_cohort_info.json`) in the top-level directory.
        """
        cohort_info_path = self.cohort_directory / "cohort_info.json"

        try:
            with open(cohort_info_path, 'w') as f:
                json.dump(self.cohort, f, indent=4)
            print(f"Saved detailed cohort info to {cohort_info_path}")
        except Exception as e:
            print(f"Failed to save {cohort_info_path}: {e}")
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