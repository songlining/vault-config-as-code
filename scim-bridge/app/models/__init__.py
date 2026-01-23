"""
SCIM Bridge Models Package

Pydantic models for SCIM 2.0 resources and operations.
"""

from .scim_user import (
    SCIMUser,
    SCIMUserPatch,
    SCIMGroup,
    SCIMEmail,
    SCIMGroupMembership,
    SCIMPatchOperation,
    SCIMListResponse,
    SCIMError,
    SCIM_USER_SCHEMA,
    SCIM_PATCH_SCHEMA,
)

__all__ = [
    "SCIMUser",
    "SCIMUserPatch",
    "SCIMGroup",
    "SCIMEmail",
    "SCIMGroupMembership",
    "SCIMPatchOperation",
    "SCIMListResponse",
    "SCIMError",
    "SCIM_USER_SCHEMA",
    "SCIM_PATCH_SCHEMA",
]
