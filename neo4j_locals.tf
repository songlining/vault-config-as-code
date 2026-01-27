# Neo4j Graph Data Transformation Locals
# These locals flatten and transform the YAML-driven identity data into formats
# suitable for creating graph database nodes and relationships

locals {
  # Combined human identities map for Neo4j (regular + EntraID)
  all_human_identities_map = merge(local.human_identities_map, local.entraid_human_identities_map)

  # Flatten human-to-group memberships for easy relationship creation (regular humans)
  human_group_memberships = flatten([
    for group_name, group_config in local.identity_groups_map : [
      for human_name in try(group_config.human_identities, []) : {
        human_name    = human_name
        group_name    = group_name
        key           = "${human_name}__${group_name}"
        identity_type = "regular"
      }
    ]
  ])

  # Flatten EntraID human-to-group memberships
  entraid_human_group_memberships = flatten([
    for group_name, group_config in local.identity_groups_map : [
      for human_name in try(group_config.entraid_human_identities, []) : {
        human_name    = human_name
        group_name    = group_name
        key           = "${human_name}__${group_name}_entraid"
        identity_type = "entraid"
      }
    ]
  ])

  # Combined human group memberships
  all_human_group_memberships = concat(local.human_group_memberships, local.entraid_human_group_memberships)

  # Flatten application-to-group memberships
  app_group_memberships = flatten([
    for group_name, group_config in local.identity_groups_map : [
      for app_name in group_config.application_identities : {
        app_name   = app_name
        group_name = group_name
        key        = "${app_name}__${group_name}"
      }
    ]
  ])

  # Flatten group-to-subgroup relationships
  group_subgroup_relationships = flatten([
    for group_name, group_config in local.identity_groups_map : [
      for subgroup_name in group_config.sub_groups : {
        parent_group = group_name
        subgroup     = subgroup_name
        key          = "${group_name}__${subgroup_name}"
      }
    ]
  ])

  # Extract all unique policies from identities and groups
  all_policies = distinct(concat(
    # Policies from regular human identities
    flatten([
      for human_name, human in local.human_identities_map :
      human.policies.identity_policies
    ]),
    # Policies from EntraID human identities  
    flatten([
      for human_name, human in local.entraid_human_identities_map :
      human.policies.identity_policies
    ]),
    # Policies from application identities
    flatten([
      for app_name, app in local.application_identities_map :
      app.policies.identity_policies
    ]),
    # Policies from identity groups
    flatten([
      for group_name, group in local.identity_groups_map :
      group.identity_group_policies
    ])
  ))

  # Map regular human identities to their policies for relationship creation
  human_policy_relationships = flatten([
    for human_name, human in local.human_identities_map : [
      for policy in human.policies.identity_policies : {
        human_name    = human_name
        policy_name   = policy
        key           = "${human_name}__${policy}"
        identity_type = "regular"
      }
    ]
  ])

  # Map EntraID human identities to their policies
  entraid_human_policy_relationships = flatten([
    for human_name, human in local.entraid_human_identities_map : [
      for policy in human.policies.identity_policies : {
        human_name    = human_name
        policy_name   = policy
        key           = "${human_name}__${policy}_entraid"
        identity_type = "entraid"
      }
    ]
  ])

  # Combined human policy relationships
  all_human_policy_relationships = concat(local.human_policy_relationships, local.entraid_human_policy_relationships)

  # Map application identities to their policies
  app_policy_relationships = flatten([
    for app_name, app in local.application_identities_map : [
      for policy in app.policies.identity_policies : {
        app_name    = app_name
        policy_name = policy
        key         = "${app_name}__${policy}"
      }
    ]
  ])

  # Map groups to their policies
  group_policy_relationships = flatten([
    for group_name, group in local.identity_groups_map : [
      for policy in group.identity_group_policies : {
        group_name  = group_name
        policy_name = policy
        key         = "${group_name}__${policy}"
      }
    ]
  ])

  # Create auth method metadata
  auth_methods = {
    github = {
      type         = "github"
      mount_path   = "github"
      accessor     = try(vault_github_auth_backend.hashicorp.accessor, "")
      organization = "hashicorp"
    }
    pki = {
      type       = "pki"
      mount_path = "cert"
      accessor   = try(vault_auth_backend.cert.accessor, "")
    }
    aws = {
      type       = "aws"
      mount_path = "aws"
      accessor   = try(vault_auth_backend.aws.accessor, "")
    }
    github_repo_jwt = {
      type       = "jwt"
      mount_path = "github_repo_jwt"
      accessor   = try(vault_jwt_auth_backend.github_repo_jwt.accessor, "")
    }
    terraform_cloud = {
      type       = "jwt"
      mount_path = "terraform_cloud"
      accessor   = try(vault_jwt_auth_backend.terraform_cloud.accessor, "")
    }
    approle = {
      type       = "approle"
      mount_path = "approle"
      accessor   = try(vault_auth_backend.approle.accessor, "")
    }
    oidc = {
      type       = "oidc"
      mount_path = "oidc"
      accessor   = try(vault_jwt_auth_backend.entraid[0].accessor, "")
    }
  }

  # Map humans to their GitHub authentication
  human_github_auth = [
    for human_name, human in local.human_with_github : {
      human_name = human_name
      username   = human.authentication.github
      key        = "${human_name}__github"
    }
  ]

  # Map humans to their PKI authentication
  human_pki_auth = [
    for human_name, human in local.human_with_pki : {
      human_name = human_name
      cert_cn    = human.authentication.pki
      key        = "${human_name}__pki"
    }
  ]

  # Map EntraID humans to their OIDC authentication
  entraid_human_oidc_auth = [
    for human_name, human in local.entraid_human_with_oidc : {
      human_name = human_name
      username   = human.authentication.oidc
      key        = "${human_name}__oidc"
    }
  ]

  # Map applications to their PKI authentication
  app_pki_auth = [
    for app_name, app in local.app_with_pki : {
      app_name = app_name
      cert_cn  = app.authentication.pki
      key      = "${app_name}__pki"
    }
  ]

  # Map applications to their GitHub repo authentication
  app_github_repo_auth = [
    for app_name, app in local.app_with_github_repo : {
      app_name = app_name
      repo     = app.authentication.github_repo
      key      = "${app_name}__github_repo"
    }
  ]

  # Map applications to their Terraform Cloud workspace authentication
  app_tfc_auth = [
    for app_name, app in local.app_with_tfc_workspace : {
      app_name  = app_name
      workspace = app.authentication.tfc_workspace
      key       = "${app_name}__tfc"
    }
  ]

  # Map applications to their AWS auth role
  app_aws_auth = [
    for app_name, app in local.application_identities_map : {
      app_name = app_name
      role     = app.authentication.aws_auth_role
      key      = "${app_name}__aws"
    }
    if try(app.authentication.aws_auth_role, "") != ""
  ]
}
