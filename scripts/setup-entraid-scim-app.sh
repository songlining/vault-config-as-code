#!/bin/bash
# EntraID SCIM Enterprise Application Setup Script
#
# This script automates Part 3 of the E2E Testing Runbook:
# - Creates EntraID App Registration and Service Principal
# - Configures SCIM provisioning endpoint
# - Creates test user and group
# - Assigns user to application and group
#
# ============================================================================
# PREREQUISITES
# ============================================================================
#
# 1. Azure CLI installed and logged in:
#      az login --tenant <your-tenant>.onmicrosoft.com
#    Example:
#      az login --tenant songlininggmail.onmicrosoft.com
#
# 2. ngrok installed and authenticated:
#      - Sign up at https://dashboard.ngrok.com/signup
#      - Get authtoken from https://dashboard.ngrok.com/get-started/your-authtoken
#      - Run: ngrok config add-authtoken <your-token>
#
# 3. GitHub Personal Access Token with 'repo' scope:
#      - Create at https://github.com/settings/tokens/new
#      - Select scope: 'repo' (full control of private repositories)
#
# 4. Docker and Docker Compose installed and running
#
# 5. Project .env file configured at project root (/workspaces/vault-config-as-code/.env):
#      SCIM_BEARER_TOKEN=<generated-or-custom-token>
#      GIT_REPO_URL=https://github.com/<your-org>/vault-config-as-code.git
#      GITHUB_TOKEN=ghp_<your-github-token>
#      LOG_LEVEL=DEBUG
#
# ============================================================================
# USAGE
# ============================================================================
#
#   ./scripts/setup-entraid-scim-app.sh setup <ngrok-url>
#   ./scripts/setup-entraid-scim-app.sh cleanup
#   ./scripts/setup-entraid-scim-app.sh status
#
# Example:
#   ./scripts/setup-entraid-scim-app.sh setup https://abc123.ngrok-free.app

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
APP_NAME="Vault SCIM Provisioning (Test)"
TEST_USER_UPN_PREFIX="scimtestuser"
TEST_GROUP_NAME="SCIM-Test-Developers"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
STATE_FILE="${PROJECT_ROOT}/.entraid-scim-state.json"

# Helper functions
print_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

print_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_info() {
    echo -e "${CYAN}[INFO]${NC} $1"
}

# Check Azure CLI login
check_az_login() {
    print_info "Checking Azure CLI login status..."
    if ! az account show &>/dev/null; then
        print_error "Not logged in to Azure CLI. Run: az login --tenant <your-tenant>"
        exit 1
    fi

    TENANT_ID=$(az account show --query tenantId -o tsv)
    TENANT_DOMAIN=$(az account show --query user.name -o tsv | cut -d'@' -f2)
    USER_EMAIL=$(az account show --query user.name -o tsv)

    print_success "Logged in as: $USER_EMAIL"
    print_success "Tenant ID: $TENANT_ID"
    print_success "Tenant Domain: $TENANT_DOMAIN"
}

# Save state to file
save_state() {
    local key="$1"
    local value="$2"

    if [ ! -f "$STATE_FILE" ]; then
        echo "{}" > "$STATE_FILE"
    fi

    # Use jq if available, otherwise use python
    if command -v jq &>/dev/null; then
        jq --arg k "$key" --arg v "$value" '.[$k] = $v' "$STATE_FILE" > "${STATE_FILE}.tmp" && mv "${STATE_FILE}.tmp" "$STATE_FILE"
    else
        python3 -c "
import json
with open('$STATE_FILE', 'r') as f:
    data = json.load(f)
data['$key'] = '$value'
with open('$STATE_FILE', 'w') as f:
    json.dump(data, f, indent=2)
"
    fi
}

# Load state from file
load_state() {
    local key="$1"

    if [ ! -f "$STATE_FILE" ]; then
        echo ""
        return
    fi

    if command -v jq &>/dev/null; then
        jq -r --arg k "$key" '.[$k] // empty' "$STATE_FILE"
    else
        python3 -c "
import json
with open('$STATE_FILE', 'r') as f:
    data = json.load(f)
print(data.get('$key', ''))
"
    fi
}

# Generate random password
generate_password() {
    openssl rand -base64 16 | tr -d '/+=' | head -c 16
    echo "!Aa1"  # Append to meet complexity requirements
}

# Create App Registration
create_app_registration() {
    print_info "Creating App Registration: $APP_NAME..."

    # Check if app already exists
    EXISTING_APP=$(az ad app list --display-name "$APP_NAME" --query "[0].appId" -o tsv 2>/dev/null || echo "")

    if [ -n "$EXISTING_APP" ]; then
        print_warning "App Registration already exists: $EXISTING_APP"
        APP_ID="$EXISTING_APP"
    else
        # Create the app registration
        APP_ID=$(az ad app create \
            --display-name "$APP_NAME" \
            --sign-in-audience "AzureADMyOrg" \
            --query appId -o tsv)

        print_success "Created App Registration: $APP_ID"
    fi

    save_state "app_id" "$APP_ID"

    # Get the object ID
    APP_OBJECT_ID=$(az ad app show --id "$APP_ID" --query id -o tsv)
    save_state "app_object_id" "$APP_OBJECT_ID"

    echo "$APP_ID"
}

# Create Service Principal (Enterprise Application)
create_service_principal() {
    local app_id="$1"
    print_info "Creating Service Principal for App ID: $app_id..."

    # Check if SP already exists
    EXISTING_SP=$(az ad sp list --filter "appId eq '$app_id'" --query "[0].id" -o tsv 2>/dev/null || echo "")

    if [ -n "$EXISTING_SP" ]; then
        print_warning "Service Principal already exists: $EXISTING_SP"
        SP_ID="$EXISTING_SP"
    else
        # Create service principal
        SP_ID=$(az ad sp create --id "$app_id" --query id -o tsv)
        print_success "Created Service Principal: $SP_ID"
    fi

    save_state "sp_id" "$SP_ID"

    # Enable the service principal
    az ad sp update --id "$SP_ID" --set accountEnabled=true 2>/dev/null || true

    echo "$SP_ID"
}

# Configure SCIM Provisioning via Graph API
configure_scim_provisioning() {
    local sp_id="$1"
    local scim_url="$2"
    local bearer_token="$3"

    print_info "Configuring SCIM provisioning for SP: $sp_id..."
    print_info "SCIM Endpoint: ${scim_url}/scim/v2"

    # Get access token for Graph API
    ACCESS_TOKEN=$(az account get-access-token --resource https://graph.microsoft.com --query accessToken -o tsv)

    # Check if synchronization job exists
    print_info "Checking for existing synchronization jobs..."
    SYNC_JOBS=$(curl -s -X GET \
        -H "Authorization: Bearer $ACCESS_TOKEN" \
        -H "Content-Type: application/json" \
        "https://graph.microsoft.com/v1.0/servicePrincipals/${sp_id}/synchronization/jobs" 2>/dev/null || echo '{"value":[]}')

    JOB_COUNT=$(echo "$SYNC_JOBS" | python3 -c "import sys, json; data=json.load(sys.stdin); print(len(data.get('value', [])))" 2>/dev/null || echo "0")

    if [ "$JOB_COUNT" = "0" ]; then
        print_info "Creating synchronization job template..."

        # First, we need to instantiate a synchronization template
        # For custom SCIM apps, we use the 'customappsso' template
        CREATE_JOB_RESULT=$(curl -s -X POST \
            -H "Authorization: Bearer $ACCESS_TOKEN" \
            -H "Content-Type: application/json" \
            -d '{"templateId": "customappsso"}' \
            "https://graph.microsoft.com/v1.0/servicePrincipals/${sp_id}/synchronization/jobs" 2>/dev/null || echo '{"error":"failed"}')

        if echo "$CREATE_JOB_RESULT" | grep -q "error"; then
            print_warning "Could not create sync job via template. This may require manual setup in Azure Portal."
            print_info "Alternative: Configure provisioning manually in Azure Portal > Enterprise Applications > $APP_NAME > Provisioning"
        else
            print_success "Created synchronization job"
        fi
    else
        print_info "Synchronization job already exists"
    fi

    # Configure SCIM credentials via Graph API
    print_info "Configuring SCIM credentials..."

    CREDENTIALS_PAYLOAD=$(cat <<EOF
{
    "value": [
        {
            "key": "BaseAddress",
            "value": "${scim_url}/scim/v2"
        },
        {
            "key": "SecretToken",
            "value": "${bearer_token}"
        }
    ]
}
EOF
)

    CRED_RESULT=$(curl -s -X PUT \
        -H "Authorization: Bearer $ACCESS_TOKEN" \
        -H "Content-Type: application/json" \
        -d "$CREDENTIALS_PAYLOAD" \
        "https://graph.microsoft.com/v1.0/servicePrincipals/${sp_id}/synchronization/secrets" 2>/dev/null || echo '{"error":"failed"}')

    if echo "$CRED_RESULT" | grep -q "error"; then
        print_warning "Could not configure SCIM credentials via API."
        print_info "Please configure manually in Azure Portal:"
        echo ""
        echo "  1. Go to Azure Portal > Enterprise Applications > '$APP_NAME'"
        echo "  2. Click 'Provisioning' in the left sidebar"
        echo "  3. Set Provisioning Mode to 'Automatic'"
        echo "  4. Enter Tenant URL: ${scim_url}/scim/v2"
        echo "  5. Enter Secret Token: ${bearer_token}"
        echo "  6. Click 'Test Connection' then 'Save'"
        echo ""
    else
        print_success "SCIM credentials configured"
    fi

    save_state "scim_url" "$scim_url"
    save_state "scim_configured" "true"
}

# Create test user
create_test_user() {
    print_info "Creating test user..."

    # Get tenant domain
    TENANT_DOMAIN=$(az rest --method GET --url "https://graph.microsoft.com/v1.0/domains" --query "value[?isDefault].id" -o tsv 2>/dev/null | head -1)

    if [ -z "$TENANT_DOMAIN" ]; then
        TENANT_DOMAIN="songlininggmail.onmicrosoft.com"
    fi

    TEST_USER_UPN="${TEST_USER_UPN_PREFIX}@${TENANT_DOMAIN}"
    TEST_USER_PASSWORD=$(generate_password)

    # Check if user already exists
    EXISTING_USER=$(az ad user list --filter "userPrincipalName eq '$TEST_USER_UPN'" --query "[0].id" -o tsv 2>/dev/null || echo "")

    if [ -n "$EXISTING_USER" ]; then
        print_warning "Test user already exists: $TEST_USER_UPN"
        USER_ID="$EXISTING_USER"
    else
        # Create the user
        USER_ID=$(az ad user create \
            --display-name "SCIM Test User" \
            --user-principal-name "$TEST_USER_UPN" \
            --password "$TEST_USER_PASSWORD" \
            --force-change-password-next-sign-in false \
            --mail-nickname "$TEST_USER_UPN_PREFIX" \
            --query id -o tsv 2>/dev/null || echo "")

        if [ -z "$USER_ID" ]; then
            print_error "Failed to create test user"
            return 1
        fi

        print_success "Created test user: $TEST_USER_UPN"
        print_info "Password: $TEST_USER_PASSWORD"

        # Update user with additional attributes (job title, department)
        sleep 2  # Wait for user to be created

        az ad user update --id "$USER_ID" \
            --job-title "Software Engineer" \
            --department "Platform Engineering" 2>/dev/null || print_warning "Could not set job title/department"
    fi

    save_state "test_user_id" "$USER_ID"
    save_state "test_user_upn" "$TEST_USER_UPN"
    save_state "test_user_password" "$TEST_USER_PASSWORD"

    echo "$USER_ID"
}

# Create test group
create_test_group() {
    print_info "Creating test group: $TEST_GROUP_NAME..."

    # Check if group already exists
    EXISTING_GROUP=$(az ad group list --filter "displayName eq '$TEST_GROUP_NAME'" --query "[0].id" -o tsv 2>/dev/null || echo "")

    if [ -n "$EXISTING_GROUP" ]; then
        print_warning "Test group already exists: $EXISTING_GROUP"
        GROUP_ID="$EXISTING_GROUP"
    else
        # Create the group
        GROUP_ID=$(az ad group create \
            --display-name "$TEST_GROUP_NAME" \
            --mail-nickname "scim-test-developers" \
            --description "Test group for SCIM provisioning" \
            --query id -o tsv)

        print_success "Created test group: $TEST_GROUP_NAME ($GROUP_ID)"
    fi

    save_state "test_group_id" "$GROUP_ID"

    echo "$GROUP_ID"
}

# Assign user to application
assign_user_to_app() {
    local sp_id="$1"
    local user_id="$2"

    print_info "Assigning user to application..."

    # Get access token for Graph API
    ACCESS_TOKEN=$(az account get-access-token --resource https://graph.microsoft.com --query accessToken -o tsv)

    # Check if assignment already exists
    EXISTING_ASSIGNMENT=$(curl -s -X GET \
        -H "Authorization: Bearer $ACCESS_TOKEN" \
        "https://graph.microsoft.com/v1.0/servicePrincipals/${sp_id}/appRoleAssignedTo" 2>/dev/null | \
        python3 -c "import sys, json; data=json.load(sys.stdin); assignments=[a for a in data.get('value',[]) if a.get('principalId')=='$user_id']; print(assignments[0]['id'] if assignments else '')" 2>/dev/null || echo "")

    if [ -n "$EXISTING_ASSIGNMENT" ]; then
        print_warning "User already assigned to application"
        return 0
    fi

    # Create app role assignment
    # Using default app role (empty GUID means default access)
    ASSIGNMENT_PAYLOAD=$(cat <<EOF
{
    "principalId": "${user_id}",
    "resourceId": "${sp_id}",
    "appRoleId": "00000000-0000-0000-0000-000000000000"
}
EOF
)

    RESULT=$(curl -s -X POST \
        -H "Authorization: Bearer $ACCESS_TOKEN" \
        -H "Content-Type: application/json" \
        -d "$ASSIGNMENT_PAYLOAD" \
        "https://graph.microsoft.com/v1.0/servicePrincipals/${sp_id}/appRoleAssignedTo" 2>/dev/null)

    if echo "$RESULT" | grep -q "error"; then
        print_warning "Could not assign user to app via API: $(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('error',{}).get('message','unknown'))" 2>/dev/null)"
        print_info "Please assign manually in Azure Portal > Enterprise Applications > Users and groups"
    else
        print_success "User assigned to application"
    fi

    save_state "user_assigned" "true"
}

# Assign user to group
assign_user_to_group() {
    local group_id="$1"
    local user_id="$2"

    print_info "Adding user to group..."

    # Check if user is already a member
    IS_MEMBER=$(az ad group member check --group "$group_id" --member-id "$user_id" --query value -o tsv 2>/dev/null || echo "false")

    if [ "$IS_MEMBER" = "true" ]; then
        print_warning "User is already a member of the group"
        return 0
    fi

    # Add user to group
    az ad group member add --group "$group_id" --member-id "$user_id" 2>/dev/null

    if [ $? -eq 0 ]; then
        print_success "User added to group"
    else
        print_warning "Could not add user to group"
    fi

    save_state "user_in_group" "true"
}

# Test SCIM connection
test_scim_connection() {
    local sp_id="$1"

    print_info "Testing SCIM connection..."

    ACCESS_TOKEN=$(az account get-access-token --resource https://graph.microsoft.com --query accessToken -o tsv)

    RESULT=$(curl -s -X POST \
        -H "Authorization: Bearer $ACCESS_TOKEN" \
        -H "Content-Type: application/json" \
        "https://graph.microsoft.com/v1.0/servicePrincipals/${sp_id}/synchronization/jobs/validateCredentials" \
        -d '{}' 2>/dev/null || echo '{"error":"failed"}')

    if echo "$RESULT" | grep -q "error"; then
        print_warning "Could not test connection via API"
        print_info "Test manually: Azure Portal > Enterprise Applications > Provisioning > Test Connection"
    else
        print_success "SCIM connection test initiated"
    fi
}

# Start provisioning
start_provisioning() {
    local sp_id="$1"

    print_info "Starting provisioning..."

    ACCESS_TOKEN=$(az account get-access-token --resource https://graph.microsoft.com --query accessToken -o tsv)

    # Get the sync job ID
    SYNC_JOBS=$(curl -s -X GET \
        -H "Authorization: Bearer $ACCESS_TOKEN" \
        "https://graph.microsoft.com/v1.0/servicePrincipals/${sp_id}/synchronization/jobs" 2>/dev/null)

    JOB_ID=$(echo "$SYNC_JOBS" | python3 -c "import sys, json; data=json.load(sys.stdin); jobs=data.get('value',[]); print(jobs[0]['id'] if jobs else '')" 2>/dev/null || echo "")

    if [ -z "$JOB_ID" ]; then
        print_warning "No synchronization job found"
        print_info "Configure provisioning manually in Azure Portal first"
        return 1
    fi

    # Start the job
    RESULT=$(curl -s -X POST \
        -H "Authorization: Bearer $ACCESS_TOKEN" \
        "https://graph.microsoft.com/v1.0/servicePrincipals/${sp_id}/synchronization/jobs/${JOB_ID}/start" 2>/dev/null || echo '{"error":"failed"}')

    if echo "$RESULT" | grep -q "error"; then
        print_warning "Could not start provisioning via API"
    else
        print_success "Provisioning started"
    fi

    save_state "provisioning_started" "true"
}

# Provision on demand
provision_on_demand() {
    local sp_id="$1"
    local user_id="$2"

    print_info "Triggering on-demand provisioning for user..."

    ACCESS_TOKEN=$(az account get-access-token --resource https://graph.microsoft.com --query accessToken -o tsv)

    # Get the sync job ID
    SYNC_JOBS=$(curl -s -X GET \
        -H "Authorization: Bearer $ACCESS_TOKEN" \
        "https://graph.microsoft.com/v1.0/servicePrincipals/${sp_id}/synchronization/jobs" 2>/dev/null)

    JOB_ID=$(echo "$SYNC_JOBS" | python3 -c "import sys, json; data=json.load(sys.stdin); jobs=data.get('value',[]); print(jobs[0]['id'] if jobs else '')" 2>/dev/null || echo "")

    if [ -z "$JOB_ID" ]; then
        print_warning "No synchronization job found"
        return 1
    fi

    # Provision on demand
    PAYLOAD=$(cat <<EOF
{
    "parameters": [
        {
            "subjects": [
                {
                    "objectId": "${user_id}",
                    "objectTypeName": "User"
                }
            ],
            "ruleId": "userProvisioningRule"
        }
    ]
}
EOF
)

    RESULT=$(curl -s -X POST \
        -H "Authorization: Bearer $ACCESS_TOKEN" \
        -H "Content-Type: application/json" \
        -d "$PAYLOAD" \
        "https://graph.microsoft.com/v1.0/servicePrincipals/${sp_id}/synchronization/jobs/${JOB_ID}/provisionOnDemand" 2>/dev/null)

    if echo "$RESULT" | grep -q "error"; then
        print_warning "On-demand provisioning may need manual trigger in Azure Portal"
        echo "Error details: $(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('error',{}).get('message','unknown'))" 2>/dev/null || echo "$RESULT")"
    else
        print_success "On-demand provisioning triggered"
    fi
}

# Show status
show_status() {
    print_header "EntraID SCIM Configuration Status"

    if [ ! -f "$STATE_FILE" ]; then
        print_warning "No configuration found. Run 'setup' first."
        return 1
    fi

    echo -e "${CYAN}Configuration State:${NC}"
    cat "$STATE_FILE" | python3 -m json.tool 2>/dev/null || cat "$STATE_FILE"

    echo ""
    echo -e "${CYAN}Azure Resources:${NC}"

    APP_ID=$(load_state "app_id")
    SP_ID=$(load_state "sp_id")
    USER_ID=$(load_state "test_user_id")
    GROUP_ID=$(load_state "test_group_id")

    if [ -n "$APP_ID" ]; then
        echo "  App Registration: $APP_ID"
        az ad app show --id "$APP_ID" --query "{name:displayName,appId:appId}" -o table 2>/dev/null || echo "    (not found)"
    fi

    if [ -n "$SP_ID" ]; then
        echo "  Service Principal: $SP_ID"
    fi

    if [ -n "$USER_ID" ]; then
        echo "  Test User: $(load_state "test_user_upn")"
    fi

    if [ -n "$GROUP_ID" ]; then
        echo "  Test Group: $TEST_GROUP_NAME"
    fi

    echo ""
    echo -e "${CYAN}SCIM Configuration:${NC}"
    echo "  SCIM URL: $(load_state "scim_url")/scim/v2"
    echo "  Configured: $(load_state "scim_configured")"
    echo "  Provisioning Started: $(load_state "provisioning_started")"
}

# Cleanup all resources
cleanup() {
    print_header "Cleaning Up EntraID Resources"

    if [ ! -f "$STATE_FILE" ]; then
        print_warning "No state file found. Nothing to clean up."
        return 0
    fi

    # Load state
    APP_ID=$(load_state "app_id")
    SP_ID=$(load_state "sp_id")
    USER_ID=$(load_state "test_user_id")
    GROUP_ID=$(load_state "test_group_id")

    # Delete in reverse order of creation

    # Remove user from group
    if [ -n "$GROUP_ID" ] && [ -n "$USER_ID" ]; then
        print_info "Removing user from group..."
        az ad group member remove --group "$GROUP_ID" --member-id "$USER_ID" 2>/dev/null || true
    fi

    # Delete group
    if [ -n "$GROUP_ID" ]; then
        print_info "Deleting test group..."
        az ad group delete --group "$GROUP_ID" 2>/dev/null || true
        print_success "Deleted group: $GROUP_ID"
    fi

    # Delete user
    if [ -n "$USER_ID" ]; then
        print_info "Deleting test user..."
        az ad user delete --id "$USER_ID" 2>/dev/null || true
        print_success "Deleted user: $USER_ID"
    fi

    # Delete service principal
    if [ -n "$SP_ID" ]; then
        print_info "Deleting service principal..."
        az ad sp delete --id "$SP_ID" 2>/dev/null || true
        print_success "Deleted service principal: $SP_ID"
    fi

    # Delete app registration
    if [ -n "$APP_ID" ]; then
        print_info "Deleting app registration..."
        az ad app delete --id "$APP_ID" 2>/dev/null || true
        print_success "Deleted app registration: $APP_ID"
    fi

    # Remove state file
    rm -f "$STATE_FILE"
    print_success "Removed state file"

    print_success "Cleanup complete!"
}

# Main setup function
setup() {
    local ngrok_url="$1"

    if [ -z "$ngrok_url" ]; then
        print_error "Usage: $0 setup <ngrok-url>"
        print_info "Example: $0 setup https://abc123.ngrok-free.app"
        exit 1
    fi

    # Remove trailing slash if present
    ngrok_url="${ngrok_url%/}"

    print_header "EntraID SCIM Enterprise Application Setup"

    # Check prerequisites
    check_az_login

    # Generate or load bearer token
    if [ -n "$SCIM_BEARER_TOKEN" ]; then
        BEARER_TOKEN="$SCIM_BEARER_TOKEN"
        print_info "Using SCIM_BEARER_TOKEN from environment"
    else
        BEARER_TOKEN=$(openssl rand -base64 32)
        print_info "Generated new bearer token"
    fi
    save_state "bearer_token" "$BEARER_TOKEN"

    # Step 1: Create App Registration
    print_header "Step 1: Create App Registration"
    APP_ID=$(create_app_registration)

    # Step 2: Create Service Principal
    print_header "Step 2: Create Service Principal"
    SP_ID=$(create_service_principal "$APP_ID")

    # Step 3: Configure SCIM Provisioning
    print_header "Step 3: Configure SCIM Provisioning"
    configure_scim_provisioning "$SP_ID" "$ngrok_url" "$BEARER_TOKEN"

    # Step 4: Create Test User
    print_header "Step 4: Create Test User"
    USER_ID=$(create_test_user)

    # Step 5: Create Test Group
    print_header "Step 5: Create Test Group"
    GROUP_ID=$(create_test_group)

    # Step 6: Assign User to Application
    print_header "Step 6: Assign User to Application"
    assign_user_to_app "$SP_ID" "$USER_ID"

    # Step 7: Assign User to Group
    print_header "Step 7: Assign User to Group"
    assign_user_to_group "$GROUP_ID" "$USER_ID"

    # Summary
    print_header "Setup Complete!"
    echo -e "${CYAN}Summary:${NC}"
    echo "  App Registration ID: $APP_ID"
    echo "  Service Principal ID: $SP_ID"
    echo "  Test User: $(load_state "test_user_upn")"
    echo "  Test User Password: $(load_state "test_user_password")"
    echo "  Test Group: $TEST_GROUP_NAME"
    echo ""
    echo -e "${CYAN}SCIM Configuration:${NC}"
    echo "  Tenant URL: ${ngrok_url}/scim/v2"
    echo "  Bearer Token: $BEARER_TOKEN"
    echo ""
    echo -e "${YELLOW}Important:${NC}"
    echo "  1. Ensure SCIM Bridge is running with this bearer token:"
    echo "     export SCIM_BEARER_TOKEN='$BEARER_TOKEN'"
    echo ""
    echo "  2. If SCIM provisioning wasn't configured automatically, configure it manually:"
    echo "     - Azure Portal > Enterprise Applications > '$APP_NAME' > Provisioning"
    echo "     - Set Mode to 'Automatic'"
    echo "     - Enter Tenant URL and Secret Token above"
    echo "     - Test Connection, then Save"
    echo ""
    echo "  3. To start provisioning:"
    echo "     $0 start-provisioning"
    echo ""
    echo "  4. To trigger on-demand provisioning for the test user:"
    echo "     $0 provision-user"
    echo ""
    echo -e "${GREEN}State saved to: $STATE_FILE${NC}"
}

# Help
show_help() {
    cat << EOF
EntraID SCIM Enterprise Application Setup Script

Usage: $(basename "$0") <command> [options]

Commands:
  setup <ngrok-url>     Create and configure EntraID Enterprise Application
                        Example: $0 setup https://abc123.ngrok-free.app

  status                Show current configuration status

  start-provisioning    Start the provisioning job

  provision-user        Trigger on-demand provisioning for test user

  test-connection       Test SCIM connection

  cleanup               Delete all created resources

  help                  Show this help message

Environment Variables:
  SCIM_BEARER_TOKEN     If set, uses this token instead of generating one

Prerequisites:
  1. Azure CLI installed and logged in:
       az login --tenant <your-tenant>.onmicrosoft.com

  2. ngrok installed and authenticated:
       - Sign up: https://dashboard.ngrok.com/signup
       - Add token: ngrok config add-authtoken <token>

  3. GitHub Personal Access Token (repo scope):
       - Create at: https://github.com/settings/tokens/new

  4. Docker and Docker Compose running

  5. Project .env file at repo root with:
       SCIM_BEARER_TOKEN=<token>
       GIT_REPO_URL=https://github.com/<org>/vault-config-as-code.git
       GITHUB_TOKEN=ghp_<token>
       LOG_LEVEL=DEBUG

  6. Azure AD permissions: Application Administrator or Global Administrator

Examples:
  # Initial setup
  $0 setup https://abc123.ngrok-free.app

  # Check status
  $0 status

  # Clean up everything
  $0 cleanup

For detailed instructions, see:
  docs/ENTRAID_E2E_TESTING_RUNBOOK.md
EOF
}

# Command: start provisioning
cmd_start_provisioning() {
    SP_ID=$(load_state "sp_id")
    if [ -z "$SP_ID" ]; then
        print_error "No service principal found. Run 'setup' first."
        exit 1
    fi
    start_provisioning "$SP_ID"
}

# Command: provision user
cmd_provision_user() {
    SP_ID=$(load_state "sp_id")
    USER_ID=$(load_state "test_user_id")
    if [ -z "$SP_ID" ] || [ -z "$USER_ID" ]; then
        print_error "Missing configuration. Run 'setup' first."
        exit 1
    fi
    provision_on_demand "$SP_ID" "$USER_ID"
}

# Command: test connection
cmd_test_connection() {
    SP_ID=$(load_state "sp_id")
    if [ -z "$SP_ID" ]; then
        print_error "No service principal found. Run 'setup' first."
        exit 1
    fi
    test_scim_connection "$SP_ID"
}

# Main entry point
main() {
    local command="${1:-help}"

    case "$command" in
        setup)
            setup "$2"
            ;;
        status)
            show_status
            ;;
        start-provisioning)
            cmd_start_provisioning
            ;;
        provision-user)
            cmd_provision_user
            ;;
        test-connection)
            cmd_test_connection
            ;;
        cleanup)
            cleanup
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            print_error "Unknown command: $command"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

main "$@"
