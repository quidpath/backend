#!/bin/bash
# Quick deployment script for OVH - Run this after cloning all repos

set -euo pipefail

echo "🚀 QuidPath ERP - Quick OVH Deployment"
echo "========================================"

DEPLOY_DIR="$HOME/quidpath-deployment"

# Check if directories exist
if [ ! -d "$DEPLOY_DIR/backend" ] || [ ! -d "$DEPLOY_DIR/frontend" ] || [ ! -d "$DEPLOY_DIR/billing" ] || [ ! -d "$DEPLOY_DIR/tazama" ]; then
    echo "❌ Error: Service directories not found in $DEPLOY_DIR"
    echo "Please clone all repositories first:"
    echo "  cd ~/quidpath-deployment"
    echo "  git clone <backend-repo> backend"
    echo "  git clone <frontend-repo> frontend"
    echo "  git clone <billing-repo> billing"
    echo "  git clone <tazama-repo> tazama"
    exit 1
fi

# Step 1: Create .env files from templates
echo ""
echo "📝 Step 1: Creating .env files..."
if [ -f "$DEPLOY_DIR/backend/create-env-templates.sh" ]; then
    bash "$DEPLOY_DIR/backend/create-env-templates.sh"
    echo "⚠️  IMPORTANT: Edit .env files and set all passwords and secrets!"
    echo "   Press Enter to continue after editing .env files..."
    read
else
    echo "⚠️  create-env-templates.sh not found. Please create .env files manually."
fi

# Step 2: Create shared network
echo ""
echo "📦 Step 2: Creating Docker network..."
docker network create quidpath_network 2>/dev/null || echo "Network already exists"

# Step 3: Create data directories
echo ""
echo "📁 Step 3: Creating data directories..."
sudo mkdir -p /mnt/quidpath-data/{postgres,media,staticfiles,certbot/{conf,www}}
sudo chown -R $USER:$USER /mnt/quidpath-data 2>/dev/null || sudo chown -R quidpath:quidpath /mnt/quidpath-data

# Step 4: Deploy services
echo ""
echo "🚀 Step 4: Deploying all services..."
bash "$DEPLOY_DIR/backend/deploy-all-services.sh"

# Step 5: Setup Nginx
echo ""
echo "🌐 Step 5: Setting up Nginx..."
sudo bash "$DEPLOY_DIR/backend/setup-nginx-ovh.sh"

# Step 6: Health check
echo ""
echo "🏥 Step 6: Running health checks..."
bash "$DEPLOY_DIR/backend/check-services.sh"

echo ""
echo "✅ Deployment complete!"
echo ""
echo "Your services should now be available at:"
echo "  • https://quidpath.com (Frontend)"
echo "  • https://api.quidpath.com (Backend API)"
echo "  • https://billing.quidpath.com (Billing)"
echo "  • https://ai.quidpath.com (Tazama AI)"
echo ""
echo "If SSL certificates failed, run manually:"
echo "  sudo certbot --nginx -d api.quidpath.com -d quidpath.com -d www.quidpath.com -d billing.quidpath.com -d ai.quidpath.com"
