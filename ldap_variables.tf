# LDAP Authentication Variables
# These variables configure the LDAP auth backend for Vault

variable "enable_ldap_auth" {
  description = "Enable LDAP authentication backend"
  type        = bool
  default     = false
}

variable "ldap_url" {
  description = "LDAP server URL"
  type        = string
  default     = "ldap://openldap-vault-config:389"
}

variable "ldap_userdn" {
  description = "Base DN for user lookups"
  type        = string
  default     = "ou=people,dc=demo,dc=hashicorp,dc=com"
}

variable "ldap_groupdn" {
  description = "Base DN for group lookups"
  type        = string
  default     = "ou=groups,dc=demo,dc=hashicorp,dc=com"
}

variable "ldap_binddn" {
  description = "DN for binding to LDAP (service account)"
  type        = string
  default     = "cn=admin,dc=demo,dc=hashicorp,dc=com"
}

variable "ldap_bindpass" {
  description = "Password for LDAP bind DN"
  type        = string
  sensitive   = true
  default     = "admin123"
}

variable "ldap_userattr" {
  description = "Attribute used for user matching"
  type        = string
  default     = "cn"
}

variable "ldap_groupattr" {
  description = "Attribute for group names"
  type        = string
  default     = "cn"
}

variable "ldap_groupfilter" {
  description = "LDAP filter for group membership lookup"
  type        = string
  default     = "(&(objectClass=groupOfNames)(member={{.UserDN}}))"
}
