# SCIM Integration Plan: EntraID to Vault

## Overview

Integrate Microsoft EntraID (Azure AD) user provisioning into the Vault configuration-as-code repository using SCIM protocol. Users will be provisioned via SCIM webhooks → YAML files → Git PRs → Terraform → Vault, and authenticate via OIDC at runtime.

**Architecture**: SCIM Bridge + OIDC Hybrid
- **Provisioning**: SCIM bridge service receives 
cod from EntraID, generates YAML files, creates Git PRs for manual review
- **Authentication**: OIDC backend allows users to login via EntraID (no passwords stored)
- **Deployment**: Docker container running alongside existing Vault/Neo4j services
- **Deprovisioning**: Soft delete (YAML file retained with `disabled: true` flag)
- **Groups**: Internal groups with YAML-managed membership

## What is a SCIM Bridge?

A **SCIM bridge** is a middleware service that translates SCIM (System for Cross-domain Identity Management) protocol webhooks into actions in your target system.

**Traditional SCIM Flow:**
```
Entra ID → SCIM → Target System (creates users directly in database/API)
```

**This SCIM Bridge Flow:**
```
Entra ID → SCIM Bridge → YAML files → Git PR → Manual Review → Terraform → Vault
```

**Why a Bridge is Needed:**
1. Vault doesn't natively accept SCIM - it uses its own APIs
2. You manage Vault via Terraform (Infrastructure as Code) - not direct API calls
3. You want Git-based workflow with PR review - not automatic provisioning
4. You require manual approval for all identity changes

**What the SCIM Bridge Does:**
- **Receives** SCIM webhooks from Entra ID (user create/update/delete, group changes)
- **Transforms** SCIM payloads to Vault identity YAML format
- **Validates** generated YAML against JSON schema
- **Updates** identity_groups YAML files for group memberships
- **Creates** Git branches, commits changes, and opens GitHub PRs
- **Maintains** mapping between SCIM UUIDs and Vault identity names

It's essentially a **translator + automation layer** that bridges Entra ID's SCIM protocol and your Terraform-based Vault configuration workflow.

## User Choices Applied

✅ **Hosting**: Docker locally with existing docker-compose.yml
✅ **Deprovisioning**: Soft delete - preserves audit trail
✅ **Approvals**: Manual review for all SCIM changes
✅ **Groups**: Internal groups with YAML-managed membership (SCIM bridge updates group YAML files)

## Architecture Diagram

```
EntraID (Azure AD)
    │
    ├── SCIM Events ──────────┐
    │   (User CRUD)           │
    │                         ▼
    │              ┌─────────────────────┐
    │              │  SCIM Bridge        │
    │              │  (FastAPI/Docker)   │
    │              ├─────────────────────┤
    │              │ • Receives webhooks │
    │              │ • Generates YAML    │
    │              │ • Creates Git PRs   │
    │              │ • Validates schema  │
    │              └──────────┬──────────┘
    │                         │
    │                         ▼
    │              ┌─────────────────────┐
    │              │  Git Repository     │
    │              │  (Pull Requests)    │
    │              ├─────────────────────┤
    │              │ identities/         │
    │              │ entraid_human_*.yaml│
    │              └──────────┬──────────┘
    │                         │ (Manual Review)
    │                         ▼
    │              ┌─────────────────────┐
    │              │  Terraform Apply    │
    │              ├─────────────────────┤
    │              │ vault_identity_     │
    │              │   entity            │
    │              │ vault_identity_     │
    │              │   entity_alias      │
    │              │ (oidc mount)        │◄── OIDC Login
    │              └─────────────────────┘   (Runtime Auth)
```

## Implementation Phases

### Phase 1: OIDC Authentication Backend (Week 1-2)

**Objective**: Enable EntraID users to authenticate to Vault via OIDC

#### 1.1 EntraID App Registration
- Create app registration in Azure Portal
- Configure redirect URIs: `http://localhost:8200/ui/vault/auth/oidc/oidc/callback`
- Generate client secret
- Note tenant ID, client ID, client secret

#### 1.2 Terraform Configuration Files

**Create New File: `entraid_variables.tf`**
```hcl
# Entra ID OIDC Authentication Variables

variable "enable_entraid_auth" {
  description = "Enable Entra ID OIDC authentication backend"
  type        = bool
  default     = false
}

variable "entraid_tenant_id" {
  description = "Azure AD/Entra ID tenant ID"
  type        = string
  default     = ""
}

variable "entraid_client_id" {
  description = "Entra ID application client ID"
  type        = string
  sensitive   = true
  default     = ""
}

variable "entraid_client_secret" {
  description = "Entra ID application client secret"
  type        = string
  sensitive   = true
  default     = ""
}

variable "entraid_oidc_scopes" {
  description = "OIDC scopes to request from Entra ID"
  type        = list(string)
  default     = ["openid", "profile", "email"]
}
```

**Create New File: `entraid-auth.tf`**
```hcl
# Entra ID OIDC Authentication Backend Configuration

resource "vault_jwt_auth_backend" "entraid" {
  count              = var.enable_entraid_auth ? 1 : 0
  description        = "OIDC auth method for Entra ID (Azure AD)"
  type               = "oidc"
  path               = "oidc"

  # Entra ID OIDC endpoints
  oidc_discovery_url = "https://login.microsoftonline.com/${var.entraid_tenant_id}/v2.0"
  oidc_client_id     = var.entraid_client_id
  oidc_client_secret = var.entraid_client_secret

  # Use email as the primary claim
  default_role       = "entraid-user"

  # Token settings matching LDAP pattern
  tune {
    default_lease_ttl  = "8h"
    max_lease_ttl      = "168h"
    token_type         = "service"
  }
}

resource "vault_jwt_auth_backend_role" "entraid_user" {
  count         = var.enable_entraid_auth ? 1 : 0
  backend       = vault_jwt_auth_backend.entraid[0].path
  role_name     = "entraid-user"

  # Token configuration
  token_ttl     = 3600 * 8
  token_max_ttl = 3600 * 24 * 7

  # User claim mapping - use email as canonical identifier
  user_claim            = "email"
  groups_claim          = "groups"

  # Allowed redirect URIs
  allowed_redirect_uris = [
    "${var.vault_url}/ui/vault/auth/oidc/oidc/callback",
    "http://localhost:8250/oidc/callback",
  ]

  oidc_scopes = var.entraid_oidc_scopes
  role_type   = "oidc"
}
```

**Create New File: `entraid_identities.tf`**
```hcl
# Entra ID Human Identity Entities

resource "vault_identity_entity" "entraid_human" {
  for_each = local.entraid_human_identities_map
  name     = each.key

  policies = concat(
    [for i in each.value.policies.identity_policies : i],
    ["human-identity-token-policies"]
  )

  metadata = {
    role              = each.value.identity.role
    team              = each.value.identity.team
    email             = each.value.identity.email
    status            = try(each.value.identity.status, "active")
    entraid_upn       = try(each.value.metadata.entraid_upn, each.value.identity.email)
    entraid_object_id = try(each.value.metadata.entraid_object_id, "")
    spiffe_id         = "spiffe://vault/entraid/human/${each.value.identity.role}/${each.value.identity.team}/${each.value.identity.name}"
  }

  disabled = try(each.value.authentication.disabled, false) || try(each.value.identity.status, "active") == "deactivated"
}

# OIDC Entity Alias
resource "vault_identity_entity_alias" "entraid_human_oidc" {
  for_each       = var.enable_entraid_auth ? local.entraid_human_with_oidc : {}
  mount_accessor = vault_jwt_auth_backend.entraid[0].accessor
  canonical_id   = vault_identity_entity.entraid_human[each.key].id
  name           = each.value.authentication.oidc
}

# GitHub Entity Alias (multi-auth support)
resource "vault_identity_entity_alias" "entraid_human_github" {
  for_each       = local.entraid_human_with_github
  mount_accessor = vault_github_auth_backend.hashicorp.accessor
  canonical_id   = vault_identity_entity.entraid_human[each.key].id
  name           = each.value.authentication.github
}

# PKI Entity Alias (multi-auth support)
resource "vault_identity_entity_alias" "entraid_human_pki" {
  for_each       = local.entraid_human_with_pki
  mount_accessor = vault_auth_backend.cert.accessor
  canonical_id   = vault_identity_entity.entraid_human[each.key].id
  name           = each.value.authentication.pki
}
```

**Update Existing File: `data.tf` (add after line 150)**
```hcl
# Entra ID human identities
entraid_human_identities_map = {
  for filename, config in local.configs_by_type.identities :
  config.identity.name => config
  if startswith(filename, "entraid_human_")
}

entraid_human_with_oidc = {
  for k, v in local.entraid_human_identities_map :
  k => v if try(v.authentication.oidc, null) != null && v.authentication.oidc != "" && try(v.authentication.disabled, false) == false
}

entraid_human_with_github = {
  for k, v in local.entraid_human_identities_map :
  k => v if try(v.authentication.github, null) != null && v.authentication.github != ""
}

entraid_human_with_pki = {
  for k, v in local.entraid_human_identities_map :
  k => v if try(v.authentication.pki, null) != null && v.authentication.pki != ""
}
```

**Update Existing File: `identity_groups.tf` (add after line 54)**
```hcl
# Internal group members (Entra ID human identities)
resource "vault_identity_group_member_entity_ids" "entraid_human_group" {
  for_each = {
    for name, config in local.internal_groups_map :
    name => config if try(length(config.entraid_human_identities), 0) > 0
  }
  group_id          = vault_identity_group.internal_group[each.key].id
  member_entity_ids = [for i in each.value.entraid_human_identities : vault_identity_entity.entraid_human[i].id]
  exclusive         = false
}
```

**Update Existing File: `dev.tfvars`**
```hcl
# Entra ID OIDC Authentication Backend
enable_entraid_auth = true

entraid_tenant_id      = "your-tenant-id-here"
entraid_client_id      = "your-client-id-here"
entraid_client_secret  = "your-client-secret-here"
```

#### 1.3 YAML Schema

**Create New File: `identities/schema_entraid_human.yaml`**
```yaml
$schema: "http://json-schema.org/draft-07/schema#"
title: "Entra ID Human Identity Schema"
description: "Schema for defining Entra ID-provisioned human identities in Vault"
type: object
properties:
  $schema:
    type: string
    description: "JSON Schema reference for this document"
  metadata:
    type: object
    properties:
      version:
        type: string
        pattern: "^[0-9]+\\.[0-9]+\\.[0-9]+$"
        description: "Semantic version of this identity configuration"
      created_date:
        type: string
        format: date
        description: "Date when this identity was created"
      description:
        type: string
        description: "Brief description of this human identity"
      entraid_object_id:
        type: string
        description: "Entra ID object ID (immutable identifier)"
      entraid_upn:
        type: string
        description: "Entra ID User Principal Name"
      provisioned_via_scim:
        type: boolean
        description: "Whether this identity was provisioned via SCIM"
        default: false
    required:
      - version
      - created_date
      - description
  identity:
    type: object
    properties:
      name:
        type: string
        description: "Full name of the person"
        minLength: 1
      email:
        type: string
        format: email
        description: "Email address (matches OIDC claim)"
      role:
        type: string
        description: "Job role or position"
        minLength: 1
      team:
        type: string
        description: "Team or department"
        minLength: 1
      status:
        type: string
        enum: ["active", "deactivated"]
        description: "Identity status - deactivated users cannot authenticate"
        default: "active"
    required:
      - name
      - email
      - role
      - team
  authentication:
    type: object
    properties:
      oidc:
        type: string
        format: email
        description: "OIDC email address (primary authentication method)"
      github:
        type: string
        description: "GitHub username (optional multi-auth)"
        pattern: "^[a-zA-Z0-9\\-_]+$"
      pki:
        type: string
        description: "PKI certificate identifier (optional multi-auth)"
        pattern: "^[a-zA-Z0-9\\-\\.]+$"
      disabled:
        type: boolean
        description: "When true, all authentication methods are disabled"
        default: false
    required:
      - oidc
  policies:
    type: object
    properties:
      identity_policies:
        type: array
        items:
          type: string
        description: "List of Vault policies assigned to this identity"
        minItems: 0
    required:
      - identity_policies
required:
  - metadata
  - identity
  - authentication
  - policies
additionalProperties: false
```

**Example Identity File: `identities/entraid_human_alice_smith.yaml`**
```yaml
$schema: "./schema_entraid_human.yaml"

metadata:
  version: "1.0.0"
  created_date: "2026-01-23"
  description: "Entra ID Human Identity for Alice Smith"
  entraid_object_id: "550e8400-e29b-41d4-a716-446655440000"
  entraid_upn: "alice.smith@company.com"
  provisioned_via_scim: true

identity:
  name: "Alice Smith"
  email: "alice.smith@company.com"
  role: "senior_engineer"
  team: "platform_engineering"
  status: "active"

authentication:
  oidc: "alice.smith@company.com"
  github: "asmith"  # Optional multi-auth
  disabled: false

policies:
  identity_policies:
    - "developer-policy"
```

#### 1.4 Update Validation Script

**Modify: `identities/validate_identities.py`**

Update the `load_schemas()` method (around line 59-98):
```python
def load_schemas(self) -> bool:
    """Load all schema files from the identities directory."""
    schema_files = {
        'application': self.identities_dir / 'schema_application.yaml',
        'human': self.identities_dir / 'schema_human.yaml',
        'ldap_human': self.identities_dir / 'schema_ldap_human.yaml',
        'entraid_human': self.identities_dir / 'schema_entraid_human.yaml'  # ADD THIS
    }

    for schema_type, schema_path in schema_files.items():
        # LDAP and Entra ID schemas are optional
        if schema_type in ['ldap_human', 'entraid_human'] and not schema_path.exists():
            print(f"⚠️  Optional schema not found, skipping: {schema_path}")
            continue

        if not schema_path.exists():
            self.errors.append(f"Schema file not found: {schema_path}")
            return False
        # ... rest of the method remains the same
```

Update the `determine_schema_type()` method (around line 100-121):
```python
def determine_schema_type(self, file_path: Path) -> Optional[str]:
    """Determine which schema to use based on the filename."""
    filename = file_path.name.lower()

    if filename.startswith('application_'):
        return 'application'
    elif filename.startswith('entraid_human_'):  # CHECK THIS FIRST (most specific)
        return 'entraid_human'
    elif filename.startswith('ldap_human_'):     # THEN THIS
        return 'ldap_human'
    elif filename.startswith('human_'):          # THEN GENERIC HUMAN
        return 'human'
    elif filename.startswith('schema_'):
        return None  # Skip schema files
    else:
        self.warnings.append(f"Cannot determine schema type for file: {file_path}")
        return None
```

#### 1.5 Testing

- Manually create test user YAML: `identities/entraid_human_test_user.yaml`
- Run `terraform plan -var-file=dev.tfvars`
- Apply Terraform
- Test OIDC login: `vault login -method=oidc`
- Verify entity created and policies attached

**Critical Files**:
- [entraid_variables.tf](../entraid_variables.tf) (new)
- [entraid-auth.tf](../entraid-auth.tf) (new)
- [entraid_identities.tf](../entraid_identities.tf) (new)
- [data.tf](../data.tf) (update lines ~138+)
- [identity_groups.tf](../identity_groups.tf) (update for EntraID membership)
- [identities/schema_entraid_human.yaml](../identities/schema_entraid_human.yaml) (new)
- [identities/validate_identities.py](../identities/validate_identities.py) (update)

---

### Phase 2: SCIM Bridge Service (Week 3-4)

**Objective**: Build and deploy SCIM webhook service that generates YAML files and creates PRs

#### 2.1 SCIM Bridge Directory Structure

Create `scim-bridge/` directory with:
```
scim-bridge/
├── app/
│   ├── main.py                 # FastAPI application
│   ├── models/
│   │   ├── scim_user.py        # SCIM User Pydantic models
│   │   └── scim_group.py       # SCIM Group Pydantic models
│   ├── handlers/
│   │   ├── users.py            # User CRUD operations
│   │   ├── groups.py           # Group operations
│   │   └── auth.py             # Bearer token auth
│   ├── services/
│   │   ├── yaml_generator.py  # YAML file generation
│   │   ├── git_handler.py     # Git operations (clone, commit, PR)
│   │   └── validator.py       # Schema validation
│   └── config.py               # Configuration management
├── tests/
│   ├── test_users.py
│   └── test_yaml_generation.py
├── Dockerfile
├── requirements.txt
└── .env.example
```

#### 2.2 Core Components

**SCIM Endpoints** (main.py):
- `POST /scim/v2/Users` - Create user → Generate YAML → Create PR
- `PATCH /scim/v2/Users/{id}` - Update user → Update YAML → Create PR
- `DELETE /scim/v2/Users/{id}` - Deactivate user → Soft delete → Create PR
- `GET /scim/v2/Users` - List users (for reconciliation)
- Bearer token authentication on all endpoints

**Create New File: `scim-bridge/app/main.py`**
```python
from fastapi import FastAPI, Depends, HTTPException
from typing import Optional
import os

from app.models.scim_user import SCIMUser, SCIMUserPatch
from app.services.yaml_generator import YAMLGenerator
from app.services.git_handler import GitHandler
from app.services.group_handler import GroupHandler
from app.services.user_store import UserStore
from app.handlers.auth import verify_bearer_token

app = FastAPI(title="SCIM Bridge for Vault", version="1.0.0")

# Initialize services
yaml_gen = YAMLGenerator(schema_path="/app/identities/schema_entraid_human.yaml")
git_handler = GitHandler(
    repo_url=os.getenv('GIT_REPO_URL'),
    github_token=os.getenv('GITHUB_TOKEN')
)
group_handler = GroupHandler(repo_clone_dir="/data/repo")
user_store = UserStore(data_file="/data/user_mapping.json")

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "scim-bridge"}

@app.post("/scim/v2/Users", status_code=201)
def create_user(user: SCIMUser, token: str = Depends(verify_bearer_token)):
    """SCIM 2.0 User Creation with Group Sync"""
    try:
        # Generate user YAML
        filename, yaml_content = yaml_gen.scim_to_yaml(user.dict())

        # Sync group memberships
        modified_group_files = []
        if user.groups:
            modified_group_files = group_handler.sync_user_groups(
                display_name=user.displayName,
                scim_groups=user.groups
            )

        # Create PR with both user and group files
        pr_url = git_handler.create_pr_for_user(
            filename=filename,
            yaml_content=yaml_content,
            operation='create',
            username=user.displayName,
            additional_files=modified_group_files
        )

        # Store mapping
        user_store.add_user(scim_id=user.id, name=user.displayName, filename=filename)

        return {
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
            "id": user.id,
            "userName": user.userName,
            "displayName": user.displayName,
            "groups": user.groups,
            "meta": {
                "resourceType": "User",
                "location": f"/scim/v2/Users/{user.id}"
            },
            "custom": {
                "pr_url": pr_url,
                "yaml_file": filename,
                "groups_updated": len(modified_group_files)
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/scim/v2/Users/{user_id}")
def update_user(user_id: str, patch: SCIMUserPatch, token: str = Depends(verify_bearer_token)):
    """SCIM 2.0 User Update - handles group membership changes"""
    user_data = user_store.get_user(user_id)
    if not user_data:
        raise HTTPException(status_code=404, detail="User not found")

    modified_files = []

    # Process PATCH operations
    for operation in patch.Operations:
        if operation.path == "groups":
            if operation.op == "add":
                for group in operation.value:
                    group_file = group_handler._add_user_to_group_by_name(
                        group_name=group.get('display'),
                        user_name=user_data['displayName']
                    )
                    if group_file:
                        modified_files.append(group_file)
            elif operation.op == "remove":
                for group in operation.value:
                    group_file = group_handler.remove_user_from_group(
                        display_name=user_data['displayName'],
                        group_display_name=group.get('display')
                    )
                    if group_file:
                        modified_files.append(group_file)

    # Create PR for group membership changes
    if modified_files:
        pr_url = git_handler.create_pr_for_groups(
            modified_files=modified_files,
            operation='update-membership',
            username=user_data['displayName']
        )
        return {"status": "updated", "pr_url": pr_url}

    return {"status": "no changes"}

@app.delete("/scim/v2/Users/{user_id}")
def deactivate_user(user_id: str, token: str = Depends(verify_bearer_token)):
    """SCIM 2.0 User Deactivation (Soft Delete)"""
    user_data = user_store.get_user(user_id)
    if not user_data:
        raise HTTPException(status_code=404, detail="User not found")

    # Mark as deactivated
    deactivated_user = {**user_data, 'active': False}
    filename, yaml_content = yaml_gen.scim_to_yaml(deactivated_user)

    pr_url = git_handler.create_pr_for_user(
        filename=filename,
        yaml_content=yaml_content,
        operation='deactivate',
        username=user_data['displayName']
    )

    return {"status": "deactivated", "pr_url": pr_url}

@app.get("/scim/v2/Users")
def list_users(token: str = Depends(verify_bearer_token)):
    """SCIM 2.0 User List (for reconciliation)"""
    users = user_store.list_all_users()
    return {
        "schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
        "totalResults": len(users),
        "Resources": users
    }
```

**YAML Generator** (yaml_generator.py):
- Transform SCIM user payload to `entraid_human_*.yaml` format
- Map EntraID attributes: userName → oidc, displayName → name, title → role, department → team
- Sanitize filenames: "Alice Smith" → `entraid_human_alice_smith.yaml`
- Validate against schema before writing

**SCIM Attribute Mapping:**
```
SCIM Field              → YAML Field
─────────────────────────────────────────
userName                → authentication.oidc
displayName             → identity.name
emails[0].value         → identity.email
title                   → identity.role
department              → identity.team
id (UUID)               → metadata.entraid_object_id
userName (UPN)          → metadata.entraid_upn
active (boolean)        → identity.status (active/deactivated)
```

**Create New File: `scim-bridge/app/services/yaml_generator.py`**
```python
from typing import Dict, Any, Tuple
import yaml
import re
from datetime import date

class YAMLGenerator:
    """Generate Vault identity YAML files from SCIM user payloads"""

    def __init__(self, schema_path: str):
        self.schema_path = schema_path

    def scim_to_yaml(self, scim_user: Dict[str, Any]) -> Tuple[str, str]:
        """
        Convert SCIM user to YAML identity file.

        Returns:
            (filename, yaml_content)
        """
        # Extract fields with safe defaults
        display_name = scim_user.get('displayName', 'Unknown User')
        username = scim_user.get('userName', '')
        email = scim_user.get('emails', [{}])[0].get('value', username)
        title = scim_user.get('title', 'employee')
        department = scim_user.get('department', 'general')
        scim_id = scim_user.get('id', '')
        active = scim_user.get('active', True)

        # Generate filename
        filename = self._generate_filename(display_name)

        # Build YAML structure
        identity_data = {
            '$schema': './schema_entraid_human.yaml',
            'metadata': {
                'version': '1.0.0',
                'created_date': str(date.today()),
                'description': f'Entra ID Human Identity for {display_name}',
                'entraid_object_id': scim_id,
                'entraid_upn': username,
                'provisioned_via_scim': True
            },
            'identity': {
                'name': display_name,
                'email': email,
                'role': self._sanitize_role(title),
                'team': self._sanitize_team(department),
                'status': 'active' if active else 'deactivated'
            },
            'authentication': {
                'oidc': email,
                'disabled': not active
            },
            'policies': {
                'identity_policies': []
            }
        }

        # Convert to YAML
        yaml_content = yaml.dump(
            identity_data,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True
        )

        return filename, yaml_content

    def _generate_filename(self, display_name: str) -> str:
        """Generate entraid_human_firstname_lastname.yaml"""
        sanitized = display_name.lower()
        sanitized = re.sub(r'[^a-z0-9\s]', '', sanitized)
        sanitized = sanitized.replace(' ', '_')
        return f"entraid_human_{sanitized}.yaml"

    def _sanitize_role(self, title: str) -> str:
        """Convert job title to role slug"""
        if not title:
            return 'employee'
        return re.sub(r'[^a-z0-9]', '_', title.lower()).strip('_')

    def _sanitize_team(self, department: str) -> str:
        """Convert department to team slug"""
        if not department:
            return 'general'
        return re.sub(r'[^a-z0-9]', '_', department.lower()).strip('_')
```

**Git Handler** (git_handler.py):
- Clone/pull vault-config-as-code repository
- Create feature branch: `scim-provision-{username}-{timestamp}`
- Commit YAML changes with descriptive message
- Push to remote
- Create GitHub PR via API with labels: `scim-provisioning`, `needs-review`

**Group Handler** (group_handler.py):
- Read group information from SCIM user payload
- Update identity_groups/*.yaml files
- Add/remove users from `entraid_human_identities` lists
- Include group file changes in same PR

#### 2.3 Docker Integration

**Create New File: `scim-bridge/Dockerfile`**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install git for repo operations
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/

# Create data directory for persistent storage
RUN mkdir -p /data

# Expose port
EXPOSE 8000

# Run FastAPI with uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Create New File: `scim-bridge/requirements.txt`**
```
fastapi==0.109.0
uvicorn[standard]==0.27.0
pydantic==2.5.3
pyyaml==6.0.1
jsonschema==4.21.1
requests==2.31.0
python-multipart==0.0.6
```

**Update `docker-compose.yml`** (add after Neo4j service):
```yaml
  scim-bridge:
    build: ./scim-bridge
    container_name: scim-bridge
    ports:
      - "8080:8000"
    environment:
      - SCIM_BEARER_TOKEN=${SCIM_BEARER_TOKEN}
      - GIT_REPO_URL=${GIT_REPO_URL:-https://github.com/your-org/vault-config-as-code.git}
      - GITHUB_TOKEN=${GITHUB_TOKEN}
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
    volumes:
      - scim-data:/data
      - scim-logs:/app/logs
    networks:
      - vault-network
    depends_on:
      - vault
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

# Add to volumes section:
volumes:
  scim-data:
    driver: local
  scim-logs:
    driver: local
```

#### 2.4 Secrets Management

Store in environment variables or Vault:
- `SCIM_BEARER_TOKEN` - Token for EntraID to authenticate to SCIM bridge
- `GITHUB_TOKEN` - Personal access token for creating PRs
- `GIT_SSH_KEY` or `GIT_PAT` - For Git push access

#### 2.5 Testing

- Start SCIM bridge: `docker compose up scim-bridge`
- Test health endpoint: `curl http://localhost:8080/health`
- Simulate SCIM user creation via curl/Postman
- Verify YAML file generated in local repo clone
- Verify PR created in GitHub
- Test schema validation with invalid data

**Critical Files**:
- [scim-bridge/app/main.py](../scim-bridge/app/main.py) (new)
- [scim-bridge/app/services/yaml_generator.py](../scim-bridge/app/services/yaml_generator.py) (new)
- [scim-bridge/app/services/git_handler.py](../scim-bridge/app/services/git_handler.py) (new)
- [scim-bridge/Dockerfile](../scim-bridge/Dockerfile) (new)
- [docker-compose.yml](../docker-compose.yml) (update)

---

### Phase 2.5: Group Synchronization Design

**Objective**: Handle Entra ID group memberships and sync them to Vault Identity Groups

#### 2.5.1 Group Sync Strategy

The SCIM bridge will update `identity_groups/*.yaml` files when Entra ID sends group membership information in SCIM requests.

**How Entra ID Sends Group Info:**
- User creation includes groups: `POST /scim/v2/Users` with `groups` array
- Group membership changes: `PATCH /scim/v2/Users/{id}` with operations to add/remove groups

**Scenarios:**

**Scenario 1: User Created with Group Memberships**
```
1. Entra ID sends: POST /scim/v2/Users
   {
     "userName": "alice@company.com",
     "displayName": "Alice Smith",
     "groups": [{"value": "developers", "display": "Developers"}]
   }

2. SCIM Bridge:
   a) Creates identities/entraid_human_alice_smith.yaml
   b) Updates identity_groups/identity_group_developers.yaml:
      entraid_human_identities:
        - "Alice Smith"
   c) Creates single PR with both file changes
```

**Scenario 2: User Added to Group**
```
1. Entra ID sends: PATCH /scim/v2/Users/{id}
   Operations: [{"op": "add", "path": "groups", "value": [{"value": "admins"}]}]

2. SCIM Bridge:
   a) Updates identity_groups/identity_group_admins.yaml
   b) Adds "Alice Smith" to entraid_human_identities list
   c) Creates PR for group membership change
```

**Scenario 3: User Removed from Group**
```
1. Entra ID sends: PATCH /scim/v2/Users/{id}
   Operations: [{"op": "remove", "path": "groups", "value": [{"value": "developers"}]}]

2. SCIM Bridge:
   a) Updates identity_groups/identity_group_developers.yaml
   b) Removes "Alice Smith" from entraid_human_identities list
   c) Creates PR for group membership removal
```

#### 2.5.2 Group Handler Implementation

**Create New File: `scim-bridge/app/services/group_handler.py`**
```python
import yaml
import os
import re
from typing import List, Dict, Optional

class GroupHandler:
    """Manage identity_groups YAML files for SCIM group sync"""

    def __init__(self, repo_clone_dir: str):
        self.groups_dir = os.path.join(repo_clone_dir, "identity_groups")
        self.group_name_mapping = {}

    def sync_user_groups(self, display_name: str, scim_groups: List[Dict]) -> List[str]:
        """
        Update all relevant identity_groups YAML files for user's group memberships.

        Args:
            display_name: User's display name (e.g., "Alice Smith")
            scim_groups: List of SCIM group objects [{"value": "id", "display": "name"}]

        Returns:
            List of modified YAML file paths
        """
        modified_files = []
        existing_groups = self._load_all_groups()

        for scim_group in scim_groups:
            group_display_name = scim_group.get('display', '')
            group_file = self._find_group_file(group_display_name, existing_groups)

            if group_file:
                if self._add_user_to_group(group_file, display_name):
                    modified_files.append(group_file)
            else:
                new_file = self._create_group_file(group_display_name, display_name)
                modified_files.append(new_file)

        return modified_files

    def remove_user_from_group(self, display_name: str, group_display_name: str) -> Optional[str]:
        """Remove user from a group's YAML file"""
        existing_groups = self._load_all_groups()
        group_file = self._find_group_file(group_display_name, existing_groups)

        if not group_file:
            return None

        with open(group_file, 'r') as f:
            group_data = yaml.safe_load(f)

        members = group_data.get('entraid_human_identities', [])
        if display_name in members:
            members.remove(display_name)
            group_data['entraid_human_identities'] = members

            with open(group_file, 'w') as f:
                yaml.dump(group_data, f, default_flow_style=False, sort_keys=False)

            return group_file

        return None

    def _load_all_groups(self) -> Dict[str, Dict]:
        """Load all identity_groups/*.yaml files"""
        groups = {}
        for filename in os.listdir(self.groups_dir):
            if filename.endswith('.yaml') and not filename.startswith('example'):
                filepath = os.path.join(self.groups_dir, filename)
                with open(filepath, 'r') as f:
                    groups[filepath] = yaml.safe_load(f)
        return groups

    def _find_group_file(self, group_display_name: str, existing_groups: Dict) -> Optional[str]:
        """Find existing group file by display name"""
        for filepath, group_data in existing_groups.items():
            if group_data.get('name') == group_display_name:
                return filepath
        return None

    def _add_user_to_group(self, group_file: str, display_name: str) -> bool:
        """Add user to group's entraid_human_identities list"""
        with open(group_file, 'r') as f:
            group_data = yaml.safe_load(f)

        if 'entraid_human_identities' not in group_data:
            group_data['entraid_human_identities'] = []

        if display_name not in group_data['entraid_human_identities']:
            group_data['entraid_human_identities'].append(display_name)

            with open(group_file, 'w') as f:
                yaml.dump(group_data, f, default_flow_style=False, sort_keys=False)

            return True

        return False

    def _create_group_file(self, group_display_name: str, first_member: str) -> str:
        """Create new identity_groups YAML file"""
        slug = group_display_name.lower().replace(' ', '_')
        slug = re.sub(r'[^a-z0-9_]', '', slug)
        filename = f"identity_group_{slug}.yaml"
        filepath = os.path.join(self.groups_dir, filename)

        group_data = {
            'name': group_display_name,
            'contact': 'scim-provisioning@company.com',
            'human_identities': [],
            'ldap_human_identities': [],
            'entraid_human_identities': [first_member],
            'application_identities': [],
            'sub_groups': [],
            'identity_group_policies': []
        }

        with open(filepath, 'w') as f:
            yaml.dump(group_data, f, default_flow_style=False, sort_keys=False)

        return filepath
```

#### 2.5.3 Updated Identity Groups YAML Structure

**Example: `identity_groups/identity_group_developers.yaml`**
```yaml
name: Developers
contact: engineering-leads@company.com
type: internal

# Human identities (GitHub auth)
human_identities:
  - "Yulei Liu"
  - "Simon Lynch"

# LDAP-authenticated humans
ldap_human_identities:
  - "John Doe"

# Entra ID-authenticated humans (added by SCIM bridge)
entraid_human_identities:
  - "Alice Smith"
  - "Bob Johnson"

# Application identities
application_identities:
  - "Core Banking Backend"

# Sub-groups
sub_groups: []

# Vault policies assigned to this group
identity_group_policies:
  - "developer-secrets-consumer"
  - "developer-pki-role"
```

#### 2.5.4 End-to-End Group Sync Flow

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Entra ID Admin assigns user to application              │
│    User: Alice Smith                                        │
│    Groups: Developers, Platform-Engineering                 │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Entra ID SCIM Provisioning sends POST /scim/v2/Users    │
│    {                                                        │
│      "displayName": "Alice Smith",                          │
│      "groups": [                                            │
│        {"display": "Developers"},                           │
│        {"display": "Platform-Engineering"}                  │
│      ]                                                      │
│    }                                                        │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. SCIM Bridge Processing                                   │
│    a) Generate: identities/entraid_human_alice_smith.yaml   │
│    b) Update: identity_groups/identity_group_developers.yaml│
│       Add "Alice Smith" to entraid_human_identities         │
│    c) Update: identity_groups/identity_group_platform-...   │
│       Add "Alice Smith" to entraid_human_identities         │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. Git PR Created                                           │
│    Branch: scim-create-alice-smith-20260123                 │
│    Files Changed:                                           │
│      + identities/entraid_human_alice_smith.yaml            │
│      M identity_groups/identity_group_developers.yaml       │
│      M identity_groups/identity_group_platform-engineer...  │
│    Labels: scim-provisioning, needs-review                  │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼ (Manual Review)
┌─────────────────────────────────────────────────────────────┐
│ 5. Vault Admin Reviews and Merges PR                       │
│    - Verifies user details correct                          │
│    - Confirms group memberships appropriate                 │
│    - Checks YAML validation passes                          │
│    - Merges to main branch                                  │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. Terraform Apply                                          │
│    terraform apply -var-file=dev.tfvars                     │
│                                                             │
│    Creates:                                                 │
│    - vault_identity_entity.entraid_human["Alice Smith"]     │
│    - vault_identity_entity_alias.entraid_human_oidc[...]    │
│                                                             │
│    Updates:                                                 │
│    - vault_identity_group_member_entity_ids for Developers  │
│    - vault_identity_group_member_entity_ids for Platform    │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ 7. Alice can now:                                           │
│    - Login via: vault login -method=oidc                    │
│    - Inherits policies from:                                │
│      * human-identity-token-policies (base)                 │
│      * developer-secrets-consumer (from Developers group)   │
│      * platform-engineering-policies (from Platform group)  │
└─────────────────────────────────────────────────────────────┘
```

---

### Phase 3: EntraID SCIM Configuration (Week 5)

**Objective**: Configure EntraID to send SCIM provisioning events to the bridge

#### 3.1 Expose SCIM Bridge

**For local development**:
- Use ngrok or similar tunnel: `ngrok http 8080`
- Note public URL: `https://abc123.ngrok.io`
- Configure EntraID to use: `https://abc123.ngrok.io/scim/v2`

**For production**:
- Deploy behind public load balancer with TLS
- Use proper domain: `https://scim-bridge.company.com/scim/v2`

#### 3.2 EntraID Enterprise Application

In Azure Portal:
1. Navigate to Enterprise Applications → Your OIDC app
2. Enable Provisioning → Automatic mode
3. Configure:
   - **Tenant URL**: `https://<public-endpoint>/scim/v2`
   - **Secret Token**: `${SCIM_BEARER_TOKEN}` (same as bridge env var)
4. Set up attribute mappings:
   - `userPrincipalName` → `userName`
   - `displayName` → `displayName`
   - `mail` → `emails[0].value`
   - `jobTitle` → `title`
   - `department` → `department`
5. Assign users/groups to provision
6. Test connection
7. Start provisioning

#### 3.3 Initial Sync

- EntraID performs initial sync (can take 20-40 minutes)
- Monitor SCIM bridge logs: `docker logs -f scim-bridge`
- Review created PRs in GitHub
- Approve and merge PRs manually
- Run `terraform apply -var-file=dev.tfvars`
- Verify entities created in Vault

**Critical Configuration**:
- EntraID provisioning settings
- SCIM attribute mappings
- Public endpoint with TLS

---

### Phase 4: Pilot Testing (Week 6)

**Objective**: Test end-to-end workflow with 5-10 pilot users

#### 4.1 Select Pilot Users

- Choose 5-10 users from EntraID
- Assign to enterprise application
- EntraID provisions via SCIM

#### 4.2 Provisioning Flow

1. EntraID sends `POST /scim/v2/Users`
2. SCIM bridge generates `entraid_human_*.yaml`
3. PR created with label `scim-provisioning`
4. **Manual review** - verify YAML correctness
5. Merge PR
6. CI/CD runs `terraform apply`
7. Vault entity created with OIDC alias
8. User can now login

#### 4.3 User Testing

Pilot users test:
- Login via Vault UI → OIDC method
- Access secrets/policies based on group membership
- Generate identity tokens
- PKI/certificate operations (if applicable)

#### 4.4 Group Membership

Update `identity_groups/identity_group_*.yaml`:
```yaml
entraid_human_identities:
  - "Alice Smith"
  - "Bob Johnson"
```

Run terraform apply to sync group membership.

#### 4.5 Deprovisioning Test

- Remove user from EntraID app assignment
- EntraID sends `DELETE /scim/v2/Users/{id}`
- SCIM bridge updates YAML:
  ```yaml
  identity:
    status: "deactivated"
  authentication:
    disabled: true
  policies:
    identity_policies: []
  ```
- PR created for review
- Merge and apply Terraform
- Verify user cannot login

#### 4.6 Gather Feedback

- Document issues encountered
- Collect user experience feedback
- Refine YAML mappings if needed
- Update documentation

**Success Criteria**:
- All pilot users provisioned successfully
- OIDC authentication works
- Group policies applied correctly
- Deprovisioning disables access
- <5% error rate

---

### Phase 5: Production Rollout (Week 7-8)

**Objective**: Enable SCIM for all EntraID users

#### 5.1 Preparation

- Document user migration process
- Create helpdesk runbook
- Set up monitoring alerts for SCIM bridge
- Train support staff

#### 5.2 Gradual Rollout

**Week 7**:
- Assign 25% of users to EntraID enterprise app
- Monitor SCIM events and PR creation
- Review and merge PRs (can batch review if patterns are consistent)
- Address issues promptly

**Week 8**:
- Assign remaining 75% of users
- Continue monitoring
- Ensure all PRs reviewed and merged
- Run terraform apply to sync all entities

#### 5.3 Group Synchronization

Update all relevant group YAML files with EntraID users:
```yaml
# identity_groups/identity_group_developers.yaml
entraid_human_identities:
  - "Alice Smith"
  - "Bob Johnson"
  # ... all developer users from EntraID
```

Consider scripting this if you have many users/groups.

#### 5.4 Validation

After full rollout:
```bash
# Check entity counts
vault list identity/entity/name

# Verify OIDC aliases
vault list identity/entity-alias/id

# Test group membership
vault read identity/group/name/developers

# Validate policies
vault token lookup # as EntraID user
```

#### 5.5 Monitoring

Monitor continuously:
- SCIM bridge logs for errors
- PR creation frequency
- Terraform apply success rate
- User authentication success rate
- Entity/alias counts

---

## Implementation Details and Design Decisions

### Key Design Decisions

#### 1. Email as Primary Identifier
**Decision**: Use email (not UPN) for OIDC alias name

**Rationale:**
- Entra ID SCIM sends both `userName` (UPN) and `emails[0].value` (email)
- OIDC backend returns `email` claim by default
- Email is more portable (UPN can change if domain changes)
- Consistent with existing GitHub auth pattern

#### 2. Multi-Auth Support
**Decision**: Support OIDC + GitHub + PKI for Entra ID users

**Rationale:**
- Follows established pattern from LDAP implementation
- Users can authenticate via Entra ID OIDC (primary) or GitHub (backup/convenience)
- PKI support enables certificate-based auth for service accounts
- Single entity with multiple aliases

**Example YAML with Multi-Auth:**
```yaml
authentication:
  oidc: "alice.smith@company.com"  # Primary
  github: "asmith"                  # Optional backup
  pki: "alice.smith.cert"          # Optional for advanced use
  disabled: false
```

#### 3. File Naming Convention
**Decision**: Use `entraid_human_firstname_lastname.yaml` pattern

**Rationale:**
- Consistent with existing `ldap_human_*.yaml` pattern
- data.tf filters by filename prefix: `startswith(filename, "entraid_human_")`
- Easy to identify provisioning source at a glance
- Enables separate resources per identity type

**Filename Generation:**
```python
# Input: displayName = "Alice Smith"
# Output: entraid_human_alice_smith.yaml

def generate_filename(display_name: str) -> str:
    sanitized = display_name.lower().replace(' ', '_')
    sanitized = re.sub(r'[^a-z0-9_]', '', sanitized)
    return f"entraid_human_{sanitized}.yaml"
```

#### 4. Soft Delete Strategy
**Decision**: Deactivated users marked with `status: deactivated` and `disabled: true`

**Rationale:**
- Preserves audit trail for compliance
- File history retained in Git
- Can be reactivated if user returns
- Prevents accidental data loss

**Soft Delete Implementation:**
```yaml
identity:
  status: "deactivated"
authentication:
  disabled: true
```

#### 5. Group Management Approach
**Decision**: SCIM bridge updates identity_groups YAML files

**Rationale:**
- Provides manual review for group membership changes
- Maintains Git audit trail
- Consistent with GitOps workflow
- Alternative (OIDC group claims) bypasses manual review

### Potential Issues and Mitigations

#### Issue 1: SCIM ID Persistence
**Problem**: SCIM uses UUIDs to identify users, but Terraform uses names. If user name changes, mapping breaks.

**Mitigation:**
- Store SCIM ID in `metadata.entraid_object_id` (immutable)
- Maintain persistent mapping file: `scim-bridge/data/user_mapping.json`
- On UPDATE, lookup existing filename by SCIM ID before regenerating YAML

#### Issue 2: Race Conditions
**Problem**: Multiple SCIM requests arriving simultaneously could create conflicting Git branches/PRs.

**Mitigation:**
- Add timestamp to branch names: `scim-create-alice-smith-20260123143022`
- Use FastAPI background tasks for PR creation (non-blocking)
- Implement request queuing if needed

#### Issue 3: Schema Validation Failures
**Problem**: SCIM bridge generates invalid YAML that fails Terraform validation.

**Mitigation:**
- Validate YAML against schema BEFORE creating PR
- Return SCIM error response if validation fails
- Log validation errors for debugging

#### Issue 4: Group Name Mismatches
**Problem**: Entra ID group names don't match existing Vault group YAML filenames.

**Mitigation:**
- Implement fuzzy matching (e.g., "Developers" matches "identity_group_developers")
- Create new group files if no match found
- Allow manual mapping configuration in SCIM bridge config

#### Issue 5: Entra ID Attribute Mapping Mismatches
**Problem**: Entra ID sends unexpected attribute values (e.g., null title, weird department names).

**Mitigation:**
- Use safe defaults: `title or "employee"`, `department or "general"`
- Sanitize all inputs (remove special characters, lowercase)
- Log warnings for unexpected values

**Configuration Example:**
```python
ATTRIBUTE_MAPPINGS = {
    'role_defaults': {
        None: 'employee',
        '': 'employee'
    },
    'team_defaults': {
        None: 'general',
        '': 'general'
    }
}
```

### Local Development Best Practices

#### Using ngrok for Local Testing
```bash
# 1. Start ngrok tunnel
ngrok http 8080

# 2. Note the public URL
# Output: https://abc123.ngrok.io

# 3. Configure Entra ID provisioning
# Tenant URL: https://abc123.ngrok.io/scim/v2

# 4. Keep laptop powered on during testing
```

**Considerations:**
- ngrok free tier URLs change on restart
- Paid ngrok ($8/month) provides stable subdomain
- Alternative: Cloudflare Tunnel (free, more stable)

#### Mock SCIM Client for Rapid Development
For faster iteration without ngrok, create a mock client:

```python
# mock-entraid-scim-client.py
import requests

SCIM_BRIDGE_URL = "http://localhost:8080/scim/v2"
BEARER_TOKEN = "your-scim-bearer-token"

def create_user(username, email, display_name):
    response = requests.post(
        f"{SCIM_BRIDGE_URL}/Users",
        headers={
            "Authorization": f"Bearer {BEARER_TOKEN}",
            "Content-Type": "application/scim+json"
        },
        json={
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
            "userName": email,
            "name": {"formatted": display_name},
            "emails": [{"primary": True, "value": email}],
            "active": True,
            "groups": [{"display": "Developers"}]
        }
    )
    return response.json()

# Test locally without Entra ID
create_user("alice", "alice@company.com", "Alice Smith")
```

### Testing Group Sync

**Manual Test:**
```bash
# 1. Create test group file
cat > identity_groups/identity_group_test_group.yaml <<EOF
name: Test Group
contact: admin@company.com
human_identities: []
ldap_human_identities: []
entraid_human_identities: []
application_identities: []
sub_groups: []
identity_group_policies:
  - "test-policy"
EOF

# 2. Simulate SCIM user creation with group
curl -X POST http://localhost:8080/scim/v2/Users \
  -H "Authorization: Bearer ${SCIM_BEARER_TOKEN}" \
  -H "Content-Type: application/scim+json" \
  -d '{
    "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
    "userName": "alice.smith@company.com",
    "displayName": "Alice Smith",
    "groups": [{"display": "Test Group"}],
    "active": true,
    "id": "550e8400-e29b-41d4-a716-446655440000"
  }'

# 3. Verify group file updated
cat identity_groups/identity_group_test_group.yaml
# Should show:
#   entraid_human_identities:
#     - "Alice Smith"

# 4. Check PR created
gh pr view --json files

# 5. Merge PR and apply
gh pr merge <PR_NUMBER>
terraform apply -var-file=dev.tfvars

# 6. Verify group membership in Vault
vault read identity/group/name/"Test Group"
```

---

## File Changes Summary

### New Terraform Files

1. **entraid_variables.tf** - Variables for EntraID configuration
   - `enable_entraid_auth` (bool)
   - `entraid_tenant_id` (string)
   - `entraid_client_id` (string, sensitive)
   - `entraid_client_secret` (string, sensitive)

2. **entraid-auth.tf** - OIDC auth backend
   - `vault_jwt_auth_backend.entraid` - OIDC backend on `/oidc` path
   - `vault_jwt_auth_backend_role.entraid_user` - Default role for all EntraID users

3. **entraid_identities.tf** - Identity entities and aliases
   - `vault_identity_entity.entraid_human` - For each EntraID user
   - `vault_identity_entity_alias.entraid_human_oidc` - Links entity to OIDC email
   - `vault_identity_entity_alias.entraid_human_github` - Optional multi-auth
   - `vault_identity_entity_alias.entraid_human_pki` - Optional multi-auth

### Updated Terraform Files

4. **data.tf** (lines ~138+) - Add EntraID identity parsing
   ```hcl
   entraid_human_identities_map = {
     for filename, config in local.configs_by_type.identities :
     config.identity.name => config
     if startswith(filename, "entraid_human_")
   }

   entraid_human_with_oidc = { ... }
   entraid_human_with_github = { ... }
   entraid_human_with_pki = { ... }
   ```

5. **identity_groups.tf** - Add EntraID group membership
   ```hcl
   resource "vault_identity_group_member_entity_ids" "entraid_human_group" {
     for_each = { ... filter for entraid_human_identities ... }
     group_id = vault_identity_group.internal_group[each.key].id
     member_entity_ids = [
       for i in each.value.entraid_human_identities :
       vault_identity_entity.entraid_human[i].id
     ]
   }
   ```

6. **dev.tfvars** - Add EntraID values
   ```hcl
   enable_entraid_auth    = true
   entraid_tenant_id      = "your-tenant-id"
   entraid_client_id      = "your-client-id"
   entraid_client_secret  = "your-client-secret"
   ```

### New YAML Files

7. **identities/schema_entraid_human.yaml** - JSON Schema for EntraID users
   - Required fields: metadata, identity, authentication, policies
   - New fields: `authentication.oidc`, `authentication.disabled`, `identity.status`
   - Metadata: `entraid_object_id`, `entraid_upn`

8. **identities/entraid_human_*.yaml** - Generated by SCIM bridge
   - Naming: `entraid_human_{firstname}_{lastname}.yaml`
   - Example: `entraid_human_alice_smith.yaml`

### Updated Python Script

9. **identities/validate_identities.py** - Extend validation
   - Support `entraid_human_*.yaml` pattern
   - Load `schema_entraid_human.yaml`
   - Validate EntraID-specific fields

### New SCIM Bridge Files

10. **scim-bridge/** - Complete FastAPI application
    - `app/main.py` - FastAPI endpoints
    - `app/services/yaml_generator.py` - YAML generation logic
    - `app/services/git_handler.py` - Git operations
    - `Dockerfile` - Container image
    - `requirements.txt` - Python dependencies

11. **docker-compose.yml** - Add scim-bridge service

---

## Verification Steps

### After Phase 1 (OIDC Auth)

```bash
# Verify OIDC backend created
vault auth list | grep oidc

# Verify test entity
vault read identity/entity/name/"Test User"

# Test OIDC login
vault login -method=oidc role=entraid-user

# Verify token has correct policies
vault token lookup
```

### After Phase 2 (SCIM Bridge)

```bash
# Verify service running
docker ps | grep scim-bridge

# Test health endpoint
curl http://localhost:8080/health

# Simulate SCIM user creation
curl -X POST http://localhost:8080/scim/v2/Users \
  -H "Authorization: Bearer ${SCIM_BEARER_TOKEN}" \
  -H "Content-Type: application/scim+json" \
  -d @test_user.json

# Verify YAML created
ls -la identities/entraid_human_test_*.yaml

# Verify PR created
gh pr list --label scim-provisioning

# Validate YAML against schema
cd identities && python3 validate_identities.py
```

### After Phase 3 (EntraID Config)

```bash
# Monitor SCIM bridge logs
docker logs -f scim-bridge

# Check for incoming SCIM requests
tail -f scim-bridge/data/logs/scim.log

# Verify PRs created for provisioned users
gh pr list --label scim-provisioning --state open

# Review YAML files in PR
gh pr diff <PR_NUMBER>
```

### After Phase 4 (Pilot)

```bash
# Count EntraID entities
vault list identity/entity/name | grep -c ".*"

# Verify OIDC aliases
vault list identity/entity-alias/id | wc -l

# Check group membership
vault read identity/group/name/"EntraID Developers"

# Verify pilot user can login
vault login -method=oidc # as pilot user

# Test deactivated user cannot login
vault login -method=oidc # as deactivated user (should fail)
```

### After Phase 5 (Production)

```bash
# Final entity count
vault read sys/metrics | grep identity_entity_count

# Verify all expected users provisioned
vault list identity/entity/name | wc -l

# Check for any failed SCIM events
grep ERROR scim-bridge/data/logs/scim.log

# Validate all YAML files
cd identities && python3 validate_identities.py --verbose

# Audit group memberships
for group in $(vault list identity/group/name); do
  echo "=== $group ==="
  vault read identity/group/name/$group | grep member_entity_ids
done
```

---

## Rollback Plan

If issues occur during rollout:

1. **Stop SCIM provisioning** in EntraID (pause sync)
2. **Keep OIDC auth enabled** (existing users can still login)
3. **Do NOT merge pending PRs** until issues resolved
4. **Investigate SCIM bridge logs** for errors
5. **Fix issues** in SCIM bridge code or configuration
6. **Resume provisioning** once stable

For complete rollback:
1. Set `enable_entraid_auth = false` in tfvars
2. Run terraform apply (removes OIDC backend)
3. Delete EntraID identity YAML files
4. Run terraform apply (removes entities)
5. Users fall back to GitHub/LDAP/PKI auth

---

## Security Considerations

- **SCIM bearer token**: Rotate every 90 days, store in secure secrets manager
- **GitHub PAT**: Scope to repo access only, rotate regularly
- **TLS required**: Use HTTPS for SCIM bridge in production (ngrok provides TLS for dev)
- **Manual PR review**: Prevents malicious/incorrect provisioning (per user choice)
- **Soft delete**: Preserves audit trail for compliance
- **Entity disabled flag**: Ensures deprovisioned users cannot authenticate even if YAML exists
- **No passwords stored**: OIDC handles authentication, no credentials in YAML
- **Audit logging**: All SCIM operations logged, all Git commits traceable

---

## Success Metrics

- ✅ All EntraID users can login via OIDC
- ✅ Provisioning latency <4 hours (PR review + terraform apply)
- ✅ <5% error rate in SCIM events
- ✅ 100% schema validation pass rate
- ✅ Zero unauthorized access incidents
- ✅ Full audit trail in Git history
- ✅ Deprovisioned users denied access within 24 hours
- ✅ Group memberships accurate and up-to-date

---

## Critical Files Reference

### Terraform (to create/modify)
- [entraid_variables.tf](../entraid_variables.tf)
- [entraid-auth.tf](../entraid-auth.tf)
- [entraid_identities.tf](../entraid_identities.tf)
- [data.tf](../data.tf) - lines ~138+
- [identity_groups.tf](../identity_groups.tf)
- [dev.tfvars](../dev.tfvars)

### YAML/Schemas (to create)
- [identities/schema_entraid_human.yaml](../identities/schema_entraid_human.yaml)
- [identities/entraid_human_*.yaml](../identities/) - generated by SCIM bridge

### Python (to modify)
- [identities/validate_identities.py](../identities/validate_identities.py)

### SCIM Bridge (to create)
- [scim-bridge/app/main.py](../scim-bridge/app/main.py) - FastAPI application with SCIM endpoints
- [scim-bridge/app/services/yaml_generator.py](../scim-bridge/app/services/yaml_generator.py) - SCIM to YAML conversion
- [scim-bridge/app/services/group_handler.py](../scim-bridge/app/services/group_handler.py) - Group YAML management
- [scim-bridge/app/services/git_handler.py](../scim-bridge/app/services/git_handler.py) - Git operations and PR creation
- [scim-bridge/app/services/user_store.py](../scim-bridge/app/services/user_store.py) - SCIM ID to name mapping
- [scim-bridge/app/handlers/auth.py](../scim-bridge/app/handlers/auth.py) - Bearer token authentication
- [scim-bridge/app/models/scim_user.py](../scim-bridge/app/models/scim_user.py) - SCIM user Pydantic models
- [scim-bridge/Dockerfile](../scim-bridge/Dockerfile) - Container image
- [scim-bridge/requirements.txt](../scim-bridge/requirements.txt) - Python dependencies

### Docker (to modify)
- [docker-compose.yml](../docker-compose.yml)

---

## Timeline Summary

| Phase | Duration | Key Milestone |
|-------|----------|---------------|
| Phase 1: OIDC Auth | 1-2 weeks | OIDC login working for test user |
| Phase 2: SCIM Bridge | 2 weeks | Service running, PRs created automatically |
| Phase 3: EntraID Config | 1 week | EntraID sending SCIM events successfully |
| Phase 4: Pilot | 1 week | 5-10 users provisioned and tested |
| Phase 5: Production | 2 weeks | All users migrated, monitoring stable |
| **Total** | **7-8 weeks** | **Full SCIM integration complete** |

---

## Next Steps After Approval

1. Create feature branch: `feature/entraid-scim-integration`
2. Start with Phase 1: OIDC authentication setup
3. Commit changes incrementally with descriptive messages
4. Test thoroughly at each phase before proceeding
5. Document any deviations or learnings in commit messages
6. Create PR for team review before merging to main
