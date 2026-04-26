# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

TaxLens — "Global Accommodation Tax Intelligence Platform". Monorepo:
- `app/` — FastAPI backend (Python 3.12)
- `ui/` — React 19 + TypeScript + Vite + Tailwind 4 frontend
- `alembic/` — database migrations
- `scripts/` — data seeds and startup helpers
- `tests/` — pytest suite

Production deployment details (Railway URLs, CI/CD flow, local-vs-prod divergences, Railway CLI commands, admin credentials) are stored in the memory system at `memory/production_deployment.md`, `memory/cicd_pipeline.md`, `memory/local_vs_production.md`, `memory/database_access.md`, and `memory/railway_access.md`. Consult those when the user asks about the live app rather than re-auditing the repo.

## Local development

Recommended: `docker-compose up` — brings up PostGIS on host port **5433**, API on **8001**, UI on **3001**. Runs migrations and data seeds (`seed_data`, `seed_countries`, `seed_enhancement`) automatically.

Backend alone:
```bash
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload
```
Requires a Postgres with the extensions from `scripts/init_extensions.sql` (`ltree`, `postgis`, `btree_gist`, `pg_trgm`). Reads `.env` via pydantic-settings.

Frontend alone:
```bash
cd ui && npm ci && npm run dev
```
Vite dev server proxies `/v1` and `/health` to `http://localhost:8001` (see `ui/vite.config.ts`).

## Tests, lint, types

```bash
pytest tests/ -m "not live and not integration"            # unit tests (no DB)
pytest tests/ -m integration                               # DB-backed
pytest tests/test_tax_rate_service.py                      # single file
pytest tests/test_tax_rate_service.py::test_name           # single test
pytest tests/ -m "not live" --cov=app --cov-report=term    # with coverage
ruff check app/ tests/          # lint (ruff check --fix to autofix)
mypy app/                       # type check
cd ui && npm run lint           # frontend ESLint
cd ui && npm run build          # tsc -b && vite build
```

Pytest markers (declared in `pyproject.toml`): `live` (external API calls, including `test_ai_agent_live.py`) and `integration` (needs running Postgres). Both are excluded from default unit runs.

**Ruff quirks to respect:** line length is 100, and `pyproject.toml` has `per-file-ignores` for `E501` on several services, scripts, and schemas. Don't reflow long lines in those files unless the user asks — they're intentionally exempted.

**Mypy quirks to respect:** `pyproject.toml` disables several error codes globally (`name-defined`, `no-any-return`, `arg-type`, `return-value`, `assignment`, `attr-defined`, `index`, `operator`, `var-annotated`, `import-untyped`). Don't tighten these without explicit direction — existing code relies on the looseness.

## Database

PostGIS PostgreSQL 16. Required extensions are installed by `scripts/init_extensions.sql` in docker-compose; Railway's Postgres plugin has them enabled.

Two DB URL env vars, both handled in `app/config.py`:
- `DATABASE_URL` — async (`postgresql+asyncpg://...`), used by SQLAlchemy async engine
- `DATABASE_URL_SYNC` — sync (`postgresql://...`), used by Alembic and psycopg2-based scripts

Config auto-normalizes Railway's `postgres://` prefix and auto-derives `DATABASE_URL_SYNC` from `DATABASE_URL` when the sync var is at its default — in practice you usually only set `DATABASE_URL`.

```bash
alembic upgrade head                                   # apply migrations
alembic revision --autogenerate -m "message"           # new migration (requires running DB)
alembic downgrade -1                                   # roll back one
python -m scripts.seed_data                            # core tax rate seed
python -m scripts.seed_countries                       # country jurisdictions
python -m scripts.seed_admin_user                      # idempotent admin (admin@taxlens.io)
```

## Architecture

### Backend (`app/`)

Entry point `app/main.py`: FastAPI app with a lifespan that starts/stops `scheduler.py` (APScheduler). The scheduler **degrades gracefully** — if it fails to start, the API still serves; don't rewrite it to crash on scheduler errors.

Routers registered in `main.py`: `auth`, `api_keys`, `jurisdictions`, `tax_rates`, `tax_rules`, `tax_calculation`, `monitoring`, `audit`. Business logic belongs in `app/services/`, not in routers.

Key service boundaries to keep in mind:
- **`app/core/rule_engine.py`** — standalone tax rule evaluator. Pure domain logic, no I/O. `tax_calculation_service.py` delegates here.
- **`app/services/scheduler.py`** — APScheduler setup; drives `monitoring_service.py` + `monitoring_job_service.py` on a cron-ish interval.
- **`ai_agent_service.py` / `discovery_agent_service.py`** — Anthropic Claude integration. Prompt templates in `app/services/prompts/`. Model/token/turn limits are configurable via `ANTHROPIC_*` env vars. Empty `ANTHROPIC_API_KEY` disables monitoring/discovery features but the rest of the API still works.
- **`change_detection_service.py`** — diffs new scrape results against historical tax rates to produce `detected_change` records.
- **`auth_service.py` + `api_key_service.py`** — dual auth scheme: JWT (python-jose + bcrypt via passlib) for user sessions, `X-API-Key` header for programmatic access. Both gate the same routes.
- **`web_scraper.py`** — shared scraper used by monitoring/discovery.
- **`geocode_service.py`** — OpenCage primary, Nominatim fallback (no API key required).

**Middleware** (`app/middleware.py`): CORS, rate limiting, auth. Rate limiting is **only enabled when `ENVIRONMENT=production`** — don't add test assertions that rate limiting is active in dev/test.

**Config validation** (`app/config.py` `_validate_production`): when `ENVIRONMENT=production`, startup raises `ValueError` if `API_KEY`, `JWT_SECRET` are still at their defaults, or `CORS_ORIGINS == "*"`. This is intentional — preserves the safety check if you refactor config.

**DB session** (`app/db/session.py`): async SQLAlchemy engine, pool_size 20, max_overflow 10, pre-ping on, recycle 1800s.

**Models** (`app/models/`): SQLAlchemy 2.0 ORM with shared `base.py`. Core entities: jurisdiction, property_classification, tax_category, tax_rate, tax_rule, monitored_source, monitoring_job, monitoring_schedule, detected_change, audit_log, api_key, user.

### Frontend (`ui/`)

React 19 + TypeScript + Vite 7 + Tailwind 4 + react-router-dom 7. The API base URL is read from `import.meta.env.VITE_API_URL` (set in `ui/.env.production` for prod builds, proxied to `localhost:8001` in dev).

Admin-only tabs (Changes, Monitoring, Discovery) are hidden from regular users — see commit `58cd2c5`. If you're tweaking navigation, check whether new items should be admin-gated the same way.

`ui/README.md` is the default Vite template and is not project-specific — ignore it.
