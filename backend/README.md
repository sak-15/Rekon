# Rekon Backend

FastAPI service powering the multi-tenant SaaS Payment & Settlement Reconciliation Engine.

## Quickstart

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run development server
uvicorn app.main:app --reload --port 8000
```

## Endpoints

- `GET /health` - Service health status
- `GET /docs` - Interactive Swagger OpenAPI documentation
