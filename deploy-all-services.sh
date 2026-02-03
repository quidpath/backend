#!/bin/bash

# QuidPath All Services Deployment Script
# This script deploys Main Backend, Billing Service, and Tazama AI

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}QuidPath Services Deployment${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Please run as root${NC}"
    exit 1
fi

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Docker is not installed${NC}"
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker compose &> /dev/null; then
    echo -e "${RED}Docker Compose is not installed${NC}"
    exit 1
fi

# Create shared network if it doesn't exist
echo -e "${YELLOW}Creating shared Docker network...${NC}"
docker network create quidpath_network 2>/dev/null || echo "Network already exists"

# Deploy Main Backend
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Deploying Main Backend${NC}"
echo -e "${GREEN}========================================${NC}"
cd /root/quidpath-deployment/backend

if [ ! -f .env ]; then
    echo -e "${RED}.env file not found in backend directory${NC}"
    exit 1
fi

echo -e "${YELLOW}Pulling latest code...${NC}"
git pull origin main

echo -e "${YELLOW}Building Docker image...${NC}"
docker compose down
docker compose build --no-cache

echo -e "${YELLOW}Starting services...${NC}"
docker compose up -d

echo -e "${YELLOW}Waiting for database to be ready...${NC}"
sleep 10

echo -e "${YELLOW}Running migrations...${NC}"
docker exec django-backend python manage.py migrate

echo -e "${YELLOW}Collecting static files...${NC}"
docker exec django-backend python manage.py collectstatic --noinput

echo -e "${GREEN}Main Backend deployed successfully${NC}"

# Deploy Billing Service
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Deploying Billing Service${NC}"
echo -e "${GREEN}========================================${NC}"
cd /root/quidpath-deployment/billing

if [ ! -f .env ]; then
    echo -e "${RED}.env file not found in billing directory${NC}"
    exit 1
fi

echo -e "${YELLOW}Pulling latest code...${NC}"
git pull origin main

echo -e "${YELLOW}Building Docker image...${NC}"
docker compose down
docker compose build --no-cache

echo -e "${YELLOW}Starting services...${NC}"
docker compose up -d

echo -e "${YELLOW}Waiting for database to be ready...${NC}"
sleep 10

echo -e "${YELLOW}Running migrations...${NC}"
docker exec billing-backend python manage.py migrate

echo -e "${YELLOW}Collecting static files...${NC}"
docker exec billing-backend python manage.py collectstatic --noinput

echo -e "${GREEN}Billing Service deployed successfully${NC}"

# Deploy Tazama AI Service
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Deploying Tazama AI Service${NC}"
echo -e "${GREEN}========================================${NC}"
cd /root/quidpath-deployment/tazama

if [ ! -f .env ]; then
    echo -e "${RED}.env file not found in tazama directory${NC}"
    exit 1
fi

echo -e "${YELLOW}Pulling latest code...${NC}"
git pull origin main

echo -e "${YELLOW}Building Docker image...${NC}"
docker compose down
docker compose build --no-cache

echo -e "${YELLOW}Starting services...${NC}"
docker compose up -d

echo -e "${YELLOW}Waiting for database to be ready...${NC}"
sleep 10

echo -e "${YELLOW}Running migrations...${NC}"
docker exec tazama-ai-backend python manage.py migrate

echo -e "${YELLOW}Collecting static files...${NC}"
docker exec tazama-ai-backend python manage.py collectstatic --noinput

echo -e "${GREEN}Tazama AI Service deployed successfully${NC}"

# Health Check
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Health Check${NC}"
echo -e "${GREEN}========================================${NC}"

echo -e "${YELLOW}Checking Docker containers...${NC}"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo ""
echo -e "${YELLOW}Checking service health...${NC}"

echo -n "Main Backend: "
if curl -s -f http://localhost:8000/api/auth/health/ > /dev/null 2>&1; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${RED}FAILED${NC}"
fi

echo -n "Billing Service: "
if curl -s -f http://localhost:8002/api/billing/health/ > /dev/null 2>&1; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${RED}FAILED${NC}"
fi

echo -n "Tazama AI: "
if curl -s -f http://localhost:8001/api/tazama/health/ > /dev/null 2>&1; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${RED}FAILED${NC}"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Deployment Complete${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "1. Verify all services are running: docker ps"
echo "2. Check logs: docker logs <container-name>"
echo "3. Test endpoints:"
echo "   - Main Backend: https://api.quidpath.com/api/auth/health/"
echo "   - Billing: https://billing.quidpath.com/api/billing/health/"
echo "   - Tazama AI: https://ai.quidpath.com/api/tazama/health/"
echo "4. Create superusers if needed:"
echo "   - docker exec -it django-backend python manage.py createsuperuser"
echo "   - docker exec -it billing-backend python manage.py createsuperuser"
echo "   - docker exec -it tazama-ai-backend python manage.py createsuperuser"
echo ""
