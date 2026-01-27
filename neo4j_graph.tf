# Neo4j Graph Database Resources
# Creates nodes and relationships in Neo4j to visualize Vault identity hierarchy
#
# Graph Model:
#   Nodes: HumanIdentity, ApplicationIdentity, IdentityGroup, Policy, AuthMethod
#   Relationships: MEMBER_OF, HAS_SUBGROUP, HAS_POLICY, AUTHENTICATES_VIA

# Clear existing graph data and create constraints/indexes
resource "null_resource" "neo4j_initialize" {
  count = var.enable_neo4j_integration ? 1 : 0

  depends_on = [null_resource.neo4j_connectivity_check]

  provisioner "local-exec" {
    command = <<-EOT
      docker exec neo4j-vault-graph cypher-shell -u ${var.neo4j_username} -p ${var.neo4j_password} <<'CYPHER'
      // Clear all existing data
      MATCH (n) DETACH DELETE n;

      // Create constraints for uniqueness
      CREATE CONSTRAINT human_identity_name IF NOT EXISTS FOR (h:HumanIdentity) REQUIRE h.name IS UNIQUE;
      CREATE CONSTRAINT app_identity_name IF NOT EXISTS FOR (a:ApplicationIdentity) REQUIRE a.name IS UNIQUE;
      CREATE CONSTRAINT group_name IF NOT EXISTS FOR (g:IdentityGroup) REQUIRE g.name IS UNIQUE;
      CREATE CONSTRAINT policy_name IF NOT EXISTS FOR (p:Policy) REQUIRE p.name IS UNIQUE;
      CREATE CONSTRAINT auth_method_type IF NOT EXISTS FOR (a:AuthMethod) REQUIRE a.type IS UNIQUE;

      // Create indexes for performance
      CREATE INDEX human_vault_id IF NOT EXISTS FOR (h:HumanIdentity) ON (h.vault_id);
      CREATE INDEX app_vault_id IF NOT EXISTS FOR (a:ApplicationIdentity) ON (a.vault_id);
      CREATE INDEX group_vault_id IF NOT EXISTS FOR (g:IdentityGroup) ON (g.vault_id);
CYPHER
    EOT
  }

  triggers = {
    # Re-initialize if any identity configuration changes
    human_identities         = jsonencode(local.human_identities_map)
    entraid_human_identities = jsonencode(local.entraid_human_identities_map)
    app_identities           = jsonencode(local.application_identities_map)
    groups                   = jsonencode(local.identity_groups_map)
  }
}

# Create Regular Human Identity nodes
resource "null_resource" "neo4j_human_identities" {
  for_each = var.enable_neo4j_integration ? local.human_identities_map : {}

  depends_on = [null_resource.neo4j_initialize]

  provisioner "local-exec" {
    command = <<-EOT
      docker exec neo4j-vault-graph cypher-shell -u ${var.neo4j_username} -p ${var.neo4j_password} <<'CYPHER'
      MERGE (h:Identity:HumanIdentity {name: "${each.value.identity.name}"})
      SET h.email = "${each.value.identity.email}",
          h.role = "${each.value.identity.role}",
          h.team = "${each.value.identity.team}",
          h.github_username = "${try(each.value.authentication.github, "")}",
          h.pki_cert = "${try(each.value.authentication.pki, "")}",
          h.vault_id = "${vault_identity_entity.human[each.key].id}",
          h.spiffe_id = "spiffe://vault/human/${each.value.identity.role}/${each.value.identity.team}/${each.value.identity.name}",
          h.identity_type = "regular";
CYPHER
    EOT
  }

  triggers = {
    config = jsonencode(each.value)
  }
}

# Create EntraID Human Identity nodes
resource "null_resource" "neo4j_entraid_human_identities" {
  for_each = var.enable_neo4j_integration ? local.entraid_human_identities_map : {}

  depends_on = [null_resource.neo4j_initialize]

  provisioner "local-exec" {
    command = <<-EOT
      docker exec neo4j-vault-graph cypher-shell -u ${var.neo4j_username} -p ${var.neo4j_password} <<'CYPHER'
      MERGE (h:Identity:HumanIdentity {name: "${each.value.identity.name}"})
      SET h.email = "${each.value.identity.email}",
          h.role = "${each.value.identity.role}",
          h.team = "${each.value.identity.team}",
          h.oidc_auth = "${try(each.value.authentication.oidc, "")}",
          h.vault_id = "${vault_identity_entity.entraid_human[each.key].id}",
          h.spiffe_id = "spiffe://vault/entraid/human/${each.value.identity.role}/${each.value.identity.team}/${each.value.identity.name}",
          h.entraid_object_id = "${try(each.value.identity.entraid_object_id, "")}",
          h.entraid_upn = "${try(each.value.identity.entraid_upn, "")}",
          h.status = "${try(each.value.identity.status, "active")}",
          h.disabled = ${try(each.value.identity.disabled, false)},
          h.provisioned_via_scim = ${try(each.value.identity.provisioned_via_scim, false)},
          h.identity_type = "entraid";
CYPHER
    EOT
  }

  triggers = {
    config = jsonencode(each.value)
  }
}

# Create Application Identity nodes
resource "null_resource" "neo4j_app_identities" {
  for_each = var.enable_neo4j_integration ? local.application_identities_map : {}

  depends_on = [null_resource.neo4j_initialize]

  provisioner "local-exec" {
    command = <<-EOT
      docker exec neo4j-vault-graph cypher-shell -u ${var.neo4j_username} -p ${var.neo4j_password} <<'CYPHER'
      MERGE (a:Identity:ApplicationIdentity {name: "${each.value.identity.name}"})
      SET a.contact = "${each.value.identity.contact}",
          a.environment = "${each.value.identity.environment}",
          a.business_unit = "${each.value.identity.business_unit}",
          a.aws_auth_role = "${try(each.value.authentication.aws_auth_role, "")}",
          a.pki_cert = "${try(each.value.authentication.pki, "")}",
          a.github_repo = "${try(each.value.authentication.github_repo, "")}",
          a.tfc_workspace = "${try(each.value.authentication.tfc_workspace, "")}",
          a.vault_id = "${vault_identity_entity.application[each.key].id}",
          a.spiffe_id = "spiffe://vault/application/${each.value.identity.environment}/${each.value.identity.business_unit}/${each.value.identity.name}";
CYPHER
    EOT
  }

  triggers = {
    config = jsonencode(each.value)
  }
}

# Create Identity Group nodes (internal groups)
resource "null_resource" "neo4j_internal_identity_groups" {
  for_each = var.enable_neo4j_integration ? local.internal_groups_map : {}

  depends_on = [null_resource.neo4j_initialize]

  provisioner "local-exec" {
    command = <<-EOT
      docker exec neo4j-vault-graph cypher-shell -u ${var.neo4j_username} -p ${var.neo4j_password} <<'CYPHER'
      MERGE (g:IdentityGroup {name: "${each.key}"})
      SET g.contact = "${each.value.contact}",
          g.type = "internal",
          g.vault_id = "${vault_identity_group.internal_group[each.key].id}",
          g.policies = ${jsonencode(each.value.identity_group_policies)};
CYPHER
    EOT
  }

  triggers = {
    config = jsonencode(each.value)
  }
}

# Create Identity Group nodes (external groups)
resource "null_resource" "neo4j_external_identity_groups" {
  for_each = var.enable_neo4j_integration ? local.external_groups_map : {}

  depends_on = [null_resource.neo4j_initialize]

  provisioner "local-exec" {
    command = <<-EOT
      docker exec neo4j-vault-graph cypher-shell -u ${var.neo4j_username} -p ${var.neo4j_password} <<'CYPHER'
      MERGE (g:IdentityGroup {name: "${each.key}"})
      SET g.contact = "${each.value.contact}",
          g.type = "external",
          g.ldap_group_name = "${try(each.value.ldap_group_name, "")}",
          g.vault_id = "${vault_identity_group.external_group[each.key].id}",
          g.policies = ${jsonencode(each.value.identity_group_policies)};
CYPHER
    EOT
  }

  triggers = {
    config = jsonencode(each.value)
  }
}

# Create Policy nodes
resource "null_resource" "neo4j_policies" {
  for_each = var.enable_neo4j_integration ? toset(local.all_policies) : []

  depends_on = [null_resource.neo4j_initialize]

  provisioner "local-exec" {
    command = <<-EOT
      docker exec neo4j-vault-graph cypher-shell -u ${var.neo4j_username} -p ${var.neo4j_password} <<'CYPHER'
      MERGE (p:Policy {name: "${each.key}"});
CYPHER
    EOT
  }
}

# Create Auth Method nodes
resource "null_resource" "neo4j_auth_methods" {
  for_each = var.enable_neo4j_integration ? local.auth_methods : {}

  depends_on = [null_resource.neo4j_initialize]

  provisioner "local-exec" {
    command = <<-EOT
      docker exec neo4j-vault-graph cypher-shell -u ${var.neo4j_username} -p ${var.neo4j_password} <<'CYPHER'
      MERGE (a:AuthMethod {type: "${each.value.type}"})
      SET a.mount_path = "${each.value.mount_path}",
          a.accessor = "${each.value.accessor}";
CYPHER
    EOT
  }

  triggers = {
    config = jsonencode(each.value)
  }
}

# Create Human -> Group MEMBER_OF relationships (regular humans)
resource "null_resource" "neo4j_human_group_relationships" {
  for_each = var.enable_neo4j_integration ? { for m in local.human_group_memberships : m.key => m } : {}

  depends_on = [
    null_resource.neo4j_human_identities,
    null_resource.neo4j_internal_identity_groups,
    null_resource.neo4j_external_identity_groups
  ]

  provisioner "local-exec" {
    command = <<-EOT
      docker exec neo4j-vault-graph cypher-shell -u ${var.neo4j_username} -p ${var.neo4j_password} <<'CYPHER'
      MATCH (h:HumanIdentity {name: "${each.value.human_name}", identity_type: "regular"})
      MATCH (g:IdentityGroup {name: "${each.value.group_name}"})
      MERGE (h)-[:MEMBER_OF]->(g);
CYPHER
    EOT
  }
}

# Create EntraID Human -> Group MEMBER_OF relationships 
resource "null_resource" "neo4j_entraid_human_group_relationships" {
  for_each = var.enable_neo4j_integration ? { for m in local.entraid_human_group_memberships : m.key => m } : tomap({})

  depends_on = [
    null_resource.neo4j_entraid_human_identities,
    null_resource.neo4j_internal_identity_groups,
    null_resource.neo4j_external_identity_groups
  ]

  provisioner "local-exec" {
    command = <<-EOT
      docker exec neo4j-vault-graph cypher-shell -u ${var.neo4j_username} -p ${var.neo4j_password} <<'CYPHER'
      MATCH (h:HumanIdentity {name: "${each.value.human_name}", identity_type: "entraid"})
      MATCH (g:IdentityGroup {name: "${each.value.group_name}"})
      MERGE (h)-[:MEMBER_OF]->(g);
CYPHER
    EOT
  }
}

# Create Application -> Group MEMBER_OF relationships
resource "null_resource" "neo4j_app_group_relationships" {
  for_each = var.enable_neo4j_integration ? { for m in local.app_group_memberships : m.key => m } : tomap({})

  depends_on = [
    null_resource.neo4j_app_identities,
    null_resource.neo4j_internal_identity_groups,
    null_resource.neo4j_external_identity_groups
  ]

  provisioner "local-exec" {
    command = <<-EOT
      docker exec neo4j-vault-graph cypher-shell -u ${var.neo4j_username} -p ${var.neo4j_password} <<'CYPHER'
      MATCH (a:ApplicationIdentity {name: "${each.value.app_name}"})
      MATCH (g:IdentityGroup {name: "${each.value.group_name}"})
      MERGE (a)-[:MEMBER_OF]->(g);
CYPHER
    EOT
  }
}

# Create Group -> Subgroup HAS_SUBGROUP relationships
resource "null_resource" "neo4j_group_subgroup_relationships" {
  for_each = var.enable_neo4j_integration ? { for r in local.group_subgroup_relationships : r.key => r } : tomap({})

  depends_on = [
    null_resource.neo4j_internal_identity_groups,
    null_resource.neo4j_external_identity_groups
  ]

  provisioner "local-exec" {
    command = <<-EOT
      docker exec neo4j-vault-graph cypher-shell -u ${var.neo4j_username} -p ${var.neo4j_password} <<'CYPHER'
      MATCH (parent:IdentityGroup {name: "${each.value.parent_group}"})
      MATCH (sub:IdentityGroup {name: "${each.value.subgroup}"})
      MERGE (parent)-[:HAS_SUBGROUP]->(sub);
CYPHER
    EOT
  }
}

# Create Regular Human -> Policy HAS_POLICY relationships
resource "null_resource" "neo4j_human_policy_relationships" {
  for_each = var.enable_neo4j_integration ? { for r in local.human_policy_relationships : r.key => r } : tomap({})

  depends_on = [
    null_resource.neo4j_human_identities,
    null_resource.neo4j_policies
  ]

  provisioner "local-exec" {
    command = <<-EOT
      docker exec neo4j-vault-graph cypher-shell -u ${var.neo4j_username} -p ${var.neo4j_password} <<'CYPHER'
      MATCH (h:HumanIdentity {name: "${each.value.human_name}", identity_type: "regular"})
      MATCH (p:Policy {name: "${each.value.policy_name}"})
      MERGE (h)-[:HAS_POLICY]->(p);
CYPHER
    EOT
  }
}

# Create EntraID Human -> Policy HAS_POLICY relationships
resource "null_resource" "neo4j_entraid_human_policy_relationships" {
  for_each = var.enable_neo4j_integration ? { for r in local.entraid_human_policy_relationships : r.key => r } : tomap({})

  depends_on = [
    null_resource.neo4j_entraid_human_identities,
    null_resource.neo4j_policies
  ]

  provisioner "local-exec" {
    command = <<-EOT
      docker exec neo4j-vault-graph cypher-shell -u ${var.neo4j_username} -p ${var.neo4j_password} <<'CYPHER'
      MATCH (h:HumanIdentity {name: "${each.value.human_name}", identity_type: "entraid"})
      MATCH (p:Policy {name: "${each.value.policy_name}"})
      MERGE (h)-[:HAS_POLICY]->(p);
CYPHER
    EOT
  }
}

# Create Application -> Policy HAS_POLICY relationships
resource "null_resource" "neo4j_app_policy_relationships" {
  for_each = var.enable_neo4j_integration ? { for r in local.app_policy_relationships : r.key => r } : tomap({})

  depends_on = [
    null_resource.neo4j_app_identities,
    null_resource.neo4j_policies
  ]

  provisioner "local-exec" {
    command = <<-EOT
      docker exec neo4j-vault-graph cypher-shell -u ${var.neo4j_username} -p ${var.neo4j_password} <<'CYPHER'
      MATCH (a:ApplicationIdentity {name: "${each.value.app_name}"})
      MATCH (p:Policy {name: "${each.value.policy_name}"})
      MERGE (a)-[:HAS_POLICY]->(p);
CYPHER
    EOT
  }
}

# Create Group -> Policy HAS_POLICY relationships
resource "null_resource" "neo4j_group_policy_relationships" {
  for_each = var.enable_neo4j_integration ? { for r in local.group_policy_relationships : r.key => r } : tomap({})

  depends_on = [
    null_resource.neo4j_internal_identity_groups,
    null_resource.neo4j_external_identity_groups,
    null_resource.neo4j_policies
  ]

  provisioner "local-exec" {
    command = <<-EOT
      docker exec neo4j-vault-graph cypher-shell -u ${var.neo4j_username} -p ${var.neo4j_password} <<'CYPHER'
      MATCH (g:IdentityGroup {name: "${each.value.group_name}"})
      MATCH (p:Policy {name: "${each.value.policy_name}"})
      MERGE (g)-[:HAS_POLICY]->(p);
CYPHER
    EOT
  }
}

# Create Human -> GitHub Auth AUTHENTICATES_VIA relationships
resource "null_resource" "neo4j_human_github_auth" {
  for_each = var.enable_neo4j_integration ? { for a in local.human_github_auth : a.key => a } : tomap({})

  depends_on = [
    null_resource.neo4j_human_identities,
    null_resource.neo4j_auth_methods
  ]

  provisioner "local-exec" {
    command = <<-EOT
      docker exec neo4j-vault-graph cypher-shell -u ${var.neo4j_username} -p ${var.neo4j_password} <<'CYPHER'
      MATCH (h:HumanIdentity {name: "${each.value.human_name}"})
      MATCH (a:AuthMethod {type: "github"})
      MERGE (h)-[r:AUTHENTICATES_VIA]->(a)
      SET r.username = "${each.value.username}";
CYPHER
    EOT
  }
}

# Create Human -> PKI Auth AUTHENTICATES_VIA relationships
resource "null_resource" "neo4j_human_pki_auth" {
  for_each = var.enable_neo4j_integration ? { for a in local.human_pki_auth : a.key => a } : tomap({})

  depends_on = [
    null_resource.neo4j_human_identities,
    null_resource.neo4j_auth_methods
  ]

  provisioner "local-exec" {
    command = <<-EOT
      docker exec neo4j-vault-graph cypher-shell -u ${var.neo4j_username} -p ${var.neo4j_password} <<'CYPHER'
      MATCH (h:HumanIdentity {name: "${each.value.human_name}"})
      MATCH (a:AuthMethod {type: "pki"})
      MERGE (h)-[r:AUTHENTICATES_VIA]->(a)
      SET r.cert_cn = "${each.value.cert_cn}";
CYPHER
    EOT
  }
}

# Create EntraID Human -> OIDC Auth AUTHENTICATES_VIA relationships
resource "null_resource" "neo4j_entraid_human_oidc_auth" {
  for_each = var.enable_neo4j_integration ? { for a in local.entraid_human_oidc_auth : a.key => a } : tomap({})

  depends_on = [
    null_resource.neo4j_entraid_human_identities,
    null_resource.neo4j_auth_methods
  ]

  provisioner "local-exec" {
    command = <<-EOT
      docker exec neo4j-vault-graph cypher-shell -u ${var.neo4j_username} -p ${var.neo4j_password} <<'CYPHER'
      MATCH (h:HumanIdentity {name: "${each.value.human_name}", identity_type: "entraid"})
      MATCH (a:AuthMethod {type: "oidc"})
      MERGE (h)-[r:AUTHENTICATES_VIA]->(a)
      SET r.username = "${each.value.username}";
CYPHER
    EOT
  }
}

# Create Application -> PKI Auth AUTHENTICATES_VIA relationships
resource "null_resource" "neo4j_app_pki_auth" {
  for_each = var.enable_neo4j_integration ? { for a in local.app_pki_auth : a.key => a } : tomap({})

  depends_on = [
    null_resource.neo4j_app_identities,
    null_resource.neo4j_auth_methods
  ]

  provisioner "local-exec" {
    command = <<-EOT
      docker exec neo4j-vault-graph cypher-shell -u ${var.neo4j_username} -p ${var.neo4j_password} <<'CYPHER'
      MATCH (a:ApplicationIdentity {name: "${each.value.app_name}"})
      MATCH (auth:AuthMethod {type: "pki"})
      MERGE (a)-[r:AUTHENTICATES_VIA]->(auth)
      SET r.cert_cn = "${each.value.cert_cn}";
CYPHER
    EOT
  }
}

# Create Application -> GitHub Repo JWT Auth AUTHENTICATES_VIA relationships
resource "null_resource" "neo4j_app_github_repo_auth" {
  for_each = var.enable_neo4j_integration ? { for a in local.app_github_repo_auth : a.key => a } : tomap({})

  depends_on = [
    null_resource.neo4j_app_identities,
    null_resource.neo4j_auth_methods
  ]

  provisioner "local-exec" {
    command = <<-EOT
      docker exec neo4j-vault-graph cypher-shell -u ${var.neo4j_username} -p ${var.neo4j_password} <<'CYPHER'
      MATCH (a:ApplicationIdentity {name: "${each.value.app_name}"})
      MATCH (auth:AuthMethod {type: "jwt", mount_path: "github_repo_jwt"})
      MERGE (a)-[r:AUTHENTICATES_VIA]->(auth)
      SET r.repository = "${each.value.repo}";
CYPHER
    EOT
  }
}

# Create Application -> Terraform Cloud JWT Auth AUTHENTICATES_VIA relationships
resource "null_resource" "neo4j_app_tfc_auth" {
  for_each = var.enable_neo4j_integration ? { for a in local.app_tfc_auth : a.key => a } : tomap({})

  depends_on = [
    null_resource.neo4j_app_identities,
    null_resource.neo4j_auth_methods
  ]

  provisioner "local-exec" {
    command = <<-EOT
      docker exec neo4j-vault-graph cypher-shell -u ${var.neo4j_username} -p ${var.neo4j_password} <<'CYPHER'
      MATCH (a:ApplicationIdentity {name: "${each.value.app_name}"})
      MATCH (auth:AuthMethod {type: "jwt", mount_path: "terraform_cloud"})
      MERGE (a)-[r:AUTHENTICATES_VIA]->(auth)
      SET r.workspace = "${each.value.workspace}";
CYPHER
    EOT
  }
}

# Create Application -> AWS Auth AUTHENTICATES_VIA relationships
resource "null_resource" "neo4j_app_aws_auth" {
  for_each = var.enable_neo4j_integration ? { for a in local.app_aws_auth : a.key => a } : tomap({})

  depends_on = [
    null_resource.neo4j_app_identities,
    null_resource.neo4j_auth_methods
  ]

  provisioner "local-exec" {
    command = <<-EOT
      docker exec neo4j-vault-graph cypher-shell -u ${var.neo4j_username} -p ${var.neo4j_password} <<'CYPHER'
      MATCH (a:ApplicationIdentity {name: "${each.value.app_name}"})
      MATCH (auth:AuthMethod {type: "aws"})
      MERGE (a)-[r:AUTHENTICATES_VIA]->(auth)
      SET r.role = "${each.value.role}";
CYPHER
    EOT
  }
}
