#!/bin/bash
set -x  # Print commands as they execute

echo "=== Starting Backend Deployment ==="

# Configure git
git config user.email "bethwel@quidpath.com"
git config user.name "Bethwel Kimutai"

# Show current status
echo "=== Current Status ==="
git status

# Checkout Development
echo "=== Switching to Development ==="
git checkout Development

# Add all changes
echo "=== Adding changes ==="
git add -A

# Show what will be committed
echo "=== Files to commit ==="
git status --short

# Commit
echo "=== Committing ==="
git commit -m "fix: Disable stage deployments and fix network configuration"

# Push to Development
echo "=== Pushing to Development ==="
git push origin Development

# Checkout master
echo "=== Switching to master ==="
git checkout master

# Pull latest
echo "=== Pulling latest master ==="
git pull origin master

# Merge Development
echo "=== Merging Development into master ==="
git merge Development -m "Merge: Fix network configuration and disable stage deployments"

# Push to master (triggers production deployment)
echo "=== Pushing to master (DEPLOYING TO PRODUCTION) ==="
git push origin master

echo "=== Backend Deployment Complete! ==="
