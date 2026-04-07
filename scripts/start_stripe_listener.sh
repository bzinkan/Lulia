#!/bin/bash
# Start Stripe webhook listener for local development
# The webhook secret it outputs must match STRIPE_WEBHOOK_SECRET in .env.development

echo "Starting Stripe webhook listener..."
echo "Forwarding events to http://localhost:8000/api/v1/webhooks/stripe"
echo ""

stripe listen --forward-to http://localhost:8000/api/v1/webhooks/stripe
