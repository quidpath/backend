# OVH Cloud Deployment Guide - QuidPath ERP

Complete deployment guide for all QuidPath services on OVH Cloud.

## Prerequisites

- OVH cloud server (Ubuntu 22.04+)
- SSH access to server
- Domain names configured:
  - `quidpath.com` (frontend)
  - `api.quidpath.com` (backend)
  - `billing.quidpath.com` (billing service)
  - `ai.quidpath.com` (Tazama AI service)
- DNS A records pointing to your OVH server IP

## Quick Start

```bash
# 1. Clone all repositories to ~/quidpath-deployment
cd ~/quidpath-deployment
git clone <your-backend-repo> backend
git clone <your-frontend-repo> frontend
git clone <your-billing-repo> billing
git clone <your-tazama-repo> tazama

# 2. Create .env files for each service (see below)

# 3. Run deployment script
chmod +x ~/quidpath-deployment/backend/deploy-all-services.sh
~/quidpath-deployment/backend/deploy-all-services.sh
```

## Environment Variables

### Backend (.env)
```bash
DJANGO_ENV=prod
DJANGO_SETTINGS_MODULE=quidpath_backend.settings.prod
DEBUG=False
SECRET_KEY=<generate-with-openssl-rand-hex-32>
ALLOWED_HOSTS=api.quidpath.com,quidpath.com,www.quidpath.com
CSRF_TRUSTED_ORIGINS=https://quidpath.com,https://www.quidpath.com,https://api.quidpath.com

DATABASE_URL=postgresql://quidpath_user:<password>@postgres_prod:5432/quidpath_db
POSTGRES_DB=quidpath_db
POSTGRES_USER=quidpath_user
POSTGRES_PASSWORD=<strong-password>

SMTP_USER=<your-email>
SMTP_PASSWORD=<app-password>
DEFAULT_FROM_EMAIL=noreply@quidpath.com

BILLING_SERVICE_URL=http://billing-backend:8000/api/billing
TAZAMA_AI_API_URL=http://tazama-ai-backend:8001/api/tazama/

PORT=8000
WORKERS=4
```

### Frontend (.env)
```bash
NEXT_PUBLIC_API_BASE_URL=https://api.quidpath.com/
NEXT_PUBLIC_TAZAMA_AI_API_URL=https://ai.quidpath.com/api/tazama/
NEXT_PUBLIC_BILLING_SERVICE_URL=https://billing.quidpath.com/api/billing
NODE_ENV=production
```

### Billing (.env)
```bash
DJANGO_ENV=prod
DJANGO_SETTINGS_MODULE=billing_service.settings.prod
DEBUG=False
SECRET_KEY=<generate-secret-key>
ALLOWED_HOSTS=billing.quidpath.com

DATABASE_URL=postgresql://billing_user:<password>@postgres_billing_prod:5432/billing_db
POSTGRES_DB=billing_db
POSTGRES_USER=billing_user
POSTGRES_PASSWORD=<strong-password>

ERP_BACKEND_URL=http://django-backend:8000
```

### Tazama AI (.env)
```bash
DJANGO_ENV=prod
DJANGO_SETTINGS_MODULE=tazama_ai.settings.prod
DEBUG=False
SECRET_KEY=<generate-secret-key>
ALLOWED_HOSTS=ai.quidpath.com

DATABASE_URL=postgresql://tazama_user:<password>@db:5432/tazama_db
POSTGRES_DB=tazama_db
POSTGRES_USER=tazama_user
POSTGRES_PASSWORD=<strong-password>

ERP_BACKEND_URL=http://django-backend:8000
```

## Service Ports

- Backend: `127.0.0.1:8000` (internal only, accessed via Nginx)
- Frontend: `127.0.0.1:3000` (internal only, accessed via Nginx)
- Billing: `127.0.0.1:8002` (internal only, accessed via Nginx)
- Tazama AI: `127.0.0.1:8001` (internal only, accessed via Nginx)
- Nginx: `80:80, 443:443` (public)

## Deployment Steps

1. **Setup server** (already done based on your output)
2. **Create directories and network**
3. **Deploy each service**
4. **Configure Nginx**
5. **Get SSL certificates**
6. **Verify all services**

## Troubleshooting

### Check service status
```bash
docker ps
docker-compose -f ~/quidpath-deployment/backend/docker-compose.yml ps
```

### View logs
```bash
docker-compose -f ~/quidpath-deployment/backend/docker-compose.yml logs -f
docker-compose -f ~/quidpath-deployment/frontend/docker-compose.yml logs -f
```

### Restart services
```bash
cd ~/quidpath-deployment/backend && docker-compose restart
cd ~/quidpath-deployment/frontend && docker-compose restart
```

### Test endpoints
```bash
curl http://localhost:8000/api/auth/health/
curl http://localhost:3000/
curl http://localhost:8002/api/billing/health/
curl http://localhost:8001/api/tazama/
```
