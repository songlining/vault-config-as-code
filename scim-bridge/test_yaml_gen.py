#!/usr/bin/env python3
"""
Test script for YAML Generator Service

Tests the YAMLGenerator with example SCIM data to verify proper conversion.
"""

import sys
sys.path.insert(0, '/workspaces/vault-config-as-code/scim-bridge')

from app.services.yaml_generator import YAMLGenerator

# Create generator instance
generator = YAMLGenerator(schema_path="../identities/schema_entraid_human.yaml")

# Test case 1: Full SCIM user with all fields
print("=" * 80)
print("Test Case 1: Full SCIM user with all fields")
print("=" * 80)

scim_user_full = {
    "id": "12345678-1234-1234-1234-123456789abc",
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
    "title": "Senior Engineer",
    "department": "Platform Engineering"
}

filename1, yaml_content1 = generator.scim_to_yaml(scim_user_full)
print(f"Generated filename: {filename1}")
print(f"\nGenerated YAML:\n{yaml_content1}")

# Test case 2: Deactivated user
print("=" * 80)
print("Test Case 2: Deactivated user (active=false)")
print("=" * 80)

scim_user_deactivated = {
    "id": "87654321-4321-4321-4321-cba987654321",
    "userName": "john.doe@contoso.onmicrosoft.com",
    "displayName": "John Doe",
    "emails": [
        {
            "value": "john.doe@contoso.com",
            "type": "work",
            "primary": True
        }
    ],
    "active": False,  # Deactivated
    "title": "Software Developer",
    "department": "Engineering"
}

filename2, yaml_content2 = generator.scim_to_yaml(scim_user_deactivated)
print(f"Generated filename: {filename2}")
print(f"\nGenerated YAML:\n{yaml_content2}")

# Test case 3: User with special characters in name/title/department
print("=" * 80)
print("Test Case 3: User with special characters")
print("=" * 80)

scim_user_special = {
    "id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    "userName": "mary.o'brien-smith@contoso.onmicrosoft.com",
    "displayName": "Mary O'Brien-Smith",
    "emails": [
        {
            "value": "mary.obrien@contoso.com",
            "type": "work",
            "primary": True
        }
    ],
    "active": True,
    "title": "VP of Product & Engineering",
    "department": "Product/Engineering Division"
}

filename3, yaml_content3 = generator.scim_to_yaml(scim_user_special)
print(f"Generated filename: {filename3}")
print(f"\nGenerated YAML:\n{yaml_content3}")

# Test case 4: Minimal user (missing optional fields)
print("=" * 80)
print("Test Case 4: Minimal user (missing optional fields)")
print("=" * 80)

scim_user_minimal = {
    "id": "11111111-2222-3333-4444-555555555555",
    "userName": "bob.smith@contoso.onmicrosoft.com",
    "displayName": "Bob Smith",
    "active": True
}

filename4, yaml_content4 = generator.scim_to_yaml(scim_user_minimal)
print(f"Generated filename: {filename4}")
print(f"\nGenerated YAML:\n{yaml_content4}")

print("=" * 80)
print("All tests completed successfully!")
print("=" * 80)
