#!/usr/bin/env bash

# Neo4j Utility Script for Vault Identity Graph Management
# This script provides helpful commands for managing the Neo4j graph database

set -e

# Configuration
NEO4J_URL="${NEO4J_URL:-bolt://localhost:7687}"
NEO4J_USER="${NEO4J_USER:-neo4j}"
NEO4J_PASS="${NEO4J_PASS:-vaultgraph123}"
BACKUP_DIR="./neo4j-backups"
QUERIES_DIR="./neo4j_queries"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

# Check if cypher-shell is available
check_cypher_shell() {
    if ! command -v cypher-shell &> /dev/null; then
        print_error "cypher-shell not found. Please install it first:"
        echo "  macOS: brew install cypher-shell"
        echo "  Linux: apt-get install cypher-shell"
        echo "  Or download from: https://neo4j.com/download-center/#cyphershell"
        exit 1
    fi
}

# Test Neo4j connectivity
test_connection() {
    print_info "Testing connection to Neo4j at ${NEO4J_URL}..."
    if cypher-shell -a "${NEO4J_URL}" -u "${NEO4J_USER}" -p "${NEO4J_PASS}" \
        "RETURN 'Connected!' as message" &> /dev/null; then
        print_success "Successfully connected to Neo4j"
        return 0
    else
        print_error "Failed to connect to Neo4j"
        print_info "Make sure Neo4j is running: docker-compose up -d neo4j"
        return 1
    fi
}

# Clear all graph data
clear_graph() {
    print_warning "This will DELETE ALL data from the Neo4j database!"
    read -p "Are you sure? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        print_info "Operation cancelled"
        return 0
    fi

    print_info "Clearing all graph data..."
    cypher-shell -a "${NEO4J_URL}" -u "${NEO4J_USER}" -p "${NEO4J_PASS}" \
        "MATCH (n) DETACH DELETE n;" || {
        print_error "Failed to clear graph data"
        return 1
    }
    print_success "All graph data cleared"
}

# Show graph statistics
show_stats() {
    print_info "Fetching graph statistics..."
    echo ""
    cypher-shell -a "${NEO4J_URL}" -u "${NEO4J_USER}" -p "${NEO4J_PASS}" <<'CYPHER'
// Node counts by type
MATCH (n)
WITH labels(n) as labels, count(n) as count
UNWIND labels as label
RETURN label, sum(count) as total
ORDER BY total DESC;

// Relationship counts by type
MATCH ()-[r]->()
RETURN type(r) as RelationshipType, count(r) as Count
ORDER BY Count DESC;

// Total statistics
MATCH (n)
WITH count(n) as nodeCount
MATCH ()-[r]->()
RETURN nodeCount as TotalNodes, count(r) as TotalRelationships;
CYPHER
}

# Backup graph database
backup_graph() {
    print_info "Creating backup of Neo4j graph..."

    # Create backup directory if it doesn't exist
    mkdir -p "${BACKUP_DIR}"

    # Generate timestamp for backup filename
    timestamp=$(date +"%Y%m%d_%H%M%S")
    backup_file="${BACKUP_DIR}/neo4j_backup_${timestamp}.cypher"

    # Export all nodes and relationships as Cypher commands
    print_info "Exporting data to ${backup_file}..."

    cypher-shell -a "${NEO4J_URL}" -u "${NEO4J_USER}" -p "${NEO4J_PASS}" \
        --format plain <<'CYPHER' > "${backup_file}"
// Export all nodes
MATCH (n)
RETURN 'CREATE ' +
       '(' + coalesce(id(n), 'n') + ':' + reduce(s = '', label IN labels(n) | s + label + ':') +
       ' ' + toString(properties(n)) + ');' as statement;

// Export all relationships
MATCH (a)-[r]->(b)
RETURN 'MATCH (a), (b) WHERE id(a) = ' + id(a) + ' AND id(b) = ' + id(b) +
       ' CREATE (a)-[' + type(r) + ' ' + toString(properties(r)) + ']->(b);' as statement;
CYPHER

    print_success "Backup created: ${backup_file}"
    print_info "Backup size: $(du -h "${backup_file}" | cut -f1)"
}

# List available backups
list_backups() {
    print_info "Available backups:"
    if [ -d "${BACKUP_DIR}" ] && [ "$(ls -A ${BACKUP_DIR})" ]; then
        ls -lh "${BACKUP_DIR}"/*.cypher 2>/dev/null || print_warning "No backups found"
    else
        print_warning "No backups found in ${BACKUP_DIR}"
    fi
}

# Restore from backup
restore_backup() {
    local backup_file="$1"

    if [ -z "$backup_file" ]; then
        print_error "Please specify a backup file to restore"
        list_backups
        return 1
    fi

    if [ ! -f "$backup_file" ]; then
        print_error "Backup file not found: $backup_file"
        return 1
    fi

    print_warning "This will REPLACE all current data with the backup!"
    read -p "Are you sure? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        print_info "Operation cancelled"
        return 0
    fi

    print_info "Clearing current data..."
    clear_graph

    print_info "Restoring from backup: $backup_file..."
    cypher-shell -a "${NEO4J_URL}" -u "${NEO4J_USER}" -p "${NEO4J_PASS}" \
        < "$backup_file" || {
        print_error "Failed to restore backup"
        return 1
    }

    print_success "Backup restored successfully"
}

# Run validation checks
run_validation() {
    print_info "Running validation checks..."
    if [ ! -f "${QUERIES_DIR}/validation_checks.cypher" ]; then
        print_error "Validation script not found: ${QUERIES_DIR}/validation_checks.cypher"
        return 1
    fi

    cypher-shell -a "${NEO4J_URL}" -u "${NEO4J_USER}" -p "${NEO4J_PASS}" \
        < "${QUERIES_DIR}/validation_checks.cypher"
}

# Setup indexes and constraints
setup_indexes() {
    print_info "Setting up indexes and constraints..."
    if [ ! -f "${QUERIES_DIR}/setup_indexes.cypher" ]; then
        print_error "Setup script not found: ${QUERIES_DIR}/setup_indexes.cypher"
        return 1
    fi

    cypher-shell -a "${NEO4J_URL}" -u "${NEO4J_USER}" -p "${NEO4J_PASS}" \
        < "${QUERIES_DIR}/setup_indexes.cypher" || {
        print_error "Failed to setup indexes"
        return 1
    }

    print_success "Indexes and constraints created"
}

# Export graph to JSON
export_json() {
    local output_file="${1:-graph_export.json}"
    print_info "Exporting graph to JSON: ${output_file}..."

    cypher-shell -a "${NEO4J_URL}" -u "${NEO4J_USER}" -p "${NEO4J_PASS}" \
        --format plain <<'CYPHER' > "${output_file}"
MATCH (n)
OPTIONAL MATCH (n)-[r]->(m)
WITH collect(DISTINCT n) as nodes, collect(DISTINCT r) as relationships
RETURN {
    nodes: nodes,
    relationships: relationships
} as graph;
CYPHER

    print_success "Graph exported to ${output_file}"
}

# Show help
show_help() {
    cat << EOF
Neo4j Utility Script for Vault Identity Graph Management

Usage: $0 [COMMAND] [OPTIONS]

Commands:
    test            Test connection to Neo4j
    stats           Show graph statistics (node/relationship counts)
    clear           Clear all data from the graph database
    backup          Create a backup of the graph database
    list-backups    List available backups
    restore FILE    Restore from a backup file
    validate        Run validation checks on the graph
    setup           Setup indexes and constraints
    export [FILE]   Export graph to JSON (default: graph_export.json)
    help            Show this help message

Environment Variables:
    NEO4J_URL       Neo4j connection URL (default: bolt://localhost:7687)
    NEO4J_USER      Neo4j username (default: neo4j)
    NEO4J_PASS      Neo4j password (default: vaultgraph123)

Examples:
    $0 test                                 # Test connection
    $0 stats                                # Show statistics
    $0 backup                               # Create backup
    $0 restore neo4j-backups/backup.cypher  # Restore from backup
    $0 validate                             # Run validation checks
    $0 export my-graph.json                 # Export to JSON

For more information, see docs/neo4j_setup.md
EOF
}

# Main command dispatcher
main() {
    local command="${1:-help}"

    # Check for cypher-shell except for help command
    if [ "$command" != "help" ]; then
        check_cypher_shell
    fi

    case "$command" in
        test)
            test_connection
            ;;
        stats)
            test_connection && show_stats
            ;;
        clear)
            test_connection && clear_graph
            ;;
        backup)
            test_connection && backup_graph
            ;;
        list-backups)
            list_backups
            ;;
        restore)
            test_connection && restore_backup "$2"
            ;;
        validate)
            test_connection && run_validation
            ;;
        setup)
            test_connection && setup_indexes
            ;;
        export)
            test_connection && export_json "$2"
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            print_error "Unknown command: $command"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

# Run main function
main "$@"
