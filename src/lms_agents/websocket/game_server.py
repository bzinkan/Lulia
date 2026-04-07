"""
WebSocket Game Server — handles real-time game communication.

Endpoint: WS /ws/games/{pin}
Both teacher and students connect here. Messages are JSON.
"""
import json
import logging
from typing import Dict, Set

from fastapi import WebSocket, WebSocketDisconnect

from src.lms_agents.tools.game_session_manager import (
    join_game, answer_question, next_question, start_game, end_game,
)
from src.lms_agents.tools.redis_client import get_game_state, get_leaderboard

log = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections per game PIN."""

    def __init__(self):
        self.connections: Dict[str, Set[WebSocket]] = {}
        self.teacher_connections: Dict[str, WebSocket] = {}

    async def connect(self, pin: str, websocket: WebSocket, is_teacher: bool = False):
        await websocket.accept()
        self.connections.setdefault(pin, set()).add(websocket)
        if is_teacher:
            self.teacher_connections[pin] = websocket

    def disconnect(self, pin: str, websocket: WebSocket):
        if pin in self.connections:
            self.connections[pin].discard(websocket)
        if self.teacher_connections.get(pin) == websocket:
            del self.teacher_connections[pin]

    async def broadcast(self, pin: str, message: dict):
        if pin in self.connections:
            data = json.dumps(message)
            dead = set()
            for ws in self.connections[pin]:
                try:
                    await ws.send_text(data)
                except Exception:
                    dead.add(ws)
            self.connections[pin] -= dead

    async def send_to_teacher(self, pin: str, message: dict):
        ws = self.teacher_connections.get(pin)
        if ws:
            try:
                await ws.send_text(json.dumps(message))
            except Exception:
                pass


manager = ConnectionManager()


async def handle_game_websocket(websocket: WebSocket, pin: str):
    """Handle a WebSocket connection for a game session."""
    state = get_game_state(pin)
    if not state:
        await websocket.close(code=4004, reason="Game not found")
        return

    is_teacher = False
    player_id = None

    await manager.connect(pin, websocket)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            msg_type = msg.get("type")

            if msg_type == "teacher_connect":
                is_teacher = True
                manager.teacher_connections[pin] = websocket
                state = get_game_state(pin)
                await websocket.send_text(json.dumps({
                    "type": "game_state",
                    "state": {
                        "pin": pin,
                        "status": state.get("status"),
                        "players": [{"name": p["name"], "avatar": p["avatar"], "score": p.get("score", 0)} for p in state.get("players", [])],
                        "current_question": state.get("current_question", -1),
                        "total_questions": len(state.get("questions", [])),
                        "title": state.get("title", ""),
                    },
                }))

            elif msg_type == "join":
                result = join_game(pin, msg.get("name", "Student"), msg.get("avatar", "🐻"))
                if "error" not in result:
                    player_id = result["player_id"]
                    await websocket.send_text(json.dumps({"type": "joined", **result}))
                    await manager.broadcast(pin, {
                        "type": "player_joined",
                        "player": {"name": result["name"], "avatar": result["avatar"]},
                        "player_count": result["player_count"],
                    })
                else:
                    await websocket.send_text(json.dumps({"type": "error", "message": result["error"]}))

            elif msg_type == "start_game" and is_teacher:
                result = start_game(pin)
                q_state = get_game_state(pin)
                q = q_state["questions"][0] if q_state.get("questions") else None
                await manager.broadcast(pin, {
                    "type": "game_started",
                    "question": {"question_text": q["question_text"], "options": q["options"], "question_number": q["question_number"]} if q else None,
                    "total_questions": len(q_state.get("questions", [])),
                })

            elif msg_type == "answer" and player_id:
                result = answer_question(pin, player_id, msg.get("answer", ""), msg.get("time_taken", 0))
                await websocket.send_text(json.dumps({"type": "answer_result", **result}))
                await manager.broadcast(pin, {"type": "player_answered", "player_id": player_id})

            elif msg_type == "next_question" and is_teacher:
                result = next_question(pin)
                if result.get("status") == "finished":
                    await manager.broadcast(pin, {"type": "game_finished", **result})
                else:
                    q = result.get("question", {})
                    await manager.broadcast(pin, {
                        "type": "new_question",
                        "question": q,
                        "current": result.get("current_question"),
                        "total": result.get("total_questions"),
                    })

            elif msg_type == "show_leaderboard" and is_teacher:
                lb = get_leaderboard(pin)
                await manager.broadcast(pin, {
                    "type": "leaderboard",
                    "leaderboard": [{"name": p["name"], "avatar": p["avatar"], "score": p.get("score", 0)} for p in lb[:10]],
                })

            elif msg_type == "end_game" and is_teacher:
                result = end_game(pin)
                await manager.broadcast(pin, {"type": "game_finished", **result})

    except WebSocketDisconnect:
        manager.disconnect(pin, websocket)
