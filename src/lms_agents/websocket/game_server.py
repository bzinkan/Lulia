"""
WebSocket Game Server — handles real-time game communication.

Endpoint: WS /ws/games/{pin}
Both teacher and students connect here. Messages are JSON.

MULTI-INSTANCE BROADCAST (AWS-ready):
  Every instance keeps its own local connections in memory, but broadcasts go
  through Redis pub/sub on channel `game:{pin}:events`. Each instance runs a
  background pubsub listener that receives events and forwards them to the
  sockets it holds locally. This means 10 students sharded across 3 Fargate
  tasks still all see the same `new_question` event.

Supported client -> server events:
  teacher_connect           — teacher hello; unlocks control events
  join {name, avatar}       — student joins lobby
  start_game                — teacher starts the game
  next_question             — teacher advances (also Bingo's "Call Next")
  pick_question {index}     — teacher jumps to a cell (Jeopardy)
  answer {answer, ...}      — student submits
  bingo                     — student shouts bingo
  show_leaderboard          — teacher requests leaderboard broadcast
  end_game                  — teacher ends

Server -> client events are the same as before (game_state, joined,
player_joined, game_started, new_question, current_question, answer_result,
player_answered, bingo_claimed, leaderboard, game_finished, error).
"""
import asyncio
import json
import logging
import os
from typing import Dict, Set

from fastapi import WebSocket, WebSocketDisconnect

from src.lms_agents.tools.game_session_manager import (
    join_game, answer_question, next_question, start_game, end_game,
    pick_question_by_index,
)
from src.lms_agents.tools.redis_client import get_game_state, get_leaderboard

log = logging.getLogger(__name__)


def _pubsub_channel(pin: str) -> str:
    return f"game:{pin}:events"


class ConnectionManager:
    def __init__(self):
        # Per-PIN set of sockets this instance holds
        self.connections: Dict[str, Set[WebSocket]] = {}
        self.teacher_connections: Dict[str, WebSocket] = {}
        # Per-PIN background task that listens to Redis pub/sub for this pin.
        # Kept until the last socket for that pin disconnects.
        self._listeners: Dict[str, asyncio.Task] = {}

    async def connect(self, pin: str, websocket: WebSocket):
        await websocket.accept()
        is_first = pin not in self.connections or len(self.connections[pin]) == 0
        self.connections.setdefault(pin, set()).add(websocket)
        if is_first:
            # Spin up a listener for this pin on this instance
            task = asyncio.create_task(self._subscribe(pin))
            self._listeners[pin] = task

    def disconnect(self, pin: str, websocket: WebSocket):
        if pin in self.connections:
            self.connections[pin].discard(websocket)
            if not self.connections[pin]:
                # Last local socket for this pin — stop the listener
                task = self._listeners.pop(pin, None)
                if task and not task.done():
                    task.cancel()
                del self.connections[pin]
        if self.teacher_connections.get(pin) == websocket:
            del self.teacher_connections[pin]

    async def _local_deliver(self, pin: str, message: dict):
        """Send a message to every local socket for this pin."""
        if pin not in self.connections:
            return
        data = json.dumps(message)
        dead = set()
        for ws in list(self.connections[pin]):
            try:
                await ws.send_text(data)
            except Exception:
                dead.add(ws)
        self.connections[pin] -= dead

    async def broadcast(self, pin: str, message: dict):
        """Publish to Redis so every instance (including this one) delivers."""
        try:
            # Use the sync redis client's publish; it's fast and fire-and-forget.
            from src.lms_agents.tools.redis_client import get_redis
            get_redis().publish(_pubsub_channel(pin), json.dumps(message))
        except Exception as e:
            log.warning(f"[GameWS] Redis publish failed, falling back to local: {e}")
            await self._local_deliver(pin, message)

    async def send_direct(self, websocket: WebSocket, message: dict):
        """Send to a single socket — used for per-client responses (joined, error, answer_result)."""
        try:
            await websocket.send_text(json.dumps(message))
        except Exception:
            pass

    async def _subscribe(self, pin: str):
        """Background task: listen to Redis pub/sub for this pin's events."""
        try:
            from src.lms_agents.tools.redis_client import get_redis
            pubsub = get_redis().pubsub()
            pubsub.subscribe(_pubsub_channel(pin))
            loop = asyncio.get_event_loop()
            while pin in self.connections and self.connections[pin]:
                # Blocking get_message runs in a thread so we don't block the event loop
                msg = await loop.run_in_executor(
                    None,
                    lambda: pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0),
                )
                if msg is None:
                    continue
                if msg.get("type") != "message":
                    continue
                try:
                    payload = json.loads(msg["data"])
                except (ValueError, TypeError):
                    continue
                await self._local_deliver(pin, payload)
            try:
                pubsub.unsubscribe(_pubsub_channel(pin))
                pubsub.close()
            except Exception:
                pass
        except asyncio.CancelledError:
            pass
        except Exception as e:
            log.error(f"[GameWS] pubsub listener {pin} died: {e}")


manager = ConnectionManager()


def _player_summary(p: dict) -> dict:
    return {
        "player_id": p.get("player_id"),
        "name": p.get("name"),
        "avatar": p.get("avatar"),
        "score": p.get("score", 0),
    }


def _teacher_question(q: dict | None) -> dict | None:
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
                await manager.send_direct(websocket, {
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
                })

            elif msg_type == "join":
                result = join_game(pin, msg.get("name", "Student"), msg.get("avatar", "🐻"))
                if "error" not in result:
                    player_id = result["player_id"]
                    await manager.send_direct(websocket, {"type": "joined", **result})
                    state = get_game_state(pin)
                    await manager.broadcast(pin, {
                        "type": "player_joined",
                        "player": {"name": result["name"], "avatar": result["avatar"], "player_id": player_id},
                        "player_count": result["player_count"],
                        "players": [_player_summary(p) for p in state.get("players", [])],
                    })
                    # Late-join sync
                    if state.get("status") == "playing":
                        q_idx = state.get("current_question", 0)
                        questions = state.get("questions", [])
                        q = questions[q_idx] if 0 <= q_idx < len(questions) else None
                        await manager.send_direct(websocket, {
                            "type": "current_question",
                            "question": _teacher_question(q),
                            "current_question": q_idx,
                            "total_questions": len(questions),
                            "all_questions": questions,
                        })
                else:
                    await manager.send_direct(websocket, {"type": "error", "message": result["error"]})

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
                    "all_questions": questions,
                })

            elif msg_type == "answer" and player_id:
                result = answer_question(pin, player_id, msg.get("answer", ""), msg.get("time_taken", 0))
                await manager.send_direct(websocket, {"type": "answer_result", **result})
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
                    await manager.send_direct(websocket, {"type": "error", "message": result["error"]})
                else:
                    await manager.broadcast(pin, {
                        "type": "new_question",
                        "question": result["question"],
                        "current_question": result["current_question"],
                        "total_questions": result["total_questions"],
                    })

            elif msg_type == "bingo":
                claimant = msg.get("player_id") or player_id
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
