#!/usr/bin/env python3
"""
Mock EntraID SCIM Client Script

This script simulates EntraID sending SCIM requests to the SCIM Bridge for local testing.
It can be used to test user creation, group updates, and deactivation workflows without
requiring an actual EntraID tenant.

Usage:
    python mock-entraid-scim-client.py

Configuration:
    Set SCIM_BRIDGE_URL and BEARER_TOKEN environment variables or modify the defaults below.

Examples:
    # Test full user lifecycle
    python mock-entraid-scim-client.py

    # Set custom endpoint and token
    export SCIM_BRIDGE_URL="http://localhost:8080"
    export BEARER_TOKEN="test-token-123"
    python mock-entraid-scim-client.py
"""

import json
import os
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional, Any

import requests


class MockEntraIDSCIMClient:
    """Mock SCIM client that simulates EntraID user provisioning operations."""

    def __init__(self, base_url: str, bearer_token: str):
        """Initialize the mock SCIM client.
        
        Args:
            base_url: SCIM Bridge base URL (e.g., http://localhost:8080)
            bearer_token: Bearer token for authentication
        """
        self.base_url = base_url.rstrip('/')
        self.bearer_token = bearer_token
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {bearer_token}',
            'Content-Type': 'application/scim+json',
            'Accept': 'application/scim+json'
        })

    def create_user(self, user_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create a new user via SCIM POST request.
        
        Args:
            user_data: SCIM user payload dict
            
        Returns:
            SCIM response dict or None if failed
        """
        url = f"{self.base_url}/scim/v2/Users"
        
        print(f"\n🔄 Creating user: {user_data.get('displayName', 'Unknown')}")
        print(f"📧 Email: {user_data.get('userName', 'N/A')}")
        print(f"🏢 Role: {user_data.get('title', 'N/A')}")
        print(f"👥 Team: {user_data.get('department', 'N/A')}")
        print(f"📋 Groups: {', '.join([g['display'] for g in user_data.get('groups', [])])}")
        
        try:
            response = self.session.post(url, json=user_data)
            print(f"📤 POST {url}")
            print(f"📊 Status: {response.status_code}")
            
            if response.status_code == 201:
                result = response.json()
                print(f"✅ User created successfully!")
                print(f"🆔 SCIM ID: {result.get('id', 'N/A')}")
                if 'urn:ietf:params:scim:schemas:extension:vault:2.0:User' in result:
                    vault_ext = result['urn:ietf:params:scim:schemas:extension:vault:2.0:User']
                    print(f"📁 YAML File: {vault_ext.get('yamlFilename', 'N/A')}")
                    print(f"🔗 PR URL: {vault_ext.get('prUrl', 'N/A')}")
                return result
            else:
                print(f"❌ Failed to create user: {response.status_code}")
                print(f"🔍 Response: {response.text}")
                return None
                
        except requests.RequestException as e:
            print(f"💥 Request failed: {e}")
            return None

    def update_user_groups(self, user_id: str, groups_to_add: List[Dict], groups_to_remove: List[Dict]) -> bool:
        """Update user's group memberships via SCIM PATCH request.
        
        Args:
            user_id: SCIM user ID (EntraID object ID)
            groups_to_add: List of group objects to add user to
            groups_to_remove: List of group objects to remove user from
            
        Returns:
            True if successful, False otherwise
        """
        url = f"{self.base_url}/scim/v2/Users/{user_id}"
        
        operations = []
        
        # Add operations for new groups
        for group in groups_to_add:
            operations.append({
                "op": "add",
                "path": "groups",
                "value": group
            })
            
        # Remove operations for leaving groups
        for group in groups_to_remove:
            operations.append({
                "op": "remove", 
                "path": f"groups[display eq \"{group['display']}\"]"
            })
        
        patch_payload = {
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
            "Operations": operations
        }
        
        print(f"\n🔄 Updating group memberships for user {user_id}")
        if groups_to_add:
            print(f"➕ Adding to groups: {', '.join([g['display'] for g in groups_to_add])}")
        if groups_to_remove:
            print(f"➖ Removing from groups: {', '.join([g['display'] for g in groups_to_remove])}")
            
        try:
            response = self.session.patch(url, json=patch_payload)
            print(f"📤 PATCH {url}")
            print(f"📊 Status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Group memberships updated successfully!")
                if 'urn:ietf:params:scim:schemas:extension:vault:2.0:User' in result:
                    vault_ext = result['urn:ietf:params:scim:schemas:extension:vault:2.0:User']
                    print(f"🔗 Groups PR URL: {vault_ext.get('prUrl', 'N/A')}")
                return True
            else:
                print(f"❌ Failed to update groups: {response.status_code}")
                print(f"🔍 Response: {response.text}")
                return False
                
        except requests.RequestException as e:
            print(f"💥 Request failed: {e}")
            return False

    def deactivate_user(self, user_id: str) -> bool:
        """Deactivate a user via SCIM DELETE request.
        
        Args:
            user_id: SCIM user ID (EntraID object ID)
            
        Returns:
            True if successful, False otherwise
        """
        url = f"{self.base_url}/scim/v2/Users/{user_id}"
        
        print(f"\n🔄 Deactivating user {user_id}")
        
        try:
            response = self.session.delete(url)
            print(f"📤 DELETE {url}")
            print(f"📊 Status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ User deactivated successfully!")
                print(f"⚠️  Status: {result.get('active', 'Unknown')}")
                if 'urn:ietf:params:scim:schemas:extension:vault:2.0:User' in result:
                    vault_ext = result['urn:ietf:params:scim:schemas:extension:vault:2.0:User']
                    print(f"📁 YAML File: {vault_ext.get('yamlFilename', 'N/A')}")
                    print(f"🔗 PR URL: {vault_ext.get('prUrl', 'N/A')}")
                return True
            else:
                print(f"❌ Failed to deactivate user: {response.status_code}")
                print(f"🔍 Response: {response.text}")
                return False
                
        except requests.RequestException as e:
            print(f"💥 Request failed: {e}")
            return False

    def list_users(self) -> Optional[List[Dict]]:
        """List all users via SCIM GET request (reconciliation).
        
        Returns:
            List of user dicts or None if failed
        """
        url = f"{self.base_url}/scim/v2/Users"
        
        print(f"\n🔄 Listing all users (reconciliation)")
        
        try:
            response = self.session.get(url)
            print(f"📤 GET {url}")
            print(f"📊 Status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                users = result.get('Resources', [])
                print(f"✅ Retrieved {len(users)} users")
                
                for i, user in enumerate(users, 1):
                    print(f"  {i}. {user.get('displayName', 'Unknown')} ({user.get('userName', 'N/A')})")
                    print(f"     ID: {user.get('id', 'N/A')}, Active: {user.get('active', 'Unknown')}")
                
                return users
            else:
                print(f"❌ Failed to list users: {response.status_code}")
                print(f"🔍 Response: {response.text}")
                return None
                
        except requests.RequestException as e:
            print(f"💥 Request failed: {e}")
            return None

    def test_health_endpoint(self) -> bool:
        """Test the SCIM Bridge health endpoint.
        
        Returns:
            True if healthy, False otherwise
        """
        url = f"{self.base_url}/health"
        
        print(f"🏥 Testing health endpoint...")
        
        try:
            # Don't use session (health endpoint shouldn't require auth)
            response = requests.get(url, timeout=5)
            print(f"📤 GET {url}")
            print(f"📊 Status: {response.status_code}")
            
            if response.status_code == 200:
                print(f"✅ SCIM Bridge is healthy!")
                return True
            else:
                print(f"⚠️  Health check failed: {response.status_code}")
                return False
                
        except requests.RequestException as e:
            print(f"💥 Health check failed: {e}")
            return False


def create_sample_user_data(name: str, email: str, title: str, department: str, groups: List[str]) -> Dict[str, Any]:
    """Create a sample SCIM user payload.
    
    Args:
        name: Display name (e.g., "Jane Smith")
        email: Email/UPN (e.g., "jane.smith@contoso.com")
        title: Job title (e.g., "Senior Engineer") 
        department: Team/department (e.g., "Platform Engineering")
        groups: List of group names (e.g., ["Developers", "Senior Engineers"])
        
    Returns:
        SCIM user payload dict
    """
    # Generate a fake EntraID object ID (UUID format)
    import uuid
    entraid_object_id = str(uuid.uuid4())
    
    user_data = {
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
        "id": entraid_object_id,
        "externalId": entraid_object_id,
        "userName": email,  # User Principal Name
        "displayName": name,
        "emails": [
            {
                "value": email,
                "type": "work", 
                "primary": True
            }
        ],
        "active": True,
        "title": title,
        "department": department
    }
    
    # Add groups if provided
    if groups:
        user_data["groups"] = []
        for group_name in groups:
            user_data["groups"].append({
                "value": str(uuid.uuid4()),  # Fake group ID
                "$ref": f"/Groups/{uuid.uuid4()}",
                "display": group_name,
                "type": "direct"
            })
    
    return user_data


def main():
    """Main function to run the mock SCIM client test scenarios."""
    
    # Configuration
    SCIM_BRIDGE_URL = os.environ.get('SCIM_BRIDGE_URL', 'http://localhost:8080')
    BEARER_TOKEN = os.environ.get('BEARER_TOKEN', 'test-bearer-token-change-me')
    
    print("🚀 Mock EntraID SCIM Client")
    print("=" * 50)
    print(f"📡 SCIM Bridge URL: {SCIM_BRIDGE_URL}")
    print(f"🔐 Bearer Token: {BEARER_TOKEN[:8]}{'*' * 8}")
    print()
    
    # Initialize client
    client = MockEntraIDSCIMClient(SCIM_BRIDGE_URL, BEARER_TOKEN)
    
    # Test health endpoint first
    if not client.test_health_endpoint():
        print("\n❌ Health check failed - is the SCIM Bridge running?")
        print("   Try: docker compose up -d scim-bridge")
        sys.exit(1)
    
    print("\n" + "=" * 50)
    print("🧪 Starting SCIM Test Scenarios")
    print("=" * 50)
    
    # Test Scenario 1: Create new user
    print("\n📋 Test 1: Create New User")
    print("-" * 30)
    
    user_data = create_sample_user_data(
        name="Alice Johnson",
        email="alice.johnson@contoso.com", 
        title="Senior Software Engineer",
        department="Platform Engineering",
        groups=["Developers", "Senior Engineers", "Platform Team"]
    )
    
    created_user = client.create_user(user_data)
    if not created_user:
        print("❌ User creation failed, skipping remaining tests")
        return
    
    user_id = created_user.get('id')
    
    # Wait for async processing
    print("\n⏳ Waiting 2 seconds for PR creation...")
    time.sleep(2)
    
    # Test Scenario 2: Update user's group memberships
    print("\n📋 Test 2: Update Group Memberships") 
    print("-" * 30)
    
    # Add to new groups
    new_groups = [
        {
            "value": str(uuid.uuid4()),
            "$ref": f"/Groups/{uuid.uuid4()}",
            "display": "Tech Leads",
            "type": "direct"
        },
        {
            "value": str(uuid.uuid4()), 
            "$ref": f"/Groups/{uuid.uuid4()}",
            "display": "Architecture Committee",
            "type": "direct"
        }
    ]
    
    # Remove from existing groups
    old_groups = [
        {
            "value": str(uuid.uuid4()),
            "$ref": f"/Groups/{uuid.uuid4()}",  
            "display": "Platform Team",
            "type": "direct"
        }
    ]
    
    import uuid
    client.update_user_groups(user_id, new_groups, old_groups)
    
    # Wait for async processing
    print("\n⏳ Waiting 2 seconds for PR creation...")
    time.sleep(2)
    
    # Test Scenario 3: List users (reconciliation)
    print("\n📋 Test 3: List Users (Reconciliation)")
    print("-" * 30)
    
    client.list_users()
    
    # Test Scenario 4: Deactivate user
    print("\n📋 Test 4: Deactivate User")
    print("-" * 30)
    
    client.deactivate_user(user_id)
    
    # Final summary
    print("\n" + "=" * 50)
    print("🎉 SCIM Test Scenarios Complete!")
    print("=" * 50)
    print()
    print("📋 Summary of operations performed:")
    print("   ✅ Health check")
    print("   ✅ User creation (POST /scim/v2/Users)")
    print("   ✅ Group membership update (PATCH /scim/v2/Users/{id})")  
    print("   ✅ User listing/reconciliation (GET /scim/v2/Users)")
    print("   ✅ User deactivation (DELETE /scim/v2/Users/{id})")
    print()
    print("🔍 Check the SCIM Bridge logs for detailed processing:")
    print("   docker logs -f scim-bridge")
    print()
    print("📂 Check your Git repository for generated PRs:")
    print("   - User identity YAML files in identities/ directory")
    print("   - Group membership updates in identity_groups/ directory")


if __name__ == "__main__":
    main()