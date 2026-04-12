"""
Pricing Configuration — tiers, credits, and costs.
"""
import os

TIERS = {
    "free": {"price_cents": 0, "credits_per_month": 25, "max_classes": 1, "max_students": 30},
    "basic": {"price_cents": 1499, "credits_per_month": 75, "max_classes": 3, "max_students": 100, "stripe_price_env": "STRIPE_PRICE_BASIC"},
    "plus": {"price_cents": 2999, "credits_per_month": 200, "max_classes": 6, "max_students": 200, "stripe_price_env": "STRIPE_PRICE_PLUS"},
    "premium": {"price_cents": 4999, "credits_per_month": 400, "max_classes": 12, "max_students": 500, "stripe_price_env": "STRIPE_PRICE_PREMIUM"},
    "max": {"price_cents": 9999, "credits_per_month": 1500, "max_classes": -1, "max_students": -1, "stripe_price_env": "STRIPE_PRICE_MAX"},
}

CREDIT_COSTS = {
    "worksheet": 1, "task_cards": 1, "exit_ticket": 1, "quiz_test": 2, "flashcards": 1,
    "bingo": 1, "morning_work": 1, "study_guide": 2, "reading_comprehension": 2, "graphic_organizer": 1,
    "vocab_cards": 1, "anchor_chart": 1, "homework_packet": 3, "sub_plans": 2, "parent_newsletter": 1,
    "lab_activity": 2, "lab_report": 1,
    "word_search": 1, "crossword": 2, "board_game": 3, "scavenger_hunt": 3, "escape_room": 5,
    "lesson_plan": 3, "video_short": 5, "video_long": 10, "video_voice_clone": 15,
    "interactive_activity": 3, "live_game": 4, "accommodation_version": 1, "ai_fill_template": 2,
}

# Short Clips (Veo 3 Fast): 3 credits per second of generated clip.
# Used by routers/clips.py — charged at generation time against the
# dual-bucket credit wallet (monthly first, then purchased).
CLIP_CREDITS_PER_SECOND = 3

# Short Clip previews (Imagen 3): 4 still thumbnails from the same prompt
# so teachers can pick the visual style before committing to Veo.
CLIP_PREVIEW_IMAGES = 4          # images per preview set
CLIP_FREE_PREVIEWS_PER_MONTH = 6  # ≈ $1/mo Imagen cost per teacher
CLIP_PREVIEW_CREDITS = 1          # after the free allowance, teacher pays 1 credit per set (break-even)

# Credit packs (one-time purchase, never expire, roll over until used).
# Prices mirror subscription tiers so per-credit rate is consistent
# whether a teacher subscribes higher or tops up via packs.
CREDIT_PACKS = [
    {"id": "credits_75",   "credits": 75,   "price_cents": 1499, "name": "75 Credits",   "stripe_price_env": "STRIPE_PRICE_CREDITS_75"},
    {"id": "credits_200",  "credits": 200,  "price_cents": 2999, "name": "200 Credits",  "stripe_price_env": "STRIPE_PRICE_CREDITS_200"},
    {"id": "credits_400",  "credits": 400,  "price_cents": 4999, "name": "400 Credits",  "stripe_price_env": "STRIPE_PRICE_CREDITS_400"},
    {"id": "credits_1500", "credits": 1500, "price_cents": 9999, "name": "1500 Credits", "stripe_price_env": "STRIPE_PRICE_CREDITS_1500"},
]


def get_stripe_price_id(env_key: str) -> str:
    return os.environ.get(env_key, "")


def get_credit_cost(template_id: str) -> int:
    return CREDIT_COSTS.get(template_id, 1)
