#!/bin/bash
# Wrapper script for Ralph Loop - runs from project root
exec "$(dirname "$0")/.ralph-loop/ralph-claude.sh" "$@"
