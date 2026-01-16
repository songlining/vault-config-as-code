# Internal Groups (YAML-managed membership)
# Groups without explicit type field default to internal for backward compatibility
resource "vault_identity_group" "internal_group" {
  for_each                   = local.internal_groups_map
  name                       = each.key
  type                       = "internal"
  external_member_entity_ids = true # Member entity IDs managed externally via vault_identity_group_member_entity_ids
  external_member_group_ids  = true # Member group IDs managed externally via vault_identity_group_member_group_ids
  policies                   = [for i in each.value.identity_group_policies : i]
}

# External Groups (LDAP-synced membership)
# Membership is automatically managed by Vault based on LDAP group membership
resource "vault_identity_group" "external_group" {
  for_each = local.external_groups_map
  name     = each.key
  type     = "external"
  policies = [for i in each.value.identity_group_policies : i]
}

# LDAP Group Alias - links external Vault group to LDAP group
resource "vault_identity_group_alias" "ldap_group_alias" {
  for_each       = var.enable_ldap_auth ? local.external_groups_map : {}
  name           = each.value.ldap_group_name
  mount_accessor = vault_ldap_auth_backend.ldap[0].accessor
  canonical_id   = vault_identity_group.external_group[each.key].id
}

# Internal group members (human identities)
resource "vault_identity_group_member_entity_ids" "human_group" {
  for_each          = local.internal_groups_map
  group_id          = vault_identity_group.internal_group[each.key].id
  member_entity_ids = [for i in each.value.human_identities : vault_identity_entity.human[i].id]
  exclusive         = false
}

# Internal group members (application identities)
resource "vault_identity_group_member_entity_ids" "application_group" {
  for_each          = local.internal_groups_map
  group_id          = vault_identity_group.internal_group[each.key].id
  member_entity_ids = [for i in each.value.application_identities : vault_identity_entity.application[i].id]
  exclusive         = false
}

# Internal group members (LDAP human identities)
resource "vault_identity_group_member_entity_ids" "ldap_human_group" {
  for_each = {
    for name, config in local.internal_groups_map :
    name => config if try(length(config.ldap_human_identities), 0) > 0
  }
  group_id          = vault_identity_group.internal_group[each.key].id
  member_entity_ids = [for i in each.value.ldap_human_identities : vault_identity_entity.ldap_human[i].id]
  exclusive         = false
}

# Sub-groups (supports both internal and external groups as members)
resource "vault_identity_group_member_group_ids" "group_group" {
  for_each = local.internal_groups_map
  group_id = vault_identity_group.internal_group[each.key].id
  member_group_ids = [
    for i in each.value.sub_groups :
    try(vault_identity_group.internal_group[i].id, vault_identity_group.external_group[i].id)
  ]
  exclusive = false
}

