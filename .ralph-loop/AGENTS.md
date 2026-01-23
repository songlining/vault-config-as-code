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
- Include `$schema` reference at top of YAML files
- Sanitize user input: lowercase, replace spaces with underscores, remove special chars

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
