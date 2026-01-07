# Neo4j Setup and Configuration Guide

This guide explains how to set up and use the Neo4j graph database integration for visualizing Vault identity relationships.

## Table of Contents
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Starting Neo4j](#starting-neo4j)
- [Accessing Neo4j Browser](#accessing-neo4j-browser)
- [Enabling in Terraform](#enabling-in-terraform)
- [Applying Configuration](#applying-configuration)
- [Customizing Visualizations](#customizing-visualizations)
- [Troubleshooting](#troubleshooting)

## Prerequisites

### Required Software

1. **Docker and Docker Compose**
   - macOS: Install [Docker Desktop](https://www.docker.com/products/docker-desktop)
   - Linux: Install via package manager (`apt-get install docker-compose`)
   - Windows: Install [Docker Desktop](https://www.docker.com/products/docker-desktop)

2. **cypher-shell** (Neo4j CLI tool)
   ```bash
   # macOS
   brew install cypher-shell

   # Linux
   apt-get install cypher-shell

   # Windows or Manual Install
   # Download from https://neo4j.com/download-center/#cyphershell
   ```

3. **Terraform** (already installed for Vault configuration)
   ```bash
   terraform --version
   # Should be >= 1.10.0
   ```

## Installation

### Step 1: Start Neo4j with Docker Compose

The Neo4j service is already configured in `docker-compose.yml`. Simply start it:

```bash
# Start both Vault and Neo4j
docker-compose up -d

# Or start only Neo4j
docker-compose up -d neo4j
```

Verify Neo4j is running:

```bash
docker-compose ps
# Should show neo4j-vault-graph as "running"
```

Check Neo4j logs:

```bash
docker-compose logs neo4j
# Should see "Started." message
```

### Step 2: Verify cypher-shell Connectivity

Test that you can connect to Neo4j:

```bash
cypher-shell -a bolt://localhost:7687 -u neo4j -p vaultgraph123 "RETURN 'Connected!' as message"
```

Expected output:
```
+-------------+
| message     |
+-------------+
| "Connected!"|
+-------------+
```

## Accessing Neo4j Browser

Neo4j Browser is a web-based interface for exploring and querying the graph database.

### Access URL
```
http://localhost:7474
```

### Login Credentials
- **Username**: `neo4j`
- **Password**: `vaultgraph123`
- **Connection URL**: `bolt://localhost:7687` (pre-filled)

### First-Time Setup

1. Open http://localhost:7474 in your web browser
2. You should see the Neo4j Browser login screen
3. Enter the credentials above and click "Connect"
4. You'll see the Neo4j Browser interface with:
   - Query editor at the top
   - Visualization area in the center
   - Database info sidebar on the left

## Enabling in Terraform

### Step 1: Update `dev.tfvars`

Add Neo4j configuration to your `dev.tfvars` file:

```hcl
# Enable Neo4j integration
enable_neo4j_integration = true

# Neo4j connection details (or use defaults)
neo4j_url      = "bolt://localhost:7687"
neo4j_username = "neo4j"
neo4j_password = "vaultgraph123"
```

### Step 2: Initialize Terraform (if first time)

```bash
terraform init
```

This ensures all required providers are available.

## Applying Configuration

### Full Apply

To create/update both Vault identities and Neo4j graph:

```bash
terraform apply -var-file=dev.tfvars
```

### Apply Only Neo4j Resources

To update only the graph database:

```bash
terraform apply -var-file=dev.tfvars -target=module.neo4j
```

### What Happens During Apply

1. **Connectivity Check**: Terraform verifies Neo4j is accessible
2. **Graph Initialization**: Clears old data, creates constraints and indexes
3. **Node Creation**: Creates nodes for all identities, groups, policies, auth methods
4. **Relationship Creation**: Links nodes based on memberships, policies, authentication

The process typically takes 30-60 seconds depending on the number of identities.

### Verify Success

After `terraform apply` completes:

1. Open Neo4j Browser (http://localhost:7474)
2. Run this query to see all nodes:
   ```cypher
   MATCH (n) RETURN count(n) as TotalNodes
   ```
3. Run this query to see a sample visualization:
   ```cypher
   MATCH (n)-[r]-(m)
   RETURN n, r, m
   LIMIT 25
   ```

## Customizing Visualizations

### Import Custom Graph Styling

1. Open Neo4j Browser
2. Click the **gear icon** (⚙️) in the bottom left corner
3. Scroll to "Graph Stylesheet"
4. Click "Import Graph Style Sheet"
5. Copy and paste the contents of `neo4j_queries/graph_style.grass`
6. Click "Apply"

This will set custom colors and sizes for different node types:
- **HumanIdentity**: Blue circles
- **ApplicationIdentity**: Green circles
- **IdentityGroup**: Orange circles
- **Policy**: Purple circles
- **AuthMethod**: Red circles

### Customize Further

In Neo4j Browser, after running a query:

1. Click on a node type label at the bottom of the visualization
2. Customize:
   - **Color**: Click the color picker
   - **Size**: Adjust the diameter slider
   - **Caption**: Choose which property to display (e.g., `name`, `email`)
   - **Icon**: Upload custom icons (optional)

3. Export your custom style:
   - Click gear icon → "Export Graph Style Sheet"
   - Save for later use

## Using Pre-Built Queries

### Via Neo4j Browser

1. Navigate to `docs/neo4j_queries.md`
2. Find a query you want to run
3. Copy the Cypher code
4. Paste into Neo4j Browser query editor
5. Click the blue "play" button or press Ctrl+Enter (Cmd+Enter on Mac)

### Via cypher-shell

Run Cypher script files directly:

```bash
# Run index setup
cypher-shell -a bolt://localhost:7687 -u neo4j -p vaultgraph123 < neo4j_queries/setup_indexes.cypher

# Run validation checks
cypher-shell -a bolt://localhost:7687 -u neo4j -p vaultgraph123 < neo4j_queries/validation_checks.cypher
```

### Via Visualization Queries

Open `neo4j_queries/visualization_queries.cypher` and copy queries to create beautiful visualizations.

## Common Tasks

### Find All Groups a Person Belongs To

```cypher
MATCH path = (h:HumanIdentity {name: "Yulei Liu"})-[:MEMBER_OF*]->(g:IdentityGroup)
RETURN path
```

### See Application's Authentication Methods

```cypher
MATCH (a:ApplicationIdentity {name: "Core Banking Backend"})-[r:AUTHENTICATES_VIA]->(auth:AuthMethod)
RETURN a.name, auth.type, properties(r)
```

### Visualize Group Hierarchy

```cypher
MATCH path = (g:IdentityGroup {name: "Core Banking"})-[:HAS_SUBGROUP*0..]->(sg:IdentityGroup)
RETURN path
```

### Find Policies for an Identity

```cypher
MATCH (h:HumanIdentity {name: "Yulei Liu"})-[:MEMBER_OF*0..]->()-[:HAS_POLICY]->(p:Policy)
RETURN DISTINCT p.name
```

## Troubleshooting

### Neo4j Won't Start

**Problem**: Docker container doesn't start or exits immediately

**Solutions**:
1. Check Docker logs:
   ```bash
   docker-compose logs neo4j
   ```
2. Ensure port 7474 and 7687 are not in use:
   ```bash
   lsof -i :7474
   lsof -i :7687
   ```
3. Remove old volumes and restart:
   ```bash
   docker-compose down -v
   docker-compose up -d neo4j
   ```

### Can't Connect with cypher-shell

**Problem**: `Connection refused` or `Authentication failed`

**Solutions**:
1. Verify Neo4j is running:
   ```bash
   docker-compose ps neo4j
   ```
2. Wait for Neo4j to fully start (can take 10-20 seconds):
   ```bash
   docker-compose logs -f neo4j
   # Wait for "Started." message
   ```
3. Check credentials match `docker-compose.yml`:
   ```yaml
   NEO4J_AUTH: neo4j/vaultgraph123
   ```

### Terraform Apply Fails

**Problem**: `Error: local-exec provisioner error`

**Solutions**:
1. Ensure cypher-shell is installed:
   ```bash
   which cypher-shell
   ```
2. Test connectivity manually:
   ```bash
   cypher-shell -a bolt://localhost:7687 -u neo4j -p vaultgraph123 "RETURN 1"
   ```
3. Check Neo4j is healthy:
   ```bash
   curl http://localhost:7474
   ```

### Empty Graph After Apply

**Problem**: Neo4j shows 0 nodes after `terraform apply`

**Solutions**:
1. Check Terraform didn't skip Neo4j resources:
   ```bash
   terraform plan -var-file=dev.tfvars | grep neo4j
   ```
2. Ensure `enable_neo4j_integration = true` in `dev.tfvars`
3. Run validation:
   ```bash
   cypher-shell -a bolt://localhost:7687 -u neo4j -p vaultgraph123 "MATCH (n) RETURN count(n)"
   ```
4. Re-apply targeting Neo4j:
   ```bash
   terraform apply -var-file=dev.tfvars -replace=null_resource.neo4j_initialize[0]
   ```

### Browser Visualization is Messy

**Problem**: Graph visualization is hard to read

**Solutions**:
1. Use LIMIT in queries:
   ```cypher
   MATCH (n)-[r]-(m) RETURN n, r, m LIMIT 25
   ```
2. Focus on specific subgraphs:
   ```cypher
   MATCH (h:HumanIdentity {name: "Yulei Liu"})-[r*0..2]-(related)
   RETURN h, r, related
   ```
3. Apply the custom graph style from `graph_style.grass`
4. Use the physics controls in Browser:
   - Click and drag nodes to reposition
   - Use the settings gear to adjust forces
   - Pin nodes in place with right-click

### Performance is Slow

**Problem**: Queries take a long time to run

**Solutions**:
1. Ensure indexes are created:
   ```bash
   cypher-shell -a bolt://localhost:7687 -u neo4j -p vaultgraph123 < neo4j_queries/setup_indexes.cypher
   ```
2. Use LIMIT clauses:
   ```cypher
   MATCH path = (n)-[*]-(m) RETURN path LIMIT 100
   ```
3. Increase Neo4j memory in `docker-compose.yml`:
   ```yaml
   NEO4J_dbms_memory_heap_max__size: 2G
   ```
4. Use `PROFILE` to analyze query performance:
   ```cypher
   PROFILE MATCH (n)-[r]-(m) RETURN n, r, m LIMIT 100
   ```

## Advanced Configuration

### Changing Neo4j Password

1. Update `docker-compose.yml`:
   ```yaml
   NEO4J_AUTH: neo4j/your-new-password
   ```
2. Update `neo4j_variables.tf` default or `dev.tfvars`:
   ```hcl
   neo4j_password = "your-new-password"
   ```
3. Restart:
   ```bash
   docker-compose down -v
   docker-compose up -d
   terraform apply -var-file=dev.tfvars
   ```

### Persisting Data

Data is already persisted in Docker volumes. To backup:

```bash
# Backup Neo4j data
docker cp neo4j-vault-graph:/data ./neo4j-backup

# Restore
docker cp ./neo4j-backup neo4j-vault-graph:/data
```

### Remote Neo4j Instance

To use a remote Neo4j instance instead of Docker:

1. Update `dev.tfvars`:
   ```hcl
   neo4j_url      = "bolt://your-neo4j-host:7687"
   neo4j_username = "your-username"
   neo4j_password = "your-password"
   ```

2. Ensure remote instance is accessible and has APOC plugin installed

## Next Steps

- Read the [Query Library](neo4j_queries.md) for useful queries
- Follow the [Quick Start Guide](neo4j_quickstart.md) for a tutorial
- Explore visualization queries in `neo4j_queries/visualization_queries.cypher`
- Run validation checks with `neo4j_queries/validation_checks.cypher`
