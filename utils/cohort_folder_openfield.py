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

    def __init__(self, cohort_directory, multi=False, body_sensor=True):
        """
        Args:
            cohort_directory (str or Path): Path to the folder containing all sessions.
            multi (bool, optional): If True, indicates that the cohort folder might 
                                    contain multiple subfolders, each with session 
                                    directories.
        """
        self.cohort_directory = Path(cohort_directory)
        self.multi = multi
        self.body_sensor = body_sensor

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
        self.check_for_processed_data()
        self.make_concise_cohort_logs()

        # Save the final JSONs
        self.save_cohort_info()

    def get_session(self, session_id, concise=False):
        """
        Returns the dictionary for a given session ID.
        
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
                "body_sensor": self.body_sensor
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
                if self.body_sensor:
                    required_files = {
                        "arduino_daq_h5": "ArduinoDAQ.h5",
                        "head_sensor_h5": "Head_sensor.h5",
                        "body_sensor_h5": "Body_sensor.h5",
                        "metadata_json": "metadata.json"
                    }
                else:
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

    def check_for_processed_data(self):
        """
        Check for processed data files that indicate analysis has been done,
        including NWB files.
        """
        print("Checking for processed data files...")
        for mouse_id, mouse_data in self.cohort["mice"].items():
            for session_id, session_dict in mouse_data["sessions"].items():
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

    def make_concise_cohort_logs(self):
        """
        Builds a 'concise' dictionary summarizing which sessions are 
        complete vs incomplete.
        """
        print("Building concise cohort logs...")
        self.cohort_concise["complete_data"] = {}
        self.cohort_concise["incomplete_data"] = {}

        for mouse_id, mouse_data in self.cohort["mice"].items():
            for session_id, session_dict in mouse_data["sessions"].items():
                raw_data_ok = session_dict["raw_data"].get("is_all_raw_data_present?", False)
                processed_data_ok = session_dict["processed_data"].get("processed_data_present?", False)
                
                # Session is complete if both raw and processed data are present
                is_complete = raw_data_ok and processed_data_ok
                
                # Create a summary with essential information
                session_summary = {
                    "directory": session_dict["directory"],
                    "raw_data_present": raw_data_ok,
                    "processed_data_present": processed_data_ok,
                    "missing_files": session_dict["raw_data"]["missing_files"],
                    "NWB_file": session_dict["processed_data"].get("NWB_file", "None"),
                    "portable": True
                }
                
                if is_complete:
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