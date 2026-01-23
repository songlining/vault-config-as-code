# EntraID (Microsoft Entra ID) OIDC Authentication Variables
# These variables configure the EntraID OIDC auth backend for Vault

variable "enable_entraid_auth" {
  description = "Enable EntraID OIDC authentication backend"
  type        = bool
  default     = false
}

variable "entraid_tenant_id" {
  description = "EntraID (Azure AD) tenant ID for OIDC discovery URL"
  type        = string
  default     = ""
}

variable "entraid_client_id" {
  description = "EntraID application (client) ID for OIDC authentication"
  type        = string
  sensitive   = true
  default     = ""
}

variable "entraid_client_secret" {
  description = "EntraID application client secret for OIDC authentication"
  type        = string
  sensitive   = true
  default     = ""
}

variable "entraid_oidc_scopes" {
  description = "OIDC scopes to request from EntraID during authentication"
  type        = list(string)
  default     = ["openid", "profile", "email"]
}
