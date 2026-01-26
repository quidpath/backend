#!/bin/bash
# Health check script for all services

echo "🔍 Checking QuidPath Services Health"
echo "====================================="

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

check_service() {
    local name=$1
    local url=$2
    
    if curl -f -s "$url" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ $name: Healthy${NC}"
        return 0
    else
        echo -e "${RED}❌ $name: Unhealthy${NC}"
        return 1
    fi
}

echo ""
echo "Checking Docker containers..."
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "django-backend|quidpath-frontend|billing-backend|tazama-ai-backend|postgres"

echo ""
echo "Checking service endpoints..."

# Backend
check_service "Backend (localhost:8000)" "http://localhost:8000/api/auth/health/" || echo "  → Check: docker-compose -f ~/quidpath-deployment/backend/docker-compose.yml logs"

# Frontend
check_service "Frontend (localhost:3000)" "http://localhost:3000/" || echo "  → Check: docker-compose -f ~/quidpath-deployment/frontend/docker-compose.yml logs"

# Billing
check_service "Billing (localhost:8002)" "http://localhost:8002/api/billing/health/" || echo "  → Check: docker-compose -f ~/quidpath-deployment/billing/docker-compose.yml logs"

# Tazama AI
check_service "Tazama AI (localhost:8001)" "http://localhost:8001/api/tazama/" || echo "  → Check: docker-compose -f ~/quidpath-deployment/tazama/docker-compose.yml logs"

echo ""
echo "Checking Nginx..."
if systemctl is-active --quiet nginx; then
    echo -e "${GREEN}✅ Nginx: Running${NC}"
else
    echo -e "${RED}❌ Nginx: Not running${NC}"
    echo "  → Start with: sudo systemctl start nginx"
fi

echo ""
echo "Checking SSL certificates..."
if [ -f /etc/letsencrypt/live/api.quidpath.com/fullchain.pem ]; then
    echo -e "${GREEN}✅ SSL certificates: Found${NC}"
else
    echo -e "${YELLOW}⚠️  SSL certificates: Not found${NC}"
    echo "  → Run: sudo bash ~/quidpath-deployment/backend/setup-nginx-ovh.sh"
fi

echo ""
echo "Disk usage:"
df -h /mnt/quidpath-data

echo ""
echo "Done!"
