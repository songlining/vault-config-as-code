#!/usr/bin/env python3
"""
Test script for SCIM Bridge main.py application

This script performs basic validation of the main FastAPI application:
- Verifies import and initialization
- Tests endpoint method signatures
- Validates SCIM response structures
"""

import sys
import os
import tempfile
import json
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

def test_imports():
    """Test that all imports work correctly."""
    print("Testing imports...")
    
    try:
        from main import app, startup_event, health_check, create_user, update_user, delete_user, list_users
        from models import SCIMUser, SCIMUserPatch, SCIMListResponse, SCIMError
        from handlers import verify_bearer_token
        from services import YAMLGenerator, GitHandler, GroupHandler, UserStore
        print("✅ All imports successful")
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

def test_app_initialization():
    """Test FastAPI app initialization."""
    print("\nTesting app initialization...")
    
    try:
        from main import app
        
        # Check app title
        if app.title == "SCIM Bridge for Vault":
            print("✅ App title correct")
        else:
            print(f"❌ App title incorrect: {app.title}")
            return False
        
        # Check that app has the expected routes
        route_paths = [route.path for route in app.routes]
        expected_paths = ["/health", "/scim/v2/Users", "/scim/v2/Users/{user_id}"]
        
        for expected_path in expected_paths:
            if any(expected_path in path for path in route_paths):
                print(f"✅ Route {expected_path} found")
            else:
                print(f"❌ Route {expected_path} not found")
                return False
        
        print("✅ App initialization successful")
        return True
        
    except Exception as e:
        print(f"❌ App initialization error: {e}")
        return False

def test_scim_models():
    """Test SCIM model creation and validation."""
    print("\nTesting SCIM models...")
    
    try:
        from models import SCIMUser, SCIMUserPatch, SCIMEmail, SCIMGroupMembership, SCIMPatchOperation
        
        # Test SCIMUser model
        user = SCIMUser(
            id="12345678-1234-1234-1234-123456789abc",
            userName="test.user@contoso.com",
            displayName="Test User",
            emails=[SCIMEmail(value="test.user@contoso.com", type="work", primary=True)],
            active=True,
            title="Engineer",
            department="IT"
        )
        
        print("✅ SCIMUser model creation successful")
        
        # Test SCIMUserPatch model
        patch = SCIMUserPatch(
            Operations=[
                SCIMPatchOperation(op="replace", path="active", value=False)
            ]
        )
        
        print("✅ SCIMUserPatch model creation successful")
        
        # Verify JSON serialization
        user_json = user.model_dump()
        if isinstance(user_json, dict) and "userName" in user_json:
            print("✅ SCIM model serialization successful")
        else:
            print("❌ SCIM model serialization failed")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ SCIM models error: {e}")
        return False

def test_yaml_generator():
    """Test YAML generation functionality."""
    print("\nTesting YAML generator...")
    
    try:
        from services import YAMLGenerator
        
        # Create a temporary schema file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write('''
$schema: "http://json-schema.org/draft-07/schema#"
title: "Test Schema"
type: object
properties:
  test:
    type: string
''')
            schema_path = f.name
        
        try:
            # Initialize YAML generator
            generator = YAMLGenerator(schema_path=schema_path)
            
            # Test SCIM to YAML conversion
            scim_data = {
                "id": "12345678-1234-1234-1234-123456789abc",
                "userName": "test.user@contoso.com",
                "displayName": "Test User",
                "emails": [{"value": "test.user@contoso.com", "type": "work", "primary": True}],
                "active": True,
                "title": "Engineer",
                "department": "IT"
            }
            
            filename, yaml_content = generator.scim_to_yaml(scim_data)
            
            if filename and filename.endswith('.yaml') and filename.startswith('entraid_human_'):
                print("✅ YAML filename generation successful")
            else:
                print(f"❌ YAML filename generation failed: {filename}")
                return False
            
            if yaml_content and 'identity:' in yaml_content and 'authentication:' in yaml_content:
                print("✅ YAML content generation successful")
            else:
                print("❌ YAML content generation failed")
                return False
            
            return True
            
        finally:
            # Clean up temp file
            os.unlink(schema_path)
        
    except Exception as e:
        print(f"❌ YAML generator error: {e}")
        return False

def test_user_store():
    """Test user store functionality."""
    print("\nTesting user store...")
    
    try:
        from services import UserStore
        
        # Create temporary store file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            store_path = f.name
        
        try:
            # Initialize user store
            store = UserStore(store_path=store_path)
            
            # Test adding user
            store.add_user(
                scim_id="test-id-123",
                vault_name="Test User",
                yaml_filename="entraid_human_test_user.yaml"
            )
            
            # Test retrieving user
            user_data = store.get_user("test-id-123")
            
            if user_data and user_data["vault_name"] == "Test User":
                print("✅ User store operations successful")
                return True
            else:
                print(f"❌ User store retrieval failed: {user_data}")
                return False
            
        finally:
            # Clean up temp file
            os.unlink(store_path)
        
    except Exception as e:
        print(f"❌ User store error: {e}")
        return False

def test_endpoint_signatures():
    """Test that endpoint functions have correct signatures."""
    print("\nTesting endpoint signatures...")
    
    try:
        from main import health_check, create_user, update_user, delete_user, list_users
        import inspect
        
        # Test health_check signature
        sig = inspect.signature(health_check)
        if len(sig.parameters) == 0:
            print("✅ health_check signature correct")
        else:
            print(f"❌ health_check signature incorrect: {sig}")
            return False
        
        # Test create_user signature
        sig = inspect.signature(create_user)
        if 'user' in sig.parameters:
            print("✅ create_user signature correct")
        else:
            print(f"❌ create_user signature incorrect: {sig}")
            return False
        
        # Test update_user signature
        sig = inspect.signature(update_user)
        if 'user_id' in sig.parameters and 'patch' in sig.parameters:
            print("✅ update_user signature correct")
        else:
            print(f"❌ update_user signature incorrect: {sig}")
            return False
        
        # Test delete_user signature
        sig = inspect.signature(delete_user)
        if 'user_id' in sig.parameters:
            print("✅ delete_user signature correct")
        else:
            print(f"❌ delete_user signature incorrect: {sig}")
            return False
        
        # Test list_users signature
        sig = inspect.signature(list_users)
        if 'startIndex' in sig.parameters and 'count' in sig.parameters:
            print("✅ list_users signature correct")
        else:
            print(f"❌ list_users signature incorrect: {sig}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Endpoint signatures error: {e}")
        return False

def run_all_tests():
    """Run all test functions."""
    print("SCIM Bridge Main Application Test Suite")
    print("=" * 50)
    
    tests = [
        test_imports,
        test_app_initialization,
        test_scim_models,
        test_yaml_generator,
        test_user_store,
        test_endpoint_signatures
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ Test {test.__name__} failed with exception: {e}")
            results.append(False)
    
    print("\n" + "=" * 50)
    print(f"Test Results: {sum(results)}/{len(results)} passed")
    
    if all(results):
        print("🎉 All tests passed!")
        return True
    else:
        print("⚠️  Some tests failed")
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)