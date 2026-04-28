#!/bin/bash
set -e

echo "=========================================="
echo "Committing and Deploying All Services"
echo "=========================================="

# Configure git identity
configure_git() {
    git config user.email "bethwel@quidpath.com"
    git config user.name "Bethwel Kimutai"
}

# Function to commit and push to master
deploy_service() {
    local service_path=$1
    local service_name=$2
    
    echo ""
    echo "=========================================="
    echo "Deploying: $service_name"
    echo "=========================================="
    
    cd "$service_path"
    
    # Configure git
    configure_git
    
    # Checkout master
    echo "Checking out master..."
    git checkout master
    
    # Pull latest
    echo "Pulling latest..."
    git pull origin master
    
    # Add all changes
    echo "Adding changes..."
    git add -A
    
    # Check if there are changes
    if git diff --cached --quiet; then
        echo "No changes to commit for $service_name"
        return 0
    fi
    
    # Commit
    echo "Committing..."
    git commit -m "fix: Update network configuration to auto-create prod_quidpath_network

- Changed from external: true to managed network
- Network will be created automatically on deployment
- Fixes 'network not found' deployment errors"
    
    # Push to master (triggers production deployment)
    echo "Pushing to master (DEPLOYING TO PRODUCTION)..."
    git push origin master
    
    echo "✓ $service_name deployed!"
}

# Get base directory
BASE_DIR=$(pwd)

# Deploy all services
deploy_service "$BASE_DIR/backend" "Backend"
deploy_service "$BASE_DIR/inventory" "Inventory"
deploy_service "$BASE_DIR/frontend" "Frontend"
deploy_service "$BASE_DIR/billing" "Billing"
deploy_service "$BASE_DIR/pos" "POS"
deploy_service "$BASE_DIR/crm" "CRM"
deploy_service "$BASE_DIR/hrm" "HRM"
deploy_service "$BASE_DIR/project-management" "Projects"

echo ""
echo "=========================================="
echo "ALL SERVICES DEPLOYED TO PRODUCTION!"
echo "=========================================="
echo ""
echo "Deployments triggered for:"
echo "  ✓ Backend"
echo "  ✓ Inventory"
echo "  ✓ Frontend"
echo "  ✓ Billing"
echo "  ✓ POS"
echo "  ✓ CRM"
echo "  ✓ HRM"
echo "  ✓ Projects"
echo ""
echo "Monitor deployments at:"
echo "  https://github.com/quidpath/backend/actions"
echo "  https://github.com/quidpath/inventory/actions"
echo "  (and other repositories)"
echo ""
