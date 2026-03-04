# Quidpath Backend

Django REST API for **Quidpath** — an ERP platform with authentication, organizations, banking, accounting, payments, and subscription billing.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Django](https://img.shields.io/badge/django-3.2+-green.svg)](https://www.djangoproject.com/)

---

## What this system does

- **Authentication** — Login, register (corporate & individual), JWT refresh, profile, forgot/reset password, email activation, logo upload, notifications, subscription plans and payment initiation.
- **Organizations (OrgAuth)** — Create/list/update corporates, corporate users and roles, subscription webhooks from billing service, “my subscription” and feature-check APIs.
- **Banking** — Bank accounts, internal transfers, bank reconciliation, bank charges, transactions (CRUD).
- **Accounting** — Customers, vendors, quotations, invoices, purchase orders, vendor bills, expenses, chart of accounts (types, sub-types, accounts), journal entries (post/unpost), general ledger, trial balance, financial reports (P&amp;L, balance sheet, income statement, cash flow), aging reports, inventory (warehouses, items, stock movements), attachments, audit logs, recurring transactions, currency rates.
- **Payments** — Individual billing plans, subscribe, subscription status, payment history; M-Pesa callback.
- **Billing integration** — Proxies to external billing service: subscription status, invoices, plans, subscribe, payment initiate, promotion validate (`/api/billing/`).
- **Internal APIs** — Auth verification for microservices (`/api/internal/auth/verify/`).

Access to the main app is gated by subscription/trial (middleware); billing and a few auth paths are exempt.

---

## Tech stack

- **Python 3.11**, Django 3.2+, Django REST Framework  
- **PostgreSQL** (via `DATABASE_URL`)  
- **Redis** (Channels / caching)  
- **Daphne** (ASGI in production), **Gunicorn** (optional via `start.sh`)  
- **JWT** (Simple JWT), **Channels** for WebSockets  

---

## Quick start (local development)

### Prerequisites

- Python 3.11+
- PostgreSQL 13+
- Redis (optional for Channels)

### Setup

```bash
# Clone and enter project
git clone <repo-url>
cd quidpath-backend

# Virtual environment
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate

# Install dependencies
pip install -r requirements/base.txt
# or requirements/dev.txt if you use it

# Environment
cp .env.dev .env
# Edit .env: set DATABASE_URL, SECRET_KEY, etc.

# Database
createdb devdb   # or your DB name from DATABASE_URL
python manage.py migrate
python manage.py createsuperuser

# Run
export DJANGO_SETTINGS_MODULE=quidpath_backend.settings.dev
export DJANGO_ENV=dev
python manage.py runserver
```

API base: `http://localhost:8000/` (or the port you use).  
Django admin: `http://localhost:8000/admin/`.

---

## Running with Docker (development)

Compose brings up PostgreSQL, Redis, and the backend with hot-reload.

```bash
docker compose -f docker-compose.dev.yml up -d
```

- Backend: `http://localhost:8000`  
- DB: `postgres_dev:5432`, user `devuser`, db `devdb`  
- Redis: `redis_dev:6379`  

Migrations run automatically; for a fresh DB you may need to run them once:

```bash
docker compose -f docker-compose.dev.yml exec backend python manage.py migrate
```

---

## Production / staging deployment

- The app runs as a **Docker image** (see `Dockerfile`). Entrypoint: `entrypoint.sh` (wait for DB → migrate → bootstrap_data → collectstatic → start Daphne on port **8004**).
- **Compose**: `docker-compose.yml` (production), `docker-compose.stage.yml` (staging) — services: `db`, `redis`, `backend`. Env (e.g. `DATABASE_URL`, `POSTGRES_*`, `SECRET_KEY`, `JWT_SECRET_KEY`, `BILLING_SERVICE_URL`, M-Pesa, etc.) must be provided via `--env-file` or the deployment pipeline.
- **CI/CD**: `.github/workflows/deploy.yml` builds and pushes the image on push to `Development` / `master`, and sends the chosen compose file + env secrets to the infra repo (e.g. `stevendegwa/infra`) for deployment. Staging uses `docker-compose.stage.yml` and stage-specific secrets (`POSTGRES_USER_STAGE`, etc.).

See `docs/staging-database-credentials.md` if the stage backend fails with Postgres authentication errors.

---

## Main API surface (by app)

All paths are relative to the API base (e.g. `https://api.quidpath.com/` or `http://localhost:8000/`). Most require JWT (`Authorization: Bearer <access_token>`).

| Area | Examples |
|------|----------|
| **Auth** | `POST /login/`, `POST /register/`, `POST /register-individual/`, `POST /activate-account/`, `GET /get_profile/`, `POST /token/refresh/`, `POST /password-forgot/`, `POST /reset-password/`, `GET /plans/`, `POST /payments/initiate/`, `GET /subscription/status/`, `GET /notifications/`, `GET /health/` |
| **OrgAuth** | `POST /corporate/create`, `GET /corporate/list`, `POST /corporate-users/create`, `GET /subscription/my-subscription`, `POST /subscription/sync`, `POST /webhooks/subscription` |
| **Banking** | `POST /bank-account/add/`, `GET /bank-account/list/`, `POST /internal-transfer/create/`, `GET /bank-reconciliation/list/`, `POST /transaction/create/`, `GET /transaction/list/` |
| **Accounting** | `POST /customer/create/`, `POST /vendor/create/`, `POST /quotation/create-and-post/`, `POST /invoice/create-and-post/`, `POST /purchase-orders/create-and-post/`, `POST /vendor-bill/create/`, `POST /expense/create/`, `POST /journal/create/`, `GET /ledger/list/`, `GET /trial-balance/`, `GET /reports/balance-sheet/`, `GET /reports/income-statement/`, inventory, attachments, audit-logs, currency rates |
| **Payments** | `GET /api/payments/individual/plans/`, `POST /api/payments/individual/subscribe/`, `GET /api/payments/individual/subscription/status/`, `POST /api/payments/mpesa/callback/` |
| **Billing** | `GET /api/billing/status/`, `GET /api/billing/invoices/`, `GET /api/billing/plans/`, `POST /api/billing/subscribe/`, `POST /api/billing/payment/initiate/`, `POST /api/billing/promotion/validate/` |
| **Internal** | `POST /api/internal/auth/verify/` |

---

## Project layout (relevant parts)

```
quidpath-backend/
├── Authentication/          # Auth, profile, plans, notifications
├── OrgAuth/                 # Corporates, corporate users, subscription API
├── Banking/                 # Bank accounts, transfers, reconciliation, transactions
├── Accounting/              # Invoicing, POs, vendor bills, expenses, GL, reports, inventory
├── Payments/                # Individual billing, M-Pesa callback
├── quidpath_backend/        # Settings, URLs, ASGI/WSGI, core
│   ├── core/                # Billing client, middleware, billing + internal views
│   └── settings/            # base, dev, prod
├── excel_extractor/         # Excel/book utilities (used internally)
├── entrypoint.sh            # Docker entry (migrate, bootstrap, daphne)
├── start.sh                 # Alternative: gunicorn
├── Dockerfile
├── docker-compose.dev.yml
├── docker-compose.stage.yml
├── docker-compose.yml
├── .github/workflows/deploy.yml
├── requirements/
│   ├── base.txt
│   ├── dev.txt
│   └── prod.txt
└── docs/
    └── staging-database-credentials.md
```

---

## Environment variables (summary)

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | PostgreSQL connection string (required) |
| `SECRET_KEY` | Django secret |
| `JWT_SECRET_KEY` | JWT signing |
| `DEBUG`, `ALLOWED_HOSTS` | Django run mode and hosts |
| `REDIS_HOST`, `REDIS_PORT` | Redis for Channels/cache |
| `USE_MEMORY_CHANNEL_LAYER` | Use in-memory layer instead of Redis |
| `BILLING_SERVICE_URL` | Base URL of billing service for `/api/billing/` |
| `SMTP_*` | Email (e.g. activation, notifications) |
| `MPESA_*` | M-Pesa (environment, keys, short code, passkey, callback URL) |

See `.env.dev` or `.env.stage` in the repo for more; production values are typically provided by the deployment pipeline.

---

## License

See [LICENSE](LICENSE) in the repository.
