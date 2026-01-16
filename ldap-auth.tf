# LDAP Authentication Backend Configuration
# This configures Vault's LDAP auth method for user authentication

resource "vault_ldap_auth_backend" "ldap" {
  count        = var.enable_ldap_auth ? 1 : 0
  path         = "ldap"
  url          = var.ldap_url
  userdn       = var.ldap_userdn
  userattr     = var.ldap_userattr
  groupdn      = var.ldap_groupdn
  groupattr    = var.ldap_groupattr
  groupfilter  = var.ldap_groupfilter
  binddn       = var.ldap_binddn
  bindpass     = var.ldap_bindpass
  starttls     = false
  insecure_tls = true

  # Token settings
  token_ttl     = 3600 * 8      # 8 hours
  token_max_ttl = 3600 * 24 * 7 # 7 days
}
