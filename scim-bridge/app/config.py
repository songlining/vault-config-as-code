"""
Configuration module for SCIM Bridge.

This module provides environment variable configuration and settings management
using Pydantic Settings for type-safe configuration.
"""
import os
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, validator
from pydantic_settings import BaseSettings


class SCIMBridgeSettings(BaseSettings):
    """
    Configuration settings for SCIM Bridge application.
    
    All settings are loaded from environment variables with validation.
    """
    
    # Required environment variables
    scim_bearer_token: str = Field(
        ...,
        env="SCIM_BEARER_TOKEN",
        description="Bearer token for SCIM API authentication from EntraID"
    )
    
    github_token: str = Field(
        ...,
        env="GITHUB_TOKEN",
        description="GitHub personal access token for PR creation"
    )
    
    # Environment variables with defaults
    git_repo_url: str = Field(
        "https://github.com/your-org/vault-config-as-code.git",
        env="GIT_REPO_URL",
        description="Git repository URL for configuration files"
    )
    
    log_level: str = Field(
        "INFO",
        env="LOG_LEVEL",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    )
    
    repo_clone_dir: Path = Field(
        Path("/data/repo"),
        env="REPO_CLONE_DIR",
        description="Local directory path for cloning Git repository"
    )
    
    user_mapping_file: Path = Field(
        Path("/data/user_mapping.json"),
        env="USER_MAPPING_FILE",
        description="JSON file path for persistent user ID mapping"
    )
    
    # Additional configuration
    schema_file_path: Path = Field(
        Path("identities/schema_entraid_human.yaml"),
        env="SCHEMA_FILE_PATH",
        description="Path to EntraID human identity YAML schema file (relative to repo root)"
    )
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
    
    @validator("log_level")
    def validate_log_level(cls, v):
        """Validate log level is one of the standard Python logging levels."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"LOG_LEVEL must be one of: {', '.join(valid_levels)}")
        return v.upper()
    
    @validator("git_repo_url")
    def validate_git_repo_url(cls, v):
        """Validate Git repository URL format."""
        if not v.startswith(("https://", "git@")):
            raise ValueError("GIT_REPO_URL must be HTTPS or SSH format")
        if "github.com" not in v:
            raise ValueError("GIT_REPO_URL must be a GitHub repository")
        return v
    
    @validator("repo_clone_dir", "user_mapping_file")
    def validate_paths(cls, v):
        """Ensure paths are Path objects."""
        if isinstance(v, str):
            return Path(v)
        return v
    
    @validator("scim_bearer_token", "github_token")
    def validate_tokens(cls, v, field):
        """Validate required tokens are not empty."""
        if not v or not v.strip():
            raise ValueError(f"{field.name} cannot be empty")
        return v.strip()
    
    def ensure_data_directories(self) -> None:
        """
        Create necessary data directories if they don't exist.
        
        This method creates:
        - Parent directory for user mapping file
        - Parent directory for repository clone
        """
        # Create user mapping file directory
        self.user_mapping_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Create repository clone directory
        self.repo_clone_dir.mkdir(parents=True, exist_ok=True)
    
    def get_schema_path(self) -> Path:
        """
        Get the full path to the schema file within the cloned repository.
        
        Returns:
            Path: Full path to schema_entraid_human.yaml file
        """
        return self.repo_clone_dir / self.schema_file_path


# Global settings instance
settings: Optional[SCIMBridgeSettings] = None


def get_settings() -> SCIMBridgeSettings:
    """
    Get the global settings instance, creating it if necessary.
    
    This function implements a singleton pattern for settings to avoid
    re-reading environment variables on every request.
    
    Returns:
        SCIMBridgeSettings: The global settings instance
    
    Raises:
        ValueError: If required environment variables are missing or invalid
    """
    global settings
    if settings is None:
        settings = SCIMBridgeSettings()
        # Ensure data directories exist
        settings.ensure_data_directories()
    return settings


def reload_settings() -> SCIMBridgeSettings:
    """
    Force reload settings from environment variables.
    
    This is useful for testing or when environment variables change.
    
    Returns:
        SCIMBridgeSettings: New settings instance
    """
    global settings
    settings = SCIMBridgeSettings()
    settings.ensure_data_directories()
    return settings