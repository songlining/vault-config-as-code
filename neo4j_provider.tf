# Neo4j Graph Database Integration
#
# NOTE: This implementation uses local-exec provisioner with cypher-shell instead of
# a Terraform provider because the neo4j-labs/neo4j provider is not actively maintained.
# This approach is more reliable and gives us full control over the graph operations.
#
# Requirements:
#   - Neo4j running and accessible (docker-compose up -d)
#   - cypher-shell CLI tool (installed via: brew install cypher-shell or download from Neo4j)
#
# The cypher-shell tool can be installed:
#   macOS: brew install cypher-shell
#   Linux: apt-get install cypher-shell or download from https://neo4j.com/download-center/
#   Windows: Download from https://neo4j.com/download-center/
#
# Connection is configured via variables in neo4j_variables.tf

# Null resource to test Neo4j connectivity
resource "null_resource" "neo4j_connectivity_check" {
  count = var.enable_neo4j_integration ? 1 : 0

  provisioner "local-exec" {
    command = <<-EOT
      echo "Testing Neo4j connectivity..."
      cypher-shell -a ${var.neo4j_url} -u ${var.neo4j_username} -p ${var.neo4j_password} \
        "RETURN 'Neo4j connection successful' as message" || \
        (echo "ERROR: Cannot connect to Neo4j. Please ensure Neo4j is running (docker-compose up -d)" && exit 1)
    EOT
  }

  triggers = {
    always_run = timestamp()
  }
}

# Note: We'll use null_resource with local-exec provisioners in neo4j_graph.tf
# to execute Cypher commands that create nodes and relationships.
# This approach is more maintainable than using an unmaintained provider.
