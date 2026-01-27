#!/bin/bash
#
# E2E Test Script for Story-34: Complete E2E Test with Vault Entity Creation via Terraform
# Tests the full GitOps workflow: EntraID SCIM → YAML Generation → Terraform → Vault Entity
#
# Usage: ./scripts/e2e_test_entraid_scim.sh [test_user_name]
#
# Default test user: "Alice Johnson" (can be overridden with parameter)
#

set -e  # Exit on any error

# Configuration
VAULT_ADDR=${VAULT_ADDR:-"http://172.26.0.2:8200"}
VAULT_TOKEN=${VAULT_TOKEN:-"dev-root-token"}
TEST_USER=${1:-"Alice Johnson"}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[PASS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[FAIL]${NC} $1"
}

# Test result tracking
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

run_test() {
    local test_name="$1"
    local test_command="$2"
    
    TESTS_RUN=$((TESTS_RUN + 1))
    log_info "Running test: $test_name"
    
    if eval "$test_command" > /dev/null 2>&1; then
        log_success "$test_name"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        log_error "$test_name"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
}

# Verify prerequisites
verify_prerequisites() {
    log_info "=== Verifying Prerequisites ==="
    
    # Check Vault connectivity
    run_test "Vault server connectivity" "vault status"
    
    # Check Docker containers
    run_test "Vault container running" "docker ps --filter 'name=vault' --format 'table {{.Names}}' | grep -q vault"
    run_test "SCIM Bridge container running" "docker ps --filter 'name=scim-bridge' --format 'table {{.Names}}' | grep -q scim-bridge"
    
    # Check Terraform state
    run_test "Terraform initialized" "cd '$PROJECT_ROOT' && terraform version"
    
    echo
}

# Test YAML file validation
verify_yaml_files() {
    log_info "=== Verifying YAML Configuration Files ==="
    
    local yaml_file="$PROJECT_ROOT/identities/entraid_human_alice_johnson.yaml"
    
    run_test "SCIM-generated YAML exists" "test -f '$yaml_file'"
    
    if [ -f "$yaml_file" ]; then
        run_test "YAML contains entraid_object_id" "grep -q 'entraid_object_id:' '$yaml_file'"
        run_test "YAML contains provisioned_via_scim" "grep -q 'provisioned_via_scim: true' '$yaml_file'"
        run_test "YAML contains OIDC authentication" "grep -q 'oidc:' '$yaml_file'"
    fi
    
    echo
}

# Test Vault entity creation and management
verify_vault_entities() {
    log_info "=== Verifying Vault Entity Management ==="
    
    # Check if entity exists
    run_test "Vault entity exists" "vault list identity/entity/name | grep -q '$TEST_USER'"
    
    if vault list identity/entity/name | grep -q "$TEST_USER"; then
        # Get entity details
        local entity_output=$(vault read identity/entity/name/"$TEST_USER" -format=json)
        
        # Verify entity metadata
        run_test "Entity has entraid_object_id metadata" "echo '$entity_output' | jq -r '.data.metadata.entraid_object_id' | grep -q '^[a-f0-9-]\{36\}$'"
        run_test "Entity has email metadata" "echo '$entity_output' | jq -r '.data.metadata.email' | grep -q '@'"
        run_test "Entity has role metadata" "echo '$entity_output' | jq -r '.data.metadata.role' | grep -q '.'"
        run_test "Entity has status metadata" "echo '$entity_output' | jq -r '.data.metadata.status' | grep -qE '(active|deactivated)'"
        
        # Verify policies are assigned
        run_test "Entity has policies assigned" "echo '$entity_output' | jq -r '.data.policies[]' | grep -q 'policy'"
        
        # Check entity status
        local disabled_status=$(echo "$entity_output" | jq -r '.data.disabled')
        local status_metadata=$(echo "$entity_output" | jq -r '.data.metadata.status')
        
        if [ "$status_metadata" = "active" ]; then
            run_test "Active user has disabled=false" "[ '$disabled_status' = 'false' ]"
        elif [ "$status_metadata" = "deactivated" ]; then
            run_test "Deactivated user has disabled=true" "[ '$disabled_status' = 'true' ]"
        fi
    fi
    
    echo
}

# Test OIDC entity aliases
verify_entity_aliases() {
    log_info "=== Verifying OIDC Entity Aliases ==="
    
    if vault list identity/entity/name | grep -q "$TEST_USER"; then
        local entity_output=$(vault read identity/entity/name/"$TEST_USER" -format=json)
        local alias_id=$(echo "$entity_output" | jq -r '.data.aliases[0].id // empty')
        
        if [ -n "$alias_id" ]; then
            run_test "Entity has OIDC alias" "vault read identity/entity-alias/id/'$alias_id'"
            
            local alias_output=$(vault read identity/entity-alias/id/"$alias_id" -format=json)
            run_test "Alias linked to OIDC auth method" "echo '$alias_output' | jq -r '.data.mount_type' | grep -q 'oidc'"
            run_test "Alias has correct email format" "echo '$alias_output' | jq -r '.data.name' | grep -q '@'"
        else
            log_error "No aliases found for entity '$TEST_USER'"
            TESTS_FAILED=$((TESTS_FAILED + 1))
        fi
    fi
    
    echo
}

# Test Terraform integration
verify_terraform_integration() {
    log_info "=== Verifying Terraform Integration ==="
    
    cd "$PROJECT_ROOT"
    
    # Test basic terraform functionality
    run_test "Terraform validate passes" "terraform validate"
    run_test "Terraform workspace is default" "terraform workspace show | grep -q default"
    
    # Test terraform plan with timeout handling
    log_info "Running test: Terraform plan runs successfully"
    TESTS_RUN=$((TESTS_RUN + 1))
    
    if timeout 120 terraform plan -var-file=dev.tfvars >/dev/null 2>&1; then
        local plan_exit_code=$?
        if [ $plan_exit_code -eq 0 ] || [ $plan_exit_code -eq 2 ]; then
            log_success "Terraform plan runs successfully"
            TESTS_PASSED=$((TESTS_PASSED + 1))
            
            # Check plan details
            if [ $plan_exit_code -eq 0 ]; then
                log_success "Infrastructure is in sync (no pending changes)"
            else
                log_warning "Infrastructure has pending changes (expected during active testing)"
            fi
        else
            log_error "Terraform plan failed with exit code: $plan_exit_code"
            TESTS_FAILED=$((TESTS_FAILED + 1))
        fi
    else
        log_error "Terraform plan timed out or failed"
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi
    
    echo
}

# Test authentication backends
verify_auth_backends() {
    log_info "=== Verifying Authentication Backends ==="
    
    run_test "OIDC auth method exists" "vault auth list | grep -q 'oidc/'"
    
    if vault auth list | grep -q 'oidc/'; then
        run_test "OIDC auth method configured" "vault read auth/oidc/config"
        
        local oidc_config=$(vault read auth/oidc/config -format=json)
        run_test "OIDC has client_id configured" "echo '$oidc_config' | jq -r '.data.oidc_client_id' | grep -q '.'"
        run_test "OIDC has discovery_url configured" "echo '$oidc_config' | jq -r '.data.oidc_discovery_url' | grep -q 'microsoft'"
    fi
    
    echo
}

# Generate test summary
generate_summary() {
    log_info "=== Test Summary ==="
    echo "Tests Run: $TESTS_RUN"
    echo "Tests Passed: $TESTS_PASSED"
    echo "Tests Failed: $TESTS_FAILED"
    
    if [ $TESTS_FAILED -eq 0 ]; then
        log_success "ALL TESTS PASSED! ✅"
        echo
        log_info "E2E GitOps workflow validated successfully:"
        log_info "  ✅ SCIM provisioning → YAML generation"
        log_info "  ✅ Terraform state management"
        log_info "  ✅ Vault entity lifecycle (active/disabled)"
        log_info "  ✅ OIDC authentication integration"
        log_info "  ✅ EntraID metadata preservation"
        return 0
    else
        log_error "Some tests failed. Please check the output above."
        return 1
    fi
}

# Main execution
main() {
    echo "========================================="
    echo "E2E Test: EntraID SCIM → Vault Entities"
    echo "========================================="
    echo "Test User: $TEST_USER"
    echo "Vault URL: $VAULT_ADDR"
    echo "Timestamp: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
    echo "========================================="
    echo
    
    # Export Vault environment variables
    export VAULT_ADDR
    export VAULT_TOKEN
    
    # Run all test suites
    verify_prerequisites
    verify_yaml_files
    verify_vault_entities
    verify_entity_aliases
    verify_auth_backends
    verify_terraform_integration
    
    # Generate final summary
    generate_summary
}

# Execute main function
main "$@"