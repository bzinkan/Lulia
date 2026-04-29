# Pre-AWS Deployment Checklist

Before deploying Lulia to AWS (ECS/Fargate, RDS, S3, CloudFront), verify all of these work locally.

## Core Features
- [ ] Assignment generation (5-agent crew) produces valid output
- [ ] All 22 templates render correctly in all 4 themes
- [ ] 5 puzzle generators produce valid grids/boards
- [ ] Generation History prevents duplicates
- [ ] Weekly Planner suggests and approves plans
- [ ] Accommodation versions generated with same template (dignity)
- [ ] Analytics aggregation and insights work
- [ ] Grading pipeline handles digital + scan submissions

## Integrations
- [ ] Google OAuth flow completes
- [ ] Push to Classroom creates coursework
- [ ] Calendar sync creates events
- [ ] Stripe checkout flow works (subscription + credits)
- [ ] Stripe webhooks update tier and credits
- [ ] ElevenLabs/Polly TTS generates audio
- [ ] Video assembly produces playable MP4

## Interactive & Games
- [ ] Interactive activities deploy to MinIO and load in browser
- [ ] Live games backend smoke test only if Arcade is re-enabled; Arcade UI is shelved for launch
- [ ] Redis game state check only if Arcade is re-enabled

## Admin
- [ ] Admin login works
- [ ] All admin pages load with data
- [ ] Feature flags control feature visibility
- [ ] Support tickets create and reply

## Quality
- [ ] All tests pass: `docker compose exec api pytest tests/ -v`
- [ ] No critical errors in logs
- [ ] Lighthouse Performance: 80+
- [ ] Lighthouse Accessibility: 90+
- [ ] Demo data seed script works

## Documentation
- [ ] README complete
- [ ] DEVELOPMENT.md accurate
- [ ] STRIPE_SETUP.md accurate
- [ ] CHANGELOG up to date

## Security
- [ ] No secrets in git history
- [ ] All secrets from env vars
- [ ] SQL parameterized (no injection)
- [ ] File upload size limits in place
- [ ] Auth on all protected endpoints

## Phase 26 — Short Clips, dual-bucket credits, pack repricing

### Database migrations (run after RDS is provisioned)
- [ ] `docker compose exec api python scripts/migrate_dual_bucket_credits.py`
      (adds `teachers.credits_purchased` column, backfills Max-tier teachers to 1500)
- [ ] `docker compose exec api python scripts/migrate_short_clips.py`
      (creates `short_clips` table for Veo-generated clips)

### Google Cloud / Vertex AI (only if short clips remain in the launch plan)
- [ ] Enable **Vertex AI API** on the GCP project used for production
- [ ] Create a service account with role `Vertex AI User`
- [ ] Download the service-account JSON key, mount it on the ECS task at `/secrets/gcp-sa.json`
- [ ] Set ECS task env vars:
  - `GOOGLE_CLOUD_PROJECT` — your GCP project ID
  - `GOOGLE_CLOUD_REGION=us-central1`
  - `GOOGLE_APPLICATION_CREDENTIALS=/secrets/gcp-sa.json`
  - `VEO_MODEL_ID=veo-3.0-fast-generate-preview` (or latest Fast model ID)
- [ ] Add `google-genai` to `requirements.txt` and rebuild the Docker image
- [ ] If short clips are enabled, verify POST `/api/v1/clips/generate` with a small test prompt produces a real clip URI
- [ ] Note: Vertex AI service account is **backend-only auth** — unrelated to the user-facing Google OAuth flow used for Classroom/Slides/Forms

### Stripe — new credit pack prices (tier-aligned)
Pack prices now mirror subscription tiers so per-credit rate is consistent.
- [ ] In Stripe Dashboard, create 4 **one-time** prices:
  - 75 credits / $14.99
  - 200 credits / $29.99
  - 400 credits / $49.99
  - 1500 credits / $99.99
- [ ] Set ECS env vars to the new price IDs:
  - `STRIPE_PRICE_CREDITS_75`
  - `STRIPE_PRICE_CREDITS_200`
  - `STRIPE_PRICE_CREDITS_400`
  - `STRIPE_PRICE_CREDITS_1500`
- [ ] Archive old Stripe pack prices (`credits_50`, `credits_150`, `credits_500`, old `credits_1500` at $179.99)
- [ ] In the Stripe webhook handler (`stripe_webhooks.py`), verify that **credit-pack purchases call `grant_credits(..., bucket="purchased")`** — purchased credits never expire; they must not land in the monthly-reset bucket
- [ ] Verify: test pack purchase in Stripe test mode → check `teachers.credits_purchased` increments, `teachers.credit_balance` untouched

### Live Games — optional multi-instance WebSocket readiness

Arcade UI is shelved for the initial launch, but the backend is intentionally
kept. Treat this section as a non-launch-gating readiness checklist unless
games are explicitly re-enabled.

- [ ] Set ECS env var `NEXT_PUBLIC_WS_URL=wss://school-pilot.net` on the
      dashboard container (or whatever the production hostname is)
- [ ] ALB target group for API has `stickiness.enabled = true`, type
      `lb_cookie`, duration ~2 hours. Without this, a student's WebSocket
      can bounce mid-game between tasks and lose state.
- [ ] CloudFront cache behavior for `/ws/*`: forward all headers, bypass
      cache (`CachePolicy: Managed-CachingDisabled`, `OriginRequestPolicy:
      Managed-AllViewer`). WebSocket upgrade headers must pass through.
- [ ] CloudFront distribution supports WebSocket: confirmed on modern
      distributions by default but verify "WebSocket support" isn't
      explicitly disabled.
- [ ] Redis: ensure `REDIS_HOST`/`REDIS_PORT` point to ElastiCache or
      Redis container reachable from all API tasks. The pub/sub channel
      is `game:{pin}:events` — no setup required, Redis creates on demand.
- [ ] Fargate task definition has **at least 2 API tasks** to actually
      exercise the multi-instance path. Single-task runs use local
      delivery via the same code path (Redis publish still works).

### End-to-end verification
- [ ] Confirm final video direction before treating clip/video generation as launch-gating; current strategy is undecided
- [ ] If short clips are enabled, generate a 30-sec clip from `/clips` page — charges 90 credits, monthly-first spend order in `credit_transactions_v2.metadata`
- [ ] If short clips are enabled, Free/Basic account hitting `POST /clips/generate` returns 402 with upgrade prompt
- [ ] Monthly credit reset cron does NOT reset `credits_purchased`
- [ ] If short clips are enabled, Planner refiner "Short Clip" option saves `output_template_id: 'short_clip'` on work order; approve_plan routes to Veo
- [ ] If short clips are enabled, on Veo failure, credits auto-refund to the `purchased` bucket
- [ ] Video Library, generated-video fallback, upload processing, and short-clip routes are all preserved until product direction is confirmed
- [ ] If Arcade is re-enabled, run Live Games multi-instance test: run 2+ Fargate tasks. Teacher on
      laptop, 2 students on separate phones/tabs with different IPs. All
      3 sockets should receive `new_question` simultaneously. If a student
      misses an event, suspect ALB stickiness or Redis pub/sub config.
- [ ] WebSocket URL: browser DevTools Network tab → WS filter → confirm
      connection URL is `wss://school-pilot.net/ws/games/...`, not a
      port-8000 variant.
