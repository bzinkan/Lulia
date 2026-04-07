# Stripe Setup for Lulia

## Products & Prices (Test Mode)

### Subscription Tiers (Monthly Recurring)

| Tier | Product ID | Price ID | Amount |
|------|-----------|----------|--------|
| Basic | prod_UI9vnBYq6i9UfT | price_1TJZbxABwJX7AGejnHaCjDbr | $14.99/mo |
| Plus | prod_UI9vxyEuE0dFP9 | price_1TJZc9ABwJX7AGejVq4RqGMC | $29.99/mo |
| Premium | prod_UI9vZpKZcdrrRT | price_1TJZcAABwJX7AGejBGgqz1fB | $49.99/mo |
| Max | prod_UI9vX1QggE8jEF | price_1TJZcBABwJX7AGej2XLEnGuC | $99.99/mo |

### Credit Packs (One-Time Purchase)

| Pack | Product ID | Price ID | Amount |
|------|-----------|----------|--------|
| 50 Credits | prod_UI9wRaCI7Q94l9 | price_1TJZcQABwJX7AGejZMIDbwBd | $9.99 |
| 150 Credits | prod_UI9wIdcp8s1JEe | price_1TJZcRABwJX7AGejGgUjRRMP | $24.99 |
| 500 Credits | prod_UI9wl7f9RL5C8R | price_1TJZcSABwJX7AGejo2fZHODd | $69.99 |
| 1500 Credits | prod_UI9walxecw8tLY | price_1TJZcTABwJX7AGejelygwUnJ | $179.99 |

## Development Setup

### 1. Environment Variables

All Stripe env vars are in `.env.development`:
- `STRIPE_API_KEY` — test secret key (sk_test_...)
- `STRIPE_PUBLISHABLE_KEY` — test publishable key (pk_test_...)
- `STRIPE_WEBHOOK_SECRET` — webhook signing secret (whsec_...)
- `STRIPE_PRICE_*` — price IDs for each product

### 2. Webhook Listener

Start the Stripe webhook listener for local development:

```bash
# Option 1: Run the helper script
./scripts/start_stripe_listener.sh

# Option 2: Run directly
stripe listen --forward-to http://localhost:8000/api/v1/webhooks/stripe
```

The listener:
- Forwards Stripe events to your local API
- Generates a temporary webhook secret (valid while running)
- Must be running during development for webhooks to work
- The webhook secret in .env.development matches the listener

### 3. Test Cards

| Card Number | Scenario |
|-------------|----------|
| 4242 4242 4242 4242 | Successful payment |
| 4000 0000 0000 3220 | 3D Secure required |
| 4000 0000 0000 9995 | Declined |
| 4000 0000 0000 0341 | Attach fails |

Expiry: any future date. CVC: any 3 digits. ZIP: any 5 digits.

### 4. Testing Webhooks

```bash
# Trigger a test event
stripe trigger payment_intent.succeeded

# Trigger a subscription event
stripe trigger customer.subscription.created
```

## Switching to Live Mode

1. Get live API keys from Stripe Dashboard
2. Create the same products/prices in live mode (or copy from test)
3. Update `.env.production` with live keys
4. Set up a permanent webhook endpoint in Stripe Dashboard pointing to your production URL
5. Use the live webhook signing secret
