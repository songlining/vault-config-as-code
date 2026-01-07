# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This repository demonstrates HashiCorp Vault configuration management using Terraform, implementing Infrastructure as Code principles for stateful security services. The project showcases enterprise-grade patterns for managing Vault policies, authentication methods, PKI infrastructure, and application secrets across multiple environments.

## Architecture

### Core Components
- **Main Configuration**: `main.tf` contains super-user policies and GitHub auth backend configuration
- **Terraform Modules**:
  - `applications` module: Creates KV v2 mounts and policies per application/environment
  - `vault_namespace` module: Manages Vault namespaces with admin tokens and policies
- **Identity Management**: YAML-driven identity configuration with Python validation scripts
- **PKI Infrastructure**: Certificate authority setup and role management for machine/human identities
- **Authentication Backends**: GitHub OAuth, AWS IAM roles, and PKI-based authentication
- **Neo4j Graph Database**: Visual identity relationship mapping and exploration (optional)

### Key Terraform Files
- `versions.tf`: Provider versions (Terraform ~1.10.0, Vault ~5.1.0, TLS ~4.0.6)
- `variables.tf`: Required variables include `vault_url` and `environment`
- `data.tf`: Data sources for dynamic configuration
- `provider.tf`: Vault provider configuration
- `backend-local.tf`: Terraform state backend configuration

## Development Commands

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

### Pre-commit Hooks
The repository uses pre-commit hooks for code quality:
- `terraform_fmt`: Format Terraform code
- `terraform_tflint`: Lint Terraform code
- `terraform_trivy`: Security scanning
- `terraform_validate`: Validate Terraform configuration

Run manually with:
```bash
pre-commit run --all-files
```

### Identity Validation
Validate YAML identity configurations:
```bash
cd identities
python3 validate_identities.py
```

### Local Development Environment
Start Vault Enterprise and Neo4j containers:
```bash
docker compose up -d
```

Services:
- **Vault**: `http://localhost:8200` (root token: `dev-root-token`)
- **Neo4j Browser**: `http://localhost:7474` (credentials: `neo4j/vaultgraph123`)

### Neo4j Graph Database Integration
The repository includes optional Neo4j integration for visualizing identity relationships:

```bash
# Enable Neo4j integration in dev.tfvars
enable_neo4j_integration = true

# Apply Terraform to populate graph
terraform apply -var-file=dev.tfvars

# Access Neo4j Browser
open http://localhost:7474

# Run utility commands
./scripts/neo4j_utils.sh stats      # Show graph statistics
./scripts/neo4j_utils.sh validate   # Run validation checks
./scripts/neo4j_utils.sh backup     # Create backup
```

**Neo4j Files:**
- `neo4j_provider.tf`: Provider configuration and connectivity checks
- `neo4j_variables.tf`: Neo4j-specific variables
- `neo4j_locals.tf`: Data transformation for graph relationships
- `neo4j_graph.tf`: Node and relationship creation
- `neo4j_outputs.tf`: Helpful output information
- `docker-compose.yml`: Neo4j service configuration

**Documentation:**
- `docs/neo4j_quickstart.md`: 10-minute tutorial
- `docs/neo4j_setup.md`: Detailed setup guide
- `docs/neo4j_queries.md`: Query library with 50+ examples
- `neo4j_queries/*.cypher`: Pre-built query scripts
- `neo4j_queries/graph_style.grass`: Custom visualization styling

**Graph Model:**
- **Nodes**: HumanIdentity, ApplicationIdentity, IdentityGroup, Policy, AuthMethod
- **Relationships**: MEMBER_OF, HAS_SUBGROUP, HAS_POLICY, AUTHENTICATES_VIA

**Use Cases:**
- Visual exploration of identity hierarchies
- Impact analysis before making changes
- Troubleshooting access issues
- Onboarding new team members
- Access auditing and reviews

## Important Patterns

### Module Usage
- Applications are provisioned via the `applications` module with environment-specific KV mounts
- Namespaces follow the pattern: `module.vault_namespace` for tenant isolation
- Each application gets separate secret-provider and secret-consumer policies

### Policy Management
- Super-user policy provides broad Vault administration capabilities
- Application policies follow least-privilege with separate read/write permissions
- Namespace admin policies enable delegated administration

### Authentication Flow
- GitHub OAuth for human users (requires HashiCorp organization membership)
- AWS IAM roles for service authentication
- PKI certificates for machine identity verification
- Token rotation configured for 30-day cycles

### Environment Variables
Required for Vault Enterprise:
- `VAULT_LICENSE`: Enterprise license key
- Vault connection details configured in `dev.tfvars`

## Testing and Validation

The repository includes validation scripts for identity configurations and uses Terraform's built-in validation. All infrastructure changes should be planned and reviewed before applying to prevent service disruption.