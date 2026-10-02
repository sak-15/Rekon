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

| Method | Endpoint                       | Supported Formats                                      | Auth Required    |
| ------ | ------------------------------ | ------------------------------------------------------ | ---------------- |
| `POST` | `/api/uploads/invoices`        | Chargebee, Zoho Subscriptions, generic SaaS invoices   | Yes (Bearer JWT) |
| `POST` | `/api/uploads/gateway-txns`    | Razorpay, Stripe (auto-detects gateway)                | Yes (Bearer JWT) |
| `POST` | `/api/uploads/settlements`     | Gateway settlement files (groups into batches & lines) | Yes (Bearer JWT) |
| `POST` | `/api/uploads/bank-statements` | HDFC, ICICI, Axis, and generic bank statements         | Yes (Bearer JWT) |
| `GET`  | `/api/uploads`                 | List previous upload jobs for the tenant               | Yes (Bearer JWT) |
| `GET`  | `/api/uploads/{upload_id}`     | Fetch upload job audit status & row error details      | Yes (Bearer JWT) |

### Example Ingesting Invoices:

```bash
curl -X POST http://localhost:8000/api/uploads/invoices \
  -H "Authorization: Bearer <your_jwt_token>" \
  -F "file=@invoices.csv"
```

## 8. Three-Layer Reconciliation Engine API

Rekon executes an atomic three-layer matching pipeline (Invoices ↔ Gateway Transactions ↔ Settlement Lines ↔ Bank Credits).

| Method | Endpoint                          | Description                                                         | Auth Required    |
| ------ | --------------------------------- | ------------------------------------------------------------------- | ---------------- |
| `POST` | `/api/reconcile`                  | Trigger a new three-layer reconciliation run (with optional rules)  | Yes (Bearer JWT) |
| `GET`  | `/api/reconcile`                  | List historical reconciliation runs and executive metrics           | Yes (Bearer JWT) |
| `GET`  | `/api/reconcile/{run_id}`         | Fetch detailed run report, layer counts, and financial totals       | Yes (Bearer JWT) |
| `GET`  | `/api/reconcile/{run_id}/matches` | Query itemized audit matches with filtering by `layer` and `status` | Yes (Bearer JWT) |

### Example Triggering a Reconciliation Run:

```bash
curl -X POST http://localhost:8000/api/reconcile \
  -H "Authorization: Bearer <your_jwt_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "rule_config": {
      "amount_tolerance": "1.00",
      "layer_1_date_window_days": 2,
      "layer_3_bank_window_days": 4,
      "enable_fuzzy_matching": true
    }
  }'
```

---

## 9. MDR & 18% GST Fee Audit Engine API

Rekon audits transaction fees and statutory 18% GST against personalized merchant rate cards and Indian regulatory benchmarks (UPI 0% MDR, RBI ₹20 debit cap).

| Method   | Endpoint                           | Description                                                        | Auth Required    |
| -------- | ---------------------------------- | ------------------------------------------------------------------ | ---------------- |
| `GET`    | `/api/rate-cards`                  | List active contracted rate cards (auto-seeds benchmarks if empty) | Yes (Bearer JWT) |
| `POST`   | `/api/rate-cards`                  | Create a custom rate card rule for specific payment rails          | Yes (Bearer JWT) |
| `PUT`    | `/api/rate-cards/{id}`             | Update percentage MDR, flat fee, or regulatory fee caps            | Yes (Bearer JWT) |
| `DELETE` | `/api/rate-cards/{id}`             | Delete / deactivate a rate card rule                               | Yes (Bearer JWT) |
| `POST`   | `/api/rate-cards/reset-benchmarks` | Restore standard Indian industry benchmarks (NPCI / RBI)           | Yes (Bearer JWT) |
| `POST`   | `/api/rate-cards/calculate`        | Instant interactive preview of MDR, 18% GST, and net settlement    | Yes (Bearer JWT) |
| `GET`    | `/api/fee-audit`                   | Comprehensive mathematical fee audit and overcharge classification | Yes (Bearer JWT) |
| `GET`    | `/api/fee-audit/export`            | Download pre-formatted dispute claim CSV for Razorpay / Stripe     | Yes (Bearer JWT) |

---

## 10. Exception Classification & Resolution Queue API

Rekon automatically classifies unmatched records into forensic root causes and provides an actionable resolution workflow for finance operators:

| Method | Endpoint                            | Description                                                             | Auth Required    |
| ------ | ----------------------------------- | ----------------------------------------------------------------------- | ---------------- |
| `GET`  | `/api/exceptions`                   | Query tenant exceptions with filters (`status`, `type`, `severity`)     | Yes (Bearer JWT) |
| `GET`  | `/api/exceptions/summary`           | Executive metrics: open items, total unresolved exposure, breakdowns    | Yes (Bearer JWT) |
| `POST` | `/api/exceptions/{id}/manual-match` | Manually link unmatched records with 100% confidence score & audit note | Yes (Bearer JWT) |
| `POST` | `/api/exceptions/{id}/write-off`    | 1-click write-off of minor deltas (≤ ₹50) to Rounding Expense ledger    | Yes (Bearer JWT) |
| `POST` | `/api/exceptions/batch-write-off`   | Bulk write-off of all open minor rounding deltas under threshold (≤ ₹5) | Yes (Bearer JWT) |
| `PUT`  | `/api/exceptions/{id}/status`       | Update queue status (`investigating`, `disputed`, `resolved`)           | Yes (Bearer JWT) |

### Automated Exception Taxonomy:

1. `TIMING_DIFFERENCE`: Clearing lag < 48 hours awaiting bank credit.
2. `MISSING_BANK_CREDIT`: Settlement batches > 48 hours without bank deposit (CRITICAL/HIGH severity).
3. `UNBILLED_CHARGE`: Captured gateway payments without subscription invoice.
4. `UNIDENTIFIED_BANK_DEPOSIT`: Direct bank deposit with no gateway batch linkage.
5. `PAISA_ROUNDING_DELTA`: Immaterial fractional discrepancy (≤ ₹5.00) eligible for write-off.
6. `AMOUNT_MISMATCH` & `GATEWAY_FEE_DISCREPANCY`: Variance between invoice total and charged amount or fees.

---

## 11. Verification & Testing

To run the complete automated test suite (86 passing tests):

```bash
PYTHONPATH=backend backend/.venv/bin/pytest backend/tests/ -v
```

---

## 12. Development Roadmap

- [x] **Phase 1: Step 1.1** — Project Scaffold (Docker Compose, FastAPI, React, Config)
- [x] **Phase 1: Step 1.2** — Database Schema v1 & Alembic Migrations
- [x] **Phase 1: Step 1.3** — Multi-Tenant Auth API (JWT, Register, Login)
- [x] **Phase 1: Step 1.4** — CSV Ingestion & Normalization (Razorpay, Stripe, Chargebee)
- [x] **Phase 1: Step 1.5** — Ingestion UI & Tabular Record Viewer (Phase 1 Complete 🎉)
- [x] **Phase 2** — Three-Layer Core Reconciliation Engine (Phase 2 Complete 🎉)
  - [x] **Step 2.1** — ReconciliationRun & ReconciliationMatch Models + Migration
  - [x] **Step 2.2** — Layer 1 Matching Engine (Invoices ↔ Gateway Transactions)
  - [x] **Step 2.3** — Layer 2 Matching Engine (Gateway Transactions ↔ Settlement Lines)
  - [x] **Step 2.4** — Layer 3 Matching Engine (Settlement Batches ↔ Bank Credits)
  - [x] **Step 2.5** — Reconciliation Orchestrator & Execution API (`POST /api/reconcile`)
  - [x] **Step 2.6** — Frontend Reconciliation Dashboard & Match Visualizer
- [x] **Phase 3** — MDR & 18% GST Fee Audit Engine (Phase 3 Complete 🎉)
  - [x] **Step 3.1** — Gateway Fee Rate Card Model & Migration
  - [x] **Step 3.2** — 18% GST & MDR Mathematical Audit Engine
  - [x] **Step 3.3** — Overcharge Detection & Dispute Flagging
  - [x] **Step 3.4** — Fee Audit REST APIs (`/api/rate-cards`, `/api/fee-audit`)
  - [x] **Step 3.5** — Fee Audit UI Dashboard & Rate Card Manager
- [x] **Phase 4** — Exception Classification & Resolution Queue (Phase 4 Complete 🎉)
  - [x] **Step 4.1** — ReconciliationException Data Models & Migration
  - [x] **Step 4.2** — Automated Exception Classification Engine (6 Root Causes)
  - [x] **Step 4.3** — Resolution Actions Service (Manual Match, Write-off, Batch)
  - [x] **Step 4.4** — Exception Queue REST APIs & Summary Endpoints
  - [x] **Step 4.5** — Resolution Queue Workspace UI (`ExceptionsHub.tsx`)
- [x] **Phase 5** — Founder Dashboard & Cloud Deployment (Phase 5 Complete 🎉)
  - [x] **Step 5.1** — Executive Analytics Service & REST APIs (`/api/analytics/dashboard`, waterfall, KPIs)
  - [x] **Step 5.2** — Founder Executive Dashboard UI (`ExecutiveDashboard.tsx` with 5 Hero KPIs & Realization Waterfall)
  - [x] **Step 5.3** — Production Containerization & Cloud Deployment Config (`Dockerfile`, `nginx.conf`, `railway.toml`, `DEPLOYMENT.md`)
- [ ] **Phase 6** — Revenue Recognition (Ind AS 115)
- [ ] **Phase 7** — Direct Gateway APIs & Webhooks (Razorpay, Stripe)
- [ ] **Phase 8** — Multi-rail Economics & FX Analysis

---

## 10. License

Private & Proprietary • Rekon
