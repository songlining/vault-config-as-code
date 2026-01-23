"""
User Store Service

Maintains persistent mapping between SCIM IDs (EntraID object IDs) and Vault identity data.
Provides thread-safe CRUD operations on the user mapping store.
"""

import json
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional


class UserStore:
    """
    Persistent storage for SCIM ID to Vault identity mappings.

    The store maintains a JSON file that maps SCIM user IDs (EntraID object IDs)
    to Vault identity metadata including name and YAML filename.

    Thread-safe using file locking for concurrent access.

    Example usage:
        store = UserStore("/data/user_mapping.json")

        # Add a user
        store.add_user(
            scim_id="12345678-1234-1234-1234-123456789abc",
            name="Jane Example",
            filename="entraid_human_jane_example.yaml"
        )

        # Retrieve a user
        user = store.get_user("12345678-1234-1234-1234-123456789abc")
        # Returns: {"scim_id": "...", "name": "Jane Example", "filename": "..."}

        # List all users
        all_users = store.list_all_users()
        # Returns: [{"scim_id": "...", "name": "...", "filename": "..."}, ...]

        # Delete a user
        store.delete_user("12345678-1234-1234-1234-123456789abc")
    """

    def __init__(self, data_file: str):
        """
        Initialize UserStore with path to JSON data file.

        Args:
            data_file: Path to JSON file for storing user mappings
        """
        self.data_file = Path(data_file)
        self._lock = threading.Lock()

        # Ensure parent directory exists
        self.data_file.parent.mkdir(parents=True, exist_ok=True)

        # Initialize empty file if it doesn't exist
        if not self.data_file.exists():
            self._write_data({})

    def _read_data(self) -> Dict[str, Dict[str, Any]]:
        """
        Read user mapping data from JSON file.

        Returns:
            Dictionary mapping SCIM IDs to user data
        """
        try:
            with open(self.data_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            # Return empty dict if file doesn't exist or is invalid
            return {}

    def _write_data(self, data: Dict[str, Dict[str, Any]]) -> None:
        """
        Write user mapping data to JSON file atomically.

        Uses atomic write pattern (write to temp file, then rename) to ensure
        data integrity even if write is interrupted.

        Args:
            data: Dictionary mapping SCIM IDs to user data
        """
        # Write to temporary file first
        temp_file = self.data_file.with_suffix(".tmp")

        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        # Atomic rename (replace old file with new file)
        # On POSIX systems, this is atomic and prevents partial reads
        temp_file.replace(self.data_file)

    def add_user(
        self, scim_id: str, name: str, filename: str, **extra_fields: Any
    ) -> None:
        """
        Add or update user mapping in the store.

        Args:
            scim_id: SCIM user ID (EntraID object ID UUID)
            name: User's display name (from identity.name)
            filename: YAML filename for this user (e.g., "entraid_human_jane_example.yaml")
            **extra_fields: Additional fields to store (e.g., email, role, team)
        """
        with self._lock:
            data = self._read_data()

            # Create or update user entry
            data[scim_id] = {
                "scim_id": scim_id,
                "name": name,
                "filename": filename,
                **extra_fields,
            }

            self._write_data(data)

    def get_user(self, scim_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve user data by SCIM ID.

        Args:
            scim_id: SCIM user ID (EntraID object ID UUID)

        Returns:
            Dictionary with user data (scim_id, name, filename, and any extra fields)
            or None if user not found
        """
        with self._lock:
            data = self._read_data()
            return data.get(scim_id)

    def list_all_users(self) -> List[Dict[str, Any]]:
        """
        List all users in the store.

        Returns:
            List of user dictionaries, each containing scim_id, name, filename,
            and any extra fields
        """
        with self._lock:
            data = self._read_data()
            return list(data.values())

    def delete_user(self, scim_id: str) -> bool:
        """
        Remove user from the store.

        Args:
            scim_id: SCIM user ID (EntraID object ID UUID)

        Returns:
            True if user was found and deleted, False if user not found
        """
        with self._lock:
            data = self._read_data()

            if scim_id in data:
                del data[scim_id]
                self._write_data(data)
                return True

            return False

    def user_exists(self, scim_id: str) -> bool:
        """
        Check if user exists in the store.

        Args:
            scim_id: SCIM user ID (EntraID object ID UUID)

        Returns:
            True if user exists, False otherwise
        """
        with self._lock:
            data = self._read_data()
            return scim_id in data

    def get_user_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve user data by name (case-insensitive).

        Useful for finding users when only the name is known.

        Args:
            name: User's display name

        Returns:
            Dictionary with user data or None if user not found
        """
        with self._lock:
            data = self._read_data()

            # Case-insensitive name search
            for user in data.values():
                if user.get("name", "").lower() == name.lower():
                    return user

            return None

    def get_user_by_filename(self, filename: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve user data by YAML filename.

        Useful for reverse lookups when processing YAML files.

        Args:
            filename: YAML filename (e.g., "entraid_human_jane_example.yaml")

        Returns:
            Dictionary with user data or None if user not found
        """
        with self._lock:
            data = self._read_data()

            for user in data.values():
                if user.get("filename") == filename:
                    return user

            return None
