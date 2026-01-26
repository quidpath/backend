#!/bin/bash
set -euo pipefail

echo "🚀 Deploying QuidPath ERP to OVH Cloud"
echo "========================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root or with sudo
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Please run as root or with sudo${NC}"
    exit 1
fi

# Create shared Docker network
echo -e "${YELLOW}Creating shared Docker network...${NC}"
docker network create quidpath_network 2>/dev/null || echo "Network already exists"

# Create data directories
echo -e "${YELLOW}Creating data directories...${NC}"
mkdir -p /mnt/quidpath-data/{postgres,media,staticfiles,certbot/{conf,www}}
chown -R quidpath:quidpath /mnt/quidpath-data

# Navigate to backend directory
cd ~/quidpath-deployment/backend || exit 1

# Build and start services
echo -e "${YELLOW}Building and starting backend services...${NC}"
docker-compose build
docker-compose up -d

# Wait for services to be healthy
echo -e "${YELLOW}Waiting for services to be healthy...${NC}"
sleep 10

# Run migrations
echo -e "${YELLOW}Running database migrations...${NC}"
docker-compose exec -T backend python manage.py migrate --noinput

# Collect static files
echo -e "${YELLOW}Collecting static files...${NC}"
docker-compose exec -T backend python manage.py collectstatic --noinput

echo -e "${GREEN}✅ Backend deployment complete!${NC}"
echo "Backend is running on http://localhost:8000"
echo "API will be available at https://api.quidpath.com"
