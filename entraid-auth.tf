# EntraID OIDC Authentication Backend Configuration
# This configures Vault's OIDC auth method for Microsoft EntraID user authentication

resource "vault_jwt_auth_backend" "entraid" {
  count               = var.enable_entraid_auth ? 1 : 0
  description         = "OIDC auth method for Microsoft EntraID"
  type                = "oidc"
  path                = "oidc"
  oidc_discovery_url  = "https://login.microsoftonline.com/${var.entraid_tenant_id}/v2.0"
  bound_issuer        = "https://sts.windows.net/${var.entraid_tenant_id}/"
  oidc_client_id      = var.entraid_client_id
  oidc_client_secret  = var.entraid_client_secret
  default_role        = "entraid_user"
}

resource "vault_jwt_auth_backend_role" "entraid_user" {
  backend         = vault_jwt_auth_backend.entraid[0].path
  role_name       = "entraid_user"
  user_claim      = "email"
  groups_claim    = "groups"
  allowed_redirect_uris = [
    "${var.vault_url}/ui/vault/auth/oidc/oidc/callback",
    "${var.vault_url}/v1/auth/oidc/oidc/callback",
  ]
  role_type       = "oidc"
  token_ttl       = 3600 * 8        # 8 hours
  token_max_ttl   = 3600 * 24 * 7   # 168 hours (7 days)
  oidc_scopes     = var.entraid_oidc_scopes
}
