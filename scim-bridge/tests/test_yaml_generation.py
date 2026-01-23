"""
Test file for YAML Generator Service

Tests the YAMLGenerator class functionality including:
- SCIM to YAML conversion with valid user data
- Filename generation and sanitization
- Role and team sanitization
- Active/deactivated status mapping
"""

import pytest
import yaml
from unittest.mock import Mock, patch
import tempfile
from pathlib import Path
import sys
import os

# Add the scim-bridge directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.yaml_generator import YAMLGenerator


class TestYAMLGenerator:
    """Test cases for YAMLGenerator service"""

    @pytest.fixture
    def yaml_generator(self):
        """Create a YAMLGenerator instance for testing"""
        return YAMLGenerator(schema_path="mock_schema_path.yaml")

    @pytest.fixture
    def sample_scim_user_full(self):
        """Sample SCIM user with all fields populated"""
        return {
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
            "title": "Senior Software Engineer",
            "department": "Platform Engineering Team"
        }

    @pytest.fixture
    def sample_scim_user_minimal(self):
        """Sample SCIM user with minimal required fields"""
        return {
            "userName": "john.doe@contoso.onmicrosoft.com",
            "active": True
        }

    @pytest.fixture
    def sample_scim_user_deactivated(self):
        """Sample SCIM user that is deactivated"""
        return {
            "id": "87654321-4321-4321-4321-210987654321",
            "userName": "former.employee@contoso.onmicrosoft.com",
            "displayName": "Former Employee",
            "emails": [
                {
                    "value": "former.employee@contoso.com",
                    "type": "work",
                    "primary": True
                }
            ],
            "active": False,  # Deactivated user
            "title": "Former Role",
            "department": "Former Team"
        }

    def test_scim_to_yaml_full_user(self, yaml_generator, sample_scim_user_full):
        """Test SCIM to YAML conversion with a full user profile"""
        filename, yaml_content = yaml_generator.scim_to_yaml(sample_scim_user_full)

        # Verify filename generation
        assert filename == "entraid_human_jane_example.yaml"

        # Parse YAML content to verify structure
        parsed_yaml = yaml.safe_load(yaml_content)

        # Verify schema reference
        assert parsed_yaml["$schema"] == "mock_schema_path.yaml"

        # Verify metadata section
        assert parsed_yaml["metadata"]["version"] == "1.0.0"
        assert "created_date" in parsed_yaml["metadata"]
        assert parsed_yaml["metadata"]["entraid_object_id"] == "12345678-1234-1234-1234-123456789abc"
        assert parsed_yaml["metadata"]["entraid_upn"] == "jane.example@contoso.onmicrosoft.com"
        assert parsed_yaml["metadata"]["provisioned_via_scim"] is True

        # Verify identity section
        assert parsed_yaml["identity"]["name"] == "Jane Example"
        assert parsed_yaml["identity"]["email"] == "jane.example@contoso.com"
        assert parsed_yaml["identity"]["role"] == "senior_software_engineer"
        assert parsed_yaml["identity"]["team"] == "platform_engineering_team"
        assert parsed_yaml["identity"]["status"] == "active"

        # Verify authentication section
        assert parsed_yaml["authentication"]["oidc"] == "jane.example@contoso.com"
        assert parsed_yaml["authentication"]["disabled"] is False

        # Verify policies section
        assert parsed_yaml["policies"]["identity_policies"] == ["senior_software_engineer-policy"]

    def test_scim_to_yaml_minimal_user(self, yaml_generator, sample_scim_user_minimal):
        """Test SCIM to YAML conversion with minimal user data"""
        filename, yaml_content = yaml_generator.scim_to_yaml(sample_scim_user_minimal)

        # Parse YAML content
        parsed_yaml = yaml.safe_load(yaml_content)

        # Verify defaults are applied for missing fields
        assert "johndoecontoso" in filename  # Extracted from userName (sanitized)
        assert parsed_yaml["identity"]["role"] == "user"  # Default role
        assert parsed_yaml["identity"]["team"] == "general"  # Default team
        assert parsed_yaml["identity"]["email"] == "john.doe@contoso.onmicrosoft.com"  # Fallback to userName
        assert parsed_yaml["metadata"]["entraid_object_id"] == ""  # Missing ID
        assert parsed_yaml["policies"]["identity_policies"] == ["user-policy"]

    def test_scim_to_yaml_deactivated_user(self, yaml_generator, sample_scim_user_deactivated):
        """Test SCIM to YAML conversion with deactivated user"""
        filename, yaml_content = yaml_generator.scim_to_yaml(sample_scim_user_deactivated)

        # Parse YAML content
        parsed_yaml = yaml.safe_load(yaml_content)

        # Verify deactivated status mapping
        assert parsed_yaml["identity"]["status"] == "deactivated"
        assert parsed_yaml["authentication"]["disabled"] is True
        assert filename == "entraid_human_former_employee.yaml"

    def test_filename_generation_and_sanitization(self, yaml_generator):
        """Test filename generation with various name formats requiring sanitization"""
        test_cases = [
            # (displayName, expected_filename)
            ("Jane Example", "entraid_human_jane_example.yaml"),
            ("John O'Brien-Smith", "entraid_human_john_obriensmith.yaml"),
            ("María José García", "entraid_human_mara_jos_garca.yaml"),
            ("Jean-Paul de la Montagne", "entraid_human_jeanpaul_de_la_montagne.yaml"),
            ("   Extra  Spaces   ", "entraid_human_extra_spaces.yaml"),
            ("Special@#$%Characters!", "entraid_human_specialcharacters.yaml"),
            ("", "entraid_human_user.yaml"),  # Empty name fallback
            ("123 Numeric Name", "entraid_human_123_numeric_name.yaml"),
        ]

        for display_name, expected_filename in test_cases:
            scim_user = {
                "userName": "test@contoso.com",
                "displayName": display_name,
                "active": True
            }
            filename, _ = yaml_generator.scim_to_yaml(scim_user)
            assert filename == expected_filename, f"Failed for displayName: '{display_name}'"

    def test_role_and_team_sanitization(self, yaml_generator):
        """Test role and team field sanitization"""
        test_cases = [
            # (title, department, expected_role, expected_team)
            ("Senior Software Engineer", "Platform Engineering", "senior_software_engineer", "platform_engineering"),
            ("Lead Developer", "Mobile App Team", "lead_developer", "mobile_app_team"),
            ("Product Manager", "AI/ML Division", "product_manager", "aiml_division"),
            ("VP of Engineering", "C-Suite", "vp_of_engineering", "csuite"),
            ("", "", "user", "user"),  # Empty fallback
            ("Software Engineer III", "R&D Department", "software_engineer_iii", "rd_department"),
            ("DevOps Engineer (AWS)", "Cloud Infrastructure", "devops_engineer_aws", "cloud_infrastructure"),
            ("UI/UX Designer", "Design @ Product", "uiux_designer", "design_product"),
        ]

        for title, department, expected_role, expected_team in test_cases:
            scim_user = {
                "userName": "test@contoso.com",
                "displayName": "Test User",
                "title": title,
                "department": department,
                "active": True
            }
            _, yaml_content = yaml_generator.scim_to_yaml(scim_user)
            parsed_yaml = yaml.safe_load(yaml_content)
            
            assert parsed_yaml["identity"]["role"] == expected_role, f"Failed role for title: '{title}'"
            assert parsed_yaml["identity"]["team"] == expected_team, f"Failed team for department: '{department}'"

    def test_active_deactivated_status_mapping(self, yaml_generator):
        """Test mapping of SCIM active field to YAML status and disabled fields"""
        # Test active user
        active_scim_user = {
            "userName": "active@contoso.com",
            "displayName": "Active User",
            "active": True
        }
        _, yaml_content = yaml_generator.scim_to_yaml(active_scim_user)
        parsed_yaml = yaml.safe_load(yaml_content)
        
        assert parsed_yaml["identity"]["status"] == "active"
        assert parsed_yaml["authentication"]["disabled"] is False

        # Test deactivated user
        deactivated_scim_user = {
            "userName": "deactivated@contoso.com",
            "displayName": "Deactivated User",
            "active": False
        }
        _, yaml_content = yaml_generator.scim_to_yaml(deactivated_scim_user)
        parsed_yaml = yaml.safe_load(yaml_content)
        
        assert parsed_yaml["identity"]["status"] == "deactivated"
        assert parsed_yaml["authentication"]["disabled"] is True

    def test_email_handling(self, yaml_generator):
        """Test email field extraction from SCIM emails array"""
        # Test with emails array
        scim_user_with_emails = {
            "userName": "user@contoso.onmicrosoft.com",
            "displayName": "Test User",
            "emails": [
                {"value": "primary@contoso.com", "primary": True},
                {"value": "secondary@contoso.com", "primary": False}
            ],
            "active": True
        }
        _, yaml_content = yaml_generator.scim_to_yaml(scim_user_with_emails)
        parsed_yaml = yaml.safe_load(yaml_content)
        assert parsed_yaml["identity"]["email"] == "primary@contoso.com"
        assert parsed_yaml["authentication"]["oidc"] == "primary@contoso.com"

        # Test without emails array (fallback to userName)
        scim_user_no_emails = {
            "userName": "fallback@contoso.onmicrosoft.com",
            "displayName": "Test User",
            "active": True
        }
        _, yaml_content = yaml_generator.scim_to_yaml(scim_user_no_emails)
        parsed_yaml = yaml.safe_load(yaml_content)
        assert parsed_yaml["identity"]["email"] == "fallback@contoso.onmicrosoft.com"
        assert parsed_yaml["authentication"]["oidc"] == "fallback@contoso.onmicrosoft.com"

    def test_yaml_structure_and_schema_compliance(self, yaml_generator, sample_scim_user_full):
        """Test that generated YAML has correct structure and includes all required fields"""
        _, yaml_content = yaml_generator.scim_to_yaml(sample_scim_user_full)
        parsed_yaml = yaml.safe_load(yaml_content)

        # Verify top-level sections
        required_sections = ["metadata", "identity", "authentication", "policies"]
        for section in required_sections:
            assert section in parsed_yaml, f"Missing required section: {section}"

        # Verify metadata fields
        metadata_fields = ["version", "created_date", "entraid_object_id", "entraid_upn", "provisioned_via_scim"]
        for field in metadata_fields:
            assert field in parsed_yaml["metadata"], f"Missing metadata field: {field}"

        # Verify identity fields
        identity_fields = ["name", "email", "role", "team", "status"]
        for field in identity_fields:
            assert field in parsed_yaml["identity"], f"Missing identity field: {field}"

        # Verify authentication fields
        auth_fields = ["oidc", "disabled"]
        for field in auth_fields:
            assert field in parsed_yaml["authentication"], f"Missing authentication field: {field}"

        # Verify policies fields
        assert "identity_policies" in parsed_yaml["policies"]
        assert isinstance(parsed_yaml["policies"]["identity_policies"], list)

    @patch('app.services.yaml_generator.datetime')
    def test_created_date_format(self, mock_datetime, yaml_generator, sample_scim_user_full):
        """Test that created_date is properly formatted"""
        # Mock datetime to return a fixed date
        mock_datetime.utcnow.return_value.strftime.return_value = "2026-01-23"
        
        _, yaml_content = yaml_generator.scim_to_yaml(sample_scim_user_full)
        parsed_yaml = yaml.safe_load(yaml_content)
        
        assert parsed_yaml["metadata"]["created_date"] == "2026-01-23"
        mock_datetime.utcnow.assert_called_once()