#!/bin/bash

# Master deployment script for all workspaces
# This script commits and pushes changes to both main and master branches for all modified workspaces

set -e  # Exit on any error

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  QuidPath Multi-Workspace Deployment${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# List of all workspaces
WORKSPACES=("backend" "inventory" "frontend" "crm" "hrm" "pos" "project-management" "billing")

# Function to check if workspace has changes
has_changes() {
    local WORKSPACE=$1
    if [ -d "$WORKSPACE" ]; then
        cd "$WORKSPACE"
        if [[ -n $(git status -s) ]]; then
            cd ..
            return 0
        fi
        cd ..
    fi
    return 1
}

# Function to deploy a workspace
deploy_workspace() {
    local WORKSPACE=$1
    
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  Deploying: ${WORKSPACE}${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
    
    if [ ! -d "$WORKSPACE" ]; then
        echo -e "${YELLOW}Workspace ${WORKSPACE} not found, skipping...${NC}"
        echo ""
        return
    fi
    
    cd "$WORKSPACE"
    
    # Check if it's a git repository
    if [ ! -d ".git" ]; then
        echo -e "${YELLOW}${WORKSPACE} is not a git repository, skipping...${NC}"
        echo ""
        cd ..
        return
    fi
    
    # Check for changes
    if [[ -z $(git status -s) ]]; then
        echo -e "${GREEN}No changes in ${WORKSPACE}, skipping...${NC}"
        echo ""
        cd ..
        return
    fi
    
    # Get current branch
    CURRENT_BRANCH=$(git branch --show-current)
    echo -e "${BLUE}Current branch:${NC} ${CURRENT_BRANCH}"
    echo ""
    
    # Show changes
    echo -e "${YELLOW}Changes detected:${NC}"
    git status -s
    echo ""
    
    # Stage all changes
    echo -e "${GREEN}Staging changes...${NC}"
    git add .
    
    # Commit changes
    echo -e "${GREEN}Committing changes...${NC}"
    COMMIT_MESSAGE="Enhanced landing page pricing section and fixed card overflow issues"
    git commit -m "$COMMIT_MESSAGE" || echo -e "${YELLOW}Nothing to commit${NC}"
    echo ""
    
    # Function to push to a branch
    push_to_branch() {
        local BRANCH=$1
        echo -e "${BLUE}Pushing to ${BRANCH}...${NC}"
        
        # Check if branch exists locally
        if git show-ref --verify --quiet refs/heads/${BRANCH}; then
            git checkout ${BRANCH}
            
            # Merge changes from current branch if different
            if [ "$CURRENT_BRANCH" != "$BRANCH" ]; then
                git merge ${CURRENT_BRANCH} --no-edit || {
                    echo -e "${RED}Merge conflict detected. Please resolve manually.${NC}"
                    git merge --abort
                    return 1
                }
            fi
            
            # Push to remote
            git push origin ${BRANCH} || echo -e "${YELLOW}Failed to push to ${BRANCH}${NC}"
            echo -e "${GREEN}✓ Pushed to ${BRANCH}${NC}"
        else
            # Check if branch exists on remote
            if git ls-remote --heads origin ${BRANCH} | grep -q ${BRANCH}; then
                git checkout -b ${BRANCH} origin/${BRANCH}
                
                # Merge changes from current branch
                if [ "$CURRENT_BRANCH" != "$BRANCH" ]; then
                    git merge ${CURRENT_BRANCH} --no-edit || {
                        echo -e "${RED}Merge conflict detected. Please resolve manually.${NC}"
                        git merge --abort
                        return 1
                    }
                fi
                
                git push origin ${BRANCH} || echo -e "${YELLOW}Failed to push to ${BRANCH}${NC}"
                echo -e "${GREEN}✓ Pushed to ${BRANCH}${NC}"
            else
                echo -e "${YELLOW}Branch ${BRANCH} does not exist, creating...${NC}"
                git checkout -b ${BRANCH}
                git push -u origin ${BRANCH} || echo -e "${YELLOW}Failed to push to ${BRANCH}${NC}"
                echo -e "${GREEN}✓ Created and pushed to ${BRANCH}${NC}"
            fi
        fi
        echo ""
    }
    
    # Push to main and master
    push_to_branch "main"
    push_to_branch "master"
    
    # Return to original branch
    if [ "$CURRENT_BRANCH" != "main" ] && [ "$CURRENT_BRANCH" != "master" ]; then
        git checkout ${CURRENT_BRANCH}
    fi
    
    cd ..
    echo -e "${GREEN}✓ Completed deployment for ${WORKSPACE}${NC}"
    echo ""
}

# Prompt for commit message
echo -e "${BLUE}Enter commit message (press Enter for default):${NC}"
read -r CUSTOM_COMMIT_MESSAGE
echo ""

if [ -n "$CUSTOM_COMMIT_MESSAGE" ]; then
    COMMIT_MESSAGE="$CUSTOM_COMMIT_MESSAGE"
else
    COMMIT_MESSAGE="Enhanced landing page pricing section with individual/organization toggle and fixed card overflow issues"
fi

# Check which workspaces have changes
echo -e "${BLUE}Checking for changes in workspaces...${NC}"
echo ""

WORKSPACES_WITH_CHANGES=()
for WORKSPACE in "${WORKSPACES[@]}"; do
    if has_changes "$WORKSPACE"; then
        WORKSPACES_WITH_CHANGES+=("$WORKSPACE")
        echo -e "${GREEN}✓ ${WORKSPACE} has changes${NC}"
    else
        echo -e "${YELLOW}○ ${WORKSPACE} has no changes${NC}"
    fi
done
echo ""

# If no changes, exit
if [ ${#WORKSPACES_WITH_CHANGES[@]} -eq 0 ]; then
    echo -e "${YELLOW}No changes detected in any workspace${NC}"
    exit 0
fi

# Confirm deployment
echo -e "${BLUE}The following workspaces will be deployed:${NC}"
for WORKSPACE in "${WORKSPACES_WITH_CHANGES[@]}"; do
    echo -e "  • ${GREEN}${WORKSPACE}${NC}"
done
echo ""

echo -e "${YELLOW}Do you want to proceed? (y/n):${NC}"
read -r CONFIRM

if [ "$CONFIRM" != "y" ] && [ "$CONFIRM" != "Y" ]; then
    echo -e "${RED}Deployment cancelled${NC}"
    exit 0
fi
echo ""

# Deploy each workspace with changes
for WORKSPACE in "${WORKSPACES_WITH_CHANGES[@]}"; do
    deploy_workspace "$WORKSPACE"
done

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  All Deployments Complete! ✓${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${GREEN}Deployed workspaces:${NC}"
for WORKSPACE in "${WORKSPACES_WITH_CHANGES[@]}"; do
    echo -e "  • ${GREEN}${WORKSPACE}${NC} → main & master"
done
echo ""
echo -e "${BLUE}Summary of changes:${NC}"
echo -e "  • Enhanced landing page pricing section"
echo -e "  • Added individual/organization plan toggle"
echo -e "  • Fixed card overflow issues"
echo -e "  • Improved 'Most Popular' badge positioning"
echo -e "  • Better content layout and spacing"
echo -e "  • Consistent theme colors throughout"
echo ""
