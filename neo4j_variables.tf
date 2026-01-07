variable "enable_neo4j_integration" {
  description = "Enable Neo4j graph database integration for identity visualization"
  type        = bool
  default     = false
}

variable "neo4j_url" {
  description = "Neo4j database connection URL (Bolt protocol)"
  type        = string
  default     = "bolt://localhost:7687"
}

variable "neo4j_username" {
  description = "Neo4j database username"
  type        = string
  default     = "neo4j"
}

variable "neo4j_password" {
  description = "Neo4j database password"
  type        = string
  sensitive   = true
  default     = "vaultgraph123"
}
