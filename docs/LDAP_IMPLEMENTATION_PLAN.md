# Plan: Add LDAP User Group Support to Vault-Config-as-Code

## Summary
Add LDAP authentication with external identity groups, enabling hybrid group management (YAML-managed internal groups + LDAP-synced external groups) and full identity entities for LDAP users with multi-auth support.

## User Requirements
- **Target**: Docker OpenLDAP for dev/testing
- **Group Strategy**: Hybrid per-group (each group specifies `type: internal` or `type: external`)
- **Identity Entities**: Full vault_identity_entity for LDAP users with metadata and multi-auth support

---

## Files Overview

### New Files to Create
| File | Purpose |
|------|---------|
| `ldap_variables.tf` | LDAP configuration variables |
| `ldap-auth.tf` | LDAP auth backend resource |
| `ldap_identities.tf` | LDAP user identity entities and aliases |
| `ldap-data/users.ldif` | Sample LDAP directory structure |
| `identities/ldap_human_john_doe.yaml` | Sample LDAP user identity |
| `identities/ldap_human_jane_smith.yaml` | Sample LDAP user with multi-auth |
| `identity_groups/identity_group_ldap_developers.yaml` | Sample external group |
| `identity_groups/identity_group_ldap_admins.yaml` | Sample external group |

### Files to Modify
| File | Changes |
|------|---------|
| `docker-compose.yml` | Add OpenLDAP service |
| `data.tf` | Add LDAP identity filtering, split groups by type |
| `identity_groups.tf` | Handle internal vs external groups, add group aliases |
| `dev.tfvars` | Add LDAP configuration values |

---

## Implementation Steps

### Step 1: docker-compose.yml - Add OpenLDAP

Add after neo4j service:
```yaml
  openldap:
    image: osixia/openldap:1.5.0
    container_name: openldap-vault-config
    environment:
      LDAP_ORGANISATION: "HashiCorp Demo"
      LDAP_DOMAIN: "demo.hashicorp.com"
      LDAP_BASE_DN: "dc=demo,dc=hashicorp,dc=com"
      LDAP_ADMIN_PASSWORD: "${LDAP_ADMIN_PASSWORD:-admin123}"
      LDAP_TLS: "false"
    volumes:
      - ldap-data:/var/lib/ldap
      - ldap-config:/etc/ldap/slapd.d
      - ./ldap-data/users.ldif:/container/service/slapd/assets/config/bootstrap/ldif/custom/users.ldif:ro
    ports:
      - "389:389"
    networks:
      - vault-network
```

Add volumes: `ldap-data`, `ldap-config`

### Step 2: ldap_variables.tf (NEW)

```hcl
variable "enable_ldap_auth" {
  type    = bool
  default = false
}

variable "ldap_url" {
  type    = string
  default = "ldap://openldap-vault-config:389"
}

variable "ldap_userdn" {
  type    = string
  default = "ou=people,dc=demo,dc=hashicorp,dc=com"
}

variable "ldap_groupdn" {
  type    = string
  default = "ou=groups,dc=demo,dc=hashicorp,dc=com"
}

variable "ldap_binddn" {
  type    = string
  default = "cn=admin,dc=demo,dc=hashicorp,dc=com"
}

variable "ldap_bindpass" {
  type      = string
  sensitive = true
  default   = "admin123"
}

variable "ldap_groupfilter" {
  type    = string
  default = "(&(objectClass=groupOfNames)(member={{.UserDN}}))"
}
```

### Step 3: ldap-auth.tf (NEW)

```hcl
resource "vault_ldap_auth_backend" "ldap" {
  count        = var.enable_ldap_auth ? 1 : 0
  path         = "ldap"
  url          = var.ldap_url
  userdn       = var.ldap_userdn
  userattr     = "cn"
  groupdn      = var.ldap_groupdn
  groupattr    = "cn"
  groupfilter  = var.ldap_groupfilter
  binddn       = var.ldap_binddn
  bindpass     = var.ldap_bindpass
  starttls     = false
  insecure_tls = true
  token_ttl     = 3600 * 8
  token_max_ttl = 3600 * 24 * 7
}
```

### Step 4: data.tf - Add Locals

Add to locals block:
```hcl
  # Split groups by type
  internal_groups_map = {
    for name, config in local.identity_groups_map :
    name => config if try(config.type, "internal") == "internal"
  }

  external_groups_map = {
    for name, config in local.identity_groups_map :
    name => config if try(config.type, "") == "external"
  }

  # LDAP human identities (files: ldap_human_*.yaml)
  ldap_human_identities_map = {
    for filename, config in local.configs_by_type.identities :
    config.identity.name => config
    if startswith(basename(filename), "ldap_human_")
  }

  ldap_human_with_ldap = {
    for k, v in local.ldap_human_identities_map :
    k => v if try(v.authentication.ldap, null) != null
  }

  ldap_human_with_github = {
    for k, v in local.ldap_human_identities_map :
    k => v if try(v.authentication.github, null) != null
  }
```

### Step 5: identity_groups.tf - Replace Content

```hcl
# Internal Groups (YAML-managed)
resource "vault_identity_group" "internal_group" {
  for_each                   = local.internal_groups_map
  name                       = each.key
  type                       = "internal"
  external_member_entity_ids = true
  external_member_group_ids  = true
  policies                   = [for i in each.value.identity_group_policies : i]
}

# External Groups (LDAP-synced)
resource "vault_identity_group" "external_group" {
  for_each = local.external_groups_map
  name     = each.key
  type     = "external"
  policies = [for i in each.value.identity_group_policies : i]
}

# LDAP Group Alias
resource "vault_identity_group_alias" "ldap_group_alias" {
  for_each       = var.enable_ldap_auth ? local.external_groups_map : {}
  name           = each.value.ldap_group_name
  mount_accessor = vault_ldap_auth_backend.ldap[0].accessor
  canonical_id   = vault_identity_group.external_group[each.key].id
}

# Internal group members (human)
resource "vault_identity_group_member_entity_ids" "human_group" {
  for_each          = local.internal_groups_map
  group_id          = vault_identity_group.internal_group[each.key].id
  member_entity_ids = [for i in each.value.human_identities : vault_identity_entity.human[i].id]
  exclusive         = false
}

# Internal group members (application)
resource "vault_identity_group_member_entity_ids" "application_group" {
  for_each          = local.internal_groups_map
  group_id          = vault_identity_group.internal_group[each.key].id
  member_entity_ids = [for i in each.value.application_identities : vault_identity_entity.application[i].id]
  exclusive         = false
}

# Sub-groups (supports both internal and external)
resource "vault_identity_group_member_group_ids" "group_group" {
  for_each = local.internal_groups_map
  group_id = vault_identity_group.internal_group[each.key].id
  member_group_ids = [
    for i in each.value.sub_groups :
    try(vault_identity_group.internal_group[i].id, vault_identity_group.external_group[i].id)
  ]
  exclusive = false
}
```

### Step 6: ldap_identities.tf (NEW)

```hcl
resource "vault_identity_entity" "ldap_human" {
  for_each = local.ldap_human_identities_map
  name     = each.key
  policies = concat([for i in each.value.policies.identity_policies : i], ["human-identity-token-policies"])
  metadata = {
    role      = each.value.identity.role
    team      = each.value.identity.team
    email     = each.value.identity.email
    spiffe_id = "spiffe://vault/ldap/human/${each.value.identity.role}/${each.value.identity.team}/${each.value.identity.name}"
  }
}

resource "vault_identity_entity_alias" "ldap_human_ldap" {
  for_each       = var.enable_ldap_auth ? local.ldap_human_with_ldap : {}
  mount_accessor = vault_ldap_auth_backend.ldap[0].accessor
  canonical_id   = vault_identity_entity.ldap_human[each.key].id
  name           = each.value.authentication.ldap
}

resource "vault_identity_entity_alias" "ldap_human_github" {
  for_each       = local.ldap_human_with_github
  mount_accessor = vault_github_auth_backend.hashicorp.accessor
  canonical_id   = vault_identity_entity.ldap_human[each.key].id
  name           = each.value.authentication.github
}
```

### Step 7: Sample YAML Files

**identities/ldap_human_john_doe.yaml**
```yaml
metadata:
  version: "1.0.0"
  created_date: "2025-01-16"
  description: "LDAP Human Identity for John Doe"
identity:
  name: "John Doe"
  email: "john.doe@hashicorp.com"
  role: "developer"
  team: "platform_engineering"
authentication:
  ldap: "john.doe"
policies:
  identity_policies:
    - developer-policy
```

**identity_groups/identity_group_ldap_developers.yaml**
```yaml
name: LDAP Developers
contact: yulei@hashicorp.com
type: external
ldap_group_name: vault-developers
human_identities: []
application_identities: []
sub_groups: []
identity_group_policies:
  - developer-policy
```

### Step 8: dev.tfvars

Add:
```hcl
enable_ldap_auth = true
ldap_url         = "ldap://openldap-vault-config:389"
ldap_userdn      = "ou=people,dc=demo,dc=hashicorp,dc=com"
ldap_groupdn     = "ou=groups,dc=demo,dc=hashicorp,dc=com"
ldap_binddn      = "cn=admin,dc=demo,dc=hashicorp,dc=com"
ldap_bindpass    = "admin123"
```

---

## Verification

```bash
# 1. Start services
docker compose up -d

# 2. Apply Terraform
terraform init && terraform apply -var-file=dev.tfvars

# 3. Test LDAP login
export VAULT_ADDR="http://localhost:8200"
vault login -method=ldap username=john.doe password=password123

# 4. Verify entity created
vault read identity/entity/name/"John Doe"

# 5. Verify group alias
vault read identity/group/name/"LDAP Developers"

# 6. Check token policies
vault token lookup
```

---

## Backward Compatibility
- Groups without `type` field default to `internal` (no changes needed)
- Existing human_* and application_* identity files unchanged
- LDAP is opt-in via `enable_ldap_auth = true`

---

## Appendix: Complete File Contents

### ldap-data/users.ldif (NEW)

```ldif
# Organizational Units
dn: ou=people,dc=demo,dc=hashicorp,dc=com
objectClass: organizationalUnit
ou: people

dn: ou=groups,dc=demo,dc=hashicorp,dc=com
objectClass: organizationalUnit
ou: groups

# Users
dn: cn=john.doe,ou=people,dc=demo,dc=hashicorp,dc=com
objectClass: person
objectClass: organizationalPerson
objectClass: inetOrgPerson
cn: john.doe
sn: Doe
givenName: John
mail: john.doe@hashicorp.com
uid: john.doe
userPassword: password123

dn: cn=jane.smith,ou=people,dc=demo,dc=hashicorp,dc=com
objectClass: person
objectClass: organizationalPerson
objectClass: inetOrgPerson
cn: jane.smith
sn: Smith
givenName: Jane
mail: jane.smith@hashicorp.com
uid: jane.smith
userPassword: password456

dn: cn=admin.user,ou=people,dc=demo,dc=hashicorp,dc=com
objectClass: person
objectClass: organizationalPerson
objectClass: inetOrgPerson
cn: admin.user
sn: User
givenName: Admin
mail: admin.user@hashicorp.com
uid: admin.user
userPassword: admin789

# Groups
dn: cn=vault-admins,ou=groups,dc=demo,dc=hashicorp,dc=com
objectClass: groupOfNames
cn: vault-admins
member: cn=admin.user,ou=people,dc=demo,dc=hashicorp,dc=com

dn: cn=vault-developers,ou=groups,dc=demo,dc=hashicorp,dc=com
objectClass: groupOfNames
cn: vault-developers
member: cn=john.doe,ou=people,dc=demo,dc=hashicorp,dc=com
member: cn=jane.smith,ou=people,dc=demo,dc=hashicorp,dc=com

dn: cn=vault-users,ou=groups,dc=demo,dc=hashicorp,dc=com
objectClass: groupOfNames
cn: vault-users
member: cn=john.doe,ou=people,dc=demo,dc=hashicorp,dc=com
member: cn=jane.smith,ou=people,dc=demo,dc=hashicorp,dc=com
member: cn=admin.user,ou=people,dc=demo,dc=hashicorp,dc=com
```

### identities/ldap_human_jane_smith.yaml (NEW)

```yaml
metadata:
  version: "1.0.0"
  created_date: "2025-01-16"
  description: "LDAP Human Identity for Jane Smith with multi-auth"

identity:
  name: "Jane Smith"
  email: "jane.smith@hashicorp.com"
  role: "developer"
  team: "platform_engineering"

authentication:
  ldap: "jane.smith"
  github: "janesmith"  # Multi-auth: can also use GitHub

policies:
  identity_policies:
    - developer-policy
```

### identities/ldap_human_admin_user.yaml (NEW)

```yaml
metadata:
  version: "1.0.0"
  created_date: "2025-01-16"
  description: "LDAP Admin User"

identity:
  name: "Admin User"
  email: "admin.user@hashicorp.com"
  role: "admin"
  team: "platform_engineering"

authentication:
  ldap: "admin.user"

policies:
  identity_policies:
    - super-user
```

### identity_groups/identity_group_ldap_admins.yaml (NEW)

```yaml
name: LDAP Admins
contact: yulei@hashicorp.com
type: external
ldap_group_name: vault-admins
human_identities: []
application_identities: []
sub_groups: []
identity_group_policies:
  - super-user
```

### identity_groups/identity_group_ldap_users.yaml (NEW)

```yaml
name: LDAP Users
contact: yulei@hashicorp.com
type: external
ldap_group_name: vault-users
human_identities: []
application_identities: []
sub_groups: []
identity_group_policies:
  - human-identity-token-policies
```

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         LDAP Authentication Flow                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   ┌──────────────┐        ┌──────────────┐        ┌──────────────┐     │
│   │   OpenLDAP   │        │    Vault     │        │  Terraform   │     │
│   │   (Docker)   │        │   LDAP Auth  │        │    Config    │     │
│   └──────┬───────┘        └──────┬───────┘        └──────┬───────┘     │
│          │                       │                       │              │
│   Users: │                       │                       │              │
│   - john.doe                     │                       │              │
│   - jane.smith          vault_ldap_auth_backend    ldap_variables.tf   │
│   - admin.user                   │                 ldap-auth.tf        │
│          │                       │                       │              │
│   Groups:│                       │                       │              │
│   - vault-developers             │                       │              │
│   - vault-admins        ┌────────▼────────┐              │              │
│   - vault-users         │ External Groups │◄─────────────┘              │
│          │              │ (type=external) │                             │
│          │              └────────┬────────┘                             │
│          │                       │                                      │
│          │              vault_identity_group_alias                      │
│          │                       │                                      │
│          │              ┌────────▼────────┐                             │
│          └──────────────► LDAP Group Name │                             │
│                         │ (vault-devs)    │                             │
│                         └────────┬────────┘                             │
│                                  │                                      │
│                         ┌────────▼────────┐                             │
│                         │    Policies     │                             │
│                         │ (developer-pol) │                             │
│                         └─────────────────┘                             │
│                                                                          │
├─────────────────────────────────────────────────────────────────────────┤
│                         LDAP User Identity Flow                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   ┌───────────────────┐     ┌───────────────────┐                       │
│   │ ldap_human_*.yaml │     │ vault_identity_   │                       │
│   │ (identities/)     │────►│ entity.ldap_human │                       │
│   └───────────────────┘     └─────────┬─────────┘                       │
│                                       │                                  │
│                              ┌────────┴────────┐                        │
│                              ▼                 ▼                         │
│                    ┌─────────────────┐ ┌─────────────────┐              │
│                    │ LDAP Alias      │ │ GitHub Alias    │              │
│                    │ (ldap mount)    │ │ (multi-auth)    │              │
│                    └─────────────────┘ └─────────────────┘              │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Key Concepts

### Internal vs External Groups

| Aspect | Internal Group | External Group |
|--------|---------------|----------------|
| **Type** | `type = "internal"` | `type = "external"` |
| **Membership** | YAML-defined (`human_identities`) | LDAP-synced via group alias |
| **Updates** | Requires `terraform apply` | Automatic on LDAP login |
| **Use Case** | Fine-grained control | AD/LDAP integration |

### LDAP User Identity Flow

1. YAML file `identities/ldap_human_*.yaml` defines user metadata
2. Terraform creates `vault_identity_entity.ldap_human`
3. Entity alias links LDAP username to entity
4. On LDAP login, Vault resolves entity → applies policies + metadata
5. Group membership comes from LDAP group → external group alias chain

### Multi-Auth Support

LDAP users can optionally have additional auth methods:
```yaml
authentication:
  ldap: "jane.smith"      # Primary: LDAP
  github: "janesmith"     # Secondary: GitHub (same identity entity)
```

Both auth methods resolve to the same identity entity, providing:
- Unified audit trail
- Consistent metadata
- Merged group memberships
