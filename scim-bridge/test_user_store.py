#!/usr/bin/env python3
"""
Test script for UserStore service

Tests all CRUD operations, thread safety, and edge cases.
"""

import os
import sys
import tempfile
import threading
from pathlib import Path

# Add app to path so we can import modules
sys.path.insert(0, str(Path(__file__).parent))

from app.services.user_store import UserStore


def test_basic_operations():
    """Test basic add, get, list, delete operations"""
    print("Test 1: Basic CRUD operations")

    # Use temporary file for testing
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        temp_file = f.name

    try:
        store = UserStore(temp_file)

        # Test add_user
        store.add_user(
            scim_id="12345678-1234-1234-1234-123456789abc",
            name="Jane Example",
            filename="entraid_human_jane_example.yaml",
            email="jane.example@contoso.com",
            role="senior_engineer",
            team="platform_engineering",
        )

        # Test get_user
        user = store.get_user("12345678-1234-1234-1234-123456789abc")
        assert user is not None, "User should exist"
        assert user["name"] == "Jane Example", "Name should match"
        assert user["filename"] == "entraid_human_jane_example.yaml", "Filename should match"
        assert user["email"] == "jane.example@contoso.com", "Email should match"
        assert user["role"] == "senior_engineer", "Role should match"
        assert user["team"] == "platform_engineering", "Team should match"

        # Test user_exists
        assert store.user_exists("12345678-1234-1234-1234-123456789abc"), "User should exist"
        assert not store.user_exists("nonexistent-id"), "Non-existent user should not exist"

        # Test list_all_users
        all_users = store.list_all_users()
        assert len(all_users) == 1, "Should have 1 user"
        assert all_users[0]["name"] == "Jane Example", "User name should match"

        # Test delete_user
        deleted = store.delete_user("12345678-1234-1234-1234-123456789abc")
        assert deleted, "Delete should return True"
        assert store.get_user("12345678-1234-1234-1234-123456789abc") is None, "User should be deleted"
        assert len(store.list_all_users()) == 0, "Store should be empty"

        # Test delete non-existent user
        deleted = store.delete_user("nonexistent-id")
        assert not deleted, "Delete should return False for non-existent user"

        print("✅ Test 1 passed: Basic CRUD operations work correctly\n")

    finally:
        # Clean up temp file
        os.unlink(temp_file)


def test_multiple_users():
    """Test managing multiple users"""
    print("Test 2: Multiple users")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        temp_file = f.name

    try:
        store = UserStore(temp_file)

        # Add multiple users
        users_to_add = [
            {
                "scim_id": "11111111-1111-1111-1111-111111111111",
                "name": "Alice Admin",
                "filename": "entraid_human_alice_admin.yaml",
            },
            {
                "scim_id": "22222222-2222-2222-2222-222222222222",
                "name": "Bob Builder",
                "filename": "entraid_human_bob_builder.yaml",
            },
            {
                "scim_id": "33333333-3333-3333-3333-333333333333",
                "name": "Charlie Chaplin",
                "filename": "entraid_human_charlie_chaplin.yaml",
            },
        ]

        for user in users_to_add:
            store.add_user(**user)

        # Verify all users exist
        all_users = store.list_all_users()
        assert len(all_users) == 3, "Should have 3 users"

        # Verify each user can be retrieved
        for user_data in users_to_add:
            retrieved = store.get_user(user_data["scim_id"])
            assert retrieved is not None, f"User {user_data['name']} should exist"
            assert retrieved["name"] == user_data["name"], "Name should match"

        # Update existing user
        store.add_user(
            scim_id="11111111-1111-1111-1111-111111111111",
            name="Alice Administrator",  # Changed name
            filename="entraid_human_alice_admin.yaml",
            updated=True,  # Extra field
        )

        updated_user = store.get_user("11111111-1111-1111-1111-111111111111")
        assert updated_user["name"] == "Alice Administrator", "Name should be updated"
        assert updated_user.get("updated") is True, "Extra field should be added"
        assert len(store.list_all_users()) == 3, "Should still have 3 users"

        print("✅ Test 2 passed: Multiple users managed correctly\n")

    finally:
        os.unlink(temp_file)


def test_search_methods():
    """Test get_user_by_name and get_user_by_filename methods"""
    print("Test 3: Search methods")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        temp_file = f.name

    try:
        store = UserStore(temp_file)

        # Add test users
        store.add_user(
            scim_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            name="David Developer",
            filename="entraid_human_david_developer.yaml",
        )
        store.add_user(
            scim_id="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            name="Eve Engineer",
            filename="entraid_human_eve_engineer.yaml",
        )

        # Test get_user_by_name (case-insensitive)
        user = store.get_user_by_name("David Developer")
        assert user is not None, "Should find user by exact name"
        assert user["scim_id"] == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

        user = store.get_user_by_name("david developer")
        assert user is not None, "Should find user by lowercase name"
        assert user["name"] == "David Developer"

        user = store.get_user_by_name("DAVID DEVELOPER")
        assert user is not None, "Should find user by uppercase name"

        user = store.get_user_by_name("Nonexistent User")
        assert user is None, "Should return None for non-existent name"

        # Test get_user_by_filename
        user = store.get_user_by_filename("entraid_human_eve_engineer.yaml")
        assert user is not None, "Should find user by filename"
        assert user["name"] == "Eve Engineer"
        assert user["scim_id"] == "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"

        user = store.get_user_by_filename("nonexistent_file.yaml")
        assert user is None, "Should return None for non-existent filename"

        print("✅ Test 3 passed: Search methods work correctly\n")

    finally:
        os.unlink(temp_file)


def test_persistence():
    """Test that data persists across UserStore instances"""
    print("Test 4: Data persistence")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        temp_file = f.name

    try:
        # Create store and add user
        store1 = UserStore(temp_file)
        store1.add_user(
            scim_id="persist-test-1234",
            name="Persistent User",
            filename="entraid_human_persistent_user.yaml",
        )

        # Create new store instance with same file
        store2 = UserStore(temp_file)
        user = store2.get_user("persist-test-1234")
        assert user is not None, "User should persist across instances"
        assert user["name"] == "Persistent User"

        # Modify in second instance
        store2.add_user(
            scim_id="persist-test-1234",
            name="Updated Persistent User",
            filename="entraid_human_persistent_user.yaml",
        )

        # Verify in new third instance
        store3 = UserStore(temp_file)
        user = store3.get_user("persist-test-1234")
        assert user["name"] == "Updated Persistent User", "Update should persist"

        print("✅ Test 4 passed: Data persists correctly across instances\n")

    finally:
        os.unlink(temp_file)


def test_concurrent_access():
    """Test thread-safe concurrent access"""
    print("Test 5: Thread-safe concurrent access")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        temp_file = f.name

    try:
        store = UserStore(temp_file)
        num_threads = 10
        users_per_thread = 5

        def add_users(thread_id):
            """Add multiple users from a thread"""
            for i in range(users_per_thread):
                scim_id = f"thread-{thread_id:02d}-user-{i:02d}"
                store.add_user(
                    scim_id=scim_id,
                    name=f"User {thread_id}-{i}",
                    filename=f"entraid_human_user_{thread_id}_{i}.yaml",
                )

        # Create and start threads
        threads = []
        for i in range(num_threads):
            thread = threading.Thread(target=add_users, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Verify all users were added
        all_users = store.list_all_users()
        expected_count = num_threads * users_per_thread
        assert len(all_users) == expected_count, f"Should have {expected_count} users, got {len(all_users)}"

        # Verify each user can be retrieved
        for thread_id in range(num_threads):
            for i in range(users_per_thread):
                scim_id = f"thread-{thread_id:02d}-user-{i:02d}"
                user = store.get_user(scim_id)
                assert user is not None, f"User {scim_id} should exist"

        print(f"✅ Test 5 passed: {expected_count} users added concurrently with thread safety\n")

    finally:
        os.unlink(temp_file)


def test_edge_cases():
    """Test edge cases and error handling"""
    print("Test 6: Edge cases")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        temp_file = f.name

    try:
        store = UserStore(temp_file)

        # Test empty store
        assert len(store.list_all_users()) == 0, "New store should be empty"
        assert store.get_user("nonexistent") is None, "Should return None for non-existent user"

        # Test with special characters in fields
        store.add_user(
            scim_id="special-chars-test",
            name="O'Brien-Smith, Jr.",
            filename="entraid_human_obriensmith_jr.yaml",
            special_field="Unicode: 你好 🎉",
        )

        user = store.get_user("special-chars-test")
        assert user["name"] == "O'Brien-Smith, Jr.", "Special characters in name should be preserved"
        assert user["special_field"] == "Unicode: 你好 🎉", "Unicode should be preserved"

        # Test updating with different extra fields
        store.add_user(
            scim_id="special-chars-test",
            name="O'Brien-Smith, Jr.",
            filename="entraid_human_obriensmith_jr.yaml",
            new_field="new value",
        )

        user = store.get_user("special-chars-test")
        assert user.get("new_field") == "new value", "New field should be added"

        print("✅ Test 6 passed: Edge cases handled correctly\n")

    finally:
        os.unlink(temp_file)


def main():
    """Run all tests"""
    print("=" * 70)
    print("UserStore Service Test Suite")
    print("=" * 70)
    print()

    try:
        test_basic_operations()
        test_multiple_users()
        test_search_methods()
        test_persistence()
        test_concurrent_access()
        test_edge_cases()

        print("=" * 70)
        print("✅ ALL TESTS PASSED!")
        print("=" * 70)
        return 0

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
