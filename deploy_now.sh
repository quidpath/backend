#!/bin/bash
cd "$(dirname "$0")"

# Configure git
git config user.email "bethwel@quidpath.com"
git config user.name "Bethwel Kimutai"

# Ensure on Development branch
git checkout Development

# Add all changes
git add -A

# Commit
git commit -m "fix: Disable stage deployments and fix network configuration"

# Push to Development
git push origin Development

# Merge to master
git checkout master
git pull origin master
git merge Development -m "Merge Development: Fix network configuration and disable stage deployments"
git push origin master

echo "Backend deployed to production!"
