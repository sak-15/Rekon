# Rekon Developer Handbook

## 1. Local Development Principles

- **Predictability over cleverness**: Keep code modular, strongly typed, and explicit.
- **Fail cleanly**: Always validate user inputs at API borders with Pydantic.
- **Auditability**: Every matched record and calculation step must be auditable by CAs and accountants.

---

## 2. Directory Layout & Conventions

```
backend/
  app/
    api/        # REST route definitions only. No business logic.
    core/       # App-wide settings, logging, database connections, security.
    models/     # SQLAlchemy ORM declarative models.
    schemas/    # Pydantic validation models (Request/Response).
    services/   # Pure business logic, parsers, matching logic.
```

- **Routers**: Route handlers only validate request payload and invoke services.
- **Services**: Pure functions or state-free classes. Easy to unit-test without mocks.
- **Models**: Explicit foreign keys, compound indexes on `(org_id, ...)`.

---

## 3. Running Backend Tests

```bash
cd backend
pytest tests/ -v
```

---

## 4. Code Quality & Formatting

Rekon utilizes **Ruff** for Python linting and formatting:

```bash
# Check code issues
ruff check backend/

# Auto-format code
ruff format backend/
```

For frontend:

```bash
cd frontend
npm run build # Typechecks via tsc and builds via vite
```
