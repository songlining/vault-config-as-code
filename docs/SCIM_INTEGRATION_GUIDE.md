# SCIM Integration Guide

This guide provides comprehensive instructions for implementing and configuring the Microsoft EntraID SCIM integration with the Vault configuration-as-code repository.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Phase 1: OIDC Authentication Setup](#phase-1-oidc-authentication-setup)
- [Phase 2: SCIM Bridge Implementation](#phase-2-scim-bridge-implementation)
- [Environment Configuration](#environment-configuration)
- [Local Development Setup](#local-development-setup)
- [Testing with Mock Client](#testing-with-mock-client)
- [Production Deployment](#production-deployment)
- [Verification Steps](#verification-steps)
- [Troubleshooting](#troubleshooting)
- [Related Documentation](#related-documentation)

## Overview

The SCIM integration enables automatic provisioning of Microsoft EntraID (Azure AD) users into the Vault configuration-as-code repository. Users are provisioned through a SCIM bridge service that:

1. Receives SCIM requests from EntraID
2. Generates YAML identity files following the repository schema
3. Creates GitHub pull requests for review
4. Updates group memberships automatically
5. Supports user lifecycle management (create, update, deactivate)

### Integration Flow

```
EntraID → SCIM Bridge → YAML Files → GitHub PR → Review → Merge → Terraform → Vault
```

**User Authentication:** Users authenticate via OIDC (OpenID Connect) directly to Vault using their EntraID credentials.

**User Provisioning:** User identity configuration is managed via SCIM protocol with manual approval through GitHub PRs.

## Architecture

### Components

1. **EntraID OIDC Authentication Backend** - Allows users to authenticate to Vault using EntraID credentials
2. **SCIM Bridge Service** - FastAPI microservice that processes SCIM requests and generates configuration files
3. **Identity YAML Files** - EntraID user configurations in `identities/entraid_human_*.yaml`
4. **Group YAML Files** - Group membership configurations in `identity_groups/*.yaml`
5. **GitHub Integration** - Automated PR creation for configuration changes
6. **Terraform Configuration** - Infrastructure-as-code for Vault identity resources

### Data Flow

```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐    ┌─────────────┐
│  EntraID    │───▶│ SCIM Bridge  │───▶│ GitHub PR   │───▶│ Terraform   │
│  (SCIM)     │    │ (FastAPI)    │    │ (Review)    │    │ (Apply)     │
└─────────────┘    └──────────────┘    └─────────────┘    └─────────────┘
                            │                                      │
                            ▼                                      ▼
                   ┌─────────────────┐                    ┌─────────────┐
                   │ YAML Files      │                    │ Vault       │
                   │ (identities/    │                    │ Identity    │
                   │  groups/)       │                    │ Resources   │
                   └─────────────────┘                    └─────────────┘
```

## Prerequisites

### Required Software

- **Terraform** >= 1.10.0
- **Docker** and **Docker Compose**
- **Git** with repository access
- **Python 3.11+** (for local development)
- **Node.js** (for pre-commit hooks)

### Required Access

- **Azure AD/EntraID** administrative access to create applications and configure SCIM
- **GitHub** repository admin access for creating personal access tokens and webhooks
- **Vault Enterprise** license and access to development environment

### Required Knowledge

- HashiCorp Vault administration
- Azure AD application configuration
- SCIM 2.0 protocol basics
- Git workflow and pull request reviews
- Basic Docker containerization

## Phase 1: OIDC Authentication Setup

### Step 1: Create EntraID Application

1. **Navigate to Azure Portal**
   - Go to [Azure Portal](https://portal.azure.com)
   - Navigate to **Microsoft Entra ID** > **App registrations**

2. **Create New Application**
   - Click **"New registration"**
   - Name: `Vault OIDC Authentication`
   - Supported account types: **"Accounts in this organizational directory only"**
   - Redirect URI: **Web** - `https://your-vault-url/ui/vault/auth/oidc/oidc/callback`

3. **Configure Authentication**
   - Go to **Authentication** tab
   - Add additional redirect URI: `https://your-vault-url/v1/auth/oidc/oidc/callback`
   - Enable **"Access tokens"** and **"ID tokens"** under **Implicit grant and hybrid flows**

4. **Create Client Secret**
   - Go to **Certificates & secrets** tab
   - Click **"New client secret"**
   - Description: `Vault OIDC Secret`
   - Expires: Choose appropriate duration
   - **Copy the secret value immediately** (you won't be able to see it again)

5. **Note Required Values**
   - **Tenant ID**: Found in **Overview** tab (`Directory (tenant) ID`)
   - **Client ID**: Found in **Overview** tab (`Application (client) ID`)
   - **Client Secret**: Created in previous step

### Step 2: Configure Terraform Variables

1. **Update `dev.tfvars`**:
   ```hcl
   # EntraID OIDC Authentication
   enable_entraid_auth     = true
   entraid_tenant_id      = "12345678-1234-1234-1234-123456789abc"  # Replace with your tenant ID
   entraid_client_id      = "87654321-4321-4321-4321-cba987654321"  # Replace with your client ID
   entraid_client_secret  = "your-client-secret-here"               # Replace with your client secret
   ```

2. **Validate Configuration**:
   ```bash
   terraform validate
   terraform plan -var-file=dev.tfvars
   ```

### Step 3: Deploy OIDC Configuration

1. **Apply Terraform**:
   ```bash
   terraform apply -var-file=dev.tfvars
   ```

2. **Verify OIDC Backend**:
   ```bash
   vault auth list
   # Should show 'oidc/' in the list
   ```

3. **Test OIDC Authentication**:
   - Navigate to Vault UI: `https://your-vault-url/ui/`
   - Select **OIDC** authentication method
   - Sign in with EntraID credentials

### Step 4: Create Test Identity

1. **Create Example User File**:
   ```bash
   cp identities/entraid_human_example.yaml identities/entraid_human_testuser.yaml
   ```

2. **Edit User Configuration**:
   ```yaml
   # Edit identities/entraid_human_testuser.yaml
   identity:
     name: "Test User"
     email: "testuser@yourdomain.com"
     role: "developer"
     team: "platform"
     status: "active"
   
   authentication:
     oidc: "testuser@yourdomain.com"  # Must match EntraID UPN
     disabled: false
   ```

3. **Validate and Apply**:
   ```bash
   cd identities
   python3 validate_identities.py
   cd ..
   terraform plan -var-file=dev.tfvars
   terraform apply -var-file=dev.tfvars
   ```

## Phase 2: SCIM Bridge Implementation

### Step 1: Configure Environment Variables

1. **Create SCIM Bridge Environment File**:
   ```bash
   cp scim-bridge/.env.example scim-bridge/.env
   ```

2. **Edit Environment Configuration**:
   ```bash
   # scim-bridge/.env
   SCIM_BEARER_TOKEN=your-secure-bearer-token-here
   GIT_REPO_URL=https://github.com/your-org/vault-config-as-code.git
   GITHUB_TOKEN=your-github-token-here
   LOG_LEVEL=INFO
   REPO_CLONE_DIR=/data/repo
   USER_MAPPING_FILE=/data/user_mapping.json
   ```

3. **Generate Secure Bearer Token**:
   ```bash
   # Generate a strong random token
   openssl rand -base64 32
   ```

4. **Create GitHub Personal Access Token**:
   - Go to GitHub Settings > Developer settings > Personal access tokens > Tokens (classic)
   - Generate new token with these permissions:
     - `repo` (full repository access)
     - `workflow` (if using GitHub Actions)
   - Copy the token value

### Step 2: Build and Start SCIM Bridge

1. **Build Docker Image**:
   ```bash
   docker compose build scim-bridge
   ```

2. **Start Services**:
   ```bash
   docker compose up -d vault scim-bridge
   ```

3. **Verify Service Health**:
   ```bash
   curl http://localhost:8080/health
   # Should return: {"status": "healthy"}
   ```

4. **Check Service Logs**:
   ```bash
   docker logs -f scim-bridge
   ```

### Step 3: Configure EntraID SCIM Provisioning

1. **Navigate to EntraID Application**
   - Azure Portal > Microsoft Entra ID > Enterprise applications
   - Find your Vault application or create new one for SCIM

2. **Enable Provisioning**
   - Go to **Provisioning** tab
   - Set **Provisioning Mode** to **Automatic**

3. **Configure SCIM Endpoint**
   - **Tenant URL**: `https://your-scim-bridge-url/scim/v2`
   - **Secret Token**: Your SCIM_BEARER_TOKEN value
   - Click **Test Connection** to verify

4. **Configure Attribute Mappings**
   - Map EntraID attributes to SCIM attributes:
     - `userPrincipalName` → `userName`
     - `displayName` → `displayName`
     - `mail` → `emails[type eq "work"].value`
     - `jobTitle` → `title`
     - `department` → `department`
     - `accountEnabled` → `active`

5. **Set Provisioning Scope**
   - Choose **Sync only assigned users and groups**
   - Assign test users/groups to the application

6. **Start Provisioning**
   - Click **Start provisioning**
   - Monitor provisioning logs for any errors

## Environment Configuration

### Local Development Environment Variables

```bash
# SCIM Bridge Configuration
export SCIM_BRIDGE_URL="http://localhost:8080"
export BEARER_TOKEN="test-bearer-token-change-me"

# Vault Configuration  
export VAULT_ADDR="http://localhost:8200"
export VAULT_TOKEN="dev-root-token"

# Git Configuration
export GIT_REPO_URL="https://github.com/your-org/vault-config-as-code.git"
export GITHUB_TOKEN="ghp_your-token-here"
```

### Production Environment Variables

```bash
# SCIM Bridge Configuration
export SCIM_BEARER_TOKEN="$(openssl rand -base64 32)"
export GIT_REPO_URL="https://github.com/your-org/vault-config-as-code.git"
export GITHUB_TOKEN="ghp_production-token-here"
export LOG_LEVEL="INFO"

# Network Configuration
export SCIM_BRIDGE_PORT="8080"
export VAULT_ADDR="https://vault.your-domain.com"

# Persistence Configuration
export REPO_CLONE_DIR="/data/repo"
export USER_MAPPING_FILE="/data/user_mapping.json"
```

## Local Development Setup

### Using ngrok for Testing

ngrok allows you to expose your local SCIM Bridge to the internet for testing with EntraID.

1. **Install ngrok**:
   ```bash
   # Download from https://ngrok.com/download
   # Or install via package manager
   brew install ngrok  # macOS
   sudo snap install ngrok  # Linux
   ```

2. **Start SCIM Bridge Locally**:
   ```bash
   docker compose up -d scim-bridge
   ```

3. **Expose with ngrok**:
   ```bash
   ngrok http 8080
   ```

4. **Note the ngrok URL**:
   ```
   Forwarding  https://abc123.ngrok.io -> http://localhost:8080
   ```

5. **Configure EntraID SCIM**:
   - Use ngrok URL as SCIM endpoint: `https://abc123.ngrok.io/scim/v2`
   - Keep ngrok running during testing

6. **Monitor Requests**:
   ```bash
   # Terminal 1: SCIM Bridge logs
   docker logs -f scim-bridge
   
   # Terminal 2: ngrok request inspector
   # Visit http://localhost:4040 in browser
   ```

### Local Testing Workflow

1. **Start Development Environment**:
   ```bash
   docker compose up -d vault scim-bridge
   ```

2. **Run Mock Client Tests**:
   ```bash
   cd scim-bridge
   python3 mock-entraid-scim-client.py
   ```

3. **Verify Generated Files**:
   ```bash
   # Check for new identity files
   ls -la identities/entraid_human_*
   
   # Check for group membership changes
   ls -la identity_groups/
   ```

4. **Review Pull Requests**:
   - Check GitHub repository for new PRs
   - Review YAML file changes
   - Merge PRs to trigger Terraform application

5. **Test Terraform Application**:
   ```bash
   terraform plan -var-file=dev.tfvars
   terraform apply -var-file=dev.tfvars
   ```

## Testing with Mock Client

The included mock SCIM client simulates EntraID requests for comprehensive testing.

### Basic Usage

```bash
cd scim-bridge
python3 mock-entraid-scim-client.py
```

### Custom Configuration

```bash
export SCIM_BRIDGE_URL="http://localhost:8080"
export BEARER_TOKEN="test-token-123" 
python3 mock-entraid-scim-client.py
```

### Test Scenarios

The mock client executes four test scenarios:

1. **User Creation**
   - Creates new user with complete SCIM payload
   - Tests group membership assignment
   - Verifies PR creation and YAML generation

2. **Group Membership Updates**
   - Adds user to new groups
   - Removes user from existing groups
   - Tests PATCH operation handling

3. **User Reconciliation**
   - Lists all users in the system
   - Verifies user data persistence
   - Tests GET endpoint functionality

4. **User Deactivation**
   - Soft-deletes user via DELETE operation
   - Tests status change to inactive
   - Verifies deactivation PR creation

### Expected Output

```
🚀 Mock EntraID SCIM Client
==================================================
📡 SCIM Bridge URL: http://localhost:8080
🔐 Bearer Token: test-bea********

🏥 Testing health endpoint...
✅ SCIM Bridge is healthy!

==================================================
🧪 Starting SCIM Test Scenarios
==================================================

📋 Test 1: Create New User
------------------------------
🔄 Creating user: Alice Johnson
📧 Email: alice.johnson@contoso.com
🏢 Role: Senior Software Engineer
👥 Team: Platform Engineering
📋 Groups: Developers, Senior Engineers, Platform Team
📤 POST http://localhost:8080/scim/v2/Users
📊 Status: 201
✅ User created successfully!
🆔 SCIM ID: 12345678-1234-1234-1234-123456789abc
📁 YAML File: entraid_human_alice_johnson.yaml
🔗 PR URL: https://github.com/your-org/vault-config-as-code/pull/42
```

## Production Deployment

### Container Deployment

1. **Build Production Image**:
   ```bash
   docker build -t scim-bridge:latest scim-bridge/
   ```

2. **Deploy with Docker Compose**:
   ```bash
   # Production docker-compose.yml
   version: '3.8'
   services:
     scim-bridge:
       image: scim-bridge:latest
       ports:
         - "8080:8000"
       environment:
         - SCIM_BEARER_TOKEN=${SCIM_BEARER_TOKEN}
         - GIT_REPO_URL=${GIT_REPO_URL}
         - GITHUB_TOKEN=${GITHUB_TOKEN}
         - LOG_LEVEL=INFO
       volumes:
         - scim-data:/data
       restart: unless-stopped
       healthcheck:
         test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
         interval: 30s
         timeout: 10s
         retries: 3
   ```

3. **Deploy with Kubernetes** (example):
   ```yaml
   apiVersion: apps/v1
   kind: Deployment
   metadata:
     name: scim-bridge
   spec:
     replicas: 2
     selector:
       matchLabels:
         app: scim-bridge
     template:
       metadata:
         labels:
           app: scim-bridge
       spec:
         containers:
         - name: scim-bridge
           image: scim-bridge:latest
           ports:
           - containerPort: 8000
           env:
           - name: SCIM_BEARER_TOKEN
             valueFrom:
               secretKeyRef:
                 name: scim-secrets
                 key: bearer-token
           - name: GITHUB_TOKEN
             valueFrom:
               secretKeyRef:
                 name: scim-secrets
                 key: github-token
           volumeMounts:
           - name: data
             mountPath: /data
   ```

### Security Considerations

1. **Bearer Token Management**:
   - Use strong, randomly generated tokens
   - Rotate tokens regularly
   - Store in secure secret management system
   - Never commit tokens to version control

2. **GitHub Token Permissions**:
   - Use minimal required permissions
   - Consider using GitHub App instead of personal token
   - Rotate tokens according to security policy
   - Monitor token usage in audit logs

3. **Network Security**:
   - Use HTTPS/TLS for all communications
   - Implement firewall rules to restrict access
   - Consider VPN or private network for SCIM endpoint
   - Enable request logging for audit purposes

4. **Container Security**:
   - Use non-root user in containers
   - Scan images for vulnerabilities
   - Keep base images updated
   - Implement resource limits

## Verification Steps

### Phase 1 Verification (OIDC Authentication)

1. **Verify Terraform Resources**:
   ```bash
   # Check authentication backends
   vault auth list | grep oidc
   
   # Check identity entities
   vault list identity/entity/name
   
   # Check identity groups
   vault list identity/group/name
   ```

2. **Test OIDC Authentication**:
   ```bash
   # Via Vault UI
   # 1. Navigate to https://your-vault-url/ui/
   # 2. Select OIDC method
   # 3. Authenticate with EntraID
   
   # Via CLI (if configured)
   vault auth -method=oidc
   ```

3. **Verify User Permissions**:
   ```bash
   # Login as test user and verify access
   export VAULT_TOKEN="user-token-here"
   vault auth -method=token
   vault kv list secret/  # Should work based on policies
   ```

### Phase 2 Verification (SCIM Bridge)

1. **Health Check**:
   ```bash
   curl http://localhost:8080/health
   # Expected: {"status": "healthy"}
   ```

2. **SCIM Endpoint Testing**:
   ```bash
   # Test authentication
   curl -H "Authorization: Bearer $BEARER_TOKEN" \
        http://localhost:8080/scim/v2/Users
   
   # Should return user list or empty result
   ```

3. **End-to-End Workflow**:
   ```bash
   # 1. Run mock client
   python3 scim-bridge/mock-entraid-scim-client.py
   
   # 2. Check for GitHub PRs
   # Visit your repository and look for new PRs
   
   # 3. Merge PR and apply Terraform
   git pull origin main
   terraform apply -var-file=dev.tfvars
   
   # 4. Verify user exists in Vault
   vault list identity/entity/name
   ```

### Complete Integration Verification

1. **User Provisioning Flow**:
   - EntraID user assigned to application
   - SCIM request creates GitHub PR
   - PR merged triggers Terraform
   - User can authenticate via OIDC

2. **Group Management Flow**:
   - User added to EntraID group
   - SCIM updates group membership
   - Group changes reflected in Vault policies

3. **Deactivation Flow**:
   - User removed from EntraID application
   - SCIM deactivates user
   - User authentication disabled in Vault

## Troubleshooting

### Common Issues

#### OIDC Authentication Issues

**Problem**: User cannot authenticate via OIDC
```
Error: OIDC authentication failed
```

**Solutions**:
1. Check EntraID application configuration:
   ```bash
   # Verify redirect URIs include both:
   # https://your-vault-url/ui/vault/auth/oidc/oidc/callback
   # https://your-vault-url/v1/auth/oidc/oidc/callback
   ```

2. Verify Terraform configuration:
   ```bash
   terraform plan -var-file=dev.tfvars
   # Check for any configuration drift
   ```

3. Check Vault logs:
   ```bash
   docker logs vault
   # Look for OIDC-related errors
   ```

**Problem**: "Invalid issuer" error
```
Error: token verification failed: invalid issuer
```

**Solution**: Check issuer configuration in `entraid-auth.tf`:
```hcl
bound_issuer = "https://sts.windows.net/${var.entraid_tenant_id}/"
```

#### SCIM Bridge Issues

**Problem**: SCIM Bridge returns 401 Unauthorized
```
Status: 401 - Invalid bearer token
```

**Solutions**:
1. Check bearer token configuration:
   ```bash
   # Verify token in .env file matches EntraID configuration
   grep SCIM_BEARER_TOKEN scim-bridge/.env
   ```

2. Check container environment:
   ```bash
   docker exec scim-bridge env | grep SCIM_BEARER_TOKEN
   ```

**Problem**: PR not created
```
✅ User created successfully!
🔗 PR URL: Error creating PR
```

**Solutions**:
1. Check GitHub token permissions:
   ```bash
   curl -H "Authorization: token $GITHUB_TOKEN" \
        https://api.github.com/user
   # Should return your GitHub user info
   ```

2. Verify repository access:
   ```bash
   curl -H "Authorization: token $GITHUB_TOKEN" \
        https://api.github.com/repos/your-org/vault-config-as-code
   ```

3. Check container logs:
   ```bash
   docker logs scim-bridge | grep -i error
   ```

**Problem**: YAML validation fails
```
❌ Failed to create user: 400
🔍 Response: {"error": "Schema validation failed"}
```

**Solutions**:
1. Check schema file exists:
   ```bash
   ls -la identities/schema_entraid_human.yaml
   ```

2. Validate example file:
   ```bash
   cd identities
   python3 validate_identities.py
   ```

3. Check generated YAML format:
   ```bash
   # Look at container logs for generated YAML
   docker logs scim-bridge | grep -A 20 "Generated YAML"
   ```

#### Git Operations Issues

**Problem**: Git clone/pull fails
```
💥 Request failed: Git operation failed: authentication failed
```

**Solutions**:
1. Check GitHub token in URL format:
   ```bash
   # Ensure token is properly formatted in Git URL
   echo $GIT_REPO_URL
   # Should be: https://token@github.com/owner/repo.git
   ```

2. Test Git access manually:
   ```bash
   git clone https://$GITHUB_TOKEN@github.com/your-org/vault-config-as-code.git /tmp/test
   ```

3. Check container Git configuration:
   ```bash
   docker exec scim-bridge git config --list
   ```

### Debug Commands

#### SCIM Bridge Debugging

```bash
# View detailed container logs
docker logs -f scim-bridge

# Exec into container for debugging
docker exec -it scim-bridge /bin/bash

# Check file system state
docker exec scim-bridge ls -la /data/repo/identities/

# Test health endpoint
curl -v http://localhost:8080/health

# Test SCIM endpoints with verbose output
curl -v -H "Authorization: Bearer $BEARER_TOKEN" \
     -H "Content-Type: application/scim+json" \
     http://localhost:8080/scim/v2/Users
```

#### Vault Debugging

```bash
# Check auth backends
vault auth list

# Check identity entities
vault list identity/entity/name

# Check OIDC backend configuration
vault read auth/oidc/config

# Check OIDC role configuration
vault read auth/oidc/role/entraid_user

# Test token creation
vault write auth/oidc/login role=entraid_user
```

#### GitHub API Debugging

```bash
# Test GitHub API access
curl -H "Authorization: token $GITHUB_TOKEN" \
     https://api.github.com/user

# Check repository permissions
curl -H "Authorization: token $GITHUB_TOKEN" \
     https://api.github.com/repos/your-org/vault-config-as-code

# List recent pull requests
curl -H "Authorization: token $GITHUB_TOKEN" \
     "https://api.github.com/repos/your-org/vault-config-as-code/pulls?state=all&sort=created&direction=desc"
```

### Performance Troubleshooting

#### SCIM Bridge Performance

**Monitor container resources**:
```bash
docker stats scim-bridge
```

**Check processing times**:
```bash
# Look for slow operations in logs
docker logs scim-bridge | grep -i "processing time"
```

**Monitor Git operations**:
```bash
# Git operations can be slow for large repositories
docker logs scim-bridge | grep -i "git\|clone\|pull"
```

#### Terraform Performance

**Check state file size**:
```bash
ls -lh terraform.tfstate
```

**Monitor plan/apply times**:
```bash
time terraform plan -var-file=dev.tfvars
time terraform apply -var-file=dev.tfvars
```

### Logging and Monitoring

#### Log Levels

Set appropriate log levels for different environments:

```bash
# Development
LOG_LEVEL=DEBUG

# Production  
LOG_LEVEL=INFO

# Troubleshooting
LOG_LEVEL=DEBUG
```

#### Key Log Messages

**Successful Operations**:
- `User created successfully: {user_id}`
- `PR created: {pr_url}`
- `Group membership updated for user: {user_id}`

**Error Conditions**:
- `Authentication failed: Invalid bearer token`
- `Git operation failed: {error_details}`
- `Schema validation failed: {validation_errors}`
- `GitHub API error: {api_error}`

#### Monitoring Endpoints

```bash
# Health check (no auth required)
GET /health

# SCIM endpoints (require bearer token)
GET /scim/v2/Users
POST /scim/v2/Users
PATCH /scim/v2/Users/{id}
DELETE /scim/v2/Users/{id}
```

## Related Documentation

### Project Documentation

- **[README.md](../README.md)** - Project overview and getting started guide
- **[CLAUDE.md](../CLAUDE.md)** - Development guidance and project architecture
- **[ENTRAID_SCIM_IMPLEMENTATION_PLAN.md](ENTRAID_SCIM_IMPLEMENTATION_PLAN.md)** - Detailed implementation plan and requirements
- **[LDAP_IMPLEMENTATION_PLAN.md](LDAP_IMPLEMENTATION_PLAN.md)** - LDAP integration documentation for comparison

### Configuration Files

- **`entraid_variables.tf`** - Terraform variables for EntraID configuration
- **`entraid-auth.tf`** - OIDC authentication backend configuration
- **`entraid_identities.tf`** - Identity entity and alias resources
- **`identities/schema_entraid_human.yaml`** - JSON schema for EntraID identity files
- **`identities/entraid_human_example.yaml`** - Example identity configuration

### SCIM Bridge Files

- **`scim-bridge/app/main.py`** - FastAPI application with SCIM endpoints
- **`scim-bridge/app/config.py`** - Environment configuration management
- **`scim-bridge/requirements.txt`** - Python dependencies
- **`scim-bridge/.env.example`** - Environment variable template
- **`scim-bridge/mock-entraid-scim-client.py`** - Mock client for testing

### External Documentation

- **[SCIM 2.0 Specification](https://tools.ietf.org/html/rfc7644)** - Official SCIM protocol specification
- **[Azure AD SCIM Reference](https://docs.microsoft.com/en-us/azure/active-directory/app-provisioning/use-scim-to-provision-users-and-groups)** - Microsoft EntraID SCIM documentation
- **[Vault Identity Secrets Engine](https://www.vaultproject.io/docs/secrets/identity)** - HashiCorp Vault identity management
- **[FastAPI Documentation](https://fastapi.tiangolo.com/)** - FastAPI web framework documentation
- **[Pydantic Documentation](https://pydantic-docs.helpmanual.io/)** - Data validation library documentation

### Community Resources

- **[Vault Community Forum](https://discuss.hashicorp.com/c/vault)** - HashiCorp Vault community discussions
- **[Azure AD Developer Community](https://techcommunity.microsoft.com/t5/azure-active-directory/bd-p/Azure-Active-Directory)** - Microsoft Azure AD community
- **[SCIM Specification Working Group](https://tools.ietf.org/wg/scim/)** - IETF SCIM working group

---

## Summary

This guide provides comprehensive instructions for implementing EntraID SCIM integration with Vault configuration-as-code. The integration enables:

- **Automated user provisioning** from EntraID to Vault via SCIM protocol
- **OIDC authentication** for seamless user experience  
- **GitOps workflow** with manual approval via GitHub pull requests
- **Group membership management** with automatic synchronization
- **User lifecycle management** including creation, updates, and deactivation

The two-phase implementation approach ensures a stable foundation with OIDC authentication before adding SCIM provisioning capabilities.

For questions or issues not covered in this guide, please refer to the [troubleshooting section](#troubleshooting) or consult the [related documentation](#related-documentation).