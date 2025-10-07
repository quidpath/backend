#!/bin/bash

#############################################
# Django Backend Deployment Script
# Description: Pulls and deploys the latest Docker image
#############################################

set -e  # Exit on any error
set -u  # Exit on undefined variable

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_DIR="/home/ubuntu/quidpath-erp-backend"
COMPOSE_FILE="docker-compose.yml"
SERVICE_NAME="backend"
IMAGE_NAME="bethwelkimutai/quidpath-backend:latest"
MAX_HEALTH_CHECKS=30
HEALTH_CHECK_INTERVAL=2

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Error handler
error_exit() {
    log_error "$1"
    exit 1
}

#############################################
# Main Deployment Process
#############################################

log_info "========================================="
log_info "Starting Deployment Process"
log_info "========================================="
log_info "Timestamp: $(date '+%Y-%m-%d %H:%M:%S')"
log_info "Project: quidpath-erp-backend"
log_info "Image: $IMAGE_NAME"
log_info "========================================="

# Step 1: Verify project directory exists
log_info "Checking project directory..."
if [ ! -d "$PROJECT_DIR" ]; then
    error_exit "Project directory not found: $PROJECT_DIR"
fi
cd "$PROJECT_DIR" || error_exit "Failed to change to project directory"
log_success "Project directory OK: $PROJECT_DIR"

# Step 2: Verify docker-compose.yml exists
log_info "Checking docker-compose.yml..."
if [ ! -f "$COMPOSE_FILE" ]; then
    error_exit "docker-compose.yml not found in $PROJECT_DIR"
fi
log_success "docker-compose.yml found"

# Step 3: Ensure Docker is running
log_info "Checking Docker service..."
if ! sudo systemctl is-active --quiet docker; then
    log_warning "Docker service is not running. Starting Docker..."
    sudo systemctl start docker || error_exit "Failed to start Docker service"
    sleep 3
fi
log_success "Docker service is running"

# Step 4: Verify Docker installation
log_info "Verifying Docker installation..."
docker --version || error_exit "Docker is not installed or not in PATH"
log_success "Docker is installed: $(docker --version)"

# Step 5: Verify Docker Compose installation
log_info "Verifying Docker Compose..."
if ! docker compose version >/dev/null 2>&1; then
    log_warning "Docker Compose plugin not found. Installing..."

    sudo apt-get update -y || error_exit "Failed to update apt packages"
    sudo apt-get install -y ca-certificates curl gnupg || error_exit "Failed to install dependencies"

    # Add Docker's official GPG key
    sudo install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg || error_exit "Failed to add Docker GPG key"
    sudo chmod a+r /etc/apt/keyrings/docker.gpg

    # Add Docker repository
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | \
    sudo tee /etc/apt/sources.list.d/docker.list > /dev/null || error_exit "Failed to add Docker repository"

    # Install Docker Compose
    sudo apt-get update -y || error_exit "Failed to update apt packages"
    sudo apt-get install -y docker-compose-plugin || error_exit "Failed to install Docker Compose plugin"

    log_success "Docker Compose installed successfully"
else
    log_success "Docker Compose is installed: $(docker compose version)"
fi

# Step 6: Login to Docker Hub (if credentials are available)
if [ -n "${DOCKER_USERNAME:-}" ] && [ -n "${DOCKER_PASSWORD:-}" ]; then
    log_info "Logging in to Docker Hub..."
    echo "$DOCKER_PASSWORD" | docker login -u "$DOCKER_USERNAME" --password-stdin || log_warning "Docker Hub login failed, continuing anyway..."
fi

# Step 7: Pull latest image
log_info "Pulling latest Docker image: $IMAGE_NAME"
sudo docker compose pull $SERVICE_NAME || error_exit "Failed to pull Docker image"
log_success "Successfully pulled latest image"

# Step 8: Get current container ID (if exists)
CURRENT_CONTAINER=$(sudo docker compose ps -q $SERVICE_NAME 2>/dev/null || echo "")
if [ -n "$CURRENT_CONTAINER" ]; then
    log_info "Current container ID: $CURRENT_CONTAINER"
else
    log_info "No existing container found"
fi

# Step 9: Stop and remove old container (if exists)
if [ -n "$CURRENT_CONTAINER" ]; then
    log_info "Stopping existing container..."
    sudo docker compose stop $SERVICE_NAME || log_warning "Failed to stop container gracefully"

    log_info "Removing old container..."
    sudo docker compose rm -f $SERVICE_NAME || log_warning "Failed to remove old container"
fi

# Step 10: Start new container
log_info "Starting new container..."
sudo docker compose up -d --no-deps --force-recreate $SERVICE_NAME || error_exit "Failed to start new container"
log_success "Container started successfully"

# Step 11: Wait for container to be healthy
log_info "Waiting for container to be healthy..."
for i in $(seq 1 $MAX_HEALTH_CHECKS); do
    CONTAINER_STATUS=$(sudo docker compose ps $SERVICE_NAME --format json 2>/dev/null | grep -o '"State":"[^"]*"' | cut -d'"' -f4 || echo "unknown")

    if [ "$CONTAINER_STATUS" = "running" ]; then
        log_success "Container is running and healthy!"
        break
    elif [ "$CONTAINER_STATUS" = "exited" ] || [ "$CONTAINER_STATUS" = "dead" ]; then
        log_error "Container failed to start. Showing logs:"
        sudo docker compose logs --tail=50 $SERVICE_NAME
        error_exit "Container is in $CONTAINER_STATUS state"
    fi

    echo -n "."
    sleep $HEALTH_CHECK_INTERVAL

    if [ $i -eq $MAX_HEALTH_CHECKS ]; then
        log_error "Container health check timeout. Showing logs:"
        sudo docker compose logs --tail=50 $SERVICE_NAME
        error_exit "Container did not become healthy within expected time"
    fi
done
echo ""

# Step 12: Show container status
log_info "Final container status:"
sudo docker compose ps $SERVICE_NAME

# Step 13: Show recent logs
log_info "Recent container logs:"
sudo docker compose logs --tail=20 $SERVICE_NAME

# Step 14: Cleanup old images
log_info "Cleaning up old Docker images..."
sudo docker image prune -f || log_warning "Failed to prune old images"

# Step 15: Show disk usage
log_info "Docker disk usage:"
sudo docker system df

log_success "========================================="
log_success "Deployment completed successfully!"
log_success "========================================="
log_info "Deployment timestamp: $(date '+%Y-%m-%d %H:%M:%S')"
log_info "Container name: $(sudo docker compose ps $SERVICE_NAME --format '{{.Name}}' 2>/dev/null || echo 'N/A')"
log_info "Image: $IMAGE_NAME"
log_success "========================================="

exit 0