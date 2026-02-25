#!/bin/bash
#
# CyberArk RAG - Shell Integration for Zsh
#
# Add this to your ~/.zshrc:
#   source /path/to/cyberark-rag/shell/zshrc_integration.sh
#

# Resolve project root relative to this script
_CYBERARK_RAG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)"

# Add cyai to PATH
export PATH="$PATH:${_CYBERARK_RAG_DIR}/bin"

# Create cyai alias (alternative to PATH)
alias cyai="${_CYBERARK_RAG_DIR}/bin/cyai"

# Optional: Command not found handler
# Uncomment the lines below to suggest CyberArk commands when a command is not found
#
# command_not_found_handler() {
#     local cmd=$1
#     echo "Command '$cmd' not found."
#     echo ""
#     echo "Try CyberArk AI assistant:"
#     echo "   cyai $cmd"
#     return 127
# }

# Completion function for cyai (basic)
_cyai_completion() {
    local -a suggestions
    suggestions=(
        'configure:Configure CyberArk components'
        'show:Show CyberArk information'
        'rotate:Rotate secrets'
        'authenticate:Authentication commands'
        'install:Installation commands'
        'setup:Setup commands'
    )

    _describe 'cyai commands' suggestions
}

# Register completion
compdef _cyai_completion cyai

# Print integration message
echo "CyberArk RAG terminal integration loaded"
echo "  Use: cyai <natural language command>"
