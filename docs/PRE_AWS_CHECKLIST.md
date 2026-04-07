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
