"""
WebSocket Game Server — handles real-time game communication.

Endpoint: WS /ws/games/{pin}
Both teacher and students connect here. Messages are JSON.

Supported client -> server events:
  teacher_connect           — teacher hello on connect; unlocks control events
  join {name, avatar}       — student joins lobby
  start_game                — teacher starts the game
  next_question             — teacher advances (also Bingo's "Call Next")
  pick_question {index}     — teacher jumps to a cell (Jeopardy)
  answer {answer, ...}      — student submits
  bingo                     — student shouts bingo
  show_leaderboard          — teacher requests leaderboard broadcast
  end_game                  — teacher ends

Server -> client events:
  game_state                — initial teacher snapshot (includes all_questions)
  joined {player_id, ...}   — echo to the joining student
  player_joined             — broadcast to lobby with player count
  game_started              — broadcast first question + all_questions
  new_question              — broadcast subsequent questions
  answer_result             — echo to the answering student
  player_answered           — broadcast with player_id + new_score
  bingo_claimed             — broadcast when a student shouts bingo
  leaderboard               — broadcast top N
  game_finished             — broadcast final leaderboard
  error {message}
"""
import json
import logging
from typing import Dict, Set

from fastapi import WebSocket, WebSocketDisconnect

from src.lms_agents.tools.game_session_manager import (
    join_game, answer_question, next_question, start_game, end_game,
    pick_question_by_index,
)
from src.lms_agents.tools.redis_client import get_game_state, get_leaderboard

log = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self.connections: Dict[str, Set[WebSocket]] = {}
        self.teacher_connections: Dict[str, WebSocket] = {}

    async def connect(self, pin: str, websocket: WebSocket):
        await websocket.accept()
        self.connections.setdefault(pin, set()).add(websocket)

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


manager = ConnectionManager()


def _player_summary(p: dict) -> dict:
    return {
        "player_id": p.get("player_id"),
        "name": p.get("name"),
        "avatar": p.get("avatar"),
        "score": p.get("score", 0),
    }


def _teacher_question(q: dict | None) -> dict | None:
    """Question payload for teacher view — includes answer."""
    if not q:
        return None
    return {
        "question_number": q.get("question_number"),
        "question_text": q.get("question_text"),
        "options": q.get("options"),
        "answer": q.get("answer"),
    }


async def handle_game_websocket(websocket: WebSocket, pin: str):
    state = get_game_state(pin)
    if not state:
        await websocket.accept()
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
                        "title": state.get("title", ""),
                        "game_shell_id": state.get("game_shell_id"),
                        "players": [_player_summary(p) for p in state.get("players", [])],
                        "current_question": state.get("current_question", -1),
                        "total_questions": len(state.get("questions", [])),
                        "all_questions": state.get("questions", []),
                        "settings": state.get("settings", {}),
                    },
                }))

            elif msg_type == "join":
                result = join_game(pin, msg.get("name", "Student"), msg.get("avatar", "🐻"))
                if "error" not in result:
                    player_id = result["player_id"]
                    await websocket.send_text(json.dumps({"type": "joined", **result}))
                    state = get_game_state(pin)
                    await manager.broadcast(pin, {
                        "type": "player_joined",
                        "player": {"name": result["name"], "avatar": result["avatar"], "player_id": player_id},
                        "player_count": result["player_count"],
                        "players": [_player_summary(p) for p in state.get("players", [])],
                    })
                else:
                    await websocket.send_text(json.dumps({"type": "error", "message": result["error"]}))

            elif msg_type == "start_game" and is_teacher:
                start_game(pin)
                q_state = get_game_state(pin)
                questions = q_state.get("questions", [])
                q = questions[0] if questions else None
                await manager.broadcast(pin, {
                    "type": "game_started",
                    "question": _teacher_question(q),
                    "current_question": 0,
                    "total_questions": len(questions),
                    "all_questions": questions,  # for Jeopardy board + Bingo card
                })

            elif msg_type == "answer" and player_id:
                result = answer_question(pin, player_id, msg.get("answer", ""), msg.get("time_taken", 0))
                await websocket.send_text(json.dumps({"type": "answer_result", **result}))
                await manager.broadcast(pin, {
                    "type": "player_answered",
                    "player_id": player_id,
                    "new_score": result.get("new_score", 0),
                })

            elif msg_type == "next_question" and is_teacher:
                result = next_question(pin)
                if result.get("status") == "finished":
                    await manager.broadcast(pin, {"type": "game_finished", **result})
                else:
                    q_state = get_game_state(pin)
                    q_idx = result.get("current_question", 0)
                    questions = q_state.get("questions", [])
                    q = questions[q_idx] if 0 <= q_idx < len(questions) else None
                    await manager.broadcast(pin, {
                        "type": "new_question",
                        "question": _teacher_question(q),
                        "current_question": q_idx,
                        "total_questions": result.get("total_questions"),
                    })

            elif msg_type == "pick_question" and is_teacher:
                index = msg.get("index", 0)
                result = pick_question_by_index(pin, index)
                if "error" in result:
                    await websocket.send_text(json.dumps({"type": "error", "message": result["error"]}))
                else:
                    await manager.broadcast(pin, {
                        "type": "new_question",
                        "question": result["question"],
                        "current_question": result["current_question"],
                        "total_questions": result["total_questions"],
                    })

            elif msg_type == "bingo":
                claimant = msg.get("player_id") or player_id
                # Trust client for now; teacher will verify visually. Broadcast so everyone sees it.
                state = get_game_state(pin)
                winner = next((p for p in state.get("players", []) if p.get("player_id") == claimant), None)
                await manager.broadcast(pin, {
                    "type": "bingo_claimed",
                    "player_id": claimant,
                    "player_name": winner.get("name") if winner else "Unknown",
                    "player_avatar": winner.get("avatar") if winner else "🐻",
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
    except Exception as e:
        log.error(f"[GameWS] {pin} error: {e}")
        manager.disconnect(pin, websocket)
