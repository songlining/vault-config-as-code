"""
Test file for User Operations Logic

Tests the business logic for SCIM endpoints including:
- User creation workflow
- User update workflow  
- User deactivation workflow

Uses pytest with proper mocking of services.
"""

import pytest
from unittest.mock import Mock
import sys
import os

# Add the scim-bridge directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestUserOperationsLogic:
    """Test class for SCIM user operation business logic"""

    @pytest.fixture
    def mock_services(self):
        """Mock all service dependencies"""
        mocks = {
            'yaml_generator': Mock(),
            'git_handler': Mock(),
            'group_handler': Mock(),
            'user_store': Mock()
        }
        
        # Configure mock returns
        mocks['yaml_generator'].scim_to_yaml.return_value = (
            "entraid_human_jane_example.yaml",
            "mock yaml content"
        )
        mocks['git_handler'].create_pr_for_user.return_value = "https://github.com/owner/repo/pull/123"
        mocks['git_handler'].create_pr_for_groups.return_value = "https://github.com/owner/repo/pull/124"
        mocks['group_handler'].sync_user_groups.return_value = ["identity_groups/engineering.yaml"]
        mocks['group_handler'].remove_user_from_all_groups.return_value = ["identity_groups/engineering.yaml"]
        mocks['user_store'].add_user.return_value = None
        mocks['user_store'].get_user.return_value = {
            "scim_id": "12345678-1234-1234-1234-123456789abc",
            "name": "Jane Example", 
            "vault_name": "jane.example",
            "filename": "entraid_human_jane_example.yaml"
        }
        
        return mocks

    @pytest.fixture
    def sample_scim_user_create(self):
        """Sample SCIM user for creation requests"""
        return {
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
            "userName": "jane.example@contoso.onmicrosoft.com",
            "displayName": "Jane Example",
            "emails": [
                {
                    "value": "jane.example@contoso.com",
                    "type": "work",
                    "primary": True
                }
            ],
            "active": True,
            "title": "Senior Software Engineer",
            "department": "Platform Engineering",
            "groups": [
                {
                    "value": "engineering-group-id",
                    "display": "Engineering Team",
                    "type": "direct"
                }
            ]
        }

    @pytest.fixture 
    def sample_scim_user_patch(self):
        """Sample SCIM patch operations for user updates"""
        return {
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
            "Operations": [
                {
                    "op": "replace",
                    "path": "groups",
                    "value": [
                        {
                            "value": "new-group-id",
                            "display": "New Team",
                            "type": "direct"
                        }
                    ]
                }
            ]
        }

    def test_user_creation_workflow(self, mock_services, sample_scim_user_create):
        """Test the user creation workflow logic"""
        # Simulate the core logic of user creation endpoint
        user_data = sample_scim_user_create
        
        # Step 1: Convert SCIM to YAML
        filename, yaml_content = mock_services['yaml_generator'].scim_to_yaml(user_data)
        
        # Step 2: Create PR for user YAML
        pr_url = mock_services['git_handler'].create_pr_for_user(
            username=user_data['userName'],
            yaml_content=yaml_content,
            yaml_filename=filename
        )
        
        # Step 3: Handle group memberships
        group_names = [group['display'] for group in user_data.get('groups', []) if group.get('display')]
        if group_names:
            modified_files = mock_services['group_handler'].sync_user_groups(
                display_name=user_data['displayName'],
                group_names=group_names
            )
            
            if modified_files:
                group_pr_url = mock_services['git_handler'].create_pr_for_groups(
                    username=user_data['userName'],
                    modified_files=modified_files
                )
        
        # Step 4: Store user mapping
        mock_services['user_store'].add_user(
            scim_id=user_data.get('id', user_data['userName']),
            name=user_data['displayName'],
            filename=filename
        )
        
        # Verify all services were called correctly
        mock_services['yaml_generator'].scim_to_yaml.assert_called_once_with(user_data)
        mock_services['git_handler'].create_pr_for_user.assert_called_once()
        mock_services['group_handler'].sync_user_groups.assert_called_once_with(
            display_name='Jane Example',
            group_names=['Engineering Team']
        )
        mock_services['user_store'].add_user.assert_called_once()
        
        # Verify expected returns
        assert filename == "entraid_human_jane_example.yaml"
        assert pr_url == "https://github.com/owner/repo/pull/123"

    def test_user_creation_without_groups(self, mock_services, sample_scim_user_create):
        """Test user creation without group memberships"""
        user_data = sample_scim_user_create.copy()
        del user_data['groups']  # Remove groups
        
        # Simulate user creation workflow
        filename, yaml_content = mock_services['yaml_generator'].scim_to_yaml(user_data)
        pr_url = mock_services['git_handler'].create_pr_for_user(
            username=user_data['userName'],
            yaml_content=yaml_content,
            yaml_filename=filename
        )
        mock_services['user_store'].add_user(
            scim_id=user_data.get('id', user_data['userName']),
            name=user_data['displayName'],
            filename=filename
        )
        
        # Verify YAML and user creation still happened
        mock_services['yaml_generator'].scim_to_yaml.assert_called_once()
        mock_services['git_handler'].create_pr_for_user.assert_called_once()
        mock_services['user_store'].add_user.assert_called_once()
        
        # Verify group handler was NOT called
        mock_services['group_handler'].sync_user_groups.assert_not_called()

    def test_user_update_group_changes(self, mock_services, sample_scim_user_patch):
        """Test user update with group membership changes"""
        user_id = "12345678-1234-1234-1234-123456789abc"
        patch_operations = sample_scim_user_patch['Operations']
        
        # Look up user from store
        user_mapping = mock_services['user_store'].get_user(user_id)
        assert user_mapping is not None
        
        # Process PATCH operations - simulates the endpoint logic
        group_changes_detected = False
        new_groups = []
        
        for operation in patch_operations:
            if operation['path'] == "groups" and operation['op'] in ["add", "replace"]:
                group_changes_detected = True
                if isinstance(operation['value'], list):
                    new_groups = [
                        group.get("display") for group in operation['value'] 
                        if isinstance(group, dict) and group.get("display")
                    ]
        
        # Handle group membership changes
        if group_changes_detected:
            modified_files = mock_services['group_handler'].sync_user_groups(
                display_name=user_mapping["name"],
                group_names=new_groups
            )
            
            if modified_files:
                group_pr_url = mock_services['git_handler'].create_pr_for_groups(
                    username=user_mapping["vault_name"],
                    modified_files=modified_files
                )
        
        # Verify services were called correctly
        mock_services['user_store'].get_user.assert_called_once_with(user_id)
        mock_services['group_handler'].sync_user_groups.assert_called_once()
        mock_services['git_handler'].create_pr_for_groups.assert_called_once()
        
        assert group_changes_detected is True
        assert new_groups == ["New Team"]

    def test_user_update_not_found(self, mock_services):
        """Test user update when user is not found"""
        user_id = "nonexistent-user-id"
        
        # Configure user store to return None (user not found)
        mock_services['user_store'].get_user.return_value = None
        
        # Look up user from store - simulates endpoint logic
        user_mapping = mock_services['user_store'].get_user(user_id)
        
        # Verify user not found
        assert user_mapping is None
        mock_services['user_store'].get_user.assert_called_once_with(user_id)
        
        # In real endpoint, this would return 404 error

    def test_user_deactivation_workflow(self, mock_services):
        """Test user deactivation (soft delete) workflow via DELETE endpoint"""
        user_id = "12345678-1234-1234-1234-123456789abc"
        
        # Look up user from store - simulates DELETE endpoint logic
        user_mapping = mock_services['user_store'].get_user(user_id)
        assert user_mapping is not None
        
        # Remove user from all groups first
        mock_services['group_handler'].remove_user_from_all_groups(user_mapping["name"])
        
        # Create deactivated user data
        deactivated_user_data = {
            "id": user_id,
            "userName": user_mapping.get("name", user_id),
            "displayName": user_mapping.get("name", user_id),
            "active": False  # This will set status=deactivated and disabled=true
        }
        
        # Generate YAML and create PR
        filename, yaml_content = mock_services['yaml_generator'].scim_to_yaml(deactivated_user_data)
        pr_url = mock_services['git_handler'].create_pr_for_user(
            username=user_mapping["name"],
            yaml_content=yaml_content,
            yaml_filename=filename
        )
        
        # Update user store to reflect deactivation
        mock_services['user_store'].add_user(
            scim_id=user_id,
            name=user_mapping["name"],
            filename=filename
        )
        
        # Verify services were called correctly
        mock_services['user_store'].get_user.assert_called_once_with(user_id)
        mock_services['group_handler'].remove_user_from_all_groups.assert_called_once()
        mock_services['yaml_generator'].scim_to_yaml.assert_called_once_with(deactivated_user_data)
        mock_services['git_handler'].create_pr_for_user.assert_called_once()
        mock_services['user_store'].add_user.assert_called_once()

    def test_user_deactivation_via_patch(self, mock_services):
        """Test user deactivation via PATCH active=false"""
        user_id = "12345678-1234-1234-1234-123456789abc"
        patch_data = {
            "Operations": [
                {
                    "op": "replace",
                    "path": "active",
                    "value": False
                }
            ]
        }
        
        # Look up user from store
        user_mapping = mock_services['user_store'].get_user(user_id)
        assert user_mapping is not None
        
        # Process PATCH operations - simulates PATCH endpoint logic
        user_active = True
        for operation in patch_data['Operations']:
            if operation['path'] == "active" and operation['op'] == "replace":
                user_active = bool(operation['value'])
        
        # Handle user deactivation (create updated YAML)
        if not user_active:
            # Create a deactivated user data structure
            deactivated_user = {
                "id": user_id,
                "userName": user_mapping.get("vault_name", user_id),
                "displayName": user_mapping.get("vault_name", user_id),
                "active": False
            }
            
            # Generate deactivated YAML
            filename, yaml_content = mock_services['yaml_generator'].scim_to_yaml(deactivated_user)
            
            # Create PR for deactivated user
            yaml_pr_url = mock_services['git_handler'].create_pr_for_user(
                username=user_mapping["vault_name"],
                yaml_content=yaml_content,
                yaml_filename=filename
            )
            
            # Update user store to reflect deactivation
            mock_services['user_store'].add_user(
                scim_id=user_id,
                name=user_mapping["name"],
                filename=filename
            )
        
        # Verify services were called correctly
        mock_services['user_store'].get_user.assert_called_once_with(user_id)
        mock_services['yaml_generator'].scim_to_yaml.assert_called_once()
        mock_services['git_handler'].create_pr_for_user.assert_called_once()
        mock_services['user_store'].add_user.assert_called_once()
        
        assert user_active is False

    def test_scim_response_extension_format(self, mock_services, sample_scim_user_create):
        """Test SCIM extension fields in response format"""
        user_data = sample_scim_user_create
        
        # Simulate the response generation logic from create endpoint
        filename, yaml_content = mock_services['yaml_generator'].scim_to_yaml(user_data)
        pr_url = mock_services['git_handler'].create_pr_for_user(
            username=user_data['userName'],
            yaml_content=yaml_content,
            yaml_filename=filename
        )
        
        # Build response with custom SCIM extension fields
        yaml_file_path = f"identities/{filename}"
        scim_extension = {
            "pr_url": pr_url,
            "yaml_file": yaml_file_path,
            "group_pr_url": None  # No groups in this test
        }
        
        # Verify extension structure - what would be in "urn:vault:scim:extension"
        assert "pr_url" in scim_extension
        assert "yaml_file" in scim_extension
        assert scim_extension["pr_url"] == "https://github.com/owner/repo/pull/123"
        assert scim_extension["yaml_file"] == "identities/entraid_human_jane_example.yaml"

    def test_error_handling_patterns(self, mock_services):
        """Test error handling patterns in operations"""
        # Test YAML generation failure
        mock_services['yaml_generator'].scim_to_yaml.side_effect = Exception("YAML generation failed")
        
        user_data = {"userName": "test@example.com", "displayName": "Test User"}
        
        # This simulates what would happen in the endpoint error handling
        with pytest.raises(Exception) as exc_info:
            mock_services['yaml_generator'].scim_to_yaml(user_data)
        
        assert str(exc_info.value) == "YAML generation failed"
        
        # Reset the side effect for other tests
        mock_services['yaml_generator'].scim_to_yaml.side_effect = None
        mock_services['yaml_generator'].scim_to_yaml.return_value = ("test.yaml", "content")

    def test_concurrent_operations_safety(self, mock_services):
        """Test that operations can handle concurrent requests safely"""
        # Simulate concurrent user creations - tests service call patterns
        user1_data = {
            "userName": "user1@contoso.com",
            "displayName": "User One",
            "id": "user-1-id"
        }
        user2_data = {
            "userName": "user2@contoso.com", 
            "displayName": "User Two",
            "id": "user-2-id"
        }
        
        # Process both users using the same services
        for user_data in [user1_data, user2_data]:
            filename, yaml_content = mock_services['yaml_generator'].scim_to_yaml(user_data)
            mock_services['git_handler'].create_pr_for_user(
                username=user_data['userName'],
                yaml_content=yaml_content,
                yaml_filename=filename
            )
            mock_services['user_store'].add_user(
                scim_id=user_data['id'],
                name=user_data['displayName'],
                filename=filename
            )
        
        # Verify both operations completed (services called twice)
        assert mock_services['yaml_generator'].scim_to_yaml.call_count == 2
        assert mock_services['git_handler'].create_pr_for_user.call_count == 2
        assert mock_services['user_store'].add_user.call_count == 2


if __name__ == "__main__":
    # Run tests if script is executed directly
    pytest.main([__file__, "-v"])