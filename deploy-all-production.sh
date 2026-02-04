#!/bin/bash

# Production Deployment Script for All Services
# This script deploys Main Backend, Billing, and Tazama services

set -e  # Exit on error

echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║         Quidpath Production Deployment - All Services               ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Base directory
BASE_DIR=~/quidpath-deployment

# Function to print colored messages
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "ℹ $1"
}

# Function to check if directory exists
check_directory() {
    if [ ! -d "$1" ]; then
        print_error "Directory not found: $1"
        exit 1
    fi
}

# Function to deploy a service
deploy_service() {
    local service_name=$1
    local service_dir=$2
    local port=$3
    
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Deploying: $service_name (Port $port)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    cd "$service_dir" || exit 1
    
    print_info "Stopping existing containers..."
    docker compose down
    
    print_info "Pulling latest code..."
    git pull origin main || print_warning "Git pull failed or no changes"
    
    print_info "Building and starting service..."
    docker compose up -d --build
    
    print_info "Waiting for service to be ready..."
    sleep 5
    
    # Check if container is running
    if docker ps | grep -q "$service_name"; then
        print_success "$service_name deployed successfully!"
    else
        print_error "$service_name failed to start!"
        docker logs "$service_name" --tail 20
        return 1
    fi
}

# Main deployment process
echo "Starting deployment process..."
echo ""

# Check if base directory exists
check_directory "$BASE_DIR"

# Deploy Main Backend
deploy_service "django-backend" "$BASE_DIR/backend" "8004"

# Deploy Billing Service
deploy_service "billing-backend" "$BASE_DIR/billing" "8005"

# Deploy Tazama AI Service
deploy_service "tazama-ai-backend" "$BASE_DIR/tazama" "8006"

# Verification
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Verification"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

print_info "Checking running containers..."
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "django-backend|billing-backend|tazama-ai-backend"

echo ""
print_info "Checking network connectivity..."

# Test inter-service communication
if docker exec django-backend curl -s -o /dev/null -w "%{http_code}" http://billing-backend:8000/api/billing/health/ | grep -q "401\|200"; then
    print_success "Main Backend → Billing: Connected"
else
    print_warning "Main Backend → Billing: Connection issue"
fi

if docker exec django-backend curl -s -o /dev/null -w "%{http_code}" http://tazama-ai-backend:8001/api/tazama/health/ | grep -q "401\|200"; then
    print_success "Main Backend → Tazama: Connected"
else
    print_warning "Main Backend → Tazama: Connection issue"
fi

echo ""
print_info "Testing external endpoints..."

# Test external access
if curl -s -o /dev/null -w "%{http_code}" http://localhost:8004/api/auth/health/ | grep -q "401\|200"; then
    print_success "Main Backend (8004): Accessible"
else
    print_warning "Main Backend (8004): Not accessible"
fi

if curl -s -o /dev/null -w "%{http_code}" http://localhost:8005/api/billing/health/ | grep -q "401\|200"; then
    print_success "Billing (8005): Accessible"
else
    print_warning "Billing (8005): Not accessible"
fi

if curl -s -o /dev/null -w "%{http_code}" http://localhost:8006/api/tazama/health/ | grep -q "401\|200"; then
    print_success "Tazama (8006): Accessible"
else
    print_warning "Tazama (8006): Not accessible"
fi

# Summary
echo ""
echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║                     Deployment Complete!                            ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"
echo ""
echo "Service URLs:"
echo "  • Main Backend:  http://localhost:8004"
echo "  • Billing:       http://localhost:8005"
echo "  • Tazama AI:     http://localhost:8006"
echo ""
echo "To view logs:"
echo "  docker logs django-backend -f"
echo "  docker logs billing-backend -f"
echo "  docker logs tazama-ai-backend -f"
echo ""
echo "To check status:"
echo "  docker ps"
echo ""
