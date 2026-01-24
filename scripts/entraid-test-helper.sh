#!/bin/bash
# EntraID SCIM Testing Helper Script
#
# This script provides utilities for testing the SCIM Bridge integration
# with real Microsoft EntraID (Azure AD) using ngrok tunnels.
#
# Usage: ./scripts/entraid-test-helper.sh <command>
#
# Commands:
#   start-services    Start Vault and SCIM Bridge containers
#   start-ngrok       Start ngrok tunnel (requires ngrok installed)
#   check-health      Check SCIM Bridge health through ngrok
#   show-config       Display configuration for EntraID setup
#   watch-logs        Tail SCIM Bridge logs with filtering
#   list-prs          List recent SCIM-related PRs
#   test-auth         Test SCIM authentication
#   user-store        Show current user mappings
#   cleanup           Stop services and clean up
#   help              Show this help message

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
SCIM_BRIDGE_PORT="${SCIM_BRIDGE_PORT:-8080}"
NGROK_PORT="${NGROK_PORT:-4040}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Helper functions
print_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

print_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_info() {
    echo -e "${CYAN}[INFO]${NC} $1"
}

check_env_vars() {
    local missing=0

    if [ -z "$SCIM_BEARER_TOKEN" ]; then
        print_warning "SCIM_BEARER_TOKEN not set"
        missing=1
    fi

    if [ -z "$GITHUB_TOKEN" ]; then
        print_warning "GITHUB_TOKEN not set"
        missing=1
    fi

    if [ -z "$GIT_REPO_URL" ]; then
        print_warning "GIT_REPO_URL not set"
        missing=1
    fi

    if [ $missing -eq 1 ]; then
        echo ""
        print_info "Load environment variables with: source .env"
        return 1
    fi

    return 0
}

get_ngrok_url() {
    # Try to get ngrok URL from the API
    local ngrok_info
    ngrok_info=$(curl -s http://localhost:${NGROK_PORT}/api/tunnels 2>/dev/null || echo "")

    if [ -n "$ngrok_info" ] && echo "$ngrok_info" | grep -q "public_url"; then
        echo "$ngrok_info" | grep -o '"public_url":"[^"]*"' | head -1 | cut -d'"' -f4
    else
        echo ""
    fi
}

# Command implementations
cmd_start_services() {
    print_header "Starting SCIM Bridge Services"

    cd "$PROJECT_ROOT"

    print_info "Building SCIM Bridge image..."
    docker compose build scim-bridge

    print_info "Starting Vault and SCIM Bridge..."
    docker compose up -d vault scim-bridge

    print_info "Waiting for services to be ready..."
    sleep 10

    # Check health
    local health
    health=$(curl -s http://localhost:${SCIM_BRIDGE_PORT}/health 2>/dev/null || echo '{"status":"unhealthy"}')

    if echo "$health" | grep -q '"status":"healthy"'; then
        print_success "SCIM Bridge is healthy!"
        echo "$health" | python3 -m json.tool 2>/dev/null || echo "$health"
    else
        print_error "SCIM Bridge is not healthy"
        echo "$health"
        return 1
    fi
}

cmd_start_ngrok() {
    print_header "Starting ngrok Tunnel"

    if ! command -v ngrok &> /dev/null; then
        print_error "ngrok is not installed. Install from https://ngrok.com/download"
        return 1
    fi

    # Check if ngrok is already running
    if curl -s http://localhost:${NGROK_PORT}/api/tunnels &> /dev/null; then
        print_warning "ngrok is already running"
        local url
        url=$(get_ngrok_url)
        if [ -n "$url" ]; then
            print_success "ngrok URL: $url"
            print_info "SCIM Endpoint: ${url}/scim/v2"
        fi
        return 0
    fi

    print_info "Starting ngrok on port ${SCIM_BRIDGE_PORT}..."
    print_info "Press Ctrl+C to stop ngrok"
    echo ""

    ngrok http ${SCIM_BRIDGE_PORT}
}

cmd_check_health() {
    print_header "Checking SCIM Bridge Health"

    # Check local health
    print_info "Local health check (localhost:${SCIM_BRIDGE_PORT})..."
    local local_health
    local_health=$(curl -s http://localhost:${SCIM_BRIDGE_PORT}/health 2>/dev/null || echo '{"error":"Cannot connect"}')

    if echo "$local_health" | grep -q '"status":"healthy"'; then
        print_success "Local SCIM Bridge is healthy"
    else
        print_error "Local SCIM Bridge is not healthy"
        echo "$local_health"
    fi

    # Check ngrok health
    local ngrok_url
    ngrok_url=$(get_ngrok_url)

    if [ -n "$ngrok_url" ]; then
        print_info "ngrok health check (${ngrok_url})..."
        local ngrok_health
        ngrok_health=$(curl -s "${ngrok_url}/health" 2>/dev/null || echo '{"error":"Cannot connect"}')

        if echo "$ngrok_health" | grep -q '"status":"healthy"'; then
            print_success "ngrok tunnel is working"
        else
            print_error "ngrok tunnel is not working"
            echo "$ngrok_health"
        fi
    else
        print_warning "ngrok is not running. Start with: $0 start-ngrok"
    fi
}

cmd_show_config() {
    print_header "SCIM Bridge Configuration"

    # Check environment
    echo -e "${CYAN}Environment Variables:${NC}"
    if [ -n "$SCIM_BEARER_TOKEN" ]; then
        echo "  SCIM_BEARER_TOKEN: ${SCIM_BEARER_TOKEN:0:20}... (${#SCIM_BEARER_TOKEN} chars)"
    else
        echo "  SCIM_BEARER_TOKEN: [NOT SET]"
    fi

    if [ -n "$GIT_REPO_URL" ]; then
        echo "  GIT_REPO_URL: $GIT_REPO_URL"
    else
        echo "  GIT_REPO_URL: [NOT SET]"
    fi

    if [ -n "$GITHUB_TOKEN" ]; then
        echo "  GITHUB_TOKEN: ${GITHUB_TOKEN:0:10}... (set)"
    else
        echo "  GITHUB_TOKEN: [NOT SET]"
    fi

    echo ""

    # Get ngrok URL
    local ngrok_url
    ngrok_url=$(get_ngrok_url)

    echo -e "${CYAN}EntraID Configuration Values:${NC}"
    if [ -n "$ngrok_url" ]; then
        echo "  Tenant URL:    ${ngrok_url}/scim/v2"
        echo "  Secret Token:  [Copy from SCIM_BEARER_TOKEN above]"
        echo ""
        print_success "Copy these values to your EntraID Enterprise Application"
    else
        print_warning "ngrok is not running"
        echo "  Start ngrok first: $0 start-ngrok"
        echo ""
        echo "  Once running, use:"
        echo "  Tenant URL:    https://<ngrok-url>/scim/v2"
        echo "  Secret Token:  \$SCIM_BEARER_TOKEN"
    fi

    echo ""
    echo -e "${CYAN}Local Endpoints:${NC}"
    echo "  Health:     http://localhost:${SCIM_BRIDGE_PORT}/health"
    echo "  SCIM Users: http://localhost:${SCIM_BRIDGE_PORT}/scim/v2/Users"
    echo "  API Docs:   http://localhost:${SCIM_BRIDGE_PORT}/docs"
    echo "  ngrok UI:   http://localhost:${NGROK_PORT}"
}

cmd_watch_logs() {
    print_header "SCIM Bridge Logs"

    print_info "Watching SCIM Bridge logs (Ctrl+C to stop)..."
    echo ""

    docker logs -f scim-bridge 2>&1 | while read line; do
        # Colorize log output
        if echo "$line" | grep -qi "error"; then
            echo -e "${RED}$line${NC}"
        elif echo "$line" | grep -qi "warning\|warn"; then
            echo -e "${YELLOW}$line${NC}"
        elif echo "$line" | grep -qi "success\|created\|updated"; then
            echo -e "${GREEN}$line${NC}"
        elif echo "$line" | grep -qi "POST\|PATCH\|DELETE\|GET"; then
            echo -e "${CYAN}$line${NC}"
        else
            echo "$line"
        fi
    done
}

cmd_list_prs() {
    print_header "Recent SCIM Provisioning PRs"

    if ! command -v gh &> /dev/null; then
        print_warning "GitHub CLI (gh) not installed"
        print_info "Install from: https://cli.github.com/"
        return 1
    fi

    # Extract repo from GIT_REPO_URL
    local repo
    if [ -n "$GIT_REPO_URL" ]; then
        repo=$(echo "$GIT_REPO_URL" | sed -E 's|.*github\.com[:/]([^/]+/[^/]+)(\.git)?$|\1|')
    fi

    if [ -z "$repo" ]; then
        print_error "Cannot determine repository from GIT_REPO_URL"
        return 1
    fi

    print_info "Fetching PRs from $repo..."
    echo ""

    # List open SCIM PRs
    echo -e "${CYAN}Open SCIM PRs:${NC}"
    gh pr list --repo "$repo" --label scim-provisioning --state open 2>/dev/null || echo "  None found"

    echo ""

    # List recently closed SCIM PRs
    echo -e "${CYAN}Recently Merged SCIM PRs:${NC}"
    gh pr list --repo "$repo" --label scim-provisioning --state merged --limit 5 2>/dev/null || echo "  None found"
}

cmd_test_auth() {
    print_header "Testing SCIM Authentication"

    if ! check_env_vars; then
        return 1
    fi

    local ngrok_url
    ngrok_url=$(get_ngrok_url)
    local test_url="${ngrok_url:-http://localhost:${SCIM_BRIDGE_PORT}}"

    print_info "Testing with URL: $test_url"
    echo ""

    # Test with valid token
    echo -e "${CYAN}Testing with valid bearer token:${NC}"
    local valid_response
    valid_response=$(curl -s -w "\n%{http_code}" \
        -H "Authorization: Bearer $SCIM_BEARER_TOKEN" \
        "${test_url}/scim/v2/Users" 2>/dev/null)

    local http_code="${valid_response##*$'\n'}"
    local body="${valid_response%$'\n'*}"

    if [ "$http_code" = "200" ]; then
        print_success "Valid token accepted (HTTP $http_code)"
        echo "$body" | python3 -m json.tool 2>/dev/null | head -10 || echo "$body"
    else
        print_error "Valid token rejected (HTTP $http_code)"
        echo "$body"
    fi

    echo ""

    # Test with invalid token
    echo -e "${CYAN}Testing with invalid bearer token:${NC}"
    local invalid_response
    invalid_response=$(curl -s -w "\n%{http_code}" \
        -H "Authorization: Bearer invalid-token-12345" \
        "${test_url}/scim/v2/Users" 2>/dev/null)

    http_code="${invalid_response##*$'\n'}"
    body="${invalid_response%$'\n'*}"

    if [ "$http_code" = "401" ]; then
        print_success "Invalid token correctly rejected (HTTP $http_code)"
    else
        print_warning "Unexpected response for invalid token (HTTP $http_code)"
        echo "$body"
    fi
}

cmd_user_store() {
    print_header "User Store Contents"

    print_info "Current user mappings:"
    echo ""

    docker exec scim-bridge cat /data/user_mapping.json 2>/dev/null | python3 -m json.tool 2>/dev/null || echo "No users in store or file not found"
}

cmd_cleanup() {
    print_header "Cleanup"

    print_info "Stopping Docker services..."
    cd "$PROJECT_ROOT"
    docker compose down

    print_info "Cleaning up volumes (optional)..."
    read -p "Remove SCIM data volume? (y/N) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        docker volume rm vault-config-as-code_scim-data 2>/dev/null || true
        print_success "SCIM data volume removed"
    fi

    print_success "Cleanup complete"
    print_info "Remember to stop ngrok if it's still running (Ctrl+C)"
}

cmd_help() {
    cat << EOF
EntraID SCIM Testing Helper Script

Usage: $(basename "$0") <command>

Commands:
  start-services    Start Vault and SCIM Bridge Docker containers
  start-ngrok       Start ngrok tunnel to expose SCIM Bridge
  check-health      Check SCIM Bridge health (local and through ngrok)
  show-config       Display configuration values for EntraID setup
  watch-logs        Tail SCIM Bridge logs with color highlighting
  list-prs          List recent SCIM-related GitHub PRs
  test-auth         Test SCIM authentication with bearer tokens
  user-store        Show current user ID mappings
  cleanup           Stop services and optionally clean up volumes
  help              Show this help message

Prerequisites:
  - Docker and Docker Compose installed
  - ngrok installed (for tunneling)
  - Environment variables set: SCIM_BEARER_TOKEN, GITHUB_TOKEN, GIT_REPO_URL

Quick Start:
  1. source .env                    # Load environment variables
  2. $0 start-services              # Start SCIM Bridge
  3. $0 start-ngrok                 # Start ngrok tunnel (new terminal)
  4. $0 show-config                 # Get values for EntraID configuration

For detailed instructions, see:
  docs/ENTRAID_E2E_TESTING_RUNBOOK.md
EOF
}

# Main entry point
main() {
    local command="${1:-help}"

    case "$command" in
        start-services)
            cmd_start_services
            ;;
        start-ngrok)
            cmd_start_ngrok
            ;;
        check-health)
            cmd_check_health
            ;;
        show-config)
            cmd_show_config
            ;;
        watch-logs)
            cmd_watch_logs
            ;;
        list-prs)
            cmd_list_prs
            ;;
        test-auth)
            cmd_test_auth
            ;;
        user-store)
            cmd_user_store
            ;;
        cleanup)
            cmd_cleanup
            ;;
        help|--help|-h)
            cmd_help
            ;;
        *)
            print_error "Unknown command: $command"
            echo ""
            cmd_help
            exit 1
            ;;
    esac
}

main "$@"
