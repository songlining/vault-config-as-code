# Neo4j Cypher Query Library for Vault Identity Management

This document contains useful Cypher queries for exploring and analyzing Vault identity relationships in the Neo4j graph database.

## Table of Contents
- [Basic Exploration](#basic-exploration)
- [Identity Queries](#identity-queries)
- [Group Analysis](#group-analysis)
- [Authentication Analysis](#authentication-analysis)
- [Policy Analysis](#policy-analysis)
- [Impact Analysis](#impact-analysis)
- [Validation Queries](#validation-queries)
- [Visualization Queries](#visualization-queries)

## Basic Exploration

### View All Node Types and Counts
```cypher
MATCH (n)
RETURN labels(n) as NodeType, count(n) as Count
ORDER BY Count DESC
```

### View All Relationship Types and Counts
```cypher
MATCH ()-[r]->()
RETURN type(r) as RelationshipType, count(r) as Count
ORDER BY Count DESC
```

### Get Database Statistics
```cypher
MATCH (n)
WITH labels(n) as labels, count(n) as count
UNWIND labels as label
RETURN label, sum(count) as total
ORDER BY total DESC
```

## Identity Queries

### Find All Information About a Specific Person
```cypher
MATCH (h:HumanIdentity {name: "Yulei Liu"})
OPTIONAL MATCH (h)-[:MEMBER_OF]->(g:IdentityGroup)
OPTIONAL MATCH (h)-[:HAS_POLICY]->(p:Policy)
OPTIONAL MATCH (h)-[auth:AUTHENTICATES_VIA]->(a:AuthMethod)
RETURN h, collect(DISTINCT g.name) as groups,
       collect(DISTINCT p.name) as policies,
       collect(DISTINCT {method: a.type, details: properties(auth)}) as auth_methods
```

### Find All Groups a Person Belongs To (Direct and Inherited)
```cypher
MATCH path = (h:HumanIdentity {name: "Yulei Liu"})-[:MEMBER_OF*]->(g:IdentityGroup)
RETURN path
```

### List All Humans and Their Primary Details
```cypher
MATCH (h:HumanIdentity)
RETURN h.name as Name,
       h.email as Email,
       h.role as Role,
       h.team as Team,
       h.github_username as GitHub
ORDER BY h.name
```

### List All Applications and Their Environments
```cypher
MATCH (a:ApplicationIdentity)
RETURN a.name as Application,
       a.environment as Environment,
       a.business_unit as BusinessUnit,
       a.contact as Contact
ORDER BY a.environment, a.name
```

### Find All Authentication Methods for an Identity
```cypher
MATCH (h:HumanIdentity {name: "Yulei Liu"})-[r:AUTHENTICATES_VIA]->(a:AuthMethod)
RETURN a.type as AuthMethod,
       properties(r) as Credentials
```

## Group Analysis

### Show Full Hierarchy of a Group
```cypher
MATCH path = (g:IdentityGroup {name: "Core Banking"})-[:HAS_SUBGROUP*0..]->(sg:IdentityGroup)
RETURN path
```

### List All Members of a Group (Including Subgroups)
```cypher
MATCH (g:IdentityGroup {name: "Core Banking"})-[:HAS_SUBGROUP*0..]->(sg:IdentityGroup)
MATCH (i:Identity)-[:MEMBER_OF]->(sg)
RETURN i.name as Member,
       labels(i) as Type,
       collect(DISTINCT sg.name) as Groups
ORDER BY Type, Member
```

### Count Members Per Group
```cypher
MATCH (g:IdentityGroup)
OPTIONAL MATCH (i:Identity)-[:MEMBER_OF]->(g)
RETURN g.name as Group,
       count(i) as DirectMembers
ORDER BY DirectMembers DESC
```

### Find Top-Level Groups (No Parent Groups)
```cypher
MATCH (g:IdentityGroup)
WHERE NOT ()-[:HAS_SUBGROUP]->(g)
RETURN g.name as TopLevelGroup,
       g.contact as Contact
ORDER BY g.name
```

### Find Leaf Groups (No Subgroups)
```cypher
MATCH (g:IdentityGroup)
WHERE NOT (g)-[:HAS_SUBGROUP]->()
RETURN g.name as LeafGroup
ORDER BY g.name
```

### Visualize Group Hierarchy
```cypher
MATCH path = (g:IdentityGroup)-[:HAS_SUBGROUP*0..3]->(:IdentityGroup)
RETURN path
LIMIT 50
```

## Authentication Analysis

### List All GitHub Users
```cypher
MATCH (h:HumanIdentity)-[r:AUTHENTICATES_VIA]->(a:AuthMethod {type: "github"})
RETURN h.name as Name,
       r.username as GitHubUsername,
       h.email as Email
ORDER BY r.username
```

### Find All Identities Using PKI Authentication
```cypher
MATCH (i:Identity)-[r:AUTHENTICATES_VIA]->(a:AuthMethod {type: "pki"})
RETURN i.name as Identity,
       labels(i) as Type,
       r.cert_cn as CertificateCN
ORDER BY Type, Identity
```

### List All Applications Using AWS Auth
```cypher
MATCH (a:ApplicationIdentity)-[r:AUTHENTICATES_VIA]->(auth:AuthMethod {type: "aws"})
RETURN a.name as Application,
       a.environment as Environment,
       r.role as AWSRole
ORDER BY Environment, Application
```

### Count Identities by Authentication Method
```cypher
MATCH (i:Identity)-[:AUTHENTICATES_VIA]->(a:AuthMethod)
RETURN a.type as AuthMethod,
       count(DISTINCT i) as IdentityCount
ORDER BY IdentityCount DESC
```

### Find Identities with Multiple Authentication Methods
```cypher
MATCH (i:Identity)-[:AUTHENTICATES_VIA]->(a:AuthMethod)
WITH i, count(a) as authCount, collect(a.type) as methods
WHERE authCount > 1
RETURN i.name as Identity,
       authCount as NumberOfAuthMethods,
       methods as AuthMethods
ORDER BY authCount DESC
```

## Policy Analysis

### Find All Policies Assigned to an Identity (Direct and via Groups)
```cypher
MATCH (h:HumanIdentity {name: "Yulei Liu"})-[:MEMBER_OF*0..]->(g)
MATCH (g)-[:HAS_POLICY]->(p:Policy)
RETURN DISTINCT p.name as Policy,
       'via ' + labels(g)[0] + ': ' + g.name as Source
UNION
MATCH (h:HumanIdentity {name: "Yulei Liu"})-[:HAS_POLICY]->(p:Policy)
RETURN DISTINCT p.name as Policy,
       'Direct Assignment' as Source
```

### List All Identities with a Specific Policy
```cypher
MATCH (i:Identity)-[:HAS_POLICY]->(p:Policy {name: "human-identity-token-policies"})
RETURN i.name as Identity,
       labels(i) as Type
ORDER BY Type, Identity
```

### Count Policy Assignments
```cypher
MATCH (p:Policy)
OPTIONAL MATCH (i:Identity)-[:HAS_POLICY]->(p)
OPTIONAL MATCH (g:IdentityGroup)-[:HAS_POLICY]->(p)
RETURN p.name as Policy,
       count(DISTINCT i) as DirectIdentities,
       count(DISTINCT g) as Groups,
       count(DISTINCT i) + count(DISTINCT g) as TotalAssignments
ORDER BY TotalAssignments DESC
```

### Find Unused Policies
```cypher
MATCH (p:Policy)
WHERE NOT ()-[:HAS_POLICY]->(p)
RETURN p.name as UnusedPolicy
```

### Find Policies Shared Across Multiple Groups
```cypher
MATCH (g:IdentityGroup)-[:HAS_POLICY]->(p:Policy)
WITH p, collect(g.name) as groups
WHERE size(groups) > 1
RETURN p.name as Policy,
       groups as SharedByGroups,
       size(groups) as GroupCount
ORDER BY GroupCount DESC
```

## Impact Analysis

### Find What Would Be Affected by Removing a Group
```cypher
// Direct impact
MATCH (g:IdentityGroup {name: "Core Banking Database group"})
OPTIONAL MATCH (i:Identity)-[:MEMBER_OF]->(g)
OPTIONAL MATCH (g)-[:HAS_POLICY]->(p:Policy)
OPTIONAL MATCH (parent:IdentityGroup)-[:HAS_SUBGROUP]->(g)
RETURN count(DISTINCT i) as AffectedIdentities,
       collect(DISTINCT i.name) as Identities,
       collect(DISTINCT p.name) as Policies,
       collect(DISTINCT parent.name) as ParentGroups
```

### Find All Downstream Members of a Group
```cypher
// Includes members of subgroups recursively
MATCH (g:IdentityGroup {name: "Core Banking"})-[:HAS_SUBGROUP*0..]->(sg:IdentityGroup)
MATCH (i:Identity)-[:MEMBER_OF]->(sg)
RETURN count(DISTINCT i) as TotalMembers,
       collect(DISTINCT i.name) as Members
```

### Trace Access Path from Identity to Policy
```cypher
MATCH path = (h:HumanIdentity {name: "Yulei Liu"})-[:MEMBER_OF*]->(:IdentityGroup)-[:HAS_POLICY]->(p:Policy)
RETURN path
LIMIT 20
```

### Find Identities That Would Lose a Policy if Group is Removed
```cypher
MATCH (g:IdentityGroup {name: "Core Banking Database group"})-[:HAS_POLICY]->(p:Policy)
MATCH (i:Identity)-[:MEMBER_OF]->(g)
WHERE NOT (i)-[:HAS_POLICY]->(p)  // Only has policy via this group
AND NOT (i)-[:MEMBER_OF]->(:IdentityGroup)-[:HAS_POLICY]->(p)  // No other path
RETURN i.name as Identity,
       p.name as PolicyAtRisk
```

## Validation Queries

### Check for Circular Group Dependencies
```cypher
MATCH path = (g:IdentityGroup)-[:HAS_SUBGROUP*]->(g)
RETURN path
```

### Find Orphaned Identities (Not in Any Group)
```cypher
MATCH (i:Identity)
WHERE NOT (i)-[:MEMBER_OF]->()
RETURN i.name as OrphanedIdentity,
       labels(i) as Type
ORDER BY Type, i.name
```

### Find Identities with No Authentication Methods
```cypher
MATCH (i:Identity)
WHERE NOT (i)-[:AUTHENTICATES_VIA]->()
RETURN i.name as Identity,
       labels(i) as Type
ORDER BY Type, Identity
```

### Find Identities with No Policies (Direct or via Groups)
```cypher
MATCH (i:Identity)
WHERE NOT (i)-[:HAS_POLICY]->()
AND NOT (i)-[:MEMBER_OF]->()-[:HAS_POLICY]->()
RETURN i.name as IdentityWithoutPolicies,
       labels(i) as Type
```

### Find Groups with No Members
```cypher
MATCH (g:IdentityGroup)
WHERE NOT ()-[:MEMBER_OF]->(g)
RETURN g.name as EmptyGroup
ORDER BY g.name
```

### Validate SPIFFE ID Format
```cypher
MATCH (i:Identity)
WHERE NOT i.spiffe_id STARTS WITH 'spiffe://vault/'
RETURN i.name as Identity,
       i.spiffe_id as InvalidSPIFFEID
```

## Visualization Queries

### Visualize Complete Identity Graph (Small Subset)
```cypher
MATCH (h:HumanIdentity {name: "Yulei Liu"})-[*0..3]-(related)
RETURN h, related
LIMIT 50
```

### Visualize Group Hierarchy with Members
```cypher
MATCH path1 = (g:IdentityGroup {name: "Core Banking"})-[:HAS_SUBGROUP*0..2]->(sg:IdentityGroup)
OPTIONAL MATCH path2 = (i:Identity)-[:MEMBER_OF]->(sg)
RETURN path1, path2
LIMIT 100
```

### Visualize Authentication Methods
```cypher
MATCH (i:Identity)-[r:AUTHENTICATES_VIA]->(a:AuthMethod)
RETURN i, r, a
LIMIT 50
```

### Visualize Policy Distribution
```cypher
MATCH (p:Policy)<-[:HAS_POLICY]-(entity)
WHERE labels(entity) IN [['HumanIdentity'], ['ApplicationIdentity'], ['IdentityGroup']]
RETURN p, entity
LIMIT 50
```

### Show All Paths Between Two Identities
```cypher
MATCH path = shortestPath(
  (h1:HumanIdentity {name: "Yulei Liu"})-[*]-(h2:HumanIdentity {name: "Simon Lynch"})
)
RETURN path
LIMIT 5
```

### Visualize Environment Separation
```cypher
MATCH (a:ApplicationIdentity)
WITH a.environment as env, collect(a) as apps
RETURN env, apps
```

## Advanced Queries

### Calculate Identity Centrality (Most Connected)
```cypher
MATCH (i:Identity)-[r]-()
RETURN i.name as Identity,
       labels(i) as Type,
       count(r) as Connections
ORDER BY Connections DESC
LIMIT 10
```

### Find Similar Identities (Based on Policies)
```cypher
MATCH (i1:Identity)-[:HAS_POLICY]->(p:Policy)<-[:HAS_POLICY]-(i2:Identity)
WHERE i1 <> i2
WITH i1, i2, count(p) as sharedPolicies
WHERE sharedPolicies > 2
RETURN i1.name as Identity1,
       i2.name as Identity2,
       sharedPolicies as SharedPolicies
ORDER BY sharedPolicies DESC
LIMIT 10
```

### Audit Trail: Who Has Access to What
```cypher
MATCH (i:Identity)-[:MEMBER_OF*0..]->(:IdentityGroup)-[:HAS_POLICY]->(p:Policy)
RETURN i.name as Identity,
       labels(i) as Type,
       collect(DISTINCT p.name) as Policies
ORDER BY Type, Identity
```

## Tips for Using Neo4j Browser

1. **Limit Results**: Always use `LIMIT` clause when exploring large datasets
2. **Expand Nodes**: Double-click a node in the visualization to expand its relationships
3. **Style Graph**: Click the node type labels in the bottom to customize colors
4. **Export**: Use the download button to export query results or visualizations
5. **Save Queries**: Use the star icon to save frequently used queries

## Performance Tips

- Use indexes on frequently queried properties (already created in `neo4j_graph.tf`)
- Use `EXPLAIN` or `PROFILE` before complex queries to understand execution plans
- Limit relationship depth in path queries (e.g., `[*0..3]` instead of `[*]`)
- Use `WITH` clauses to reduce intermediate result sets
