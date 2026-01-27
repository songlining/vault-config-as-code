## Azure CLI Automation Patterns

### EntraID Application Setup
- Use `az ad app create` for App Registration creation with proper sign-in audience
- Service Principal creation via `az ad sp create --id <app-id>` may require retry logic
- Graph API operations require elevated permissions (Application Administrator or Global Administrator)
- Bearer token generation: `openssl rand -base64 32` provides sufficient entropy
- State management in JSON files enables tracking and cleanup: `jq` or Python for state manipulation
- Resource naming convention: "Vault SCIM Provisioning (Test)" for clear identification
- Azure CLI authentication check: `az account show` before running automation scripts

### User and Group Management
- Test user creation pattern: `scimtestuser@<tenant>.onmicrosoft.com` for consistent naming
- User attributes: `--job-title` and `--department` parameters for SCIM mapping
- Group creation: `--mail-nickname` should be URL-safe version of display name
- User assignment to applications requires Graph API with role ID (default: 00000000-0000-0000-0000-000000000000)
- Group membership via `az ad group member add --group <id> --member-id <user-id>`

### SCIM Provisioning Configuration
- Graph API sync job creation may fail; provide manual Azure Portal fallback
- SCIM credentials configuration via PUT to `/synchronization/secrets` endpoint
- Template ID "customappsso" for custom SCIM applications
- Manual configuration instructions should include exact Azure Portal URLs
- On-demand provisioning via `/synchronization/jobs/{id}/provisionOnDemand` endpoint

### Error Handling Best Practices
- Check `az account show` before any Azure CLI operations
- Retry logic for Service Principal creation (common API timing issues)
- Graceful degradation: API failures → manual instructions with exact steps
- State persistence enables partial recovery and cleanup
- Clear error messages with troubleshooting guidance

## Azure CLI Automation Patterns

### EntraID Application Setup
- Use `az ad app create` for App Registration creation with proper sign-in audience
- Service Principal creation via `az ad sp create --id <app-id>` may require retry logic
- Graph API operations require elevated permissions (Application Administrator or Global Administrator)
- Bearer token generation: `openssl rand -base64 32` provides sufficient entropy
- State management in JSON files enables tracking and cleanup: `jq` or Python for state manipulation
- Resource naming convention: "Vault SCIM Provisioning (Test)" for clear identification
- Azure CLI authentication check: `az account show` before running automation scripts

### User and Group Management
- Test user creation pattern: `scimtestuser@<tenant>.onmicrosoft.com` for consistent naming
- User attributes: `--job-title` and `--department` parameters for SCIM mapping
- Group creation: `--mail-nickname` should be URL-safe version of display name
- User assignment to applications requires Graph API with role ID (default: 00000000-0000-0000-0000-000000000000)
- Group membership via `az ad group member add --group <id> --member-id <user-id>`

### SCIM Provisioning Configuration
- Graph API sync job creation may fail; provide manual Azure Portal fallback
- SCIM credentials configuration via PUT to `/synchronization/secrets` endpoint
- Template ID "customappsso" for custom SCIM applications
- Manual configuration instructions should include exact Azure Portal URLs
- On-demand provisioning via `/synchronization/jobs/{id}/provisionOnDemand` endpoint

### Error Handling Best Practices
- Check `az account show` before any Azure CLI operations
- Retry logic for Service Principal creation (common API timing issues)
- Graceful degradation: API failures → manual instructions with exact steps
- State persistence enables partial recovery and cleanup
- Clear error messages with troubleshooting guidance
