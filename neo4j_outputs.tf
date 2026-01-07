# Neo4j Graph Database Outputs
# Provides useful information after Terraform apply

output "neo4j_info" {
  value = var.enable_neo4j_integration ? {
    enabled        = true
    browser_url    = "http://localhost:7474"
    bolt_url       = var.neo4j_url
    username       = var.neo4j_username
    documentation  = "See docs/neo4j_quickstart.md to get started"
    query_library  = "See docs/neo4j_queries.md for useful queries"
    visualization  = "Import graph_style.grass from neo4j_queries/ for custom styling"
    note           = ""

    quick_commands = {
      test_connection = "cypher-shell -a ${var.neo4j_url} -u ${var.neo4j_username} -p '***' 'RETURN 1'"
      show_stats      = "./scripts/neo4j_utils.sh stats"
      run_validation  = "./scripts/neo4j_utils.sh validate"
      create_backup   = "./scripts/neo4j_utils.sh backup"
    }

    sample_queries = {
      view_all_nodes  = "MATCH (n) RETURN labels(n), count(n)"
      visualize_graph = "MATCH (n)-[r]-(m) RETURN n, r, m LIMIT 50"
      find_person     = "MATCH (h:HumanIdentity {name: 'Yulei Liu'})-[r*0..2]-(related) RETURN h, r, related"
    }
  } : {
    enabled        = false
    browser_url    = ""
    bolt_url       = ""
    username       = ""
    documentation  = ""
    query_library  = ""
    visualization  = ""
    note           = "Set enable_neo4j_integration = true in dev.tfvars to enable Neo4j graph visualization"

    quick_commands = {}
    sample_queries = {}
  }

  description = "Neo4j graph database connection and usage information"
}

output "neo4j_graph_summary" {
  value = var.enable_neo4j_integration ? {
    human_identities_created       = length(local.human_identities_map)
    application_identities_created = length(local.application_identities_map)
    identity_groups_created        = length(local.identity_groups_map)
    policies_created               = length(local.all_policies)
    auth_methods_configured        = length(local.auth_methods)

    relationships_created = {
      human_group_memberships      = length(local.human_group_memberships)
      app_group_memberships        = length(local.app_group_memberships)
      group_subgroup_relationships = length(local.group_subgroup_relationships)
      human_policy_assignments     = length(local.human_policy_relationships)
      app_policy_assignments       = length(local.app_policy_relationships)
      group_policy_assignments     = length(local.group_policy_relationships)
      human_github_auth           = length(local.human_github_auth)
      human_pki_auth              = length(local.human_pki_auth)
      app_pki_auth                = length(local.app_pki_auth)
      app_github_repo_auth        = length(local.app_github_repo_auth)
      app_tfc_auth                = length(local.app_tfc_auth)
      app_aws_auth                = length(local.app_aws_auth)
    }
  } : null

  description = "Summary of graph entities and relationships created in Neo4j"
}

output "neo4j_next_steps" {
  sensitive = true
  value = var.enable_neo4j_integration ? join("\n", [
    "🎉 Neo4j Graph Database Successfully Configured!",
    "",
    "Next Steps:",
    "",
    "1. Open Neo4j Browser:",
    "   http://localhost:7474",
    "   Username: ${var.neo4j_username}",
    "   Password: ${var.neo4j_password}",
    "",
    "2. Run your first query in Neo4j Browser:",
    "   MATCH (n)-[r]-(m) RETURN n, r, m LIMIT 50",
    "",
    "3. Explore the quick start guide:",
    "   docs/neo4j_quickstart.md",
    "",
    "4. Browse the query library:",
    "   docs/neo4j_queries.md",
    "",
    "5. Run validation checks:",
    "   ./scripts/neo4j_utils.sh validate",
    "",
    "6. Import custom graph styling:",
    "   Open Neo4j Browser settings (gear icon)",
    "   Import: neo4j_queries/graph_style.grass",
    "",
    "Happy exploring! 🚀"
  ]) : null

  description = "Next steps for using Neo4j graph database"
}
