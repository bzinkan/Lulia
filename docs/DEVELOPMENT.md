# Development Guide

## Quick Start

```bash
cd /path/to/lulia
docker compose up -d
```

Services will be available at:
- **Dashboard**: http://localhost:3001
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **MinIO Console**: http://localhost:9001 (minioadmin/minioadmin)

## Default Test Account

- Email: demo@lulia.com / test@lulia.com
- Teacher ID: 00000000-0000-0000-0000-000000000001
- Admin: admin@lulia.com / admin

## Seed Demo Data

```bash
docker compose exec api python scripts/seed_demo_data.py
```

## Run Tests

```bash
docker compose exec api pytest tests/ -v
```

## Import Standards

```bash
docker compose exec api python scripts/import_standards.py --national
docker compose exec api python scripts/import_standards.py --state OH
```

## Generate Lulings

```bash
# Requires REPLICATE_API_TOKEN in .env.development
docker compose exec api python scripts/generate_lulings.py
```

## Start Stripe Webhook Listener

```bash
./scripts/start_stripe_listener.sh
```

## Project Structure

```
src/lms_agents/
├── config/          # Agent YAML, tasks YAML, pricing
├── crews/           # Agent crews (assignment, planning, grading, analytics, video)
├── models/          # SQLAlchemy models (future)
├── routers/         # FastAPI route handlers (25+ routers)
├── templates/       # 22+ output templates with CSS themes
├── tools/           # Shared tools (RAG, embedding, TTS, Stripe, etc.)
├── websocket/       # WebSocket game server
├── worker/          # Background worker
└── main.py          # FastAPI app entry point

dashboard/
├── src/app/         # Next.js App Router pages
├── src/components/  # Shared React components
├── src/lib/         # API client, admin client
└── package.json

scripts/             # Database init, standards import, seed data, Lulings generation
docs/                # Project documentation
tests/               # Test suite
```

## Adding a New Template

1. Create `src/lms_agents/templates/{template_id}/config.json`
2. Add a render function in `src/lms_agents/tools/template_renderer.py`
3. Register in the `RENDERERS` dict
4. Add credit cost in `src/lms_agents/config/pricing.py`

## Adding a New Dashboard Page

1. Create `dashboard/src/app/{path}/page.jsx`
2. Add to sidebar in `dashboard/src/components/Sidebar.jsx`
3. Rebuild: `docker compose build dashboard`
