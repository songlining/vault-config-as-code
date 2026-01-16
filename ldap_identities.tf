# LDAP Human Identity Entities
# These are identity entities for users who authenticate via LDAP
# Each entity can have multiple auth method aliases (LDAP, GitHub, etc.)

resource "vault_identity_entity" "ldap_human" {
  for_each = local.ldap_human_identities_map
  name     = each.key
  policies = concat(
    [for i in each.value.policies.identity_policies : i],
    ["human-identity-token-policies"]
  )
  metadata = {
    role      = each.value.identity.role
    team      = each.value.identity.team
    email     = each.value.identity.email
    spiffe_id = "spiffe://vault/ldap/human/${each.value.identity.role}/${each.value.identity.team}/${each.value.identity.name}"
  }
}

# LDAP Entity Alias - links identity entity to LDAP authentication
resource "vault_identity_entity_alias" "ldap_human_ldap" {
  for_each       = var.enable_ldap_auth ? local.ldap_human_with_ldap : {}
  mount_accessor = vault_ldap_auth_backend.ldap[0].accessor
  canonical_id   = vault_identity_entity.ldap_human[each.key].id
  name           = each.value.authentication.ldap
}

# GitHub Entity Alias for LDAP users - enables multi-auth support
# LDAP users can also authenticate via GitHub if configured
resource "vault_identity_entity_alias" "ldap_human_github" {
  for_each       = local.ldap_human_with_github
  mount_accessor = vault_github_auth_backend.hashicorp.accessor
  canonical_id   = vault_identity_entity.ldap_human[each.key].id
  name           = each.value.authentication.github
}
