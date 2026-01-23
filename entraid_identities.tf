# EntraID Human Identity Entities
# These are identity entities for users who authenticate via EntraID OIDC
# Each entity can have multiple auth method aliases (OIDC, GitHub, PKI)

resource "vault_identity_entity" "entraid_human" {
  for_each = local.entraid_human_identities_map
  name     = each.key
  disabled = try(each.value.authentication.disabled, false) || try(each.value.identity.status, "active") == "deactivated"
  policies = concat(
    [for i in each.value.policies.identity_policies : i],
    ["human-identity-token-policies"]
  )
  metadata = {
    role              = each.value.identity.role
    team              = each.value.identity.team
    email             = each.value.identity.email
    status            = try(each.value.identity.status, "active")
    entraid_upn       = try(each.value.metadata.entraid_upn, "")
    entraid_object_id = try(each.value.metadata.entraid_object_id, "")
    spiffe_id         = "spiffe://vault/entraid/human/${each.value.identity.role}/${each.value.identity.team}/${each.value.identity.name}"
  }
}

# OIDC Entity Alias - links identity entity to EntraID OIDC authentication
resource "vault_identity_entity_alias" "entraid_human_oidc" {
  for_each       = var.enable_entraid_auth ? local.entraid_human_with_oidc : {}
  mount_accessor = vault_jwt_auth_backend.entraid[0].accessor
  canonical_id   = vault_identity_entity.entraid_human[each.key].id
  name           = each.value.authentication.oidc
}

# GitHub Entity Alias for EntraID users - enables multi-auth support
# EntraID users can also authenticate via GitHub if configured
resource "vault_identity_entity_alias" "entraid_human_github" {
  for_each       = local.entraid_human_with_github
  mount_accessor = vault_github_auth_backend.hashicorp.accessor
  canonical_id   = vault_identity_entity.entraid_human[each.key].id
  name           = each.value.authentication.github
}

# PKI Entity Alias for EntraID users - enables certificate-based authentication
# EntraID users can also authenticate via PKI certificates if configured
resource "vault_identity_entity_alias" "entraid_human_pki" {
  for_each       = local.entraid_human_with_pki
  mount_accessor = vault_auth_backend.cert.accessor
  canonical_id   = vault_identity_entity.entraid_human[each.key].id
  name           = each.value.authentication.pki
}
