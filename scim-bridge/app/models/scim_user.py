"""
SCIM 2.0 User Resource Models

Pydantic models for SCIM 2.0 User resources compliant with RFC 7643.
Supports user provisioning from Microsoft EntraID to Vault identity YAML files.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


# SCIM 2.0 Schema URNs
SCIM_USER_SCHEMA = "urn:ietf:params:scim:schemas:core:2.0:User"
SCIM_PATCH_SCHEMA = "urn:ietf:params:scim:api:messages:2.0:PatchOp"


class SCIMEmail(BaseModel):
    """SCIM email object"""
    value: str
    type: Optional[str] = "work"
    primary: Optional[bool] = True


class SCIMGroupMembership(BaseModel):
    """SCIM group membership object"""
    value: str  # Group ID
    ref: Optional[str] = Field(None, alias="$ref")  # Group resource URL
    display: Optional[str] = None  # Group display name
    type: Optional[str] = "direct"

    class Config:
        populate_by_name = True


class SCIMUser(BaseModel):
    """
    SCIM 2.0 User Resource

    Represents a user provisioned from EntraID with all required fields
    for generating Vault identity YAML files.
    """
    schemas: List[str] = Field(default=[SCIM_USER_SCHEMA])
    id: Optional[str] = None  # SCIM user ID (EntraID object ID)
    externalId: Optional[str] = None  # External identifier
    userName: str  # User Principal Name (UPN) from EntraID
    displayName: Optional[str] = None  # Full name
    emails: Optional[List[SCIMEmail]] = None  # Email addresses
    active: bool = True  # User active status
    title: Optional[str] = None  # Job title / role
    department: Optional[str] = None  # Department / team
    groups: Optional[List[SCIMGroupMembership]] = None  # Group memberships

    class Config:
        json_schema_extra = {
            "example": {
                "schemas": [SCIM_USER_SCHEMA],
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
                "department": "Platform Engineering",
                "groups": [
                    {
                        "value": "group-id-123",
                        "display": "Engineering Team"
                    }
                ]
            }
        }


class SCIMPatchOperation(BaseModel):
    """
    SCIM PATCH operation

    Represents a single operation in a PATCH request (add, remove, replace).
    """
    op: str  # Operation: "add", "remove", "replace"
    path: Optional[str] = None  # Attribute path (e.g., "groups", "active")
    value: Optional[dict | list | str | bool] = None  # Operation value

    class Config:
        json_schema_extra = {
            "example": {
                "op": "add",
                "path": "groups",
                "value": [
                    {
                        "value": "group-id-123",
                        "display": "Engineering Team"
                    }
                ]
            }
        }


class SCIMUserPatch(BaseModel):
    """
    SCIM 2.0 PATCH Request

    Used for partial updates to user resources including group membership changes.
    """
    schemas: List[str] = Field(default=[SCIM_PATCH_SCHEMA])
    Operations: List[SCIMPatchOperation]  # List of operations to apply

    class Config:
        json_schema_extra = {
            "example": {
                "schemas": [SCIM_PATCH_SCHEMA],
                "Operations": [
                    {
                        "op": "add",
                        "path": "groups",
                        "value": [
                            {
                                "value": "group-id-123",
                                "display": "Engineering Team"
                            }
                        ]
                    }
                ]
            }
        }


class SCIMGroup(BaseModel):
    """
    SCIM 2.0 Group Resource (simplified)

    Represents a group for membership operations. Used in group synchronization
    to track which groups a user belongs to.
    """
    id: str  # Group ID
    displayName: str  # Group display name
    members: Optional[List[dict]] = None  # Group members

    class Config:
        json_schema_extra = {
            "example": {
                "id": "group-id-123",
                "displayName": "Engineering Team",
                "members": [
                    {
                        "value": "user-id-456",
                        "display": "Jane Example"
                    }
                ]
            }
        }


class SCIMListResponse(BaseModel):
    """
    SCIM 2.0 List Response

    Used for GET /Users endpoint to return list of users for reconciliation.
    """
    schemas: List[str] = Field(default=["urn:ietf:params:scim:api:messages:2.0:ListResponse"])
    totalResults: int
    startIndex: int = 1
    itemsPerPage: int
    Resources: List[SCIMUser]

    class Config:
        json_schema_extra = {
            "example": {
                "schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
                "totalResults": 1,
                "startIndex": 1,
                "itemsPerPage": 1,
                "Resources": [
                    {
                        "schemas": [SCIM_USER_SCHEMA],
                        "id": "12345678-1234-1234-1234-123456789abc",
                        "userName": "jane.example@contoso.onmicrosoft.com",
                        "displayName": "Jane Example",
                        "active": True
                    }
                ]
            }
        }


class SCIMError(BaseModel):
    """
    SCIM 2.0 Error Response

    Standard error format for SCIM API responses.
    """
    schemas: List[str] = Field(default=["urn:ietf:params:scim:api:messages:2.0:Error"])
    status: int  # HTTP status code
    detail: Optional[str] = None  # Error detail message
    scimType: Optional[str] = None  # SCIM error type

    class Config:
        json_schema_extra = {
            "example": {
                "schemas": ["urn:ietf:params:scim:api:messages:2.0:Error"],
                "status": 401,
                "detail": "Authentication failed. Invalid bearer token."
            }
        }
