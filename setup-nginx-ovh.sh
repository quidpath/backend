#!/bin/bash
set -euo pipefail

echo "🔧 Setting up Nginx for OVH Cloud"
echo "=================================="

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Please run as root or with sudo${NC}"
    exit 1
fi

# Install Nginx if not installed
if ! command -v nginx &> /dev/null; then
    echo -e "${YELLOW}Installing Nginx...${NC}"
    apt update
    apt install -y nginx
fi

# Install Certbot
if ! command -v certbot &> /dev/null; then
    echo -e "${YELLOW}Installing Certbot...${NC}"
    apt install -y certbot python3-certbot-nginx
fi

# Create certbot directories
mkdir -p /mnt/quidpath-data/certbot/{conf,www}
mkdir -p /var/www/certbot

# Create symlinks for static/media files
echo -e "${YELLOW}Creating symlinks for static files...${NC}"
mkdir -p /var/www/static /var/www/media
ln -sf /mnt/quidpath-data/staticfiles/* /var/www/static/ 2>/dev/null || true
ln -sf /mnt/quidpath-data/media/* /var/www/media/ 2>/dev/null || true

# Copy Nginx configuration
echo -e "${YELLOW}Copying Nginx configuration...${NC}"
cp ~/quidpath-deployment/backend/nginx.conf /etc/nginx/sites-available/quidpath
ln -sf /etc/nginx/sites-available/quidpath /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Test Nginx configuration
echo -e "${YELLOW}Testing Nginx configuration...${NC}"
nginx -t

# Get SSL certificates for all domains
echo -e "${YELLOW}Getting SSL certificates...${NC}"
echo "This will prompt for email and agreement. Make sure DNS is configured first!"
certbot --nginx -d api.quidpath.com -d quidpath.com -d www.quidpath.com -d billing.quidpath.com -d ai.quidpath.com --non-interactive --agree-tos --email admin@quidpath.com || {
    echo -e "${RED}SSL certificate generation failed. Make sure DNS is configured correctly.${NC}"
    echo "You can run this manually later:"
    echo "certbot --nginx -d api.quidpath.com -d quidpath.com -d www.quidpath.com -d billing.quidpath.com -d ai.quidpath.com"
}

# Restart Nginx
echo -e "${YELLOW}Restarting Nginx...${NC}"
systemctl restart nginx
systemctl enable nginx

echo -e "${GREEN}✅ Nginx setup complete!${NC}"
