// Neo4j Visualization Queries
// Common queries for creating beautiful graph visualizations in Neo4j Browser
//
// Usage: Copy and paste these queries into Neo4j Browser (http://localhost:7474)

// ============================================================================
// VIZ 1: Complete Overview (Limited)
// ============================================================================
// Shows all node types and their relationships (limited to 100 for performance)
MATCH (n)
OPTIONAL MATCH (n)-[r]-(m)
RETURN n, r, m
LIMIT 100;

// ============================================================================
// VIZ 2: Specific Person's Complete Network
// ============================================================================
// Visualize everything connected to a specific person
MATCH (h:HumanIdentity {name: "Yulei Liu"})-[r*0..2]-(connected)
RETURN h, r, connected;

// ============================================================================
// VIZ 3: Group Hierarchy Tree
// ============================================================================
// Shows the complete group hierarchy structure
MATCH path = (g:IdentityGroup)-[:HAS_SUBGROUP*0..]->(sg:IdentityGroup)
RETURN path;

// ============================================================================
// VIZ 4: Group with All Members
// ============================================================================
// Visualize a specific group and all its members
MATCH (g:IdentityGroup {name: "Core Banking"})-[:HAS_SUBGROUP*0..]->(sg:IdentityGroup)
OPTIONAL MATCH (i:Identity)-[:MEMBER_OF]->(sg)
RETURN g, sg, i;

// ============================================================================
// VIZ 5: Authentication Methods Landscape
// ============================================================================
// Shows all authentication methods and which identities use them
MATCH (i:Identity)-[r:AUTHENTICATES_VIA]->(a:AuthMethod)
RETURN i, r, a
LIMIT 50;

// ============================================================================
// VIZ 6: Policy Distribution
// ============================================================================
// Visualize how policies are distributed across identities and groups
MATCH (entity)-[r:HAS_POLICY]->(p:Policy)
RETURN entity, r, p
LIMIT 50;

// ============================================================================
// VIZ 7: Production Applications Only
// ============================================================================
// Show only production applications and their relationships
MATCH (a:ApplicationIdentity {environment: "production"})-[r]-(related)
RETURN a, r, related;

// ============================================================================
// VIZ 8: Environment Segregation
// ============================================================================
// Visualize applications grouped by environment
MATCH (a:ApplicationIdentity)
OPTIONAL MATCH (a)-[r:MEMBER_OF]->(g:IdentityGroup)
OPTIONAL MATCH (a)-[auth:AUTHENTICATES_VIA]->(am:AuthMethod)
RETURN a, r, g, auth, am;

// ============================================================================
// VIZ 9: Access Path Visualization
// ============================================================================
// Show how a specific identity gets access to a specific policy
MATCH path = (h:HumanIdentity {name: "Yulei Liu"})-[:MEMBER_OF*]->(:IdentityGroup)-[:HAS_POLICY]->(p:Policy)
RETURN path
LIMIT 20;

// ============================================================================
// VIZ 10: All Humans in a Team
// ============================================================================
// Visualize all members of a specific team and their connections
MATCH (h:HumanIdentity {team: "sales_engineering_anz"})
OPTIONAL MATCH (h)-[r]-(related)
RETURN h, r, related;

// ============================================================================
// VIZ 11: Business Unit Applications
// ============================================================================
// Show all applications for a specific business unit
MATCH (a:ApplicationIdentity {business_unit: "retail_banking"})
OPTIONAL MATCH (a)-[r]-(related)
RETURN a, r, related;

// ============================================================================
// VIZ 12: GitHub Users Network
// ============================================================================
// Visualize all GitHub-authenticated users and their groups
MATCH (h:HumanIdentity)-[auth:AUTHENTICATES_VIA]->(a:AuthMethod {type: "github"})
OPTIONAL MATCH (h)-[mem:MEMBER_OF]->(g:IdentityGroup)
RETURN h, auth, a, mem, g;

// ============================================================================
// VIZ 13: Shortest Path Between Two Identities
// ============================================================================
// Find and visualize the shortest connection between two people
MATCH path = shortestPath(
  (h1:HumanIdentity {name: "Yulei Liu"})-[*]-(h2:HumanIdentity {name: "Simon Lynch"})
)
RETURN path;

// ============================================================================
// VIZ 14: High Connectivity Nodes (Hubs)
// ============================================================================
// Identify and visualize the most connected nodes in the graph
MATCH (n)-[r]-()
WITH n, count(r) as degree
WHERE degree > 5
MATCH (n)-[r]-(connected)
RETURN n, r, connected
LIMIT 100;

// ============================================================================
// VIZ 15: Orphaned Identities (If Any)
// ============================================================================
// Highlight identities that aren't connected to groups
MATCH (i:Identity)
WHERE NOT (i)-[:MEMBER_OF]->()
OPTIONAL MATCH (i)-[r]-(related)
RETURN i, r, related;

// ============================================================================
// VIZ 16: Cross-Environment Application Landscape
// ============================================================================
// Compare applications across different environments
MATCH (a:ApplicationIdentity)
WITH a.environment as env, collect(a) as apps
UNWIND apps as app
MATCH (app)-[r]-(related)
RETURN app, r, related, env
LIMIT 150;

// ============================================================================
// VIZ 17: Policy Inheritance Paths
// ============================================================================
// Show how policies are inherited through group hierarchy
MATCH path1 = (g:IdentityGroup)-[:HAS_SUBGROUP*0..2]->(sg:IdentityGroup)
MATCH path2 = (sg)-[:HAS_POLICY]->(p:Policy)
RETURN path1, path2
LIMIT 50;

// ============================================================================
// VIZ 18: Multi-Auth Identities
// ============================================================================
// Highlight identities with multiple authentication methods
MATCH (i:Identity)-[:AUTHENTICATES_VIA]->(a:AuthMethod)
WITH i, count(a) as authCount
WHERE authCount > 1
MATCH (i)-[r]-(related)
RETURN i, r, related;

// ============================================================================
// VIZ 19: Leaf Groups and Their Members
// ============================================================================
// Show groups at the bottom of the hierarchy (no subgroups) with members
MATCH (g:IdentityGroup)
WHERE NOT (g)-[:HAS_SUBGROUP]->()
MATCH (i:Identity)-[:MEMBER_OF]->(g)
RETURN g, i;

// ============================================================================
// VIZ 20: Full Identity Profile
// ============================================================================
// Complete view of a single identity with all its relationships
MATCH (h:HumanIdentity {name: "Yulei Liu"})
OPTIONAL MATCH path1 = (h)-[:MEMBER_OF]->(g:IdentityGroup)
OPTIONAL MATCH path2 = (h)-[:HAS_POLICY]->(p:Policy)
OPTIONAL MATCH path3 = (h)-[:AUTHENTICATES_VIA]->(a:AuthMethod)
OPTIONAL MATCH path4 = (g)-[:HAS_SUBGROUP*0..]->(sg:IdentityGroup)
OPTIONAL MATCH path5 = (g)-[:HAS_POLICY]->(gp:Policy)
RETURN h, path1, path2, path3, path4, path5;

// ============================================================================
// STYLE RECOMMENDATIONS
// ============================================================================
// After running a query, customize the visualization:
//
// 1. Click on node labels at the bottom of the visualization
// 2. Customize colors:
//    - HumanIdentity: #3498db (Blue)
//    - ApplicationIdentity: #2ecc71 (Green)
//    - IdentityGroup: #e67e22 (Orange)
//    - Policy: #9b59b6 (Purple)
//    - AuthMethod: #e74c3c (Red)
//
// 3. Set caption to show useful properties:
//    - HumanIdentity: name
//    - ApplicationIdentity: name
//    - IdentityGroup: name
//    - Policy: name
//    - AuthMethod: type
//
// 4. Adjust node size based on degree (number of connections)
// 5. Use relationship labels to show relationship types
