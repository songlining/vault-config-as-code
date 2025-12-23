# vault-config-as-code

This repository demonstrates HashiCorp Vault configuration management using Terraform, implementing Infrastructure as Code principles for stateful security services. The project showcases enterprise-grade patterns for managing Vault policies, authentication methods, PKI infrastructure, and application secrets across multiple environments.

## Challenges

Vault is a stateful application, meaning it needs to preserve its configurations into its backend storage. Vault can be configured via the UI, CLI or API. However, these methods are not ideal for managing configuration in a version controlled way. This repository shows how to manage Vault configuration using Terraform.

Terraform is a tool for building, changing, and versioning infrastructure safely and efficiently. In essence, it is a tool that converts what you want to CRUD operations on the target system, and store the state in its statefile.

## Prerequisites

- Terraform >= 1.10.0
- HashiCorp Vault Enterprise (running instance)
- Python 3.x (for identity validation)
- pre-commit (optional, for code quality hooks)

## Use Cases Implemented

### KV Secrets Engine
Application-specific secret storage with environment-based separation using Terraform modules for multi-tenant secret management. Each application gets dedicated KV v2 mounts per environment with granular policies for secret providers and consumers.

### Transit Secrets Engine
Encryption-as-a-Service for protecting streaming data platforms (Kafka, Kinesis, Pub/Sub) with centralized key management, seamless rotation, and DEK patterns for large payloads. Eliminates the need for applications to directly manage encryption keys while providing consistent encryption across platforms.

### PKI Secrets Engine
Two-tier certificate authority infrastructure (root + intermediate CA) enabling certificate-based machine/human identity verification and mTLS authentication. Supports automated certificate lifecycle management with configurable TTLs and revocation capabilities.

### Identity Engine
OIDC identity provider generating cryptographically signed JWT tokens with rich metadata for zero-trust authentication. Supports API gateway integration and SPIFFE-compliant workload identity with RS256 signing, automatic key rotation, and audience-specific token validation.

### Authentication Methods
Multi-modal authentication supporting GitHub OAuth for human users, AWS IAM roles for cloud services, AppRole for application authentication, and PKI certificate-based authentication for machine identities.

### Namespace Management
Multi-tenant isolation with delegated administration and environment-specific policy enforcement. Each namespace provides complete administrative control while maintaining security boundaries between tenants.

## Quick Start

1. Ensure you have a running Vault Enterprise instance and set the required environment variables:
```bash
export VAULT_LICENSE="your-vault-enterprise-license"
export VAULT_ADDR="https://your-vault-instance:8200"
export VAULT_TOKEN="your-vault-token"
```

2. Initialize and apply Terraform configuration:
```bash
terraform init
terraform plan -var-file=dev.tfvars
terraform apply -var-file=dev.tfvars
```

## Usage

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

Validate YAML identity configurations:
```bash
cd identities
python3 validate_identities.py
```

### Pre-commit Hooks

The repository uses pre-commit hooks for code quality:
- `terraform_fmt`: Format Terraform code
- `terraform_tflint`: Lint Terraform code
- `terraform_trivy`: Security scanning
- `terraform_validate`: Validate Terraform configuration

Install and run hooks:
```bash
pre-commit install
pre-commit run --all-files
```

## Architecture

### Core Components

- **Main Configuration** ([main.tf](main.tf)): Super-user policies and GitHub auth backend configuration
- **Terraform Modules**:
  - `applications` module: Creates KV v2 mounts and policies per application/environment
  - `vault_namespace` module: Manages Vault namespaces with admin tokens and policies
- **Identity Management**: YAML-driven identity configuration with Python validation scripts
- **PKI Infrastructure**: Certificate authority setup and role management for machine/human identities

### Key Files

- [versions.tf](versions.tf): Provider versions (Terraform ~1.10.0, Vault ~5.1.0, TLS ~4.0.6)
- [variables.tf](variables.tf): Required variables include `vault_url` and `environment`
- [data.tf](data.tf): Data sources for dynamic configuration
- [provider.tf](provider.tf): Vault provider configuration
- [backend-local.tf](backend-local.tf): Terraform state backend configuration

## Configuration Patterns

### Module Usage

Applications are provisioned via the `applications` module with environment-specific KV mounts. Each application gets separate secret-provider and secret-consumer policies. Namespaces follow the pattern `module.vault_namespace` for tenant isolation.

### Policy Management

- **Super-user policy**: Provides broad Vault administration capabilities
- **Application policies**: Follow least-privilege with separate read/write permissions
- **Namespace admin policies**: Enable delegated administration

### Authentication Flow

- **GitHub OAuth**: For human users (requires HashiCorp organization membership)
- **AWS IAM roles**: For service authentication
- **PKI certificates**: For machine identity verification
- Token rotation configured for 30-day cycles

## Environment Variables

Required for Vault Enterprise:
- `VAULT_LICENSE`: Enterprise license key
- `VAULT_ADDR`: Vault server URL
- `VAULT_TOKEN`: Authentication token

Configure environment-specific variables in `*.tfvars` files.

## Testing and Validation

All infrastructure changes should be planned and reviewed before applying to prevent service disruption:

1. Run `terraform plan` to preview changes
2. Validate identity configurations with Python scripts
3. Review policy changes for security implications
4. Test in development environment before applying to production

## Contributing

1. Install pre-commit hooks: `pre-commit install`
2. Format code: `terraform fmt`
3. Validate changes: `terraform validate`
4. Run all pre-commit checks: `pre-commit run --all-files`
5. Submit pull request with clear description of changes

## Support

For issues and questions, please open an issue in the repository.
