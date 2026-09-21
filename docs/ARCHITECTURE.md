# Rekon Architecture & Design Specification

## 1. System Overview

Rekon is an enterprise-grade, multi-tenant reconciliation platform specifically designed to reconcile payment and settlement flows for subscription SaaS businesses operating in India.

The platform continuously verifies that:

1. Every raised subscription invoice has an associated, successful payment attempt.
2. Every gateway charge is grouped into a settlement batch with verified fee/GST deductions.
3. Every settlement batch matches the exact net credit deposited in the company's bank account.

---

## 2. Multi-Tenancy Design

Rekon implements **logical tenant isolation via row-level scoping**:

```
 ┌────────────────────────────────────────────────────────┐
 │                    organisations                       │
 │ (id: UUID, name: VARCHAR, slug: VARCHAR, created_at)   │
 └───────────────────────────┬────────────────────────────┘
                             │ 1:N
                             ▼
 ┌────────────────────────────────────────────────────────┐
 │                        users                           │
 │ (id: UUID, org_id: FK, email: VARCHAR, role: VARCHAR)  │
 └────────────────────────────────────────────────────────┘
                             │
                             ▼
  Enforced on every business entity table:
  - invoices (org_id: FK)
  - gateway_txns (org_id: FK)
  - settlement_batches (org_id: FK)
  - settlement_lines (org_id: FK)
  - bank_credits (org_id: FK)
  - reconciliation_runs (org_id: FK)
```

### Isolation Guarantees:

- Every API endpoint requires an authenticated JWT token containing the caller's `org_id`.
- Database queries automatically filter on `org_id == current_user.org_id`.
- Unique constraints (such as `invoice_no` or `txn_id`) are compound keys scoped to `(org_id, entity_id)` to prevent collisions across different tenants.

---

## 3. Data Pipelines & Reconciliation Flow

```
+--------------------------+    +--------------------------+    +-------------------------+
|   Subscription System    |    |     Payment Gateway      |    |      Bank Statement     |
|   (Chargebee / Zoho)     |    |    (Razorpay / Stripe)   |    |    (HDFC / ICICI / etc) |
+------------+-------------+    +------------+-------------+    +------------+------------+
             |                               |                               |
             v                               v                               v
+--------------------------+    +--------------------------+    +-------------------------+
|  POST /uploads/invoices  |    | POST /uploads/gateway-tx |    |  POST /uploads/bank     |
+------------+-------------+    +------------+-------------+    +------------+------------+
             |                               |                               |
             +-------------------------------+-------------------------------+
                                             |
                                             v
                              +-----------------------------+
                              |   CSV Parser & Normalizer   |
                              |  - Canonical schema mapping |
                              |  - Data type sanitization   |
                              |  - Duplicate identification |
                              +--------------+--------------+
                                             |
                                             v
                              +-----------------------------+
                              |    PostgreSQL 16 Storage    |
                              +--------------+--------------+
                                             |
                                             v
                              +-----------------------------+
                              |    Reconciliation Engine    |
                              |  - Layer 1: Inv <-> Txn     |
                              |  - Layer 2: Txn <-> Batch   |
                              |  - Layer 3: Batch <-> Bank  |
                              |  - Fee & GST Verification   |
                              +--------------+--------------+
                                             |
                     +-----------------------+-----------------------+
                     v                                               v
      +-----------------------------+                 +-----------------------------+
      |      Reconciled Matched     |                 |       Exceptions Queue      |
      |   - Full audit trail        |                 |   - Short payments          |
      |   - Ind AS 115 revenue link |                 |   - Unmatched invoices      |
      |   - Zero variance           |                 |   - Fee overcharges         |
      +-----------------------------+                 +-----------------------------+
```

---

## 4. Reconciliation Matching Logic

### Layer 1: Invoices ↔ Gateway Transactions

1. **Exact Match**: Matches `invoice_no` against `txn.invoice_ref` and validates exact amount.
2. **Fuzzy Fallback**: If references differ, matches by `(customer_id, amount, date within ±2 days)`.
3. **Tolerance**: Allows micro-variance of $\le ₹1.00$ to accommodate rounding differences.

### Layer 2: Transactions ↔ Settlement Batches

1. Confirms each transaction is present in a settlement line item.
2. Computes the theoretical settlement sum:
   $$\text{Expected Net} = \text{Gross Amount} - \text{MDR Fee} - (\text{MDR Fee} \times 18\%\ \text{GST}) - \text{Refunds}$$
3. Verifies that the gateway's stated net settlement matches `Expected Net`.

### Layer 3: Settlement Batches ↔ Bank Statement Credits

1. Extracts gateway settlement reference / UTR from bank narration.
2. Matches batch net amount to bank credit amount.
3. Flags timing lags exceeding gateway standard settlement windows ($T+2$ or $T+3$ days).
