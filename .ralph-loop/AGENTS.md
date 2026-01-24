# Agent Knowledge Base

This file contains patterns, gotchas, and reusable solutions discovered during project development.

## Working Patterns

### Terraform Development
- Always run `terraform validate` after creating/modifying `.tf` files
- Use `count` with conditional for optional resources: `count = var.enable_feature ? 1 : 0`
- Use `try()` for safe access to optional map values
- Use `for_each` with maps for multiple similar resources
- When updating `data.tf` locals, ensure proper filtering with `if` conditions

### YAML Schema Development
- Use JSON Schema draft-07 format
- Include `$schema` reference in YAML identity files
- Mark optional fields with `default` values in schema
- Use `enum` for status fields (active/deactivated)
- Use `pattern` with regex for string validation (email, usernames)

### File Naming Conventions
- EntraID identities: `entraid_human_firstname_lastname.yaml`
- Identity groups: `identity_group_{name}.yaml`
- Filter by filename prefix using `startswith()` in `data.tf`

### Python/FastAPI Development
- Use Pydantic models for SCIM request/response validation
- Use FastAPI `Depends()` for authentication middleware
- Return SCIM-compliant responses with proper schema URNs
- Include custom fields in responses (PR URL, YAML filename)
- Use `Annotated[Type, Depends(dependency)]` for dependency injection with type hints
- Use `HTTPBearer()` for extracting bearer tokens from Authorization headers
- Use `secrets.compare_digest()` for constant-time token comparison (prevents timing attacks)
- Return 500 for missing server configuration, 401 for authentication failures
- Include WWW-Authenticate header in 401 responses per HTTP/SCIM spec

### Python Validation Scripts
- Separate required vs optional schemas in configuration
- Use helper methods to reduce code duplication
- Check file type patterns from most specific to least specific
- Handle missing optional schemas with warnings, not errors
- Return (True, []) for skipped validations to avoid false failures

## Anti-Patterns

### What to Avoid
- Don't mark Terraform resources with `count = 0` as dependencies without checking if count > 0
- Don't hardcode sensitive values - always use variables or environment variables
- Don't skip `terraform validate` - catch errors early
- Don't create YAML files without schema validation
- Don't use mutable default arguments in Python (use `None` and initialize in function)
- Don't forget to handle optional fields with `try()` in Terraform locals
- Don't use `==` for token comparison - always use `secrets.compare_digest()` for security
- Don't forget to include WWW-Authenticate header in 401 authentication error responses

## Component-Specific Knowledge

### Terraform Vault Provider
- OIDC backend uses `vault_jwt_auth_backend` with `type = "oidc"`
- Entity aliases require `mount_accessor` from auth backend resource
- Use `user_claim = "email"` for OIDC to match claim returned by EntraID
- Entity `disabled` field controls whether user can authenticate

### SCIM Protocol
- SCIM 2.0 uses specific schema URN: `urn:ietf:params:scim:schemas:core:2.0:User`
- PATCH operations use `Operations` array with `op`, `path`, `value`
- Group membership changes sent via PATCH with add/remove on `groups` path
- DELETE should perform soft delete (set active=false, disabled=true)

### YAML Generation
- Use `yaml.dump()` with `default_flow_style=False` for readable output
- Use `sort_keys=False` to preserve field order
- Use `allow_unicode=True` to handle international characters
- Include `$schema` reference at top of YAML files
- Sanitize user input: lowercase, replace spaces with underscores, remove special chars
- Field sanitization pattern:
  - Convert to lowercase
  - Replace spaces with underscores
  - Remove special characters: `re.sub(r'[^a-z0-9_]', '', value)`
  - Clean consecutive underscores: `re.sub(r'_+', '_', value)`
  - Strip leading/trailing underscores: `value.strip("_")`
  - Provide fallback default if result is empty
- SCIM to YAML mapping:
  - userName → authentication.oidc (email)
  - displayName → identity.name
  - emails[0].value → identity.email (primary email)
  - title → identity.role (sanitized)
  - department → identity.team (sanitized)
  - id → metadata.entraid_object_id (UUID)
  - active (bool) → identity.status ("active"/"deactivated")
  - active (bool) → authentication.disabled (inverted)
- Filename pattern: `entraid_human_{sanitized_name}.yaml`

### Git Operations
- Use descriptive branch names: `scim-provision-{username}-{timestamp}`
- Create PRs with labels: `scim-provisioning`, `needs-review`
- Use GitHub API for PR creation (requires personal access token)
- Commit messages should be descriptive and follow project conventions

### Docker Configuration
- Use named volumes for persistent data
- Configure health checks for all services
- Connect services to same network for inter-service communication
- Use `depends_on` for service startup order

## Troubleshooting

### Common Issues

#### Terraform Issues
- **Error**: "Invalid for_each argument" - Ensure the map value is computed before the resource
- **Error**: "Invalid index" - Use `try()` or conditional count for optional resources
- **Error**: "Provider not found" - Run `terraform init` first

#### SCIM Bridge Issues
- **401 Unauthorized** - Check `SCIM_BEARER_TOKEN` environment variable matches EntraID configuration
- **PR not created** - Check `GITHUB_TOKEN` has repo permissions
- **YAML validation fails** - Ensure generated YAML matches schema_entraid_human.yaml
- **Group file not found** - GroupHandler creates new group files if match not found

#### YAML Validation Issues
- **Schema not found** - Ensure `load_schemas()` includes entraid_human as optional schema
- **Wrong file type** - Check `determine_schema_type()` checks 'entraid_human_' prefix FIRST (before ldap_human and human)
- **Validation fails** - Ensure all required fields present and values match schema constraints
- **Optional schema missing** - Files with missing optional schemas should return (True, []) with warning, not error

### Debugging Tips

#### Terraform
```bash
# Plan with detailed output
terraform plan -var-file=dev.tfvars - detailed-exitcode

# Validate specific file
terraform validate -no-color

# Format check
terraform fmt -check
```

#### SCIM Bridge
```bash
# View container logs
docker logs -f scim-bridge

# Test health endpoint
curl http://localhost:8080/health

# Test SCIM endpoint
curl -X POST http://localhost:8080/scim/v2/Users \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/scim+json" \
  -d @test_user.json
```

#### YAML Validation
```bash
# Run validation with verbose output
cd identities
python3 validate_identities.py --verbose
```

## Story Dependencies

- Story-1 through Story-9: Phase 1 (OIDC Auth) - Can be done in parallel where possible
- Story-10 through Story-24: Phase 2 (SCIM Bridge) - Story-11 (models) should be done before handlers/services
- Story-25: Documentation - Should be done after implementation stories

### Dependency Chain
```
Story-1 (variables) → Story-2 (auth backend) → Story-3 (identities) → Story-4 (data.tf locals) → Story-5 (groups)
Story-6 (schema) → Story-7 (example file) → Story-8 (validation)
Story-9 (tfvars)

Story-10 (dirs) → Story-11 (models) → Story-12 (auth handler) → Story-13 (yaml gen) → Story-14 (user store) → Story-15 (group handler) → Story-16 (git handler) → Story-17 (main app)
Story-18 (config) → Story-19 (dockerfile) → Story-20 (requirements) → Story-21 (env example)
Story-22 (docker-compose)
Story-23 (tests)
Story-24 (mock client)

Story-25 (docs)
```

## Iteration Notes

### Iteration 1
- Notes will be added as iterations complete

### Data Persistence and Thread Safety
- Use threading.Lock for thread-safe operations in Python classes
- Acquire lock using `with self._lock:` context manager for automatic release
- Lock protects both reads and writes to prevent race conditions
- Atomic write pattern for file-based persistence:
  - Write to temporary file first: `temp_file = path.with_suffix(".tmp")`
  - Write data to temp file completely
  - Use atomic rename: `temp_file.replace(original_file)`
  - On POSIX, rename is atomic and prevents partial file reads
- JSON persistence best practices:
  - Use `indent=2` for human-readable output
  - Use `ensure_ascii=False` to preserve Unicode characters
  - Use `encoding="utf-8"` for all file operations
  - Handle FileNotFoundError and json.JSONDecodeError gracefully
- Directory creation: Use `Path.mkdir(parents=True, exist_ok=True)`

### YAML File Management for Identity Groups
- YAML file operations use pathlib.Path for cross-platform compatibility
- Read with `yaml.safe_load()`, write with `yaml.dump()` 
- Preserve field order: `sort_keys=False` in yaml.dump()
- Handle encoding: `encoding='utf-8'` and `allow_unicode=True`
- Error handling: Continue processing on malformed YAML, print warnings
- File discovery: Use `glob("*.yaml")` patterns with filtering
- Return relative paths from repo root for Git operations
- Group membership arrays: entraid_human_identities separate from human_identities
- Set operations for efficient membership synchronization:
  - `groups_to_join = target_groups - current_memberships`
  - `groups_to_leave = current_memberships - target_groups`
- Maintain sorted lists for consistency: `list.sort()` after modifications
- Group file creation: Include all required fields (name, contact, type, arrays)
- Name sanitization: lowercase, underscores, remove special chars, fallback defaults

### Git Operations and GitHub Integration
- Git command execution: Use `subprocess.run()` with `check=True` for error handling
- Capture output: `capture_output=True, text=True, encoding='utf-8'`
- GitHub URL parsing patterns:
  - SSH format: `git@github.com:owner/repo.git`
  - HTTPS format: `https://github.com/owner/repo.git`
  - Extract owner/repo by splitting path component after domain
- GitHub API authentication: Use personal access token in Authorization header
- Repository operations flow:
  - Check if directory exists and contains .git folder
  - Clone if new, pull if exists
  - Use token authentication for HTTPS: `https://token@github.com/owner/repo.git`
  - Remove directory if exists but isn't a git repository
- Branch naming for automation: `{operation-type}-{username}-{timestamp}`
- Git workflow pattern:
  - Checkout and pull main branch first
  - Create feature branch from updated main
  - Add specific files (not git add .)
  - Commit with descriptive message
  - Push branch to origin
  - Create PR immediately via API
- PR creation best practices:
  - Use markdown formatting with headers and lists
  - Include verification checklists for reviewers
  - Extract key info from file content for summaries
  - Add automation disclaimer
  - Apply labels for categorization (`scim-provisioning`, `needs-review`)
- Error handling strategies:
  - Git operations: Catch `subprocess.CalledProcessError`, print command and stderr
  - API requests: Use `response.raise_for_status()` for HTTP errors
  - Continue on non-critical errors (e.g., label application failures)


### Docker Configuration
- Use slim base images (python:3.11-slim) for smaller footprint and faster builds
- Install system dependencies with single RUN layer: apt-get update && install && clean && rm -rf /var/lib/apt/lists/*
- Copy requirements.txt before application code for better Docker layer caching
- Create non-root user for security: useradd --create-home --shell /bin/bash appuser
- Set proper ownership with chown -R user:user for application directories
- Use health checks with curl for container orchestration readiness
- Pin all dependency versions for reproducibility (critical for production)
- Separate application code (/app) from persistent data (/data) directories

### Real EntraID Integration Testing

#### ngrok Configuration
- ngrok free tier has request limits; consider paid tier for extensive testing
- ngrok URLs change on restart unless using reserved domains (paid feature)
- Use `ngrok http 8080` to expose SCIM Bridge, not the container's internal port 8000
- Monitor requests at http://localhost:4040 for debugging
- Keep ngrok running in a separate terminal during entire test session
- For persistent testing, use ngrok config file: `~/.ngrok2/ngrok.yml`

#### EntraID SCIM Provisioning Behavior
- EntraID sends initial sync within 40 minutes of enabling provisioning
- Use "Provision on demand" for immediate single-user testing
- EntraID may batch multiple changes into single PATCH request
- Group membership changes come via PATCH with `groups` path
- Deactivation sends DELETE, not PATCH with active=false
- EntraID retries failed requests with exponential backoff
- Check "Provisioning logs" in Azure Portal for detailed error information

#### EntraID Attribute Mapping Patterns
- `userPrincipalName` is the unique identifier, maps to `userName`
- `mail` may be null for some users; use fallback to `userPrincipalName`
- `jobTitle` and `department` may be null; provide defaults in YAML generator
- `objectId` (GUID) is stable; use for SCIM ID tracking
- EntraID sends `active` as boolean, not string
- `displayName` may contain special characters; sanitize for filenames

#### SCIM Request Patterns from EntraID
- POST for new user: Full user object with all mapped attributes
- PATCH for updates: Only changed attributes in Operations array
- DELETE for removal: Just the user ID, no body
- GET for reconciliation: EntraID may query all users periodically
- EntraID expects SCIM-compliant responses with proper schemas
- Include `id` field in responses for EntraID to track resources

#### Testing Workflow Best Practices
- Always start with a single test user before bulk testing
- Verify ngrok tunnel health before configuring EntraID
- Save SCIM_BEARER_TOKEN securely; regenerate after testing
- Use descriptive test user names: `scimtest-dev-<initials>`
- Clean up test users after each testing session
- Document EntraID provisioning log errors for troubleshooting

#### Common EntraID SCIM Errors
- "The supplied credentials are authorized" but no sync: Check scope settings
- "Unable to parse the incoming request": Check attribute mappings
- "Duplicate user" error: User may exist from previous test; check user store
- "Network error": ngrok tunnel may have disconnected
- "Unauthorized": Bearer token mismatch between EntraID and SCIM Bridge
