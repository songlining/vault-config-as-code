# EntraID End-to-End Testing Runbook

This runbook provides step-by-step instructions for testing the SCIM integration with a real Microsoft EntraID (Azure AD) tenant. It covers the complete user lifecycle: onboarding, group membership changes, and offboarding.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Environment Setup](#environment-setup)
- [Part 1: Start Local Services](#part-1-start-local-services)
- [Part 2: Configure ngrok Tunnel](#part-2-configure-ngrok-tunnel)
- [Part 3: Configure EntraID Enterprise Application](#part-3-configure-entraid-enterprise-application)
- [Part 4: Test User Onboarding](#part-4-test-user-onboarding)
- [Part 5: Test Group Membership Changes](#part-5-test-group-membership-changes)
- [Part 6: Test User Offboarding](#part-6-test-user-offboarding)
- [Part 7: Terraform Apply and Vault Verification](#part-7-terraform-apply-and-vault-verification)
- [Troubleshooting](#troubleshooting)
- [Cleanup](#cleanup)

---

## Prerequisites

### Required Access

- [ ] Azure tenant with EntraID administrative access
- [ ] GitHub repository with push access and PR creation permissions
- [ ] GitHub Personal Access Token with `repo` scope
- [ ] Local machine with Docker and Docker Compose installed
- [ ] ngrok account and CLI installed ([ngrok.com](https://ngrok.com))
- [ ] HashiCorp Vault Enterprise license (for local dev environment)

### Required Software

```bash
# Verify installations
docker --version          # Docker 20.x+
docker compose version    # Docker Compose v2+
ngrok version            # ngrok 3.x+
terraform version        # Terraform 1.10+
vault version            # Vault 1.15+ (for CLI testing)
gh --version             # GitHub CLI (optional but helpful)
```

### Environment Variables Setup

Create a `.env` file in the project root (this file is gitignored):

```bash
# .env file - DO NOT COMMIT
export SCIM_BEARER_TOKEN="$(openssl rand -base64 32)"
export GITHUB_TOKEN="ghp_your_github_token_here"
export GIT_REPO_URL="https://github.com/YOUR_ORG/vault-config-as-code.git"

# EntraID OIDC (for Vault authentication testing)
export ENTRAID_TENANT_ID="your-tenant-id-here"
export ENTRAID_CLIENT_ID="your-client-id-here"
export ENTRAID_CLIENT_SECRET="your-client-secret-here"

# Vault
export VAULT_ADDR="http://localhost:8200"
export VAULT_TOKEN="dev-root-token"
```

Load the environment:
```bash
source .env
echo "SCIM Bearer Token (save this for EntraID): $SCIM_BEARER_TOKEN"
```

---

## Environment Setup

### Step 1: Verify Repository State

```bash
# Ensure you're on the correct branch
git status
git pull origin main

# Verify the SCIM Bridge code exists
ls -la scim-bridge/
ls -la scim-bridge/app/main.py
```

### Step 2: Create scim-bridge/.env File

```bash
cat > scim-bridge/.env << EOF
SCIM_BEARER_TOKEN=${SCIM_BEARER_TOKEN}
GIT_REPO_URL=${GIT_REPO_URL}
GITHUB_TOKEN=${GITHUB_TOKEN}
LOG_LEVEL=DEBUG
REPO_CLONE_DIR=/data/repo
USER_MAPPING_FILE=/data/user_mapping.json
EOF

# Verify (token should be masked)
head -1 scim-bridge/.env
```

---

## Part 1: Start Local Services

### Step 1: Build and Start SCIM Bridge

```bash
# Build the SCIM Bridge Docker image
docker compose build scim-bridge

# Start Vault and SCIM Bridge
docker compose up -d vault scim-bridge

# Wait for services to be healthy
echo "Waiting for services to start..."
sleep 10

# Check service status
docker compose ps
```

### Step 2: Verify SCIM Bridge Health

```bash
# Test health endpoint
curl -s http://localhost:8080/health | jq .

# Expected output:
# {
#   "status": "healthy",
#   "timestamp": "2024-...",
#   "services": {
#     "yaml_generator": true,
#     "git_handler": true,
#     "group_handler": true,
#     "user_store": true
#   },
#   "version": "1.0.0"
# }
```

### Step 3: Test SCIM Authentication

```bash
# Test with valid token
curl -s -H "Authorization: Bearer $SCIM_BEARER_TOKEN" \
     http://localhost:8080/scim/v2/Users | jq .

# Should return empty list or existing users

# Test with invalid token (should return 401)
curl -s -H "Authorization: Bearer invalid-token" \
     http://localhost:8080/scim/v2/Users
```

---

## Part 2: Configure ngrok Tunnel

### Step 1: Start ngrok Tunnel

```bash
# Start ngrok pointing to SCIM Bridge port
ngrok http 8080

# Keep this terminal open - ngrok must stay running
```

### Step 2: Note the ngrok URL

ngrok will display output like:
```
Forwarding    https://abc123def456.ngrok-free.app -> http://localhost:8080
```

**Save this URL** - you'll need it for EntraID configuration:
```bash
# In a new terminal, set the ngrok URL
export NGROK_URL="https://abc123def456.ngrok-free.app"  # Replace with your URL
echo "SCIM Endpoint: ${NGROK_URL}/scim/v2"
```

### Step 3: Verify ngrok Tunnel

```bash
# Test health through ngrok
curl -s ${NGROK_URL}/health | jq .

# Test SCIM endpoint through ngrok
curl -s -H "Authorization: Bearer $SCIM_BEARER_TOKEN" \
     ${NGROK_URL}/scim/v2/Users | jq .
```

### Step 4: Open ngrok Inspector

Open http://localhost:4040 in your browser to monitor incoming requests from EntraID.

---

## Part 3: Configure EntraID Enterprise Application

### Step 1: Create Enterprise Application

1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to **Microsoft Entra ID** > **Enterprise applications**
3. Click **+ New application**
4. Click **+ Create your own application**
5. Name: `Vault SCIM Provisioning (Test)`
6. Select: **Integrate any other application you don't find in the gallery (Non-gallery)**
7. Click **Create**

### Step 2: Configure Provisioning

1. In your new application, go to **Provisioning** (left sidebar)
2. Click **Get started**
3. Set **Provisioning Mode** to **Automatic**
4. Under **Admin Credentials**:
   - **Tenant URL**: `https://YOUR_NGROK_URL/scim/v2` (e.g., `https://abc123.ngrok-free.app/scim/v2`)
   - **Secret Token**: Paste your `$SCIM_BEARER_TOKEN` value
5. Click **Test Connection**
   - Should show: "The supplied credentials are authorized to enable provisioning"
6. Click **Save**

### Step 3: Configure Attribute Mappings

1. Expand **Mappings**
2. Click **Provision Azure Active Directory Users**
3. Verify/configure these mappings:

| Azure AD Attribute | SCIM Attribute | Notes |
|-------------------|----------------|-------|
| `userPrincipalName` | `userName` | Required - used for OIDC |
| `displayName` | `displayName` | Required - user's full name |
| `mail` | `emails[type eq "work"].value` | Primary email |
| `jobTitle` | `title` | Maps to role in Vault |
| `department` | `urn:ietf:params:scim:schemas:extension:enterprise:2.0:User:department` | Maps to team in Vault |
| `Switch([IsSoftDeleted], , "False", "True", "True", "False")` | `active` | Required for deactivation |
| `objectId` | `externalId` | EntraID object ID |

4. Click **Save**

### Step 4: Configure Provisioning Scope

1. Under **Settings**:
   - **Scope**: Select **Sync only assigned users and groups**
   - **Provisioning Status**: Keep as **Off** for now
2. Click **Save**

### Step 5: Create Test User in EntraID

1. Go to **Microsoft Entra ID** > **Users** > **+ New user** > **Create new user**
2. Fill in details:
   - **User principal name**: `scimtest@yourdomain.com`
   - **Display name**: `SCIM Test User`
   - **First name**: `SCIM`
   - **Last name**: `Test User`
   - **Job title**: `Software Engineer`
   - **Department**: `Platform Engineering`
3. Click **Create**

### Step 6: Assign Test User to Application

1. Go back to your Enterprise Application
2. Navigate to **Users and groups** (left sidebar)
3. Click **+ Add user/group**
4. Select your test user (`SCIM Test User`)
5. Click **Assign**

---

## Part 4: Test User Onboarding

### Step 1: Start Provisioning

1. In your Enterprise Application, go to **Provisioning**
2. Click **Start provisioning**
3. Wait 1-2 minutes for initial sync (or click **Provision on demand** for immediate test)

### Step 2: Monitor SCIM Bridge Logs

```bash
# In a terminal, watch SCIM Bridge logs
docker logs -f scim-bridge

# Look for:
# - POST /scim/v2/Users requests
# - "User created successfully" messages
# - PR URLs
```

### Step 3: Monitor ngrok Inspector

Open http://localhost:4040 and look for:
- `POST /scim/v2/Users` requests from EntraID
- Response status `201 Created`
- Response body with `urn:vault:scim:extension` containing PR URL

### Step 4: Verify GitHub PR

```bash
# List recent PRs (using GitHub CLI)
gh pr list --repo YOUR_ORG/vault-config-as-code --label scim-provisioning

# Or check the PR URL from the SCIM Bridge logs
```

### Step 5: Review PR Content

The PR should contain:
- New file: `identities/entraid_human_scim_test_user.yaml`
- Content matching this structure:

```yaml
$schema: ./schema_entraid_human.yaml
metadata:
  version: "1.0"
  created_date: "2024-..."
  description: "EntraID human identity provisioned via SCIM"
  entraid_object_id: "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
  entraid_upn: "scimtest@yourdomain.com"
  provisioned_via_scim: true
identity:
  name: "SCIM Test User"
  email: "scimtest@yourdomain.com"
  role: "software_engineer"
  team: "platform_engineering"
  status: "active"
authentication:
  oidc: "scimtest@yourdomain.com"
  disabled: false
policies:
  identity_policies: []
```

### Step 6: Verification Checklist

- [ ] SCIM Bridge received POST request (check logs)
- [ ] GitHub PR was created
- [ ] YAML file has correct structure
- [ ] `entraid_object_id` matches EntraID objectId
- [ ] `provisioned_via_scim: true` is set
- [ ] `status: active` and `disabled: false`
- [ ] Role and team are sanitized (lowercase, underscores)

---

## Part 5: Test Group Membership Changes

### Step 1: Create Test Group in EntraID

1. Go to **Microsoft Entra ID** > **Groups** > **+ New group**
2. Create group:
   - **Group type**: Security
   - **Group name**: `Vault-Developers`
   - **Group description**: `Test group for SCIM provisioning`
3. Click **Create**

### Step 2: Add User to Group

1. Open the new group
2. Click **Members** > **+ Add members**
3. Select `SCIM Test User`
4. Click **Select**

### Step 3: Trigger Provisioning Sync

1. Go to Enterprise Application > **Provisioning**
2. Click **Provision on demand** (or wait for automatic sync)
3. Select the test user and click **Provision**

### Step 4: Monitor for Group Update

```bash
# Watch SCIM Bridge logs
docker logs -f scim-bridge

# Look for:
# - PATCH /scim/v2/Users/{id} requests
# - Group membership changes
# - Group PR creation
```

### Step 5: Verify Group PR

The PR should update `identity_groups/identity_group_vault_developers.yaml`:

```yaml
name: vault_developers
contact: admin@example.com
type: internal
human_identities: []
application_identities: []
entraid_human_identities:
  - scim_test_user
child_groups: []
policies:
  group_policies: []
```

### Step 6: Verification Checklist

- [ ] SCIM Bridge received PATCH request with groups
- [ ] Group file created or updated
- [ ] User added to `entraid_human_identities` array
- [ ] GitHub PR created for group changes

---

## Part 6: Test User Offboarding

### Step 1: Remove User from Application

1. Go to Enterprise Application > **Users and groups**
2. Select your test user
3. Click **Remove**
4. Confirm removal

### Step 2: Monitor for Deactivation

```bash
# Watch SCIM Bridge logs
docker logs -f scim-bridge

# Look for:
# - DELETE /scim/v2/Users/{id} requests
# - User deactivation messages
# - Deactivation PR creation
```

### Step 3: Verify Deactivation PR

The PR should update `identities/entraid_human_scim_test_user.yaml`:

```yaml
# Key changes:
identity:
  status: "deactivated"   # Changed from "active"
authentication:
  disabled: true          # Changed from false
```

### Step 4: Verification Checklist

- [ ] SCIM Bridge received DELETE request
- [ ] User removed from all group memberships
- [ ] YAML updated with `status: deactivated`
- [ ] YAML updated with `disabled: true`
- [ ] GitHub PR created for deactivation

---

## Part 7: Terraform Apply and Vault Verification

### Step 1: Merge PRs

```bash
# List all SCIM-related PRs
gh pr list --repo YOUR_ORG/vault-config-as-code --label scim-provisioning

# Merge each PR (after review)
gh pr merge PR_NUMBER --merge --repo YOUR_ORG/vault-config-as-code
```

### Step 2: Pull Changes

```bash
git pull origin main
```

### Step 3: Validate Terraform

```bash
# Validate configuration
terraform validate

# Plan changes
terraform plan -var-file=dev.tfvars

# Review the plan - should show:
# - vault_identity_entity.entraid_human["scim_test_user"] will be created
# - vault_identity_entity_alias.entraid_human_oidc["scim_test_user"] will be created
```

### Step 4: Apply Terraform

```bash
terraform apply -var-file=dev.tfvars

# Type 'yes' to confirm
```

### Step 5: Verify Vault Identity

```bash
# Set Vault address and token
export VAULT_ADDR="http://localhost:8200"
export VAULT_TOKEN="dev-root-token"

# List identity entities
vault list identity/entity/name

# Read the test user entity
vault read identity/entity/name/scim_test_user

# Verify:
# - metadata contains entraid_object_id
# - metadata contains role, team, email
# - disabled = false (or true if deactivated)
```

### Step 6: Verify Identity Alias

```bash
# List identity aliases for OIDC
vault list identity/entity-alias/id

# The user should have an OIDC alias pointing to the entraid auth backend
```

### Step 7: Test OIDC Authentication (Optional)

If OIDC is configured, test authentication:

1. Open Vault UI: http://localhost:8200/ui
2. Select **OIDC** authentication method
3. Sign in with the test user's EntraID credentials
4. Verify the user can access Vault

---

## Troubleshooting

### ngrok Issues

**Problem**: ngrok tunnel disconnects
```bash
# Restart ngrok with a reserved domain (paid feature)
ngrok http 8080 --domain=your-reserved-domain.ngrok-free.app

# Or use ngrok.yml config for persistence
```

**Problem**: EntraID can't reach ngrok URL
```bash
# Verify ngrok is running and URL is correct
curl -s ${NGROK_URL}/health

# Check for "Too Many Requests" - ngrok free tier has limits
# Consider upgrading or using reserved domains
```

### SCIM Bridge Issues

**Problem**: 401 Unauthorized from EntraID
```bash
# Verify token matches
echo $SCIM_BEARER_TOKEN
docker exec scim-bridge printenv SCIM_BEARER_TOKEN

# Token in EntraID must match exactly
```

**Problem**: PR not created
```bash
# Check GitHub token
curl -H "Authorization: token $GITHUB_TOKEN" \
     https://api.github.com/user

# Check SCIM Bridge logs for Git errors
docker logs scim-bridge | grep -i "git\|error"
```

**Problem**: YAML validation fails
```bash
# Validate example file
cd identities
python3 validate_identities.py

# Check schema exists
ls -la schema_entraid_human.yaml
```

### EntraID Issues

**Problem**: Provisioning shows errors
1. Go to Enterprise Application > **Provisioning** > **Provisioning logs**
2. Filter by failed status
3. Check error details

**Problem**: User not syncing
1. Verify user is assigned to the application
2. Check provisioning scope (assigned users only)
3. Try "Provision on demand" for specific user

**Problem**: Attribute mapping errors
1. Review attribute mappings in EntraID
2. Check if required attributes have values in user profile
3. Verify SCIM schema compatibility

### Common Error Messages

| Error | Cause | Solution |
|-------|-------|----------|
| `Invalid bearer token` | Token mismatch | Verify SCIM_BEARER_TOKEN in both places |
| `Git operation failed` | Auth/permission issue | Check GITHUB_TOKEN permissions |
| `Schema validation failed` | Malformed YAML | Check attribute mappings |
| `User not found` | Missing user mapping | Check user_store.json |

---

## Cleanup

### Step 1: Stop Provisioning

1. Go to Enterprise Application > **Provisioning**
2. Click **Stop provisioning**

### Step 2: Remove Test Users from EntraID

1. Go to **Microsoft Entra ID** > **Users**
2. Delete test users created for this runbook

### Step 3: Delete Enterprise Application

1. Go to **Enterprise applications**
2. Select your test application
3. Click **Delete**

### Step 4: Stop Local Services

```bash
# Stop ngrok (Ctrl+C in ngrok terminal)

# Stop Docker services
docker compose down

# Remove test data
docker volume rm vault-config-as-code_scim-data
```

### Step 5: Clean Up Test PRs

```bash
# Close any unmerged test PRs
gh pr list --repo YOUR_ORG/vault-config-as-code --label scim-provisioning --state open

# Close each PR
gh pr close PR_NUMBER --repo YOUR_ORG/vault-config-as-code
```

### Step 6: Revert Test Changes (if needed)

```bash
# If test identity files were merged, create PR to remove them
git checkout -b cleanup-scim-test
rm identities/entraid_human_scim_*.yaml
git add -A
git commit -m "Cleanup: Remove SCIM test identity files"
git push origin cleanup-scim-test
gh pr create --title "Cleanup SCIM Test Files" --body "Removing test identity files from E2E testing"
```

---

## Test Results Tracking

Use this section to track your test execution:

### Test Execution Log

| Date | Tester | Test Case | Result | Notes |
|------|--------|-----------|--------|-------|
| | | User Onboarding | | |
| | | Group Add | | |
| | | Group Remove | | |
| | | User Offboarding | | |
| | | Terraform Apply | | |
| | | Vault Verification | | |

### Evidence Collection

Save the following for each test run:
- [ ] ngrok inspector screenshots
- [ ] SCIM Bridge log excerpts
- [ ] GitHub PR URLs
- [ ] Vault entity read output
- [ ] EntraID provisioning logs

---

## Next Steps After Successful Testing

1. **Document learnings** in [AGENTS.md](../.ralph-loop/AGENTS.md)
2. **Update production deployment guide** with any new considerations
3. **Configure production EntraID** application with proper domain (not ngrok)
4. **Set up monitoring** for SCIM Bridge in production
5. **Configure alerts** for provisioning failures
6. **Create runbook** for production user lifecycle operations
