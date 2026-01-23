"""
YAML Generator Service

Transforms SCIM 2.0 User payloads into Vault identity YAML files that conform
to the schema_entraid_human.yaml schema.
"""

import re
from datetime import datetime
from typing import Dict, Tuple
import yaml


class YAMLGenerator:
    """
    Generates Vault identity YAML files from SCIM user payloads.

    Transforms SCIM 2.0 User resources from EntraID into properly formatted
    YAML identity files that can be committed to the repository and applied
    via Terraform to create Vault identity entities.

    Args:
        schema_path: Path to the schema_entraid_human.yaml file (relative or absolute)

    Example:
        >>> generator = YAMLGenerator(schema_path="../identities/schema_entraid_human.yaml")
        >>> scim_user = {
        ...     "id": "12345678-1234-1234-1234-123456789abc",
        ...     "userName": "jane.example@contoso.onmicrosoft.com",
        ...     "displayName": "Jane Example",
        ...     "emails": [{"value": "jane.example@contoso.com", "primary": True}],
        ...     "active": True,
        ...     "title": "Senior Engineer",
        ...     "department": "Platform Engineering"
        ... }
        >>> filename, yaml_content = generator.scim_to_yaml(scim_user)
        >>> print(filename)
        entraid_human_jane_example.yaml
    """

    def __init__(self, schema_path: str):
        """
        Initialize the YAML generator.

        Args:
            schema_path: Path to the schema_entraid_human.yaml file
        """
        self.schema_path = schema_path

    def scim_to_yaml(self, scim_user: Dict) -> Tuple[str, str]:
        """
        Convert SCIM user payload to Vault identity YAML.

        Transforms a SCIM 2.0 User resource into a YAML identity file with
        proper field mapping, sanitization, and schema compliance.

        SCIM to YAML Field Mapping:
        - userName → authentication.oidc
        - displayName → identity.name
        - emails[0].value → identity.email
        - title → identity.role (sanitized)
        - department → identity.team (sanitized)
        - id → metadata.entraid_object_id
        - userName → metadata.entraid_upn
        - active → identity.status (true→active, false→deactivated)

        Args:
            scim_user: Dictionary containing SCIM user data with fields:
                - id: EntraID object ID (UUID)
                - userName: User Principal Name (UPN)
                - displayName: Full name
                - emails: List of email objects with 'value' field
                - active: Boolean user status
                - title: Job title (optional)
                - department: Department name (optional)

        Returns:
            Tuple of (filename, yaml_content):
                - filename: Generated filename (e.g., "entraid_human_jane_example.yaml")
                - yaml_content: Complete YAML content as string

        Example:
            >>> scim_user = {"userName": "jane@example.com", "displayName": "Jane Doe", ...}
            >>> filename, content = generator.scim_to_yaml(scim_user)
        """
        # Extract primary email (first email in list or fallback to userName)
        email = scim_user.get("userName", "")
        if scim_user.get("emails") and len(scim_user["emails"]) > 0:
            email = scim_user["emails"][0].get("value", email)

        # Extract and sanitize role and team
        role = self._sanitize_field(scim_user.get("title", "user"))
        team = self._sanitize_field(scim_user.get("department", "general"))

        # Map active boolean to status string
        status = "active" if scim_user.get("active", True) else "deactivated"

        # Generate filename from displayName
        filename = self._generate_filename(scim_user.get("displayName", email))

        # Build YAML structure
        yaml_data = {
            "$schema": self.schema_path,
            "metadata": {
                "version": "1.0.0",
                "created_date": datetime.utcnow().strftime("%Y-%m-%d"),
                "description": f"EntraID user {scim_user.get('displayName', email)} provisioned via SCIM",
                "entraid_object_id": scim_user.get("id", ""),
                "entraid_upn": scim_user.get("userName", ""),
                "provisioned_via_scim": True
            },
            "identity": {
                "name": scim_user.get("displayName", email),
                "email": email,
                "role": role,
                "team": team,
                "status": status
            },
            "authentication": {
                "oidc": email,
                "disabled": not scim_user.get("active", True)
            },
            "policies": {
                "identity_policies": [
                    f"{role}-policy"
                ]
            }
        }

        # Convert to YAML string with proper formatting
        yaml_content = yaml.dump(
            yaml_data,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True
        )

        return filename, yaml_content

    def _sanitize_field(self, value: str) -> str:
        """
        Sanitize role and team fields for YAML.

        Converts to lowercase, replaces spaces with underscores, removes
        special characters, and ensures valid field values.

        Args:
            value: Raw field value (e.g., "Senior Engineer", "Platform Engineering")

        Returns:
            Sanitized value (e.g., "senior_engineer", "platform_engineering")

        Example:
            >>> generator._sanitize_field("Senior Engineer")
            'senior_engineer'
            >>> generator._sanitize_field("Platform Engineering")
            'platform_engineering'
        """
        # Convert to lowercase
        sanitized = value.lower()
        # Replace spaces with underscores
        sanitized = sanitized.replace(" ", "_")
        # Remove special characters (keep only alphanumeric and underscores)
        sanitized = re.sub(r'[^a-z0-9_]', '', sanitized)
        # Remove leading/trailing underscores
        sanitized = sanitized.strip("_")
        # Replace multiple consecutive underscores with single underscore
        sanitized = re.sub(r'_+', '_', sanitized)

        return sanitized if sanitized else "user"

    def _generate_filename(self, display_name: str) -> str:
        """
        Generate filename from display name.

        Converts display name to filename format: entraid_human_firstname_lastname.yaml
        Handles sanitization of special characters and spaces.

        Args:
            display_name: User's display name (e.g., "Jane Example")

        Returns:
            Filename (e.g., "entraid_human_jane_example.yaml")

        Example:
            >>> generator._generate_filename("Jane Example")
            'entraid_human_jane_example.yaml'
            >>> generator._generate_filename("John O'Brien-Smith")
            'entraid_human_john_obriensmith.yaml'
        """
        # Convert to lowercase
        name = display_name.lower()
        # Replace spaces with underscores
        name = name.replace(" ", "_")
        # Remove special characters (keep only alphanumeric and underscores)
        name = re.sub(r'[^a-z0-9_]', '', name)
        # Remove leading/trailing underscores
        name = name.strip("_")
        # Replace multiple consecutive underscores with single underscore
        name = re.sub(r'_+', '_', name)

        # Use sanitized name or fallback to 'user'
        if not name:
            name = "user"

        return f"entraid_human_{name}.yaml"
