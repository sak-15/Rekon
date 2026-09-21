# Rekon (रेकन) ⚡

> **Multi-Tenant SaaS Payment & Settlement Reconciliation Engine**

[![FastAPI](https://img.shields.io/badge/FastAPI-0.110-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react&logoColor=black)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.2-3178C6?style=flat-square&logo=typescript&logoColor=white)](https://www.typescriptlang.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?style=flat-square&logo=postgresql&logoColor=white)](https://www.postgresql.org)
[![TailwindCSS](https://img.shields.io/badge/TailwindCSS-3.4-38B2AC?style=flat-square&logo=tailwind-css&logoColor=white)](https://tailwindcss.com)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker&logoColor=white)](https://www.docker.com)

---

## 1. Problem Statement & Vision

For subscription SaaS businesses in India, cash collection flows through a fragmented chain:

1. **Billing & Subscriptions** (Chargebee, Recurly, Zoho Subscriptions) record who is on which plan and what invoices were raised.
2. **Payment Gateways** (Razorpay, Stripe India, Cashfree, PayU) attempt the charges via UPI AutoPay, recurring credit cards, or eNACH, while deducting Merchant Discount Rate (MDR) fees, platform charges, and 18% GST on fees.
3. **Bank Accounts** receive lump-sum settlement credits in $T+n$ cycles with brief UTR batch descriptions.

Finance teams frequently suffer from:

- **First-pass reconciliation failure rates of 2–3%**, causing untracked cash leakage.
- **Hidden MDR & GST overcharges** compared to contracted rate cards.
- **Disconnected refunds and chargebacks** that land in later settlement cycles.
- **Compliance risks** under Ind AS 115 (Revenue Recognition) and input tax credit disallowance.

**Rekon** automates the three-layer reconciliation loop, isolates data cleanly across tenants (`org_id`), audits fees and taxes down to the paisa, and surfaces exceptions in an actionable review queue.

---

## 2. The Three-Layer Reconciliation Model

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                REKON MATCHING PIPELINE                                 │
└────────────────────────────────────────────────────────────────────────────────────────┘

 [Layer 1: Invoice Matching]
  Subscription Invoices (Chargebee / Zoho)
         ▲
         │ (Exact invoice_no, fuzzy customer + amount within ±2 day tolerance)
         ▼
  Gateway Transactions (Razorpay / Stripe)
         ▲
         │ (Transaction ID reference ↔ Settlement line breakdown)
         ▼
 [Layer 2: Settlement Matching]
  Settlement Batches (Gross collections − MDR fees − 18% GST − refunds = Net Settlement)
         ▲
         │ (Batch Net Amount ↔ Bank Credit reference within ₹1 tolerance)
         ▼
 [Layer 3: Bank Credit Matching]
  Bank Statement Credits (HDFC, ICICI, Axis UTR deposits)
```

---

## 3. Architecture & Tech Stack

| Component       | Technology                             | Rationale                                                  |
| --------------- | -------------------------------------- | ---------------------------------------------------------- |
| **Backend**     | Python 3.12, FastAPI, Pydantic v2      | High throughput, asynchronous I/O, rigorous typing         |
| **Database**    | PostgreSQL 16, SQLAlchemy 2.0, Alembic | Strict relational integrity, multi-tenant isolation, ACID  |
| **Data Engine** | Pandas                                 | Vectorized CSV normalization and parsing                   |
| **Frontend**    | React 18, Vite, TypeScript             | Lightning-fast HMR, developer ergonomics, component safety |
| **Styling**     | Tailwind CSS, Lucide Icons             | Clean modern design system                                 |
| **Auth**        | JWT (HS256) + bcrypt                   | Stateless token authentication with tenant scoping         |
| **Container**   | Docker & Docker Compose                | Identical local development and production environments    |

---

## 4. Repository Structure

```
rekon/
├── backend/                  # FastAPI Application
│   ├── app/
│   │   ├── api/              # API routers (auth, uploads, reconcile, reports)
│   │   ├── core/             # Configuration, database engine, security utils
│   │   ├── models/           # SQLAlchemy database models
│   │   ├── schemas/          # Pydantic request/response schemas
│   │   ├── services/         # Parsers, matching rules, fee engines
│   │   └── main.py           # FastAPI entrypoint & middleware
│   ├── tests/                # Unit and integration tests
│   ├── pyproject.toml        # Modern Python dependencies
│   ├── requirements.txt      # Standard pip requirements
│   └── Dockerfile            # Container build for backend
│
├── frontend/                 # React + Vite Application
│   ├── src/
│   │   ├── components/       # UI elements and tables
│   │   ├── pages/            # Route views
│   │   ├── api/              # HTTP client
│   │   ├── App.tsx           # Application shell & status visualizer
│   │   └── main.tsx          # React DOM mounting
│   ├── package.json          # Node dependencies
│   ├── vite.config.ts        # Vite configuration & proxy
│   └── Dockerfile            # Container build for frontend
│
├── docs/                     # Architectural & development docs
│   ├── ARCHITECTURE.md       # Deep dive into multi-tenancy & matching rules
│   └── DEVELOPMENT.md        # Step-by-step developer guide
│
├── docker-compose.yml        # Orchestrates Postgres, Backend, and Frontend
├── .env.example              # Environment variables template
├── .gitignore                # Comprehensive version control ignore rules
└── README.md                 # Project handbook
```

---

## 5. Quick Start Guide

### Option A: Using Docker Compose (Recommended)

1. Clone or navigate to the repository:

   ```bash
   cd /Users/sakshiii/Desktop/Rekon
   ```

2. Copy the environment variables:

   ```bash
   cp .env.example .env
   ```

3. Launch the full stack:

   ```bash
   docker compose up --build
   ```

4. Access the applications:
   - **Frontend UI**: [http://localhost:5173](http://localhost:5173)
   - **Backend API**: [http://localhost:8000](http://localhost:8000)
   - **Interactive API Docs (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)
   - **Health Check**: [http://localhost:8000/health](http://localhost:8000/health)

---

### Option B: Local Development (Without Docker)

#### Prerequisites

- Node.js >= 18 and npm >= 9
- Python >= 3.10
- PostgreSQL >= 15 (or local SQLite for early testing)

#### 1. Backend Setup

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

#### 2. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

---

---

## 6. Authentication & Tenancy API

Rekon uses stateless JWT authentication with tenant scoping. When a user registers or logs in, the returned access token embeds the tenant's `org_id`. All downstream financial queries use this ID to enforce strict data isolation.

| Method | Endpoint             | Description                                       | Auth Required    |
| ------ | -------------------- | ------------------------------------------------- | ---------------- |
| `POST` | `/api/auth/register` | Register new tenant organisation and admin user   | No               |
| `POST` | `/api/auth/login`    | Authenticate with email & password, returns JWT   | No               |
| `GET`  | `/api/auth/me`       | Fetch authenticated caller profile & organisation | Yes (Bearer JWT) |

### Example Registration:

```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "org_name": "ChargeFlow Inc",
    "org_slug": "chargeflow",
    "email": "cfo@chargeflow.io",
    "password": "StrongPassword123!",
    "full_name": "Rohan Sharma",
    "currency": "INR"
  }'
```

---

## 7. CSV Ingestion & Normalization API

Rekon provides dedicated multipart endpoints to ingest financial data across the 3 layers. All endpoints perform automatic column mapping, currency/date cleaning, deduplication against previously ingested records, and row-level error audit logging in `upload_jobs`.

| Method | Endpoint | Supported Formats | Auth Required |
|---|---|---|---|
| `POST` | `/api/uploads/invoices` | Chargebee, Zoho Subscriptions, generic SaaS invoices | Yes (Bearer JWT) |
| `POST` | `/api/uploads/gateway-txns` | Razorpay, Stripe (auto-detects gateway) | Yes (Bearer JWT) |
| `POST` | `/api/uploads/settlements` | Gateway settlement files (groups into batches & lines) | Yes (Bearer JWT) |
| `POST` | `/api/uploads/bank-statements`| HDFC, ICICI, Axis, and generic bank statements | Yes (Bearer JWT) |
| `GET`  | `/api/uploads` | List previous upload jobs for the tenant | Yes (Bearer JWT) |
| `GET`  | `/api/uploads/{upload_id}` | Fetch upload job audit status & row error details | Yes (Bearer JWT) |

### Example Ingesting Invoices:
```bash
curl -X POST http://localhost:8000/api/uploads/invoices \
  -H "Authorization: Bearer <your_jwt_token>" \
  -F "file=@invoices.csv"
```

---

## 8. Verification & Testing

To run the complete automated test suite (25 passing tests):

```bash
PYTHONPATH=backend backend/.venv/bin/pytest backend/tests/ -v
```

---

## 9. Development Roadmap

- [x] **Phase 1: Step 1.1** — Project Scaffold (Docker Compose, FastAPI, React, Config)
- [x] **Phase 1: Step 1.2** — Database Schema v1 & Alembic Migrations
- [x] **Phase 1: Step 1.3** — Multi-Tenant Auth API (JWT, Register, Login)
- [x] **Phase 1: Step 1.4** — CSV Ingestion & Normalization (Razorpay, Stripe, Chargebee)
- [ ] **Phase 1: Step 1.5** — Ingestion UI & Tabular Record Viewer
- [ ] **Phase 2** — Three-Layer Core Reconciliation Engine
- [ ] **Phase 3** — MDR & 18% GST Fee Audit Engine
- [ ] **Phase 4** — Exception Classification & Resolution Queue
- [ ] **Phase 5** — Founder Dashboard & Cloud Deployment (Railway)
- [ ] **Phase 6** — Revenue Recognition (Ind AS 115)
- [ ] **Phase 7** — Direct Gateway APIs & Webhooks (Razorpay, Stripe)
- [ ] **Phase 8** — Multi-rail Economics & FX Analysis

---

## 10. License

Private & Proprietary • Rekon
