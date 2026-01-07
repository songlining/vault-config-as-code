// Neo4j Index and Constraint Setup
// Run this file to create performance indexes and data integrity constraints
//
// Usage: cypher-shell -a bolt://localhost:7687 -u neo4j -p vaultgraph123 < setup_indexes.cypher

// ============================================================================
// CONSTRAINTS (Ensure Uniqueness)
// ============================================================================

// Human Identity constraints
CREATE CONSTRAINT human_identity_name IF NOT EXISTS
FOR (h:HumanIdentity) REQUIRE h.name IS UNIQUE;

CREATE CONSTRAINT human_identity_vault_id IF NOT EXISTS
FOR (h:HumanIdentity) REQUIRE h.vault_id IS UNIQUE;

// Application Identity constraints
CREATE CONSTRAINT app_identity_name IF NOT EXISTS
FOR (a:ApplicationIdentity) REQUIRE a.name IS UNIQUE;

CREATE CONSTRAINT app_identity_vault_id IF NOT EXISTS
FOR (a:ApplicationIdentity) REQUIRE a.vault_id IS UNIQUE;

// Identity Group constraints
CREATE CONSTRAINT group_name IF NOT EXISTS
FOR (g:IdentityGroup) REQUIRE g.name IS UNIQUE;

CREATE CONSTRAINT group_vault_id IF NOT EXISTS
FOR (g:IdentityGroup) REQUIRE g.vault_id IS UNIQUE;

// Policy constraints
CREATE CONSTRAINT policy_name IF NOT EXISTS
FOR (p:Policy) REQUIRE p.name IS UNIQUE;

// Auth Method constraints
CREATE CONSTRAINT auth_method_type IF NOT EXISTS
FOR (a:AuthMethod) REQUIRE a.type IS UNIQUE;

// ============================================================================
// INDEXES (Improve Query Performance)
// ============================================================================

// Index on email for human identities
CREATE INDEX human_email IF NOT EXISTS
FOR (h:HumanIdentity) ON (h.email);

// Index on GitHub username
CREATE INDEX human_github IF NOT EXISTS
FOR (h:HumanIdentity) ON (h.github_username);

// Index on team
CREATE INDEX human_team IF NOT EXISTS
FOR (h:HumanIdentity) ON (h.team);

// Index on role
CREATE INDEX human_role IF NOT EXISTS
FOR (h:HumanIdentity) ON (h.role);

// Index on environment for applications
CREATE INDEX app_environment IF NOT EXISTS
FOR (a:ApplicationIdentity) ON (a.environment);

// Index on business unit
CREATE INDEX app_business_unit IF NOT EXISTS
FOR (a:ApplicationIdentity) ON (a.business_unit);

// Index on SPIFFE IDs
CREATE INDEX human_spiffe IF NOT EXISTS
FOR (h:HumanIdentity) ON (h.spiffe_id);

CREATE INDEX app_spiffe IF NOT EXISTS
FOR (a:ApplicationIdentity) ON (a.spiffe_id);

// Index on auth method mount paths
CREATE INDEX auth_method_mount IF NOT EXISTS
FOR (a:AuthMethod) ON (a.mount_path);

// ============================================================================
// VERIFICATION
// ============================================================================

// Show all constraints
SHOW CONSTRAINTS;

// Show all indexes
SHOW INDEXES;

// Return success message
RETURN 'Indexes and constraints created successfully!' as message;
