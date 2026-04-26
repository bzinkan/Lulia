---
name: Release checklist
about: Pre-AWS / pre-launch release gate. One per release.
title: "Release checklist — vX.Y.Z"
labels: release-gate
assignees: ''
---

> **Gating:** every box must be checked before the release is cut. The
> mirror of this list is `docs/PRE_AWS_CHECKLIST.md` — keep them in sync
> when you add a new gate.

## 🔒 Security (Phase 28 — promote to release-blockers)
- [ ] Real auth: `Depends(require_teacher)` on every protected endpoint that returns or mutates a tenant resource.
- [ ] `DEV_AUTH_BYPASS=0` in the production ECS task definition. **Verified by an explicit unauth probe.**
- [ ] `JWT_SECRET` is a 48+ char random string set in ECS Secrets Manager (not in `.env.example`-style defaults).
- [ ] Tenant-isolation tests pass against staging: `pytest tests/test_tenant_isolation.py -v`.
- [ ] Upload hardening — MIME sniff + size cap + extension allowlist on `/images/upload` and any other multipart endpoints.
- [ ] Generated-HTML audit — `tests/test_html_security.py` green; artifact validator + retry guard active.
- [ ] No secrets in git history (`gh secret list` reviewed; `.env` family ignored).
- [ ] All SQL parameterized (no `f"...{user_input}..."` in cursor.execute).
- [ ] CORS allowlist set to the production dashboard origin only.

## 🧪 Tests
- [ ] `docker compose exec api pytest tests/ -v` — all green.
- [ ] CI `Deploy` workflow green on the release commit.
- [ ] `tests/test_critical_paths.py` exercises every required external integration in CI (Claude, Gemini, Bedrock, S3, Stripe).

## 🛠 Core features
- [ ] Assignment generation (5-agent crew) produces valid output for math/ELA/science/social K-2/3-5/6-8/9-12.
- [ ] All 22 templates render in all 4 themes.
- [ ] 5 puzzle generators produce valid grids/boards.
- [ ] Generation History prevents duplicates (SHA-256 fingerprinting).
- [ ] Weekly Planner suggests + Refines + Approves a plan.
- [ ] Accommodation versions render with the same template (dignity principle).
- [ ] Analytics aggregation + per-class insights work.
- [ ] Grading pipeline handles digital + scan submissions.

## 🧩 Interactive activities
- [ ] All 6 structured templates generate + edit + word-bank toggle work end-to-end (crossword, word_search, flashcards, timeline, number_line, fill_in_blank).
- [ ] Artifact-mode HTML validates clean and renders for at least one ad-hoc topic.
- [ ] Hotspot diagram pipeline (Gemini image + vision coords) produces correct click regions OR falls back to clickable SVG for canonical anatomy topics.
- [ ] EditActivityModal: per-template form for structured, refine chips for artifact, no editing surface for hotspot.

## 🔌 Integrations
- [ ] Google OAuth flow completes on the production callback URL.
- [ ] Push to Classroom creates a real coursework item.
- [ ] Calendar sync creates events.
- [ ] Stripe checkout (subscription + credit packs) charges in test mode.
- [ ] Stripe webhooks update `tier`, `credit_balance`, `credits_purchased` correctly. **Idempotency: same event_id processed twice yields the same DB state.**
- [ ] ElevenLabs / Polly TTS generates audio.
- [ ] Video assembly produces a playable MP4.

## ⚙ Infrastructure
- [ ] All required env vars present in the ECS task definition (cross-check `.env.example`).
- [ ] RDS Postgres 16 + pgvector + pg_trgm extensions enabled.
- [ ] Alembic migrations stamp + upgrade on boot succeed (`alembic upgrade head`).
- [ ] All 6 S3 buckets created with the right CORS / public-read settings (`uploads`, `generated`, `scans`, `templates`, `activities`, plus the video-library bucket).
- [ ] CloudFront distribution: WebSocket support enabled (kept for the dormant games backend), `/ws/*` cache disabled.
- [ ] ALB target group: `stickiness.enabled=true` (lb_cookie, ~2h) — required if/when games is reactivated.
- [ ] Redis (ElastiCache) reachable from every API task; `RATE_LIMIT_STORAGE_URI=redis://...` set so per-route caps are shared.
- [ ] Inngest signing key + event key set; dashboard reachable behind SSH tunnel only.

## 📚 Docs
- [ ] [`README.md`](../README.md) reflects current architecture (no game UI, no CrewAI, structured templates documented, auth model explained).
- [ ] [`CLAUDE.md`](../CLAUDE.md) up to date.
- [ ] [`docs/DEVELOPMENT.md`](../docs/DEVELOPMENT.md) accurate.
- [ ] [`docs/STRIPE_SETUP.md`](../docs/STRIPE_SETUP.md) accurate.
- [ ] [`CHANGELOG.md`](../CHANGELOG.md) has a Phase entry for this release.

## 🚧 Live Games (shelved — confirm posture, don't unship)
- [ ] Backend (`routers/games.py`, `websocket/game_server.py`, game tables) **deployed but unlinked from any dashboard route.** Confirmed by browsing `/dashboard` → no Arcade nav.
- [ ] No new code added that depends on the games UI being present.

## 🚦 Final gate
- [ ] On-call engineer named for the release window.
- [ ] Rollback plan documented (Last-known-good ECS task definition revision, RDS snapshot ID).
- [ ] Status page banner ready to flip if needed.
