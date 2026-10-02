# Rekon Production Cloud Deployment Handbook

This guide outlines how to deploy **Rekon (रेकन)** to production cloud environments (Railway, Render, AWS, or Docker/VPS).

---

## 1. Architecture Overview

```
[ Internet / Browser ]
         │ (HTTPS: 443)
         ▼
[ Nginx Reverse Proxy (Frontend Container) ]
  ├── Serves React 18 SPA static distribution
  └── Gzip compression, asset caching, security headers
         │
         ▼ (REST API / JSON)
[ FastAPI Backend (Uvicorn ASGI Container) ]
  ├── Runs Alembic schema migrations on startup
  ├── Multi-tenant JWT authorization & rate card audits
  └── 4 Worker processes
         │
         ▼ (PostgreSQL Wire: 5432)
[ Managed PostgreSQL 16 ]
```

---

## 2. Environment Variables Checklist

Set the following environment variables in your cloud dashboard (Railway / Render / AWS Parameter Store):

| Variable                      | Description                              | Example / Recommended Value                   |
| :---------------------------- | :--------------------------------------- | :-------------------------------------------- |
| `ENVIRONMENT`                 | Deployment environment                   | `production`                                  |
| `DATABASE_URL`                | PostgreSQL connection string             | `postgresql://user:pass@host:5432/rekon_prod` |
| `SECRET_KEY`                  | 256-bit cryptographically secure secret  | Run `openssl rand -hex 32`                    |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT token validity window                | `1440` (24 hours)                             |
| `CORS_ORIGINS`                | Comma-separated allowed frontend origins | `https://app.rekon.in,https://rekon.in`       |
| `PORT`                        | Listening port for web server            | `8000` (auto-assigned by Railway/Render)      |
| `WORKERS`                     | Uvicorn parallel worker processes        | `4`                                           |

---

## 3. Deployment Methods

### Option A: 1-Click Railway Deployment (Recommended)

1. Create a new project on [Railway.app](https://railway.app).
2. Provision a **PostgreSQL** plugin.
3. Deploy from your GitHub repository:
   - **Backend Service**:
     - Root directory: `/`
     - Config file: `railway.toml`
     - Connect to PostgreSQL: set `DATABASE_URL` = `${{Postgres.DATABASE_URL}}`.
     - Set `SECRET_KEY` = `<your-openssl-key>`.
     - Railway will automatically run `backend/scripts/start_prod.sh` which executes Alembic migrations before listening for traffic.
   - **Frontend Service**:
     - Root directory: `frontend/`
     - Builder: Dockerfile (`frontend/Dockerfile`)
     - Build Arg: `VITE_API_BASE_URL` = `https://<your-backend-railway-url>`
4. Add custom domains (e.g. `api.yourcompany.com` and `rekon.yourcompany.com`).

---

### Option B: Local / Single-Server Production Spin-up (Docker Compose)

To spin up a full production stack locally or on a single Linux VM (AWS EC2 / DigitalOcean):

```bash
# 1. Generate secrets
export SECRET_KEY=$(openssl rand -hex 32)
export POSTGRES_PASSWORD=$(openssl rand -hex 16)

# 2. Start all services in detached mode
docker compose -f docker-compose.prod.yml up -d --build

# 3. Check health status
docker compose -f docker-compose.prod.yml ps

# 4. View logs
docker compose -f docker-compose.prod.yml logs -f backend
```

Access:

- Frontend: `http://localhost` (Port 80)
- Backend API Docs: `http://localhost:8000/docs`

---

## 4. Zero-Downtime Database Migrations

Database schema updates are managed via Alembic:

- The startup script `backend/scripts/start_prod.sh` automatically runs:
  ```bash
  alembic upgrade head
  ```
- Before creating a new migration:
  ```bash
  alembic revision --autogenerate -m "description_of_change"
  ```
- All migration scripts are stored in `backend/alembic/versions/` and version controlled in Git.

---

## 5. Security & Hardening Best Practices

1. **Non-Root Containers**: The backend runs as a non-privileged user `rekon` (UID 1001).
2. **Tenant Scoping**: All API queries are strictly filtered by `org_id` extracted from cryptographically verified JWT tokens.
3. **Paisa Quantization**: All monetary math uses Python `Decimal` with `ROUND_HALF_UP` to prevent IEEE floating point rounding errors.
4. **Disaster Recovery**:
   - Schedule daily pg_dump backups:
     ```bash
     pg_dump -Fc -d $DATABASE_URL > rekon_backup_$(date +%Y%m%d).dump
     ```
   - Test recovery monthly into a staging database.
