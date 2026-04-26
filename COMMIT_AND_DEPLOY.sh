#!/bin/bash
# Script to commit changes and create PR for deployment

set -e

echo "=========================================="
echo "Backend: Commit and Deploy Script"
echo "=========================================="

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Step 1: Check current branch
echo -e "${BLUE}Step 1: Checking current branch...${NC}"
CURRENT_BRANCH=$(git branch --show-current)
echo "Current branch: $CURRENT_BRANCH"

# Step 2: Ensure we're on Development branch
if [ "$CURRENT_BRANCH" != "Development" ]; then
    echo -e "${YELLOW}Switching to Development branch...${NC}"
    git checkout Development || {
        echo "Creating Development branch..."
        git checkout -b Development
    }
fi

# Step 3: Add all changes
echo -e "${BLUE}Step 2: Adding changes...${NC}"
git add -A

# Step 4: Show what will be committed
echo -e "${BLUE}Step 3: Files to be committed:${NC}"
git status --short

# Step 5: Commit changes
echo -e "${BLUE}Step 4: Committing changes...${NC}"
git commit -m "fix: Disable stage deployments and fix network configuration

- Disabled stage deployments (only master triggers production)
- Fixed docker-compose network configuration (non-external)
- Updated prod network to prod_quidpath_network
- Updated stage network to stage_quidpath_network (auto-create)
- Added network ensure scripts
- Networks will be created automatically on deployment

This fixes the POS integration issue where services couldn't communicate
due to missing Docker network." || {
    echo -e "${YELLOW}No changes to commit or commit failed${NC}"
}

# Step 6: Push to Development
echo -e "${BLUE}Step 5: Pushing to Development branch...${NC}"
git push origin Development || {
    echo -e "${YELLOW}Push failed. You may need to set upstream:${NC}"
    echo "git push --set-upstream origin Development"
}

echo ""
echo -e "${GREEN}=========================================="
echo "Changes pushed to Development branch!"
echo "==========================================${NC}"
echo ""
echo "Next steps:"
echo "1. Go to GitHub repository"
echo "2. Create a Pull Request from Development to master"
echo "3. Review the changes"
echo "4. Merge the PR"
echo "5. Production deployment will trigger automatically"
echo ""
echo "Or run these commands to merge directly:"
echo ""
echo "  git checkout master"
echo "  git merge Development"
echo "  git push origin master"
echo ""
