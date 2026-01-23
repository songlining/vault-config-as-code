"""
SCIM Bridge for Vault - Main FastAPI Application

This FastAPI application provides SCIM 2.0 endpoints for user provisioning
from Microsoft EntraID to HashiCorp Vault identity configuration-as-code.

The bridge receives SCIM webhooks from EntraID, generates YAML identity files,
syncs group memberships, creates Git PRs for manual review, and maintains
user mappings for reconciliation.

Endpoints:
- GET /health - Health check
- POST /scim/v2/Users - Create user
- PATCH /scim/v2/Users/{user_id} - Update user (including group changes)
- DELETE /scim/v2/Users/{user_id} - Deactivate user (soft delete)
- GET /scim/v2/Users - List/reconcile users
"""

import os
import logging
import tempfile
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

from fastapi import FastAPI, HTTPException, Depends, Query, status
from fastapi.responses import JSONResponse

from .models import (
    SCIMUser,
    SCIMUserPatch,
    SCIMListResponse,
    SCIMError,
    SCIM_USER_SCHEMA,
)
from .handlers import verify_bearer_token
from .services import YAMLGenerator, GitHandler, GroupHandler, UserStore

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# FastAPI app initialization
app = FastAPI(
    title="SCIM Bridge for Vault",
    description="SCIM 2.0 bridge for provisioning EntraID users to Vault identity configuration-as-code",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Global service instances (initialized on startup)
yaml_generator: Optional[YAMLGenerator] = None
git_handler: Optional[GitHandler] = None
group_handler: Optional[GroupHandler] = None
user_store: Optional[UserStore] = None
repo_clone_dir: Optional[Path] = None

@app.on_event("startup")
async def startup_event():
    """
    Initialize services on application startup.
    
    Reads environment variables and creates service instances.
    """
    global yaml_generator, git_handler, group_handler, user_store, repo_clone_dir
    
    logger.info("Starting SCIM Bridge for Vault...")
    
    # Environment variables
    repo_url = os.environ.get("GIT_REPO_URL")
    github_token = os.environ.get("GITHUB_TOKEN")
    data_dir = os.environ.get("DATA_DIR", "/app/data")
    
    # Validate required environment variables
    if not repo_url:
        logger.error("GIT_REPO_URL environment variable is required")
        raise RuntimeError("GIT_REPO_URL not configured")
    
    if not github_token:
        logger.error("GITHUB_TOKEN environment variable is required")
        raise RuntimeError("GITHUB_TOKEN not configured")
    
    # Set up data directory and repo clone path
    data_path = Path(data_dir)
    data_path.mkdir(parents=True, exist_ok=True)
    repo_clone_dir = data_path / "vault-config-repo"
    
    # Initialize services
    try:
        # Schema path for YAML generator
        schema_path = repo_clone_dir / "identities" / "schema_entraid_human.yaml"
        yaml_generator = YAMLGenerator(schema_path=str(schema_path))
        
        # Git handler for PR creation
        git_handler = GitHandler(repo_url=repo_url, github_token=github_token)
        
        # Clone/update repository
        await clone_repository()
        
        # Group handler for group membership sync
        group_handler = GroupHandler(repo_clone_dir=str(repo_clone_dir))
        
        # User store for ID mapping
        user_store_path = data_path / "user_store.json"
        user_store = UserStore(data_file=str(user_store_path))
        
        logger.info("SCIM Bridge services initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        raise


async def clone_repository():
    """Clone or update the Git repository."""
    try:
        logger.info("Cloning/updating repository...")
        git_handler.clone_or_pull(clone_dir=str(repo_clone_dir))
        logger.info("Repository clone/update completed")
    except Exception as e:
        logger.error(f"Failed to clone/update repository: {e}")
        raise


@app.get("/health")
async def health_check():
    """
    Health check endpoint.
    
    Returns:
        dict: Health status and service availability
    """
    # Check if all services are initialized
    services_status = {
        "yaml_generator": yaml_generator is not None,
        "git_handler": git_handler is not None,
        "group_handler": group_handler is not None,
        "user_store": user_store is not None,
    }
    
    all_services_ready = all(services_status.values())
    
    health_response = {
        "status": "healthy" if all_services_ready else "degraded",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "services": services_status,
        "version": "1.0.0"
    }
    
    status_code = 200 if all_services_ready else 503
    
    if not all_services_ready:
        logger.warning(f"Health check failed - services status: {services_status}")
    
    return JSONResponse(content=health_response, status_code=status_code)


@app.post("/scim/v2/Users", dependencies=[Depends(verify_bearer_token)])
async def create_user(user: SCIMUser):
    """
    Create a new user identity.
    
    This endpoint:
    1. Generates YAML identity file from SCIM data
    2. Syncs user's group memberships
    3. Creates Git PR for manual review
    4. Stores user ID mapping for future operations
    
    Args:
        user: SCIM user object
        
    Returns:
        SCIMUser: Created user with custom fields (PR URL, YAML file)
    """
    try:
        logger.info(f"Creating user: {user.userName}")
        
        # Update repository before processing
        await clone_repository()
        
        # Convert SCIM user to YAML
        user_dict = user.model_dump(exclude_none=True)
        filename, yaml_content = yaml_generator.scim_to_yaml(user_dict)
        
        # Create PR for user identity
        yaml_file_path = f"identities/{filename}"
        pr_url = git_handler.create_pr_for_user(
            username=user.userName,
            yaml_content=yaml_content,
            yaml_filename=filename
        )
        
        # Handle group memberships if provided
        group_pr_url = None
        if user.groups:
            group_names = [group.display for group in user.groups if group.display and group.display.strip()]
            if group_names:
                modified_files = group_handler.sync_user_groups(
                    display_name=user.displayName or user.userName,
                    group_names=group_names
                )
                
                if modified_files:
                    group_pr_url = git_handler.create_pr_for_groups(
                        username=user.userName,
                        modified_files=modified_files
                    )
        
        # Store user mapping for future operations
        user_store.add_user(
            scim_id=user.id or user.userName,
            name=user.displayName or user.userName,
            filename=filename
        )
        
        # Build response with custom fields
        response_user = user.model_copy()
        
        # Add custom SCIM extension fields (not in standard schema)
        response_dict = response_user.model_dump()
        response_dict["urn:vault:scim:extension"] = {
            "pr_url": pr_url,
            "yaml_file": yaml_file_path,
            "group_pr_url": group_pr_url
        }
        
        logger.info(f"User created successfully: {user.userName}, PR: {pr_url}")
        
        return JSONResponse(
            content=response_dict,
            status_code=status.HTTP_201_CREATED,
            headers={"Content-Type": "application/scim+json"}
        )
        
    except Exception as e:
        logger.error(f"Failed to create user {user.userName}: {e}")
        
        error_response = SCIMError(
            schemas=["urn:ietf:params:scim:api:messages:2.0:Error"],
            status="500",
            detail=f"Internal error creating user: {str(e)}"
        )
        
        return JSONResponse(
            content=error_response.model_dump(),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            headers={"Content-Type": "application/scim+json"}
        )


@app.patch("/scim/v2/Users/{user_id}", dependencies=[Depends(verify_bearer_token)])
async def update_user(user_id: str, patch: SCIMUserPatch):
    """
    Update an existing user identity.
    
    Handles SCIM PATCH operations including group membership changes.
    
    Args:
        user_id: SCIM user ID (EntraID object ID)
        patch: SCIM patch operations
        
    Returns:
        SCIMUser: Updated user with custom fields (PR URL, YAML file)
    """
    try:
        logger.info(f"Updating user: {user_id}")
        
        # Look up user from store
        user_mapping = user_store.get_user(user_id)
        if not user_mapping:
            error_response = SCIMError(
                schemas=["urn:ietf:params:scim:api:messages:2.0:Error"],
                status="404",
                detail=f"User not found: {user_id}"
            )
            
            return JSONResponse(
                content=error_response.model_dump(),
                status_code=status.HTTP_404_NOT_FOUND,
                headers={"Content-Type": "application/scim+json"}
            )
        
        # Update repository before processing
        await clone_repository()
        
        # Process PATCH operations
        group_changes_detected = False
        new_groups = []
        user_active = True
        
        for operation in patch.Operations:
            if operation.path == "groups" and operation.op in ["add", "replace"]:
                # Group membership change
                group_changes_detected = True
                if isinstance(operation.value, list):
                    new_groups = [
                        group.get("display") for group in operation.value 
                        if isinstance(group, dict) and group.get("display")
                    ]
                    
            elif operation.path == "active" and operation.op == "replace":
                # User activation/deactivation
                user_active = bool(operation.value)
        
        # Handle group membership changes
        group_pr_url = None
        if group_changes_detected:
            modified_files = group_handler.sync_user_groups(
                display_name=user_mapping["name"],
                group_names=new_groups
            )
            
            if modified_files:
                group_pr_url = git_handler.create_pr_for_groups(
                    username=user_mapping["vault_name"],
                    modified_files=modified_files
                )
        
        # Handle user deactivation (create updated YAML)
        yaml_pr_url = None
        if not user_active:
            # Create a mock SCIMUser for deactivation (we don't have full user data)
            deactivated_user = SCIMUser(
                id=user_id,
                userName=user_mapping.get("vault_name", user_id),
                displayName=user_mapping.get("vault_name", user_id),
                active=False
            )
            
            # Generate deactivated YAML
            user_dict = deactivated_user.model_dump(exclude_none=True)
            filename, yaml_content = yaml_generator.scim_to_yaml(user_dict)
            
            # Create PR for deactivated user
            yaml_pr_url = git_handler.create_pr_for_user(
                username=user_mapping["vault_name"],
                yaml_content=yaml_content,
                yaml_filename=filename
            )
            
            # Update user store to reflect deactivation
            user_store.add_user(
                scim_id=user_id,
                name=user_mapping["name"],
                filename=filename
            )
        
        # Build response (minimal user data since we don't store full user objects)
        response_user = SCIMUser(
            schemas=[SCIM_USER_SCHEMA],
            id=user_id,
            userName=user_mapping.get("name", user_id),
            displayName=user_mapping.get("name", user_id),
            active=user_active
        )
        
        # Add custom fields
        response_dict = response_user.model_dump()
        response_dict["urn:vault:scim:extension"] = {
            "yaml_file": f"identities/{user_mapping['filename']}",
            "group_pr_url": group_pr_url,
            "yaml_pr_url": yaml_pr_url
        }
        
        logger.info(f"User updated successfully: {user_id}")
        
        return JSONResponse(
            content=response_dict,
            status_code=status.HTTP_200_OK,
            headers={"Content-Type": "application/scim+json"}
        )
        
    except Exception as e:
        logger.error(f"Failed to update user {user_id}: {e}")
        
        error_response = SCIMError(
            schemas=["urn:ietf:params:scim:api:messages:2.0:Error"],
            status="500",
            detail=f"Internal error updating user: {str(e)}"
        )
        
        return JSONResponse(
            content=error_response.model_dump(),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            headers={"Content-Type": "application/scim+json"}
        )


@app.delete("/scim/v2/Users/{user_id}", dependencies=[Depends(verify_bearer_token)])
async def delete_user(user_id: str):
    """
    Deactivate a user identity (soft delete).
    
    Sets user status to deactivated and disabled=true in YAML.
    
    Args:
        user_id: SCIM user ID (EntraID object ID)
        
    Returns:
        Empty response with 204 status
    """
    try:
        logger.info(f"Deactivating user: {user_id}")
        
        # Look up user from store
        user_mapping = user_store.get_user(user_id)
        if not user_mapping:
            return JSONResponse(
                content={},
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        # Update repository before processing
        await clone_repository()
        
        # Remove user from all groups first
        group_handler.remove_user_from_all_groups(user_mapping["name"])
        
        # Create deactivated user YAML
        deactivated_user = SCIMUser(
            id=user_id,
            userName=user_mapping.get("name", user_id),
            displayName=user_mapping.get("name", user_id),
            active=False  # This will set status=deactivated and disabled=true
        )
        
        user_dict = deactivated_user.model_dump(exclude_none=True)
        filename, yaml_content = yaml_generator.scim_to_yaml(user_dict)
        
        # Create PR for deactivation
        pr_url = git_handler.create_pr_for_user(
            username=user_mapping["name"],
            yaml_content=yaml_content,
            yaml_filename=filename
        )
        
        # Update user store to reflect deactivation
        user_store.add_user(
            scim_id=user_id,
            name=user_mapping["name"],
            filename=filename
        )
        
        user_dict = deactivated_user.model_dump(exclude_none=True)
        filename, yaml_content = yaml_generator.scim_to_yaml(user_dict)
        
        # Create PR for deactivation
        pr_url = git_handler.create_pr_for_user(
            username=user_mapping["vault_name"],
            yaml_content=yaml_content,
            yaml_filename=filename
        )
        
        # Update user store to reflect deactivation
        user_store.update_user(
            scim_id=user_id,
            vault_name=user_mapping["vault_name"],
            yaml_filename=filename
        )
        
        logger.info(f"User deactivated successfully: {user_id}, PR: {pr_url}")
        
        # SCIM DELETE should return 204 No Content
        return JSONResponse(
            content={},
            status_code=status.HTTP_204_NO_CONTENT
        )
        
    except Exception as e:
        logger.error(f"Failed to deactivate user {user_id}: {e}")
        
        error_response = SCIMError(
            schemas=["urn:ietf:params:scim:api:messages:2.0:Error"],
            status="500",
            detail=f"Internal error deactivating user: {str(e)}"
        )
        
        return JSONResponse(
            content=error_response.model_dump(),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            headers={"Content-Type": "application/scim+json"}
        )


@app.get("/scim/v2/Users", dependencies=[Depends(verify_bearer_token)])
async def list_users(
    startIndex: int = Query(1, ge=1),
    count: int = Query(100, ge=1, le=1000)
):
    """
    List users for reconciliation.
    
    Returns paginated list of users from the user store.
    
    Args:
        startIndex: 1-based starting index for pagination
        count: Number of users to return (max 1000)
        
    Returns:
        SCIMListResponse: Paginated list of users
    """
    try:
        logger.info(f"Listing users: startIndex={startIndex}, count={count}")
        
        # Get all users from store
        all_users_list = user_store.list_all_users()
        
        # Calculate pagination
        total_results = len(all_users_list)
        start_index_0_based = startIndex - 1  # Convert to 0-based
        end_index = start_index_0_based + count
        
        # Slice users for current page
        page_users = all_users_list[start_index_0_based:end_index]
        
        # Build SCIM user resources
        resources = []
        for user_data in page_users:
            user_resource = SCIMUser(
                schemas=[SCIM_USER_SCHEMA],
                id=user_data.get("scim_id"),
                userName=user_data.get("name"),
                displayName=user_data.get("name"),
                active=True  # We don't store activation state in user store
            )
            
            # Add custom fields
            user_dict = user_resource.model_dump()
            user_dict["urn:vault:scim:extension"] = {
                "yaml_file": f"identities/{user_data.get('filename')}"
            }
            
            resources.append(user_dict)
        
        # Build SCIM ListResponse
        response = SCIMListResponse(
            schemas=["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
            totalResults=total_results,
            startIndex=startIndex,
            itemsPerPage=len(resources),
            Resources=resources
        )
        
        logger.info(f"Returned {len(resources)} users (total: {total_results})")
        
        return JSONResponse(
            content=response.model_dump(),
            status_code=status.HTTP_200_OK,
            headers={"Content-Type": "application/scim+json"}
        )
        
    except Exception as e:
        logger.error(f"Failed to list users: {e}")
        
        error_response = SCIMError(
            schemas=["urn:ietf:params:scim:api:messages:2.0:Error"],
            status="500",
            detail=f"Internal error listing users: {str(e)}"
        )
        
        return JSONResponse(
            content=error_response.model_dump(),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            headers={"Content-Type": "application/scim+json"}
        )


# Exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Convert FastAPI HTTPExceptions to SCIM error format."""
    error_response = SCIMError(
        schemas=["urn:ietf:params:scim:api:messages:2.0:Error"],
        status=str(exc.status_code),
        detail=exc.detail
    )
    
    return JSONResponse(
        content=error_response.model_dump(),
        status_code=exc.status_code,
        headers={"Content-Type": "application/scim+json"}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Convert unhandled exceptions to SCIM error format."""
    logger.error(f"Unhandled exception: {exc}")
    
    error_response = SCIMError(
        schemas=["urn:ietf:params:scim:api:messages:2.0:Error"],
        status="500",
        detail="Internal server error"
    )
    
    return JSONResponse(
        content=error_response.model_dump(),
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        headers={"Content-Type": "application/scim+json"}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)