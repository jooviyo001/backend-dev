#!/bin/bash
# Script to install Git hooks for the project

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "${BLUE}Installing Git hooks...${NC}"

# Check if we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo "${RED}Error: Not in a git repository${NC}"
    exit 1
fi

# Get the git directory
GIT_DIR=$(git rev-parse --git-dir)
HOOKS_DIR="$GIT_DIR/hooks"
PROJECT_HOOKS_DIR="$(pwd)/.githooks"

echo "Git directory: $GIT_DIR"
echo "Hooks directory: $HOOKS_DIR"
echo "Project hooks directory: $PROJECT_HOOKS_DIR"

# Check if project hooks directory exists
if [ ! -d "$PROJECT_HOOKS_DIR" ]; then
    echo "${RED}Error: Project hooks directory not found: $PROJECT_HOOKS_DIR${NC}"
    exit 1
fi

# Create hooks directory if it doesn't exist
if [ ! -d "$HOOKS_DIR" ]; then
    mkdir -p "$HOOKS_DIR"
    echo "Created hooks directory: $HOOKS_DIR"
fi

# Function to install a hook
install_hook() {
    local hook_name="$1"
    local source_file="$PROJECT_HOOKS_DIR/$hook_name"
    local target_file="$HOOKS_DIR/$hook_name"
    
    if [ ! -f "$source_file" ]; then
        echo "${YELLOW}Warning: Hook file not found: $source_file${NC}"
        return 1
    fi
    
    # Backup existing hook if it exists
    if [ -f "$target_file" ]; then
        echo "${YELLOW}Backing up existing $hook_name hook${NC}"
        cp "$target_file" "$target_file.backup.$(date +%Y%m%d_%H%M%S)"
    fi
    
    # Copy the hook
    cp "$source_file" "$target_file"
    
    # Make it executable
    chmod +x "$target_file"
    
    echo "${GREEN}✓ Installed $hook_name hook${NC}"
    return 0
}

# Install available hooks
HOOKS_INSTALLED=0
HOOKS_FAILED=0

echo "${BLUE}Installing hooks...${NC}"

# List of hooks to install
HOOKS=("pre-commit" "commit-msg" "pre-push")

for hook in "${HOOKS[@]}"; do
    if install_hook "$hook"; then
        HOOKS_INSTALLED=$((HOOKS_INSTALLED + 1))
    else
        HOOKS_FAILED=$((HOOKS_FAILED + 1))
    fi
done

# Install any other hooks found in the project hooks directory
echo "${BLUE}Checking for additional hooks...${NC}"
for hook_file in "$PROJECT_HOOKS_DIR"/*; do
    if [ -f "$hook_file" ]; then
        hook_name=$(basename "$hook_file")
        # Skip if already processed or if it's not a hook file
        if [[ " ${HOOKS[@]} " =~ " ${hook_name} " ]] || [[ "$hook_name" == *.sh ]] || [[ "$hook_name" == *.md ]] || [[ "$hook_name" == *.txt ]]; then
            continue
        fi
        
        if install_hook "$hook_name"; then
            HOOKS_INSTALLED=$((HOOKS_INSTALLED + 1))
        else
            HOOKS_FAILED=$((HOOKS_FAILED + 1))
        fi
    fi
done

# Configure Git to use the hooks directory (Git 2.9+)
echo "${BLUE}Configuring Git hooks path...${NC}"
if git config core.hooksPath "$PROJECT_HOOKS_DIR" 2>/dev/null; then
    echo "${GREEN}✓ Configured Git to use project hooks directory${NC}"
    echo "${YELLOW}Note: This requires Git 2.9 or later${NC}"
else
    echo "${YELLOW}Warning: Could not configure Git hooks path${NC}"
    echo "${YELLOW}Using traditional hooks installation method${NC}"
fi

# Summary
echo ""
echo "${BLUE}Installation Summary:${NC}"
echo "${GREEN}✓ Hooks installed: $HOOKS_INSTALLED${NC}"
if [ $HOOKS_FAILED -gt 0 ]; then
    echo "${RED}✗ Hooks failed: $HOOKS_FAILED${NC}"
fi

echo ""
echo "${BLUE}Installed hooks:${NC}"
for hook_file in "$HOOKS_DIR"/*; do
    if [ -f "$hook_file" ] && [ -x "$hook_file" ]; then
        hook_name=$(basename "$hook_file")
        echo "  - $hook_name"
    fi
done

echo ""
echo "${BLUE}Hook descriptions:${NC}"
echo "  ${YELLOW}pre-commit${NC}:  Runs code quality checks before each commit"
echo "  ${YELLOW}commit-msg${NC}:  Validates commit message format (conventional commits)"
echo "  ${YELLOW}pre-push${NC}:   Runs comprehensive checks before pushing to remote"

echo ""
echo "${GREEN}Git hooks installation completed!${NC}"
echo ""
echo "${BLUE}Next steps:${NC}"
echo "1. Install development dependencies:"
echo "   ${YELLOW}pip install -r requirements-dev.txt${NC}"
echo ""
echo "2. Test the hooks:"
echo "   ${YELLOW}git add . && git commit -m \"test: verify hooks installation\"${NC}"
echo ""
echo "3. To bypass hooks temporarily (not recommended):"
echo "   ${YELLOW}git commit --no-verify${NC}"
echo "   ${YELLOW}git push --no-verify${NC}"
echo ""
echo "4. To uninstall hooks:"
echo "   ${YELLOW}rm -f $HOOKS_DIR/pre-commit $HOOKS_DIR/commit-msg $HOOKS_DIR/pre-push${NC}"
echo "   ${YELLOW}git config --unset core.hooksPath${NC}"
echo ""
echo "${GREEN}Happy coding! 🚀${NC}"

exit 0