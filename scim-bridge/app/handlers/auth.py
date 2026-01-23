"""
Bearer token authentication handler for SCIM Bridge.

This module provides FastAPI dependency for authenticating SCIM requests
from Microsoft EntraID using bearer token authentication.
"""

import os
import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

# HTTP Bearer security scheme
security = HTTPBearer()


def verify_bearer_token(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)]
) -> str:
    """
    Verify bearer token from SCIM request against configured token.

    This function is used as a FastAPI dependency to authenticate incoming
    SCIM requests from Microsoft EntraID. It performs constant-time comparison
    to prevent timing attacks.

    Args:
        credentials: HTTP Authorization credentials extracted by FastAPI

    Returns:
        str: The verified token value

    Raises:
        HTTPException: 401 Unauthorized if token is missing, invalid, or doesn't match

    Example:
        @app.post("/scim/v2/Users", dependencies=[Depends(verify_bearer_token)])
        async def create_user(user: SCIMUser):
            # Token is already verified by dependency
            pass
    """
    # Read expected token from environment variable
    expected_token = os.environ.get("SCIM_BEARER_TOKEN")

    # Check if SCIM_BEARER_TOKEN is configured
    if not expected_token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="SCIM_BEARER_TOKEN not configured",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get token from request
    provided_token = credentials.credentials

    # Verify token is not empty
    if not provided_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token missing",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Perform constant-time comparison to prevent timing attacks
    # secrets.compare_digest() is cryptographically secure
    if not secrets.compare_digest(expected_token, provided_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Token is valid
    return provided_token
