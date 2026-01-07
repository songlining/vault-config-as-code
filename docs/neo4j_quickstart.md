# Neo4j Quick Start Guide

This tutorial will walk you through setting up and exploring the Vault identity graph in Neo4j in just 10 minutes.

## What You'll Learn

- Start Neo4j database
- Populate it with Vault identity data using Terraform
- Run your first graph queries
- Create beautiful visualizations
- Understand identity relationships

## Prerequisites

- Docker and Docker Compose installed
- Terraform installed (>= 1.10.0)
- cypher-shell CLI tool installed

See [Neo4j Setup Guide](neo4j_setup.md#prerequisites) for installation instructions.

## Step 1: Start Neo4j (2 minutes)

### Start the Docker Container

```bash
# Navigate to the repository
cd /path/to/vault-config-as-code

# Start Neo4j (and Vault if desired)
docker-compose up -d neo4j
```

### Verify Neo4j is Running

```bash
# Check container status
docker-compose ps neo4j

# Should show:
# NAME                  STATUS    PORTS
# neo4j-vault-graph    running   0.0.0.0:7474->7474/tcp, 0.0.0.0:7687->7687/tcp
```

### Wait for Neo4j to Be Ready

```bash
# Watch the logs until you see "Started."
docker-compose logs -f neo4j

# Press Ctrl+C once you see the "Started." message
```

### Test Connectivity

```bash
cypher-shell -a bolt://localhost:7687 -u neo4j -p vaultgraph123 "RETURN 'Ready!' as status"

# Expected output:
# +---------+
# | status  |
# +---------+
# | "Ready!" |
# +---------+
```

✅ **Checkpoint**: Neo4j is now running and accessible!

## Step 2: Enable Neo4j in Terraform (1 minute)

### Update dev.tfvars

Add this to your `dev.tfvars` file:

```hcl
# Enable Neo4j graph database integration
enable_neo4j_integration = true
```

That's it! The connection details use defaults that match the Docker Compose configuration.

✅ **Checkpoint**: Terraform is configured to populate Neo4j!

## Step 3: Populate the Graph (3 minutes)

### Run Terraform Apply

```bash
terraform apply -var-file=dev.tfvars
```

Terraform will:
1. Create your Vault identities (as before)
2. **NEW**: Populate Neo4j with the identity graph

### What to Expect

You'll see output like:
```
null_resource.neo4j_initialize[0]: Creating...
null_resource.neo4j_human_identities["Yulei Liu"]: Creating...
null_resource.neo4j_identity_groups["Core Banking"]: Creating...
...
Apply complete! Resources: 47 added, 0 changed, 0 destroyed.
```

The number of resources depends on how many identities you have.

### Verify the Graph was Populated

```bash
cypher-shell -a bolt://localhost:7687 -u neo4j -p vaultgraph123 \
  "MATCH (n) RETURN labels(n) as Type, count(n) as Count"
```

Expected output (your numbers will vary):
```
+--------------------------------+
| Type                  | Count  |
+--------------------------------+
| ["HumanIdentity"]     | 3      |
| ["ApplicationIdentity"]| 5     |
| ["IdentityGroup"]     | 8      |
| ["Policy"]            | 12     |
| ["AuthMethod"]        | 6      |
+--------------------------------+
```

✅ **Checkpoint**: Your Vault identities are now visualized in Neo4j!

## Step 4: Open Neo4j Browser (1 minute)

### Access the Web UI

Open your web browser and go to:
```
http://localhost:7474
```

### Login

- **Connect URL**: `bolt://localhost:7687` (pre-filled)
- **Username**: `neo4j`
- **Password**: `vaultgraph123`

Click **Connect**.

✅ **Checkpoint**: You're now in the Neo4j Browser interface!

## Step 5: Your First Queries (3 minutes)

### Query 1: See Everything

Copy and paste this into the query editor at the top:

```cypher
MATCH (n)-[r]-(m)
RETURN n, r, m
LIMIT 50
```

Click the **blue play button** or press **Ctrl+Enter**.

🎉 You should see a colorful graph visualization!

**What you're seeing:**
- Circles = Nodes (identities, groups, policies, auth methods)
- Lines = Relationships (memberships, policies, authentication)

**Try this:**
- Click and drag nodes to rearrange
- Double-click a node to expand its connections
- Hover over nodes to see properties

### Query 2: Find a Specific Person

Replace "Yulei Liu" with a name from your identities:

```cypher
MATCH (h:HumanIdentity {name: "Yulei Liu"})-[r*0..2]-(related)
RETURN h, r, related
```

**What you're seeing:**
- The blue node in the center is Yulei Liu
- Orange nodes = Groups they belong to
- Purple nodes = Policies assigned
- Red nodes = Authentication methods

### Query 3: View Group Hierarchy

```cypher
MATCH path = (g:IdentityGroup)-[:HAS_SUBGROUP*0..]->(sg:IdentityGroup)
RETURN path
```

**What you're seeing:**
- How groups are organized hierarchically
- Parent groups → Subgroups
- Useful for understanding organizational structure

### Query 4: See Authentication Landscape

```cypher
MATCH (i:Identity)-[r:AUTHENTICATES_VIA]->(a:AuthMethod)
RETURN i, r, a
LIMIT 30
```

**What you're seeing:**
- Blue/Green nodes = People and Applications
- Red nodes = Authentication methods (GitHub, PKI, AWS, etc.)
- Lines show which identities use which auth methods

## Step 6: Apply Custom Styling (1 minute)

### Make it Beautiful

1. Click the **gear icon (⚙️)** in the bottom left of Neo4j Browser
2. Scroll to "Graph Stylesheet"
3. Click "Import Graph Style Sheet"
4. Open `neo4j_queries/graph_style.grass` in a text editor
5. Copy all contents and paste into Neo4j Browser
6. Click **Apply**

Now your graph has:
- **Blue circles**: Human identities
- **Green circles**: Application identities
- **Orange circles**: Identity groups
- **Purple circles**: Policies
- **Red circles**: Authentication methods

Much easier to read!

## Common Exploration Patterns

### Pattern 1: "Who has access to what?"

```cypher
MATCH (h:HumanIdentity {name: "Yulei Liu"})-[:MEMBER_OF*0..]->()-[:HAS_POLICY]->(p:Policy)
RETURN DISTINCT p.name as Policy
```

Shows all policies that "Yulei Liu" has access to (directly or through groups).

### Pattern 2: "Who is in this group?"

```cypher
MATCH (g:IdentityGroup {name: "Core Banking"})-[:HAS_SUBGROUP*0..]->(sg:IdentityGroup)
MATCH (i:Identity)-[:MEMBER_OF]->(sg)
RETURN i.name, labels(i)
```

Lists all members of "Core Banking" group including subgroup members.

### Pattern 3: "What would removing this group affect?"

```cypher
MATCH (g:IdentityGroup {name: "Core Banking Database group"})
MATCH (i:Identity)-[:MEMBER_OF]->(g)
RETURN count(i) as AffectedIdentities, collect(i.name) as Identities
```

Shows impact analysis before making changes.

## Next Steps

### Explore More Queries

Open [docs/neo4j_queries.md](neo4j_queries.md) for a comprehensive query library including:
- Identity exploration
- Group analysis
- Authentication analysis
- Policy analysis
- Impact analysis
- Validation checks

### Run Validation Checks

```bash
cypher-shell -a bolt://localhost:7687 -u neo4j -p vaultgraph123 \
  < neo4j_queries/validation_checks.cypher
```

This runs automated checks for:
- Circular group dependencies
- Orphaned identities
- Missing authentication
- Empty groups
- Unused policies

### Try Visualization Queries

Open `neo4j_queries/visualization_queries.cypher` and try the 20 pre-built visualization queries for different perspectives on your identity graph.

## Tips for Success

### 1. Always Use LIMIT

When exploring, always add `LIMIT 50` to avoid overwhelming visualizations:

```cypher
MATCH (n)-[r]-(m) RETURN n, r, m LIMIT 50
```

### 2. Start Specific, Then Expand

Begin with a specific identity or group, then explore outward:

```cypher
// Start specific
MATCH (h:HumanIdentity {name: "Yulei Liu"})
RETURN h

// Then expand by double-clicking the node in the visualization
```

### 3. Use the Favorites

Click the ⭐ (star) icon on queries you use frequently to save them in Neo4j Browser.

### 4. Export Visualizations

Click the download icon to export:
- PNG image
- SVG image
- CSV data
- JSON data

### 5. Learn Cypher

Neo4j Browser has a built-in tutorial. Run:

```cypher
:play start
```

## Troubleshooting

### No Data Showing?

Check that Neo4j integration is enabled:

```bash
grep enable_neo4j_integration dev.tfvars
# Should show: enable_neo4j_integration = true
```

Re-run Terraform if needed:

```bash
terraform apply -var-file=dev.tfvars
```

### Visualization Too Messy?

Use more specific queries with LIMIT:

```cypher
MATCH (h:HumanIdentity)-[r]-(related)
RETURN h, r, related
LIMIT 25
```

Or focus on a specific person/group:

```cypher
MATCH (h:HumanIdentity {name: "Yulei Liu"})-[r*0..1]-(related)
RETURN h, r, related
```

### Can't Connect to Neo4j Browser?

Ensure Neo4j is running:

```bash
docker-compose ps neo4j
# Should show "running"
```

Restart if needed:

```bash
docker-compose restart neo4j
```

## Real-World Use Cases

### Use Case 1: Onboarding New Team Members

Show them the graph:
```cypher
MATCH (h:HumanIdentity)-[:MEMBER_OF]->(g:IdentityGroup)
RETURN h, g
```

They can visually see who belongs to which teams.

### Use Case 2: Access Reviews

Find all policies for a team:
```cypher
MATCH (g:IdentityGroup {name: "Core Banking"})-[:HAS_SUBGROUP*0..]->()-[:HAS_POLICY]->(p:Policy)
RETURN DISTINCT p.name
```

### Use Case 3: Incident Response

Quickly find who has access through a compromised group:
```cypher
MATCH (g:IdentityGroup {name: "Compromised Group"})-[:HAS_SUBGROUP*0..]->(sg)
MATCH (i:Identity)-[:MEMBER_OF]->(sg)
RETURN i.name, i.email
```

## Congratulations! 🎉

You've successfully:
- ✅ Set up Neo4j
- ✅ Populated it with Vault identity data
- ✅ Explored the graph visually
- ✅ Run useful queries
- ✅ Applied custom styling

You now have a powerful tool for understanding and managing Vault identities!

## Resources

- [Neo4j Setup Guide](neo4j_setup.md) - Detailed setup and configuration
- [Query Library](neo4j_queries.md) - Comprehensive Cypher query collection
- [Neo4j Browser Guide](https://neo4j.com/docs/browser-manual/current/) - Official Neo4j Browser documentation
- [Cypher Reference](https://neo4j.com/docs/cypher-manual/current/) - Complete Cypher language reference
