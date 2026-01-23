"""
SCIM Bridge Services

Business logic services for SCIM user provisioning to Vault identity YAML files.
"""

from .yaml_generator import YAMLGenerator

__all__ = ["YAMLGenerator"]
