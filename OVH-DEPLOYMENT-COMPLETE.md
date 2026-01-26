# ✅ OVH Cloud Deployment - Complete Setup

## What Has Been Configured

### ✅ Docker Configuration
- **Backend**: `docker-compose.yml` - Production ready, uses `/mnt/quidpath-data`
- **Frontend**: `docker-compose.yml` + `Dockerfile.dev` - Dev and prod ready
- **Billing**: `docker-compose.yml` - Updated for OVH paths
- **Tazama AI**: `docker-compose.yml` - Ready for deployment
- **Shared Network**: All services use `quidpath_network` for inter-service communication

### ✅ Nginx Configuration
- **Unified Nginx config** (`nginx.conf`) handles all subdomains:
  - `quidpath.com` → Frontend (port 3000)
  - `api.quidpath.com` → Backend (port 8000)
  - `billing.quidpath.com` → Billing (port 8002)
  - `ai.quidpath.com` → Tazama AI (port 8001)
- All services bind to `127.0.0.1` (internal only, accessed via Nginx)
- SSL ready with Let's Encrypt

### ✅ Security Fixes
- Removed hardcoded `SECRET_KEY` from Dockerfiles
- All services use environment variables
- Ports bound to localhost only

### ✅ Deployment Scripts
- `deploy-all-services.sh` - Deploys all services
- `setup-nginx-ovh.sh` - Configures Nginx and SSL
- `check-services.sh` - Health check script
- `create-env-templates.sh` - Creates .env templates
- `QUICK-DEPLOY-OVH.sh` - One-command deployment

## Next Steps on Your OVH Server

### 1. Complete Directory Setup
```bash
# You've already done this, but verify:
sudo mkdir -p /mnt/quidpath-data/{postgres,media,staticfiles,certbot/{conf,www}}
sudo chown -R quidpath:quidpath /mnt/quidpath-data
```

### 2. Clone All Repositories
```bash
cd ~/quidpath-deployment

# Clone each repository
git clone <your-backend-repo-url> backend
git clone <your-frontend-repo-url> frontend
git clone <your-billing-repo-url> billing
git clone <your-tazama-repo-url> tazama
```

### 3. Create .env Files
```bash
# Run the template generator
cd ~/quidpath-deployment/backend
bash create-env-templates.sh

# Copy templates to .env files
cp .env.template .env
cp ../frontend/.env.template ../frontend/.env
cp ../billing/.env.template ../billing/.env
cp ../tazama/.env.template ../tazama/.env

# Edit each .env file and replace:
# - All SECRET_KEY values (generate with: openssl rand -hex 32)
# - All database passwords
# - Email credentials
# - Any other placeholders
```

### 4. Deploy Everything
```bash
# Make scripts executable
chmod +x ~/quidpath-deployment/backend/*.sh

# Run the quick deployment script
bash ~/quidpath-deployment/backend/QUICK-DEPLOY-OVH.sh
```

### 5. Get SSL Certificates
```bash
# If SSL setup didn't work automatically:
sudo certbot --nginx \
  -d api.quidpath.com \
  -d quidpath.com \
  -d www.quidpath.com \
  -d billing.quidpath.com \
  -d ai.quidpath.com \
  --non-interactive \
  --agree-todos \
  --email your-email@quidpath.com
```

### 6. Verify Deployment
```bash
# Check all services
bash ~/quidpath-deployment/backend/check-services.sh

# Or manually:
docker ps
curl http://localhost:8000/api/auth/health/
curl http://localhost:3000/
curl http://localhost:8002/api/billing/health/
curl http://localhost:8001/api/tazama/
```

## Service Endpoints

Once deployed, your services will be available at:

- **Frontend**: https://quidpath.com
- **Backend API**: https://api.quidpath.com
- **Billing Service**: https://billing.quidpath.com
- **Tazama AI**: https://ai.quidpath.com

## Important Notes

1. **DNS Configuration**: Make sure all subdomains point to your OVH server IP:
   - `A` record: `quidpath.com` → `51.77.147.233`
   - `A` record: `api.quidpath.com` → `51.77.147.233`
   - `A` record: `billing.quidpath.com` → `51.77.147.233`
   - `A` record: `ai.quidpath.com` → `51.77.147.233`

2. **Firewall**: Ports 80 and 443 should be open (you've already done this)

3. **Database**: Each service can use its own database or share. Update `.env` files accordingly.

4. **Inter-service Communication**: Services communicate via Docker network using container names:
   - Backend → Billing: `http://billing-backend:8000`
   - Backend → Tazama: `http://tazama-ai-backend:8001`

## Troubleshooting

### Service won't start
```bash
# Check logs
docker-compose -f ~/quidpath-deployment/backend/docker-compose.yml logs
docker-compose -f ~/quidpath-deployment/frontend/docker-compose.yml logs
```

### Nginx errors
```bash
sudo nginx -t
sudo tail -f /var/log/nginx/error.log
```

### SSL certificate issues
```bash
# Check certificate status
sudo certbot certificates

# Renew manually
sudo certbot renew --dry-run
```

### Database connection issues
```bash
# Test database connection
docker exec -it postgres_prod psql -U quidpath_user -d quidpath_db -c "SELECT 1;"
```

## Maintenance Commands

```bash
# Restart all services
cd ~/quidpath-deployment/backend && docker-compose restart
cd ~/quidpath-deployment/frontend && docker-compose restart
cd ~/quidpath-deployment/billing && docker-compose restart
cd ~/quidpath-deployment/tazama && docker-compose restart

# Update code
cd ~/quidpath-deployment/backend && git pull && docker-compose build && docker-compose up -d

# View resource usage
docker stats

# Backup database
docker exec postgres_prod pg_dump -U quidpath_user quidpath_db | gzip > backup_$(date +%Y%m%d).sql.gz
```

## All Set! 🎉

Your QuidPath ERP system is now ready for OVH deployment. Follow the steps above to complete the setup on your server.
