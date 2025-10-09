#!/bin/bash

#############################################
# Django Backend Deployment Script (Optimized)
# Description: Smart deployment with minimal downtime
#############################################

set -e  # Exit on any error
set -u  # Exit on undefined variable

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
PROJECT_DIR="/home/ubuntu/quidpath-erp-backend"
COMPOSE_FILE="docker-compose.yml"
SERVICE_NAME="backend"
IMAGE_NAME="bethwelkimutai/quidpath-backend:latest"
MAX_HEALTH_CHECKS=30
HEALTH_CHECK_INTERVAL=2

# Logging functions
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
error_exit() { log_error "$1"; exit 1; }

#############################################
# Main Deployment Process
#############################################

log_info "========================================="
log_info "Starting Smart Deployment Process"
log_info "========================================="
log_info "Timestamp: $(date '+%Y-%m-%d %H:%M:%S')"

# Step 1: Change to project directory
cd "$PROJECT_DIR" || error_exit "Failed to change to project directory"
log_success "Working directory: $PROJECT_DIR"

# Step 2: Get current image ID
log_info "Checking current image..."
CURRENT_IMAGE_ID=$(sudo docker images $IMAGE_NAME --format "{{.ID}}" 2>/dev/null | head -n1 || echo "")
log_info "Current image ID: ${CURRENT_IMAGE_ID:-none}"

# Step 3: Pull latest image
log_info "Pulling latest image: $IMAGE_NAME"
sudo docker compose pull $SERVICE_NAME || error_exit "Failed to pull image"

# Step 4: Get new image ID
NEW_IMAGE_ID=$(sudo docker images $IMAGE_NAME --format "{{.ID}}" 2>/dev/null | head -n1 || echo "")
log_info "New image ID: ${NEW_IMAGE_ID:-none}"

# Step 5: Check if update is needed
if [ "$CURRENT_IMAGE_ID" = "$NEW_IMAGE_ID" ] && [ -n "$CURRENT_IMAGE_ID" ]; then
    log_warning "========================================="
    log_warning "No changes detected in Docker image!"
    log_warning "Skipping deployment to avoid unnecessary downtime"
    log_warning "========================================="

    # Still verify container is running
    CONTAINER_STATUS=$(sudo docker compose ps $SERVICE_NAME --format json 2>/dev/null | grep -o '"State":"[^"]*"' | cut -d'"' -f4 || echo "unknown")

    if [ "$CONTAINER_STATUS" = "running" ]; then
        log_success "Container is already running with latest image"
        sudo docker compose ps $SERVICE_NAME
        exit 0
    else
        log_warning "Container is not running, forcing restart..."
    fi
fi

log_info "========================================="
log_info "New image detected! Proceeding with deployment..."
log_info "========================================="

# Step 6: Run database migrations (before switching containers)
log_info "Running database migrations..."
sudo docker compose exec -T $SERVICE_NAME python manage.py migrate --noinput || log_warning "Migration failed or no container running"

# Step 7: Collect static files
log_info "Collecting static files..."
sudo docker compose exec -T $SERVICE_NAME python manage.py collectstatic --noinput --clear || log_warning "Collectstatic failed or no container running"

# Step 8: Graceful container update
log_info "Updating container with zero-downtime strategy..."

# Use 'up -d' which will recreate ONLY if image changed
sudo docker compose up -d $SERVICE_NAME || error_exit "Failed to update container"

log_success "Container updated successfully"

# Step 9: Wait for container to be healthy
log_info "Waiting for container to be healthy..."
for i in $(seq 1 $MAX_HEALTH_CHECKS); do
    CONTAINER_STATUS=$(sudo docker compose ps $SERVICE_NAME --format json 2>/dev/null | grep -o '"State":"[^"]*"' | cut -d'"' -f4 || echo "unknown")

    if [ "$CONTAINER_STATUS" = "running" ]; then
        log_success "Container is healthy!"
        break
    elif [ "$CONTAINER_STATUS" = "exited" ] || [ "$CONTAINER_STATUS" = "dead" ]; then
        log_error "Container failed! Showing logs:"
        sudo docker compose logs --tail=50 $SERVICE_NAME
        error_exit "Container is in $CONTAINER_STATUS state"
    fi

    echo -n "."
    sleep $HEALTH_CHECK_INTERVAL

    if [ $i -eq $MAX_HEALTH_CHECKS ]; then
        log_error "Health check timeout! Showing logs:"
        sudo docker compose logs --tail=50 $SERVICE_NAME
        error_exit "Container did not become healthy"
    fi
done
echo ""

# Step 10: Post-deployment tasks
log_info "Running post-deployment tasks..."

# Check if migrations are needed
log_info "Checking for pending migrations..."
sudo docker compose exec -T $SERVICE_NAME python manage.py showmigrations || log_warning "Could not check migrations"

# Step 11: Cleanup old images (keep last 2)
log_info "Cleaning up old Docker images..."
sudo docker images $IMAGE_NAME --format "{{.ID}} {{.CreatedAt}}" | tail -n +3 | awk '{print $1}' | xargs -r sudo docker rmi -f 2>/dev/null || log_info "No old images to remove"

# Step 12: Show final status
log_info "========================================="
log_success "Deployment Summary"
log_info "========================================="
sudo docker compose ps $SERVICE_NAME
log_info ""
log_info "Recent logs:"
sudo docker compose logs --tail=15 $SERVICE_NAME
log_info ""
log_info "Disk usage:"
sudo docker system df --format "table {{.Type}}\t{{.TotalCount}}\t{{.Size}}"

log_success "========================================="
log_success "Deployment completed successfully!"
log_success "Time: $(date '+%Y-%m-%d %H:%M:%S')"
log_success "========================================="

exit 0