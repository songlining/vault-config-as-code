#!/bin/bash

# Ralph Loop - Autonomous Agent Iteration System
# This script orchestrates Claude Code agents to complete project stories

set -e

# Get script directory and change to it
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Also change to project root (parent directory) for git/terraform operations
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Configuration
PRD_FILE="$SCRIPT_DIR/prd.json"
PROMPT_FILE="$SCRIPT_DIR/prompt.md"
PROGRESS_FILE="$SCRIPT_DIR/progress.txt"
AGENTS_FILE="$SCRIPT_DIR/AGENTS.md"
MAX_ITERATIONS=20
MAX_RETRIES=5
RETRY_DELAY=60

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print colored message
print_status() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# Check prerequisites
check_prerequisites() {
    print_status "$BLUE" "Checking prerequisites..."

    # Check for Claude CLI
    if ! command -v claude &> /dev/null; then
        print_status "$RED" "Error: Claude CLI is not installed"
        print_status "$YELLOW" "Install it from: https://claude.ai/code"
        exit 1
    fi

    # Check for jq
    if ! command -v jq &> /dev/null; then
        print_status "$RED" "Error: jq is not installed"
        print_status "$YELLOW" "Install it with: brew install jq (macOS) or apt install jq (Linux)"
        exit 1
    fi

    # Check for required files
    if [[ ! -f "$PRD_FILE" ]]; then
        print_status "$RED" "Error: $PRD_FILE not found"
        exit 1
    fi

    if [[ ! -f "$PROMPT_FILE" ]]; then
        print_status "$RED" "Error: $PROMPT_FILE not found"
        exit 1
    fi

    # Check if git repo
    if ! git rev-parse --is-inside-work-tree &> /dev/null; then
        print_status "$RED" "Error: Not a git repository"
        print_status "$YELLOW" "Initialize with: git init"
        exit 1
    fi

    print_status "$GREEN" "All prerequisites met!"
}

# Count incomplete stories
count_incomplete_stories() {
    jq '[.stories[] | select(.passes == false)] | length' "$PRD_FILE"
}

# Get next incomplete story
get_next_story() {
    jq -r '.stories[] | select(.passes == false) | .id' "$PRD_FILE" | head -1
}

# Get story details
get_story_details() {
    local story_id=$1
    jq -r ".stories[] | select(.id == \"$story_id\")" "$PRD_FILE"
}

# Run agent for a story
run_agent() {
    local story_id=$1
    local story_details=$(get_story_details "$story_id")
    local story_title=$(echo "$story_details" | jq -r '.title')
    local story_description=$(echo "$story_details" | jq -r '.description')
    local acceptance_criteria=$(echo "$story_details" | jq -r '.acceptance_criteria | join("\n- ")')

    print_status "$BLUE" "Working on: $story_id - $story_title"

    local prompt="You are an autonomous agent working on completing a project story.

CRITICAL: Before starting, read these files to understand context:
1. Read $PROMPT_FILE - Project requirements and instructions
2. Read $PROGRESS_FILE - Learnings from previous iterations
3. Read $AGENTS_FILE - Patterns, gotchas, and reusable solutions

WORKING DIRECTORY: $PROJECT_ROOT

CURRENT STORY TO COMPLETE:
ID: $story_id
Title: $story_title
Description: $story_description

ACCEPTANCE CRITERIA (ALL must be met):
- $acceptance_criteria

YOUR WORKFLOW:
1. READ PHASE: Read prompt.md, progress.txt, and AGENTS.md first
2. IMPLEMENT PHASE: Create/modify code, configurations, scripts as needed
3. VERIFY PHASE: Test thoroughly and verify ALL acceptance criteria are met
4. UPDATE STATE PHASE:
   - Update $PRD_FILE: Set passes=true for this story
   - Append learnings to $PROGRESS_FILE
   - Update $AGENTS_FILE with any new patterns or gotchas
5. GIT COMMIT PHASE: Commit all changes with a descriptive message

IMPORTANT RULES:
- Do NOT mark a story as complete unless ALL acceptance criteria are verified
- Document any issues, workarounds, or learnings
- Test each component after implementation
- If you encounter errors, debug and fix them before proceeding"

    cd "$PROJECT_ROOT"
    claude --dangerously-skip-permissions -p "$prompt"
    cd "$SCRIPT_DIR"
}

# Main loop
main() {
    print_status "$BLUE" "=========================================="
    print_status "$BLUE" "   Ralph Loop - Autonomous Agent System   "
    print_status "$BLUE" "=========================================="

    check_prerequisites

    local iteration=1
    while [[ $iteration -le $MAX_ITERATIONS ]]; do
        print_status "$YELLOW" "\n=== Iteration $iteration of $MAX_ITERATIONS ==="

        local incomplete=$(count_incomplete_stories)

        if [[ $incomplete -eq 0 ]]; then
            print_status "$GREEN" "\n=========================================="
            print_status "$GREEN" "   ALL STORIES COMPLETE! PROJECT DONE!   "
            print_status "$GREEN" "=========================================="
            exit 0
        fi

        print_status "$BLUE" "Stories remaining: $incomplete"

        local next_story=$(get_next_story)

        if [[ -z "$next_story" ]]; then
            print_status "$RED" "Error: Could not determine next story"
            exit 1
        fi

        local retry=1
        while [[ $retry -le $MAX_RETRIES ]]; do
            print_status "$BLUE" "Attempt $retry of $MAX_RETRIES for $next_story"

            if run_agent "$next_story"; then
                print_status "$GREEN" "Agent completed successfully"
                break
            else
                print_status "$YELLOW" "Agent failed, waiting ${RETRY_DELAY}s before retry..."
                sleep $RETRY_DELAY
                ((retry++))
            fi
        done

        if [[ $retry -gt $MAX_RETRIES ]]; then
            print_status "$RED" "Max retries exceeded for $next_story"
            exit 1
        fi

        ((iteration++))
    done

    print_status "$YELLOW" "Max iterations reached. Some stories may be incomplete."
    exit 1
}

main "$@"
