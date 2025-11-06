"""
Session management module for saving and restoring analysis state
"""

import json
import pickle
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
import numpy as np


class SessionManager:
    """Manage analysis sessions with save/resume capability"""

    def __init__(self, session_dir: str = "sessions"):
        """
        Initialize session manager

        Args:
            session_dir: Directory to store session files
        """
        self.session_dir = Path(session_dir)
        self.session_dir.mkdir(exist_ok=True)
        self.current_session = None

    def create_session(self, session_name: Optional[str] = None) -> str:
        """
        Create a new session

        Args:
            session_name: Optional session name (auto-generated if not provided)

        Returns:
            Session ID
        """
        if session_name is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            session_name = f"session_{timestamp}"

        session_id = session_name
        self.current_session = session_id

        # Create session metadata
        session_data = {
            "session_id": session_id,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "status": "active",
            "data": {},
            "progress": {},
        }

        self._save_session_data(session_id, session_data)

        return session_id

    def save_state(
        self,
        session_id: str,
        data: Dict[str, Any],
        progress: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Save current state to session

        Args:
            session_id: Session ID
            data: Data to save (will be JSON serializable or pickled if needed)
            progress: Progress information

        Returns:
            Success status
        """
        try:
            session_data = self._load_session_data(session_id)

            if session_data is None:
                # Create new session if doesn't exist
                session_data = {
                    "session_id": session_id,
                    "created_at": datetime.now().isoformat(),
                }

            # Update session data
            session_data["updated_at"] = datetime.now().isoformat()
            session_data["status"] = "paused"

            # Save data
            # Handle numpy arrays separately
            processed_data = {}
            numpy_data = {}

            for key, value in data.items():
                if isinstance(value, np.ndarray):
                    numpy_data[key] = value
                    processed_data[key] = {"type": "numpy_array", "shape": value.shape}
                else:
                    processed_data[key] = value

            session_data["data"] = processed_data

            if progress:
                session_data["progress"] = progress

            # Save JSON metadata
            self._save_session_data(session_id, session_data)

            # Save numpy arrays separately
            if numpy_data:
                numpy_path = self.session_dir / f"{session_id}_arrays.pkl"
                with open(numpy_path, "wb") as f:
                    pickle.dump(numpy_data, f)

            return True

        except Exception as e:
            print(f"Error saving session: {e}")
            return False

    def load_state(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Load state from session

        Args:
            session_id: Session ID

        Returns:
            Session data or None if not found
        """
        try:
            session_data = self._load_session_data(session_id)

            if session_data is None:
                return None

            # Load numpy arrays if they exist
            numpy_path = self.session_dir / f"{session_id}_arrays.pkl"
            if numpy_path.exists():
                with open(numpy_path, "rb") as f:
                    numpy_data = pickle.load(f)

                # Merge numpy arrays back into data
                data = session_data.get("data", {})
                for key, value in data.items():
                    if isinstance(value, dict) and value.get("type") == "numpy_array":
                        if key in numpy_data:
                            data[key] = numpy_data[key]

                session_data["data"] = data

            return session_data

        except Exception as e:
            print(f"Error loading session: {e}")
            return None

    def list_sessions(self) -> List[Dict[str, Any]]:
        """
        List all available sessions

        Returns:
            List of session metadata
        """
        sessions = []

        for session_file in self.session_dir.glob("*.json"):
            if "_arrays" not in session_file.stem:
                try:
                    with open(session_file, "r") as f:
                        session_data = json.load(f)
                        sessions.append({
                            "session_id": session_data.get("session_id"),
                            "created_at": session_data.get("created_at"),
                            "updated_at": session_data.get("updated_at"),
                            "status": session_data.get("status"),
                        })
                except Exception as e:
                    print(f"Error reading session {session_file}: {e}")

        # Sort by updated_at (most recent first)
        sessions.sort(key=lambda x: x.get("updated_at", ""), reverse=True)

        return sessions

    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session

        Args:
            session_id: Session ID

        Returns:
            Success status
        """
        try:
            session_path = self.session_dir / f"{session_id}.json"
            numpy_path = self.session_dir / f"{session_id}_arrays.pkl"

            if session_path.exists():
                session_path.unlink()

            if numpy_path.exists():
                numpy_path.unlink()

            return True

        except Exception as e:
            print(f"Error deleting session: {e}")
            return False

    def update_progress(
        self,
        session_id: str,
        progress: Dict[str, Any],
    ) -> bool:
        """
        Update progress information for a session

        Args:
            session_id: Session ID
            progress: Progress information to update

        Returns:
            Success status
        """
        try:
            session_data = self._load_session_data(session_id)

            if session_data is None:
                return False

            session_data["updated_at"] = datetime.now().isoformat()

            if "progress" not in session_data:
                session_data["progress"] = {}

            session_data["progress"].update(progress)

            self._save_session_data(session_id, session_data)

            return True

        except Exception as e:
            print(f"Error updating progress: {e}")
            return False

    def mark_completed(self, session_id: str) -> bool:
        """
        Mark a session as completed

        Args:
            session_id: Session ID

        Returns:
            Success status
        """
        try:
            session_data = self._load_session_data(session_id)

            if session_data is None:
                return False

            session_data["status"] = "completed"
            session_data["completed_at"] = datetime.now().isoformat()
            session_data["updated_at"] = datetime.now().isoformat()

            self._save_session_data(session_id, session_data)

            return True

        except Exception as e:
            print(f"Error marking session as completed: {e}")
            return False

    def _save_session_data(self, session_id: str, data: Dict[str, Any]):
        """Save session data to JSON file"""
        session_path = self.session_dir / f"{session_id}.json"
        with open(session_path, "w") as f:
            json.dump(data, f, indent=2, default=str)

    def _load_session_data(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Load session data from JSON file"""
        session_path = self.session_dir / f"{session_id}.json"

        if not session_path.exists():
            return None

        with open(session_path, "r") as f:
            return json.load(f)

    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get session information without loading full data

        Args:
            session_id: Session ID

        Returns:
            Session metadata
        """
        session_data = self._load_session_data(session_id)

        if session_data is None:
            return None

        # Return metadata only
        return {
            "session_id": session_data.get("session_id"),
            "created_at": session_data.get("created_at"),
            "updated_at": session_data.get("updated_at"),
            "completed_at": session_data.get("completed_at"),
            "status": session_data.get("status"),
            "progress": session_data.get("progress", {}),
        }
