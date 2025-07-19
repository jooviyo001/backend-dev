#!/bin/bash
# Script to configure Git settings for the project

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "${BLUE}Configuring Git settings for the project...${NC}"

# Check if we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo "${RED}Error: Not in a git repository${NC}"
    exit 1
fi

# Get project root directory
PROJECT_ROOT=$(git rev-parse --show-toplevel)
echo "Project root: $PROJECT_ROOT"

# Function to set git config with confirmation
set_git_config() {
    local key="$1"
    local value="$2"
    local description="$3"
    local scope="$4"  # local or global
    
    local current_value
    if [ "$scope" = "global" ]; then
        current_value=$(git config --global --get "$key" 2>/dev/null || echo "")
    else
        current_value=$(git config --get "$key" 2>/dev/null || echo "")
    fi
    
    if [ -n "$current_value" ] && [ "$current_value" != "$value" ]; then
        echo "${YELLOW}Current $key: $current_value${NC}"
        echo "${YELLOW}Proposed $key: $value${NC}"
        read -p "Do you want to update $description? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "${YELLOW}Skipping $description${NC}"
            return
        fi
    fi
    
    if [ "$scope" = "global" ]; then
        git config --global "$key" "$value"
        echo "${GREEN}✓ Set global $description${NC}"
    else
        git config "$key" "$value"
        echo "${GREEN}✓ Set local $description${NC}"
    fi
}

# Function to check and prompt for user info
check_user_info() {
    local user_name=$(git config --get user.name 2>/dev/null || echo "")
    local user_email=$(git config --get user.email 2>/dev/null || echo "")
    
    if [ -z "$user_name" ]; then
        echo "${YELLOW}Git user name is not set${NC}"
        read -p "Enter your name: " user_name
        if [ -n "$user_name" ]; then
            git config --global user.name "$user_name"
            echo "${GREEN}✓ Set user name: $user_name${NC}"
        fi
    else
        echo "${GREEN}✓ User name: $user_name${NC}"
    fi
    
    if [ -z "$user_email" ]; then
        echo "${YELLOW}Git user email is not set${NC}"
        read -p "Enter your email: " user_email
        if [ -n "$user_email" ]; then
            git config --global user.email "$user_email"
            echo "${GREEN}✓ Set user email: $user_email${NC}"
        fi
    else
        echo "${GREEN}✓ User email: $user_email${NC}"
    fi
}

echo "${BLUE}Checking user information...${NC}"
check_user_info

echo ""
echo "${BLUE}Configuring project-specific settings...${NC}"

# Set commit message template
if [ -f "$PROJECT_ROOT/.gitmessage" ]; then
    set_git_config "commit.template" "$PROJECT_ROOT/.gitmessage" "commit message template" "local"
fi

# Set hooks path
if [ -d "$PROJECT_ROOT/.githooks" ]; then
    set_git_config "core.hooksPath" "$PROJECT_ROOT/.githooks" "hooks path" "local"
fi

# Set line ending handling
set_git_config "core.autocrlf" "input" "line ending handling (autocrlf)" "local"
set_git_config "core.eol" "lf" "end of line character" "local"

# Set file mode handling (useful for Windows)
set_git_config "core.filemode" "false" "file mode tracking" "local"

# Set default branch name
set_git_config "init.defaultBranch" "main" "default branch name" "global"

# Set pull strategy
set_git_config "pull.rebase" "false" "pull strategy (merge)" "global"

# Set push strategy
set_git_config "push.default" "simple" "push strategy" "global"

# Set merge strategy
set_git_config "merge.ff" "false" "merge fast-forward strategy" "local"

echo ""
echo "${BLUE}Configuring helpful aliases...${NC}"

# Useful Git aliases
set_git_config "alias.st" "status" "status alias" "global"
set_git_config "alias.co" "checkout" "checkout alias" "global"
set_git_config "alias.br" "branch" "branch alias" "global"
set_git_config "alias.ci" "commit" "commit alias" "global"
set_git_config "alias.unstage" "reset HEAD --" "unstage alias" "global"
set_git_config "alias.last" "log -1 HEAD" "last commit alias" "global"
set_git_config "alias.visual" "!gitk" "visual alias" "global"

# Advanced aliases
set_git_config "alias.lg" "log --color --graph --pretty=format:'%Cred%h%Creset -%C(yellow)%d%Creset %s %Cgreen(%cr) %C(bold blue)<%an>%Creset' --abbrev-commit" "pretty log alias" "global"
set_git_config "alias.tree" "log --graph --pretty=format:'%Cred%h%Creset -%C(yellow)%d%Creset %s %Cgreen(%cr) %C(bold blue)<%an>%Creset' --abbrev-commit --all" "tree log alias" "global"
set_git_config "alias.amend" "commit --amend --no-edit" "amend alias" "global"
set_git_config "alias.fixup" "commit --fixup" "fixup alias" "global"
set_git_config "alias.squash" "commit --squash" "squash alias" "global"
set_git_config "alias.wip" "commit -am 'WIP'" "work in progress alias" "global"
set_git_config "alias.undo" "reset --soft HEAD~1" "undo last commit alias" "global"
set_git_config "alias.stash-all" "stash save --include-untracked" "stash all alias" "global"

echo ""
echo "${BLUE}Configuring diff and merge tools...${NC}"

# Configure diff tool (if available)
if command -v code >/dev/null 2>&1; then
    echo "${YELLOW}VS Code detected${NC}"
    read -p "Configure VS Code as diff/merge tool? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        set_git_config "diff.tool" "vscode" "diff tool" "global"
        set_git_config "difftool.vscode.cmd" "code --wait --diff \$LOCAL \$REMOTE" "diff tool command" "global"
        set_git_config "merge.tool" "vscode" "merge tool" "global"
        set_git_config "mergetool.vscode.cmd" "code --wait \$MERGED" "merge tool command" "global"
        set_git_config "mergetool.keepBackup" "false" "merge tool backup" "global"
    fi
elif command -v vim >/dev/null 2>&1; then
    echo "${YELLOW}Vim detected${NC}"
    read -p "Configure Vim as diff/merge tool? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        set_git_config "diff.tool" "vimdiff" "diff tool" "global"
        set_git_config "merge.tool" "vimdiff" "merge tool" "global"
    fi
fi

echo ""
echo "${BLUE}Configuring security settings...${NC}"

# Security settings
set_git_config "transfer.fsckobjects" "true" "transfer fsck" "global"
set_git_config "fetch.fsckobjects" "true" "fetch fsck" "global"
set_git_config "receive.fsckObjects" "true" "receive fsck" "global"

echo ""
echo "${BLUE}Configuring performance settings...${NC}"

# Performance settings
set_git_config "core.preloadindex" "true" "preload index" "global"
set_git_config "core.fscache" "true" "filesystem cache" "global"
set_git_config "gc.auto" "256" "garbage collection auto" "global"

echo ""
echo "${BLUE}Current Git configuration summary:${NC}"
echo "${YELLOW}User Information:${NC}"
echo "  Name: $(git config --get user.name)"
echo "  Email: $(git config --get user.email)"

echo ""
echo "${YELLOW}Project Settings:${NC}"
echo "  Commit template: $(git config --get commit.template || echo 'Not set')"
echo "  Hooks path: $(git config --get core.hooksPath || echo 'Not set')"
echo "  Line endings: $(git config --get core.autocrlf || echo 'Not set')"
echo "  Default branch: $(git config --get init.defaultBranch || echo 'Not set')"

echo ""
echo "${YELLOW}Tools:${NC}"
echo "  Diff tool: $(git config --get diff.tool || echo 'Not set')"
echo "  Merge tool: $(git config --get merge.tool || echo 'Not set')"

echo ""
echo "${GREEN}Git configuration completed!${NC}"
echo ""
echo "${BLUE}Next steps:${NC}"
echo "1. Test commit message template:"
echo "   ${YELLOW}git commit${NC} (will open editor with template)"
echo ""
echo "2. Test aliases:"
echo "   ${YELLOW}git st${NC} (status)"
echo "   ${YELLOW}git lg${NC} (pretty log)"
echo "   ${YELLOW}git tree${NC} (branch tree)"
echo ""
echo "3. Install Git hooks:"
echo "   ${YELLOW}bash .githooks/install-hooks.sh${NC}"
echo ""
echo "4. View current config:"
echo "   ${YELLOW}git config --list${NC}"
echo ""
echo "${GREEN}Happy coding! 🚀${NC}"

exit 0