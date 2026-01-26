#!/bin/bash
set -euo pipefail

echo "🚀 Deploying All QuidPath Services to OVH"
echo "=========================================="

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

DEPLOY_DIR="$HOME/quidpath-deployment"

# Create shared network
echo -e "${YELLOW}Creating shared Docker network...${NC}"
docker network create quidpath_network 2>/dev/null || echo "Network already exists"

# ============================================
# 1. Deploy Backend (api.quidpath.com)
# ============================================
echo -e "${BLUE}📦 Deploying Backend (api.quidpath.com)...${NC}"
cd "$DEPLOY_DIR/backend" || exit 1

if [ ! -f .env ]; then
    echo -e "${RED}❌ .env file not found in backend directory${NC}"
    echo "Please create .env file with required environment variables"
    exit 1
fi

docker-compose build
docker-compose up -d

echo -e "${YELLOW}Waiting for backend to be ready...${NC}"
sleep 15

docker-compose exec -T backend python manage.py migrate --noinput || true
docker-compose exec -T backend python manage.py collectstatic --noinput || true

echo -e "${GREEN}✅ Backend deployed${NC}"

# ============================================
# 2. Deploy Frontend (quidpath.com)
# ============================================
echo -e "${BLUE}📦 Deploying Frontend (quidpath.com)...${NC}"
cd "$DEPLOY_DIR/frontend" || exit 1

if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠️  .env file not found, creating from template...${NC}"
    cat > .env << 'EOF'
NEXT_PUBLIC_API_BASE_URL=https://api.quidpath.com/
NEXT_PUBLIC_TAZAMA_AI_API_URL=https://ai.quidpath.com/api/tazama/
NEXT_PUBLIC_BILLING_SERVICE_URL=https://billing.quidpath.com/api/billing
NODE_ENV=production
EOF
fi

docker-compose build
docker-compose up -d

echo -e "${GREEN}✅ Frontend deployed${NC}"

# ============================================
# 3. Deploy Billing Service (billing.quidpath.com)
# ============================================
echo -e "${BLUE}📦 Deploying Billing Service (billing.quidpath.com)...${NC}"
cd "$DEPLOY_DIR/billing" || exit 1

if [ ! -f .env ]; then
    echo -e "${RED}❌ .env file not found in billing directory${NC}"
    exit 1
fi

docker-compose build
docker-compose up -d

echo -e "${YELLOW}Waiting for billing service to be ready...${NC}"
sleep 10

docker-compose exec -T backend python manage.py migrate --noinput || true
docker-compose exec -T backend python manage.py collectstatic --noinput || true

echo -e "${GREEN}✅ Billing service deployed${NC}"

# ============================================
# 4. Deploy Tazama AI Service (ai.quidpath.com)
# ============================================
echo -e "${BLUE}📦 Deploying Tazama AI Service (ai.quidpath.com)...${NC}"
cd "$DEPLOY_DIR/tazama" || exit 1

if [ ! -f .env ]; then
    echo -e "${RED}❌ .env file not found in tazama directory${NC}"
    exit 1
fi

docker-compose build
docker-compose up -d

echo -e "${YELLOW}Waiting for Tazama service to be ready...${NC}"
sleep 10

docker-compose exec -T web python manage.py migrate --noinput || true
docker-compose exec -T web python manage.py collectstatic --noinput || true

echo -e "${GREEN}✅ Tazama AI service deployed${NC}"

# ============================================
# 5. Setup Nginx (if not already done)
# ============================================
echo -e "${BLUE}📦 Setting up Nginx reverse proxy...${NC}"
if [ ! -f /etc/nginx/sites-enabled/quidpath ]; then
    echo -e "${YELLOW}Running Nginx setup...${NC}"
    bash "$DEPLOY_DIR/backend/setup-nginx-ovh.sh"
else
    echo -e "${GREEN}Nginx already configured${NC}"
    systemctl reload nginx
fi

# ============================================
# Summary
# ============================================
echo ""
echo -e "${GREEN}=========================================="
echo "✅ All Services Deployed Successfully!"
echo "==========================================${NC}"
echo ""
echo "Services are running on:"
echo "  • Frontend:     https://quidpath.com"
echo "  • Backend API:  https://api.quidpath.com"
echo "  • Billing:       https://billing.quidpath.com"
echo "  • Tazama AI:    https://ai.quidpath.com"
echo ""
echo "Check status with:"
echo "  docker ps"
echo ""
echo "View logs with:"
echo "  docker-compose -f ~/quidpath-deployment/backend/docker-compose.yml logs -f"
echo "  docker-compose -f ~/quidpath-deployment/frontend/docker-compose.yml logs -f"
echo "  docker-compose -f ~/quidpath-deployment/billing/docker-compose.yml logs -f"
echo "  docker-compose -f ~/quidpath-deployment/tazama/docker-compose.yml logs -f"
