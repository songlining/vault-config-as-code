# Project Requirements: EntraID SCIM Integration for Vault

## Overview

Integrate Microsoft EntraID (Azure AD) user provisioning into the Vault configuration-as-code repository using SCIM protocol. Users will be provisioned via SCIM webhooks → YAML files → Git PRs → Terraform → Vault, and authenticate via OIDC at runtime.

## Architecture

**SCIM Bridge + OIDC Hybrid Architecture:**
- **Provisioning**: SCIM bridge service receives webhooks from EntraID, generates YAML files, creates Git PRs for manual review
- **Authentication**: OIDC backend allows users to login via EntraID (no passwords stored)
- **Deployment**: Docker container running alongside existing Vault/Neo4j services
- **Deprovisioning**: Soft delete (YAML file retained with `disabled: true` flag)
- **Groups**: Internal groups with YAML-managed membership

### Data Flow

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

### Phase 1: OIDC Authentication Backend
- Create EntraID app registration in Azure Portal
- Configure Terraform OIDC backend resources
- Create identity YAML schema for EntraID users
- Update validation scripts
- Test OIDC login flow

### Phase 2: SCIM Bridge Service
- Build FastAPI application with SCIM 2.0 endpoints
- Implement YAML generation from SCIM payloads
- Create Git handler for PR creation
- Implement group synchronization
- Containerize with Docker

### Phase 3: EntraID SCIM Configuration
- Expose SCIM bridge publicly (ngrok for dev)
- Configure EntraID provisioning
- Set up attribute mappings
- Test initial sync

### Phase 4: Pilot Testing
- Test with 5-10 pilot users
- Verify provisioning flow
- Test group memberships
- Validate deprovisioning

### Phase 5: Production Rollout
- Gradual user migration
- Monitor and validate
- Full deployment

## Critical Rules

1. **ALWAYS read these files before starting any work:**
   - `prompt.md` - Project requirements (this file)
   - `progress.txt` - Learnings from previous iterations
   - `AGENTS.md` - Patterns and gotchas

2. **Story completion requirements:**
   - ALL acceptance criteria must be met
   - Code/configuration must work without errors
   - Changes must be tested and verified
   - `prd.json` must be updated with `passes: true`
   - Learnings must be appended to `progress.txt`

3. **Never skip verification:**
   - Test each component after implementation
   - Verify all acceptance criteria
   - Check logs for errors
   - Document any issues encountered

## Key Design Decisions

### Email as Primary Identifier
- Use email (not UPN) for OIDC alias name
- OIDC backend returns `email` claim by default
- More portable if domain changes

### Multi-Auth Support
- Support OIDC + GitHub + PKI for Entra ID users
- Single entity with multiple aliases
- Follows established LDAP pattern

### File Naming Convention
- Use `entraid_human_firstname_lastname.yaml` pattern
- Filter by filename prefix in `data.tf`

### Soft Delete Strategy
- Deactivated users marked with `status: deactivated` and `disabled: true`
- Preserves audit trail for compliance
- Can be reactivated if user returns

### SCIM Attribute Mapping
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

## Useful Commands

### Infrastructure Management
```bash
# Initialize Terraform
terraform init

# Plan changes
terraform plan -var-file=dev.tfvars

# Apply configuration
terraform apply -var-file=dev.tfvars

# Validate configuration
terraform validate

# Format code
terraform fmt
```

### Identity Validation
```bash
# Validate YAML identity configurations
cd identities
python3 validate_identities.py
```

### Docker Services
```bash
# Start all services (Vault, Neo4j, SCIM Bridge)
docker compose up -d

# Start only SCIM bridge
docker compose up -d scim-bridge

# View SCIM bridge logs
docker logs -f scim-bridge

# Test SCIM bridge health
curl http://localhost:8080/health
```

### SCIM Bridge Testing
```bash
# Use mock SCIM client
cd scim-bridge
python mock-entraid-scim-client.py

# Run tests
cd scim-bridge
pytest
```

### EntraID/OIDC Testing
```bash
# Test OIDC login
vault login -method=oidc

# Verify entity created
vault read identity/entity/name/"User Name"

# Check OIDC aliases
vault list identity/entity-alias/id
```

## Important Files

### Terraform Files
- `entraid_variables.tf` - EntraID configuration variables
- `entraid-auth.tf` - OIDC auth backend
- `entraid_identities.tf` - Identity entities and aliases
- `data.tf` - Identity parsing locals
- `identity_groups.tf` - Group membership resources
- `dev.tfvars` - Development configuration

### YAML Files
- `identities/schema_entraid_human.yaml` - EntraID user schema
- `identities/entraid_human_*.yaml` - EntraID user identities

### SCIM Bridge Files
- `scim-bridge/app/main.py` - FastAPI application
- `scim-bridge/app/models/scim_user.py` - SCIM models
- `scim-bridge/app/services/yaml_generator.py` - YAML generation
- `scim-bridge/app/services/git_handler.py` - Git operations
- `scim-bridge/app/services/group_handler.py` - Group sync
- `scim-bridge/app/services/user_store.py` - User mapping
- `scim-bridge/Dockerfile` - Container image
- `docker-compose.yml` - Service orchestration

## Documentation Links

- Original Implementation Plan: `docs/ENTRAID_SCIM_IMPLEMENTATION_PLAN.md`
- SCIM Integration Guide: `docs/SCIM_INTEGRATION_GUIDE.md` (to be created)

## Workflow for Each Iteration

1. **Read Phase** - Read prompt.md, progress.txt, AGENTS.md
2. **Select Phase** - Find first story with passes=false
3. **Implement Phase** - Create code, scripts, configurations
4. **Verify Phase** - Test thoroughly, verify acceptance criteria
5. **Update State Phase** - Update prd.json, progress.txt, AGENTS.md
6. **Git Commit Phase** - Commit with descriptive message
