#!/usr/bin/env python3
"""
Test script to simulate EntraID group membership synchronization
without requiring the full SCIM Bridge infrastructure.
"""

import os
import sys
import yaml
import json
from pathlib import Path
from datetime import datetime

# Add the SCIM bridge app directory to the path
scim_app_dir = Path(__file__).parent / "scim-bridge" / "app"
sys.path.insert(0, str(scim_app_dir))

try:
    from services.group_handler import GroupHandler
    from services.yaml_generator import YAMLGenerator
except ImportError as e:
    print(f"❌ Failed to import SCIM Bridge modules: {e}")
    print(f"Looking for modules in: {scim_app_dir}")
    print("Please ensure the SCIM Bridge code exists in scim-bridge/app/")
    sys.exit(1)


def setup_test_environment():
    """Set up a test environment in /tmp for group testing."""
    test_dir = Path("/tmp/vault-group-test")
    
    # Clean up any existing test directory
    if test_dir.exists():
        import shutil
        shutil.rmtree(test_dir)
    
    # Create directory structure
    test_dir.mkdir()
    (test_dir / "identity_groups").mkdir()
    (test_dir / "identities").mkdir()
    
    # Copy the schema file
    schema_src = Path("/workspaces/vault-config-as-code/identities/schema_entraid_human.yaml")
    schema_dst = test_dir / "identities" / "schema_entraid_human.yaml"
    
    if schema_src.exists():
        import shutil
        shutil.copy2(schema_src, schema_dst)
    
    return test_dir


def create_test_user_yaml(test_dir: Path, user_name: str):
    """Create a test user YAML file to simulate a user that exists."""
    yaml_generator = YAMLGenerator(test_dir / "identities" / "schema_entraid_human.yaml")
    
    # Create a mock SCIM user payload
    mock_scim_user = {
        "id": "698bcd38-9b65-4dde-b88b-87c77c01e3e7",  # Our test user ID
        "userName": "scimtestuser@songlininggmail.onmicrosoft.com",
        "displayName": user_name,
        "emails": [{"value": "scimtestuser@songlininggmail.onmicrosoft.com", "primary": True}],
        "active": True,
        "title": "Test Engineer",
        "department": "QA Testing"
    }
    
    # Generate YAML content
    filename, yaml_content = yaml_generator.scim_to_yaml(mock_scim_user)
    
    # Write the YAML file
    yaml_file = test_dir / "identities" / filename
    with open(yaml_file, 'w', encoding='utf-8') as f:
        f.write(yaml_content)
    
    print(f"✅ Created test user YAML file: {filename}")
    return filename, yaml_content


def test_group_membership_sync():
    """Test the group membership synchronization workflow."""
    print("🔄 Setting up test environment...")
    test_dir = setup_test_environment()
    
    print("👤 Creating test user YAML file...")
    user_filename, user_yaml = create_test_user_yaml(test_dir, "SCIM Test User")
    
    print("🏗️ Initializing GroupHandler...")
    group_handler = GroupHandler(str(test_dir))
    
    # Test 1: Sync user to new group (should create group file)
    print("\n📋 Test 1: Adding user to new group 'SCIM-Test-Developers'")
    modified_files = group_handler.sync_user_groups(
        display_name="SCIM Test User",
        group_names=["SCIM-Test-Developers"]
    )
    
    print(f"   Modified files: {modified_files}")
    
    # Verify the group file was created
    group_file = test_dir / "identity_groups" / "identity_group_scim_test_developers.yaml"
    if group_file.exists():
        print("   ✅ Group file created successfully")
        with open(group_file, 'r', encoding='utf-8') as f:
            group_content = yaml.safe_load(f)
        print(f"   📄 Group content: {json.dumps(group_content, indent=2)}")
    else:
        print("   ❌ Group file was not created")
        return False
    
    # Test 2: Add user to additional group
    print("\n📋 Test 2: Adding user to additional group 'Developers'")
    modified_files = group_handler.sync_user_groups(
        display_name="SCIM Test User", 
        group_names=["SCIM-Test-Developers", "Developers"]
    )
    
    print(f"   Modified files: {modified_files}")
    
    # Test 3: Remove user from one group
    print("\n📋 Test 3: Removing user from 'SCIM-Test-Developers' group")
    modified_files = group_handler.sync_user_groups(
        display_name="SCIM Test User",
        group_names=["Developers"]  # Only keep Developers group
    )
    
    print(f"   Modified files: {modified_files}")
    
    # Verify the user was removed from the first group
    if group_file.exists():
        with open(group_file, 'r', encoding='utf-8') as f:
            group_content = yaml.safe_load(f)
        if "SCIM Test User" in group_content.get("entraid_human_identities", []):
            print("   ❌ User was not removed from SCIM-Test-Developers group")
            return False
        else:
            print("   ✅ User successfully removed from SCIM-Test-Developers group")
    
    # Test 4: Check Developers group file
    dev_group_file = test_dir / "identity_groups" / "identity_group_developers.yaml"
    if dev_group_file.exists():
        print("   ✅ Developers group file exists")
        with open(dev_group_file, 'r', encoding='utf-8') as f:
            dev_group_content = yaml.safe_load(f)
        
        if "SCIM Test User" in dev_group_content.get("entraid_human_identities", []):
            print("   ✅ User correctly maintained in Developers group")
        else:
            print("   ❌ User missing from Developers group")
            return False
    
    print("\n🎉 All group synchronization tests passed!")
    print(f"\n📂 Test files created in: {test_dir}")
    print("   You can inspect the generated YAML files to verify the structure.")
    
    return True


def simulate_entraid_patch_request():
    """Simulate what happens when EntraID sends a PATCH request for group changes."""
    print("\n" + "=" * 60)
    print("🔄 Simulating EntraID PATCH request workflow...")
    print("=" * 60)
    
    # This simulates the SCIM PATCH payload that EntraID would send
    mock_patch_payload = {
        "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
        "Operations": [
            {
                "op": "add",
                "path": "groups",
                "value": [
                    {
                        "value": "15402d23-f15d-40c4-b4cd-bff2a0221f80",  # Our test group ID
                        "display": "SCIM-Test-Developers",
                        "type": "direct"
                    }
                ]
            }
        ]
    }
    
    print("📨 Simulated PATCH payload from EntraID:")
    print(json.dumps(mock_patch_payload, indent=2))
    
    # Extract group information from the patch payload
    groups_to_add = []
    for operation in mock_patch_payload.get("Operations", []):
        if operation["op"] == "add" and operation["path"] == "groups":
            for group in operation["value"]:
                groups_to_add.append(group["display"])
    
    print(f"\n🏷️ Extracted groups to add: {groups_to_add}")
    
    # This is what the SCIM Bridge would do upon receiving this PATCH
    print("\n🔄 SCIM Bridge processing:")
    print("   1. Parse PATCH payload")
    print("   2. Extract group membership changes")
    print("   3. Call GroupHandler.sync_user_groups()")
    print("   4. Create Git PR with changes")
    
    return groups_to_add


if __name__ == "__main__":
    print("🧪 Testing EntraID Group Membership Synchronization")
    print("=" * 60)
    
    try:
        # Simulate the EntraID PATCH request
        groups_from_patch = simulate_entraid_patch_request()
        
        # Test the group synchronization functionality
        success = test_group_membership_sync()
        
        if success:
            print("\n✅ Group membership synchronization test completed successfully!")
            print("\n🎯 This simulates what happens when:")
            print("   1. A user is added to a group in EntraID")
            print("   2. EntraID sends a SCIM PATCH request")
            print("   3. SCIM Bridge processes the group changes")
            print("   4. GroupHandler updates identity_groups YAML files")
            print("   5. GitHandler creates a PR with the changes")
        else:
            print("\n❌ Group membership synchronization test failed!")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)