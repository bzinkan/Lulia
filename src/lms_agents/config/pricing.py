"""
Pricing Configuration — tiers, credits, and costs.
"""
import os

TIERS = {
    "free": {"price_cents": 0, "credits_per_month": 25, "max_classes": 1, "max_students": 30},
    "basic": {"price_cents": 1499, "credits_per_month": 75, "max_classes": 3, "max_students": 100, "stripe_price_env": "STRIPE_PRICE_BASIC"},
    "plus": {"price_cents": 2999, "credits_per_month": 200, "max_classes": 6, "max_students": 200, "stripe_price_env": "STRIPE_PRICE_PLUS"},
    "premium": {"price_cents": 4999, "credits_per_month": 400, "max_classes": 12, "max_students": 500, "stripe_price_env": "STRIPE_PRICE_PREMIUM"},
    "max": {"price_cents": 9999, "credits_per_month": -1, "max_classes": -1, "max_students": -1, "stripe_price_env": "STRIPE_PRICE_MAX"},
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

CREDIT_PACKS = [
    {"id": "credits_50", "credits": 50, "price_cents": 999, "name": "50 Credits", "stripe_price_env": "STRIPE_PRICE_CREDITS_50"},
    {"id": "credits_150", "credits": 150, "price_cents": 2499, "name": "150 Credits", "savings": "17%", "stripe_price_env": "STRIPE_PRICE_CREDITS_150"},
    {"id": "credits_500", "credits": 500, "price_cents": 6999, "name": "500 Credits", "savings": "30%", "stripe_price_env": "STRIPE_PRICE_CREDITS_500"},
    {"id": "credits_1500", "credits": 1500, "price_cents": 17999, "name": "1500 Credits", "savings": "40%", "stripe_price_env": "STRIPE_PRICE_CREDITS_1500"},
]


def get_stripe_price_id(env_key: str) -> str:
    return os.environ.get(env_key, "")


def get_credit_cost(template_id: str) -> int:
    return CREDIT_COSTS.get(template_id, 1)
