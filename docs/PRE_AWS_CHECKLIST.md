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
- [ ] Live games: create → join → play → score (WebSocket)
- [ ] Redis stores game state correctly

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

### Google Cloud / Vertex AI (for Veo 3 Fast short-clip generation)
- [ ] Enable **Vertex AI API** on the GCP project used for production
- [ ] Create a service account with role `Vertex AI User`
- [ ] Download the service-account JSON key, mount it on the ECS task at `/secrets/gcp-sa.json`
- [ ] Set ECS task env vars:
  - `GOOGLE_CLOUD_PROJECT` — your GCP project ID
  - `GOOGLE_CLOUD_REGION=us-central1`
  - `GOOGLE_APPLICATION_CREDENTIALS=/secrets/gcp-sa.json`
  - `VEO_MODEL_ID=veo-3.0-fast-generate-preview` (or latest Fast model ID)
- [ ] Add `google-genai` to `requirements.txt` and rebuild the Docker image
- [ ] Verify: POST `/api/v1/clips/generate` with a small test prompt produces a real clip URI
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

### End-to-end verification
- [ ] Generate a 30-sec clip from `/clips` page — charges 90 credits, monthly-first spend order in `credit_transactions_v2.metadata`
- [ ] Tier gate: Free/Basic account hitting `POST /clips/generate` returns 402 with upgrade prompt
- [ ] Monthly credit reset cron does NOT reset `credits_purchased`
- [ ] Planner refiner "Short Clip" option saves `output_template_id: 'short_clip'` on work order; approve_plan routes to Veo (not the old slides pipeline)
- [ ] On Veo failure, credits auto-refund to the `purchased` bucket
- [ ] `/videos` URL redirects to `/clips` (for bookmarks)
