# QuantEdge v3 Phase 0 Quickstart

These steps run the existing full-stack preview alongside Streamlit v2.1.1. See the [research deployment plan](../DEPLOYMENT.md) for the ten-year research build.

## Docker (recommended for first integration)
Requirements: Docker Engine and docker compose.

    docker compose -f infra/compose.yml up --build

Visit http://localhost:3000 for the Next.js dashboard.
Visit http://localhost:8000/docs for FastAPI OpenAPI.
Visit http://localhost:8000/api/v1/health/dependencies to check actual
PostgreSQL and Redis handshakes. The local sample DB credentials are **not**
for a public deployment.

## Start servers without Docker
Use Python 3.12 and Node.js 22 (Next.js 16 needs Node >=20.9):

    python -m pip install -r requirements.txt -r apps/api/requirements.txt

The source package lives in the repo's `src/` directory. Run the backend
from the repository root with that directory on the Python import path.

macOS/Linux:

    PYTHONPATH=src python -m uvicorn apps.api.main:app --reload --port 8000

Windows PowerShell:

    $env:PYTHONPATH="src"
    python -m uvicorn apps.api.main:app --reload --port 8000

In another shell:

    cd apps/web
    npm install
    cp .env.example .env.local
    npm run dev

In Windows PowerShell, use `npm.cmd install`, `Copy-Item .env.example .env.local`, and `npm.cmd run dev`.

Visit http://localhost:3000 and verify the API connection banner. Local
PostgreSQL and Redis are optional for the fictional demo; dependency health
truthfully reports "not configured" without environment variables.

## Initial proof of functionality
1. Next.js page shows a fictional QEDMO ticker and 320 daily candles.
2. Lightweight Charts renders price candles, crosshair and toggleable SMA.
3. API health indicates the research API is connected. The URL is never a
   broker or a live market-data feed.
4. "Run fictional backtest" sends a validated request through Next.js to
   FastAPI, reusing the previous causally tested Python backtest.
5. Real-symbol history is disabled by default. The optional historical adapter is a local preview with at most one year of history.
6. GitHub Actions must pass both the old Python test suite and the new
   production Node build + full HTTP/Postgres/Redis integration probe.

## Preview boundaries
The default research preview uses synthetic fixtures. The separate [watchlist setup](V3_PHASE1B_AUTH_STORAGE.md) covers GitHub sign-in, persistent watchlists and Redis. These steps do not deploy the research evaluator.

For local durable research during the rebuild, keep using the existing
Streamlit entrypoint:

    streamlit run app.py
