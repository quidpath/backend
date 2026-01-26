#!/bin/bash
# Script to create .env template files for all services

echo "📝 Creating .env template files..."

# Backend .env template
cat > ~/quidpath-deployment/backend/.env.template << 'EOF'
DJANGO_ENV=prod
DJANGO_SETTINGS_MODULE=quidpath_backend.settings.prod
DEBUG=False
SECRET_KEY=CHANGE_THIS_GENERATE_WITH_openssl_rand_-hex_32
ALLOWED_HOSTS=api.quidpath.com,quidpath.com,www.quidpath.com
CSRF_TRUSTED_ORIGINS=https://quidpath.com,https://www.quidpath.com,https://api.quidpath.com

DATABASE_URL=postgresql://quidpath_user:CHANGE_THIS@postgres_prod:5432/quidpath_db
POSTGRES_DB=quidpath_db
POSTGRES_USER=quidpath_user
POSTGRES_PASSWORD=CHANGE_THIS_STRONG_PASSWORD

SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
DEFAULT_FROM_EMAIL=noreply@quidpath.com

BILLING_SERVICE_URL=http://billing-backend:8000/api/billing
TAZAMA_AI_API_URL=http://tazama-ai-backend:8001/api/tazama/

PORT=8000
WORKERS=4
EOF

# Frontend .env template
cat > ~/quidpath-deployment/frontend/.env.template << 'EOF'
NEXT_PUBLIC_API_BASE_URL=https://api.quidpath.com/
NEXT_PUBLIC_TAZAMA_AI_API_URL=https://ai.quidpath.com/api/tazama/
NEXT_PUBLIC_BILLING_SERVICE_URL=https://billing.quidpath.com/api/billing
NODE_ENV=production
EOF

# Billing .env template
cat > ~/quidpath-deployment/billing/.env.template << 'EOF'
DJANGO_ENV=prod
DJANGO_SETTINGS_MODULE=billing_service.settings.prod
DEBUG=False
SECRET_KEY=CHANGE_THIS_GENERATE_WITH_openssl_rand_-hex_32
ALLOWED_HOSTS=billing.quidpath.com

DATABASE_URL=postgresql://billing_user:CHANGE_THIS@postgres_billing_prod:5432/billing_db
POSTGRES_DB=billing_db
POSTGRES_USER=billing_user
POSTGRES_PASSWORD=CHANGE_THIS_STRONG_PASSWORD

ERP_BACKEND_URL=http://django-backend:8000
PORT=8000
WORKERS=2
EOF

# Tazama AI .env template
cat > ~/quidpath-deployment/tazama/.env.template << 'EOF'
DJANGO_ENV=prod
DJANGO_SETTINGS_MODULE=tazama_ai.settings.prod
DEBUG=False
SECRET_KEY=CHANGE_THIS_GENERATE_WITH_openssl_rand_-hex_32
ALLOWED_HOSTS=ai.quidpath.com

DATABASE_URL=postgresql://tazama_user:CHANGE_THIS@db:5432/tazama_db
POSTGRES_DB=tazama_db
POSTGRES_USER=tazama_user
POSTGRES_PASSWORD=CHANGE_THIS_STRONG_PASSWORD

ERP_BACKEND_URL=http://django-backend:8000
GUNICORN_WORKERS=3
GUNICORN_TIMEOUT=120
EOF

echo "✅ Template files created!"
echo ""
echo "Next steps:"
echo "1. Copy templates to .env files:"
echo "   cp ~/quidpath-deployment/backend/.env.template ~/quidpath-deployment/backend/.env"
echo "   cp ~/quidpath-deployment/frontend/.env.template ~/quidpath-deployment/frontend/.env"
echo "   cp ~/quidpath-deployment/billing/.env.template ~/quidpath-deployment/billing/.env"
echo "   cp ~/quidpath-deployment/tazama/.env.template ~/quidpath-deployment/tazama/.env"
echo ""
echo "2. Edit each .env file and replace CHANGE_THIS values"
echo "3. Generate SECRET_KEY with: openssl rand -hex 32"
