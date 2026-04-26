#!/bin/bash
# Master script to commit and deploy all services

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo "=========================================="
echo "Deploy All Services to Production"
echo "=========================================="
echo ""

# Commit message
COMMIT_MSG="fix: Disable stage deployments and fix network configuration

- Disabled stage deployments (only master triggers production)
- Fixed docker-compose network configuration (non-external)
- Networks will be created automatically on deployment
- Updated prod network to prod_quidpath_network
- Updated stage network to stage_quidpath_network (auto-create)
- Added network ensure scripts and comprehensive documentation

This fixes the POS integration issue where services couldn't communicate
due to missing Docker network."

# Function to process a repository
process_repo() {
    local repo_path=$1
    local repo_name=$2
    
    echo ""
    echo -e "${BLUE}=========================================="
    echo "Processing: $repo_name"
    echo "==========================================${NC}"
    
    if [ ! -d "$repo_path" ]; then
        echo -e "${RED}Directory not found: $repo_path${NC}"
        return 1
    fi
    
    cd "$repo_path"
    
    # Check if it's a git repository
    if [ ! -d ".git" ]; then
        echo -e "${RED}Not a git repository: $repo_path${NC}"
        return 1
    fi
    
    # Get current branch
    CURRENT_BRANCH=$(git branch --show-current)
    echo "Current branch: $CURRENT_BRANCH"
    
    # Switch to Development if not already there
    if [ "$CURRENT_BRANCH" != "Development" ]; then
        echo "Switching to Development branch..."
        git checkout Development 2>/dev/null || git checkout -b Development
    fi
    
    # Check if there are changes
    if git diff --quiet && git diff --cached --quiet; then
        echo -e "${YELLOW}No changes to commit in $repo_name${NC}"
        return 0
    fi
    
    # Add all changes
    echo "Adding changes..."
    git add -A
    
    # Show status
    echo "Files changed:"
    git status --short
    
    # Commit
    echo "Committing..."
    git commit -m "$COMMIT_MSG" || {
        echo -e "${YELLOW}Commit failed (maybe no changes)${NC}"
        return 0
    }
    
    # Push to Development
    echo "Pushing to Development..."
    git push origin Development || git push --set-upstream origin Development
    
    echo -e "${GREEN}✓ $repo_name: Pushed to Development${NC}"
}

# Get the base directory
BASE_DIR=$(pwd)

# Process backend
process_repo "$BASE_DIR/backend" "Backend"

# Process inventory
process_repo "$BASE_DIR/inventory" "Inventory"

echo ""
echo -e "${GREEN}=========================================="
echo "All repositories processed!"
echo "==========================================${NC}"
echo ""
echo "Changes have been pushed to Development branch."
echo "No deployment will occur (as configured)."
echo ""
echo -e "${YELLOW}To deploy to production:${NC}"
echo ""
echo "Option 1: Via GitHub (Recommended)"
echo "  1. Go to each repository on GitHub"
echo "  2. Create Pull Request: Development → master"
echo "  3. Review and merge the PR"
echo "  4. Production deployment will trigger automatically"
echo ""
echo "Option 2: Via Command Line"
echo "  Run the following for each repository:"
echo ""
echo "  cd backend"
echo "  git checkout master"
echo "  git merge Development"
echo "  git push origin master"
echo ""
echo "  cd ../inventory"
echo "  git checkout master"
echo "  git merge Development"
echo "  git push origin master"
echo ""
echo -e "${BLUE}Repositories to update:${NC}"
echo "  - backend"
echo "  - inventory"
echo ""
echo "Note: Other services (frontend, pos, crm, hrm, projects, billing)"
echo "      have their stage workflows disabled but no code changes."
echo "      They will deploy normally when you push to their master branches."
echo ""
