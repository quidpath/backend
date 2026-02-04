# Production Port Configuration

## Updated Port Assignments

To avoid port conflicts, the production services now use the following ports:

### Service Port Mapping

| Service | Container Name | Internal Port | External Port (Host) | URL |
|---------|---------------|---------------|---------------------|-----|
| **Main Backend** | django-backend | 8000 | 8004 | http://localhost:8004 |
| **Billing Service** | billing-backend | 8000 | 8005 | http://localhost:8005 |
| **Tazama AI** | tazama-ai-backend | 8001 | 8006 | http://localhost:8006 |

### Database Ports

| Service | Container Name | Internal Port | External Port (Host) |
|---------|---------------|---------------|---------------------|
| **Main DB** | postgres_prod | 5432 | 5432 |
| **Billing DB** | postgres_billing_prod | 5432 | 5433 |
| **Tazama DB** | tazama_postgres | 5432 | 5434 |

## Important Notes

### Inter-Service Communication

Services communicate with each other using **internal container ports** on the shared `quidpath_network`:

```bash
# Main Backend → Billing Service
BILLING_SERVICE_URL=http://billing-backend:8000/api/billing

# Main Backend → Tazama Service  
TAZAMA_SERVICE_URL=http://tazama-ai-backend:8001/api/tazama

# Billing/Tazama → Main Backend
ERP_BACKEND_URL=http://django-backend:8000
```

**Key Point:** Inter-service URLs use **internal ports** (8000, 8001), NOT external ports (8004, 8005, 8006)!

### External Access (from host)

When accessing from the host machine or through nginx:

```bash
# Main Backend
curl http://localhost:8004/api/auth/health/

# Billing Service
curl http://localhost:8005/api/billing/health/

# Tazama AI
curl http://localhost:8006/api/tazama/health/
```

### Nginx Configuration

If using nginx as reverse proxy, update your configuration:

```nginx
# Main Backend
location /api/ {
    proxy_pass http://127.0.0.1:8004;
}

# Billing Service
location /api/billing/ {
    proxy_pass http://127.0.0.1:8005;
}

# Tazama AI
location /api/tazama/ {
    proxy_pass http://127.0.0.1:8006;
}
```

## Deployment Commands

### Deploy All Services

```bash
# Main Backend
cd ~/quidpath-deployment/backend
docker compose down
docker compose up -d --build

# Billing Service
cd ~/quidpath-deployment/billing
docker compose down
docker compose up -d --build

# Tazama AI
cd ~/quidpath-deployment/tazama
docker compose down
docker compose up -d --build
```

### Verify Services

```bash
# Check all containers are running
docker ps | grep -E "django-backend|billing-backend|tazama-ai-backend"

# Test each service
curl -I http://localhost:8004/api/auth/health/
curl -I http://localhost:8005/api/billing/health/
curl -I http://localhost:8006/api/tazama/health/
```

## Environment Variables

### Main Backend (.env)

```bash
# No changes needed - uses internal ports
BILLING_SERVICE_URL=http://billing-backend:8000/api/billing
TAZAMA_SERVICE_URL=http://tazama-ai-backend:8001/api/tazama
```

### Billing Service (.env)

```bash
# No changes needed - uses internal port
ERP_BACKEND_URL=http://django-backend:8000
```

### Tazama AI (.env)

```bash
# No changes needed - uses internal port
ERP_BACKEND_URL=http://django-backend:8000
```

## Troubleshooting

### Port Already in Use

If you still get "port already allocated" errors:

```bash
# Find what's using the port
sudo lsof -i :8004
sudo lsof -i :8005
sudo lsof -i :8006

# Stop the conflicting service
docker ps -a | grep <container-name>
docker stop <container-name>
docker rm <container-name>
```

### Service Can't Connect

If services can't communicate:

```bash
# Verify network
docker network inspect quidpath_network

# Should show all three containers:
# - django-backend
# - billing-backend
# - tazama-ai-backend

# Test connection from main backend
docker exec django-backend curl -I http://billing-backend:8000/api/billing/health/
docker exec django-backend curl -I http://tazama-ai-backend:8001/api/tazama/health/
```

## Summary

✅ **External Ports Changed:**
- Main Backend: 8000 → 8004
- Billing: 8002 → 8005
- Tazama: 8001 → 8006

✅ **Internal Ports Unchanged:**
- Services still communicate using original ports
- No environment variable changes needed

✅ **All services bound to 127.0.0.1:**
- Only accessible from localhost
- Use nginx for external access
