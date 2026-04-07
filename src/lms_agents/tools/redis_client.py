"""
Redis Client — wrapper for game session storage.

All game data has a 4-hour TTL. Redis is used for real-time state
that doesn't need durability (session state lives here during gameplay,
then final results are persisted to PostgreSQL).
"""
import json
import logging
import os

import redis

log = logging.getLogger(__name__)

_client: redis.Redis | None = None
SESSION_TTL = 4 * 60 * 60  # 4 hours


def get_redis() -> redis.Redis:
    """Get or create Redis connection."""
    global _client
    if _client is None:
        _client = redis.Redis(
            host=os.environ.get("REDIS_HOST", "redis"),
            port=int(os.environ.get("REDIS_PORT", 6379)),
            decode_responses=True,
        )
    return _client


def set_game_state(pin: str, state: dict):
    """Store game session state."""
    r = get_redis()
    r.setex(f"game:{pin}", SESSION_TTL, json.dumps(state))


def get_game_state(pin: str) -> dict | None:
    """Retrieve game session state."""
    r = get_redis()
    data = r.get(f"game:{pin}")
    return json.loads(data) if data else None


def delete_game_state(pin: str):
    """Remove game session state."""
    r = get_redis()
    r.delete(f"game:{pin}")


def add_player(pin: str, player: dict):
    """Add a player to a game session."""
    state = get_game_state(pin)
    if state:
        state.setdefault("players", []).append(player)
        set_game_state(pin, state)


def update_player_score(pin: str, player_id: str, points: int):
    """Update a player's score."""
    state = get_game_state(pin)
    if state:
        for p in state.get("players", []):
            if p.get("player_id") == player_id:
                p["score"] = p.get("score", 0) + points
                break
        set_game_state(pin, state)


def get_leaderboard(pin: str) -> list[dict]:
    """Get sorted leaderboard for a game."""
    state = get_game_state(pin)
    if not state:
        return []
    players = state.get("players", [])
    return sorted(players, key=lambda p: p.get("score", 0), reverse=True)
