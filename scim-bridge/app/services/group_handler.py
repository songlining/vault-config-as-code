"""
Group Handler Service

Manages identity_groups YAML files for SCIM group synchronization.
Handles adding/removing users from groups and creating new group files as needed.
"""

import os
import re
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Set, Any


class GroupHandler:
    """
    Handler for managing identity group YAML files for SCIM group synchronization.
    
    This service manages the identity_groups/*.yaml files in the Vault configuration
    repository, specifically handling the entraid_human_identities arrays for EntraID
    user group memberships.
    
    Example usage:
        handler = GroupHandler("/path/to/repo/clone")
        
        # Sync user group memberships
        modified_files = handler.sync_user_groups(
            display_name="Alice Smith",
            group_names=["Developers", "Senior Engineers"]
        )
        
        # Remove user from specific group
        modified_files = handler.remove_user_from_group(
            display_name="Alice Smith",
            group_name="Developers"
        )
    """
    
    def __init__(self, repo_clone_dir: str):
        """
        Initialize GroupHandler with repository clone directory.
        
        Args:
            repo_clone_dir: Path to the cloned repository directory containing identity_groups/
        """
        self.repo_clone_dir = Path(repo_clone_dir)
        self.identity_groups_dir = self.repo_clone_dir / "identity_groups"
        
        # Ensure the identity_groups directory exists
        if not self.identity_groups_dir.exists():
            raise ValueError(f"identity_groups directory not found: {self.identity_groups_dir}")
    
    def sync_user_groups(self, display_name: str, group_names: List[str]) -> List[str]:
        """
        Synchronize user's group memberships across all identity group files.
        
        This method ensures the user is a member of exactly the specified groups:
        - Adds user to groups they should be in but aren't currently
        - Removes user from groups they are in but shouldn't be
        - Creates new group files if groups don't exist
        
        Args:
            display_name: User's display name (e.g., "Alice Smith")
            group_names: List of group display names the user should be a member of
        
        Returns:
            List of modified file paths (relative to repo root)
        """
        modified_files = []
        target_groups = set(group_names)
        
        # Load all existing group files
        all_groups = self._load_all_groups()
        
        # Find current group memberships for this user
        current_memberships = set()
        for group_data in all_groups.values():
            if display_name in group_data.get('entraid_human_identities', []):
                current_memberships.add(group_data['name'])
        
        # Groups to add user to (target - current)
        groups_to_join = target_groups - current_memberships
        
        # Groups to remove user from (current - target)
        groups_to_leave = current_memberships - target_groups
        
        # Add user to new groups
        for group_name in groups_to_join:
            file_path = self._find_group_file(group_name)
            if file_path is None:
                # Group doesn't exist, create it
                file_path = self._create_group_file(group_name, display_name)
                if file_path:
                    modified_files.append(str(file_path.relative_to(self.repo_clone_dir)))
            else:
                # Group exists, add user to it
                if self._add_user_to_group(file_path, display_name):
                    modified_files.append(str(file_path.relative_to(self.repo_clone_dir)))
        
        # Remove user from old groups
        for group_name in groups_to_leave:
            file_path = self._find_group_file(group_name)
            if file_path and self._remove_user_from_group_file(file_path, display_name):
                modified_files.append(str(file_path.relative_to(self.repo_clone_dir)))
        
        return sorted(list(set(modified_files)))  # Remove duplicates and sort
    
    def remove_user_from_group(self, display_name: str, group_name: str) -> List[str]:
        """
        Remove user from a specific group.
        
        Args:
            display_name: User's display name (e.g., "Alice Smith")
            group_name: Group display name to remove user from
        
        Returns:
            List of modified file paths (relative to repo root)
        """
        file_path = self._find_group_file(group_name)
        if file_path is None:
            return []  # Group doesn't exist
        
        if self._remove_user_from_group_file(file_path, display_name):
            return [str(file_path.relative_to(self.repo_clone_dir))]
        
        return []
    
    def _load_all_groups(self) -> Dict[Path, Dict[str, Any]]:
        """
        Load all identity_groups/*.yaml files.
        
        Returns:
            Dictionary mapping file paths to parsed YAML content
        """
        groups = {}
        
        for yaml_file in self.identity_groups_dir.glob("*.yaml"):
            # Skip non-identity-group files (example.yaml, etc.)
            if yaml_file.name in ["example.yaml"]:
                continue
                
            try:
                with open(yaml_file, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                    if data and isinstance(data, dict) and 'name' in data:
                        groups[yaml_file] = data
            except (yaml.YAMLError, IOError) as e:
                # Log warning but continue processing other files
                print(f"Warning: Failed to load group file {yaml_file}: {e}")
                continue
        
        return groups
    
    def _find_group_file(self, display_name: str) -> Optional[Path]:
        """
        Find group file by display name.
        
        Args:
            display_name: Group display name to search for
        
        Returns:
            Path to the group file, or None if not found
        """
        all_groups = self._load_all_groups()
        
        for file_path, group_data in all_groups.items():
            if group_data.get('name') == display_name:
                return Path(file_path)
        
        return None
    
    def _add_user_to_group(self, file_path: Path, display_name: str) -> bool:
        """
        Add user to group's entraid_human_identities list.
        
        Args:
            file_path: Path to the group YAML file
            display_name: User's display name to add
        
        Returns:
            True if file was modified, False if user was already in group
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            if not data:
                return False
            
            # Ensure entraid_human_identities array exists
            if 'entraid_human_identities' not in data:
                data['entraid_human_identities'] = []
            
            # Check if user is already in the group
            if display_name in data['entraid_human_identities']:
                return False
            
            # Add user to the group
            data['entraid_human_identities'].append(display_name)
            data['entraid_human_identities'].sort()  # Keep lists sorted
            
            # Write back to file
            with open(file_path, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
            
            return True
            
        except (yaml.YAMLError, IOError) as e:
            print(f"Error adding user to group file {file_path}: {e}")
            return False
    
    def _create_group_file(self, group_name: str, first_member: str) -> Optional[Path]:
        """
        Create new group file if needed.
        
        Args:
            group_name: Display name of the group to create
            first_member: First member to add to the group
        
        Returns:
            Path to the created file, or None if creation failed
        """
        # Generate filename from group name
        sanitized_name = self._sanitize_group_name(group_name)
        file_name = f"identity_group_{sanitized_name}.yaml"
        file_path = self.identity_groups_dir / file_name
        
        # Check if file already exists
        if file_path.exists():
            return None
        
        # Create basic group structure
        group_data = {
            'name': group_name,
            'contact': 'scim-provisioning@example.com',  # Default contact
            'type': 'internal',  # SCIM groups are internal
            'human_identities': [],
            'application_identities': [],
            'entraid_human_identities': [first_member] if first_member else [],
            'sub_groups': [],
            'identity_group_policies': []
        }
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                yaml.dump(group_data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
            
            return file_path
            
        except IOError as e:
            print(f"Error creating group file {file_path}: {e}")
            return None
    
    def _remove_user_from_group_file(self, file_path: Path, display_name: str) -> bool:
        """
        Remove user from group file's entraid_human_identities list.
        
        Args:
            file_path: Path to the group YAML file
            display_name: User's display name to remove
        
        Returns:
            True if file was modified, False if user wasn't in group
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            if not data:
                return False
            
            # Check if entraid_human_identities exists and contains the user
            entraid_identities = data.get('entraid_human_identities', [])
            if display_name not in entraid_identities:
                return False
            
            # Remove user from the group
            entraid_identities.remove(display_name)
            data['entraid_human_identities'] = entraid_identities
            
            # Write back to file
            with open(file_path, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
            
            return True
            
        except (yaml.YAMLError, IOError) as e:
            print(f"Error removing user from group file {file_path}: {e}")
            return False
    
    def _sanitize_group_name(self, group_name: str) -> str:
        """
        Sanitize group name for use in filenames.
        
        Args:
            group_name: Group display name to sanitize
        
        Returns:
            Sanitized name suitable for filenames
        """
        # Convert to lowercase and replace spaces with underscores
        sanitized = group_name.lower().replace(' ', '_')
        
        # Remove special characters (keep only alphanumeric and underscores)
        sanitized = re.sub(r'[^a-z0-9_]', '', sanitized)
        
        # Replace multiple consecutive underscores with single underscore
        sanitized = re.sub(r'_+', '_', sanitized)
        
        # Remove leading/trailing underscores
        sanitized = sanitized.strip('_')
        
        # Ensure we have a valid name
        if not sanitized:
            sanitized = 'unknown_group'
        
        return sanitized
    
    def remove_user_from_all_groups(self, user_name: str) -> List[str]:
        """
        Remove user from all groups they are currently a member of.
        
        This method is used for user deactivation/deletion to clean up
        group memberships across all identity groups.
        
        Args:
            user_name: Display name of user to remove from all groups
        
        Returns:
            List of modified file paths (relative to repo root)
        """
        modified_files = []
        
        try:
            # Load all group files
            groups_data = self._load_all_groups()
            
            # Check each group for the user and remove if found
            for file_path, data in groups_data.items():
                entraid_identities = data.get('entraid_human_identities', [])
                
                # Check if user is in this group
                if user_name in entraid_identities:
                    # Remove user from the list
                    entraid_identities.remove(user_name)
                    entraid_identities.sort()  # Keep list sorted
                    data['entraid_human_identities'] = entraid_identities
                    
                    # Write back to file
                    with open(file_path, 'w', encoding='utf-8') as f:
                        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
                    
                    # Add to modified files list (relative path from repo root)
                    relative_path = file_path.relative_to(self.repo_clone_dir)
                    modified_files.append(str(relative_path))
                    
                    group_name = data.get('name', 'unknown')
                    print(f"Removed user {user_name} from group {group_name}")
        
        except Exception as e:
            print(f"Error removing user {user_name} from all groups: {e}")
        
        return modified_files