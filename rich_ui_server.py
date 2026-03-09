"""
Rich UI Server - FastAPI + WebSocket based game server
"""

import asyncio
import json
import random
import string
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from starlette.requests import Request

# Import game engine from main.py
from main import GameEngine, GameConfig, Card, RECRUIT_COST, GRACE_PRIORITY_COST, PERSONAL_RITUAL_GRACE, PERSONAL_RITUAL_GOLD

app = FastAPI(title="Coven - Rich UI")

# Static files and templates
BASE_DIR = Path(__file__).parent
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

# Game sessions storage
game_sessions: Dict[str, "GameSession"] = {}


# --- Room / Lobby data structures ---

@dataclass
class RoomPlayer:
    slot: int           # 0-3 (P1-P4)
    token: str          # UUID for reconnection
    name: str           # Display name
    websocket: Optional[WebSocket] = None
    is_connected: bool = False


class Room:
    def __init__(self, room_code: str, host_token: str):
        self.room_code = room_code
        self.host_token = host_token
        self.players: Dict[str, RoomPlayer] = {}  # token -> RoomPlayer
        self.session: Optional["GameSession"] = None
        self.state: str = "lobby"  # "lobby" | "playing" | "finished"
        self.lock = asyncio.Lock()
        self.created_at = datetime.now()


# Global dicts
rooms: Dict[str, Room] = {}           # room_code -> Room
player_tokens: Dict[str, str] = {}    # token -> room_code


# --- Pydantic models for request bodies ---

class CreateRoomRequest(BaseModel):
    name: str

class JoinRoomRequest(BaseModel):
    name: str

class StartRoomRequest(BaseModel):
    token: str
    ai_bot: bool = False


# --- Helper functions ---

def generate_room_code() -> str:
    """Generate a 6-character uppercase alphanumeric room code."""
    while True:
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        if code not in rooms:
            return code


def get_filtered_state(session: "GameSession", viewer_slot: int) -> Dict[str, Any]:
    """Return game state filtered for a specific player (hides other players' hands)."""
    state = session.get_state()
    pending = state.get("pending_input")

    if pending is not None:
        # Determine the viewer's player name from slot
        viewer_name = f"P{viewer_slot + 1}"
        pending_player = pending.get("player_name")

        if pending_player != viewer_name:
            # Replace pending_input so this viewer doesn't see another player's hand/options
            state["pending_input"] = {
                "type": "waiting",
                "waiting_for": pending_player
            }

    return state


class GameSession:
    """Manages a single game session with WebSocket connections."""

    def __init__(self, session_id: str, seed: Optional[int] = None, config: Optional[GameConfig] = None, ai_bot: bool = False):
        self.session_id = session_id
        self.seed = seed if seed is not None else random.randint(0, 999999)
        self.config = config or GameConfig()
        self.ai_bot = ai_bot
        self.engine: Optional[GameEngine] = None
        self.websocket: Optional[WebSocket] = None
        self.is_running = False

    def create_game(self, human_slots: Optional[List[int]] = None) -> None:
        """Create a new game instance."""
        if human_slots is not None:
            self.engine = GameEngine(seed=self.seed, config=self.config, human_slots=human_slots)
        else:
            self.engine = GameEngine(seed=self.seed, config=self.config, all_bots=False)
        # Enable AI for bot players
        if self.ai_bot and self.engine:
            for p in self.engine.players:
                if p.is_bot:
                    p.ai_bot = True
        self.is_running = True

    def get_state(self) -> Dict[str, Any]:
        """Get current game state for UI."""
        if self.engine is None:
            return {"error": "Game not started"}

        state = self.engine.get_state()
        pending = self.engine.get_pending_input()

        # Convert Card objects to serializable format
        result = self._serialize_state(state)
        result["pending_input"] = self._serialize_pending_input(pending) if pending else None
        result["session_id"] = self.session_id

        return result

    def _serialize_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Convert state to JSON-serializable format."""
        result = {
            "round_no": state.get("round_no", 0),
            "rounds": state.get("rounds", 6),
            "phase": state.get("phase", ""),
            "sub_phase": state.get("sub_phase"),
            "game_over": state.get("game_over", False),
            "log": state.get("log", []),
            "players": state.get("players", []),
            "revealed_upgrades": state.get("revealed_upgrades", []),
            "trick_history": [],
            "current_trick_plays": [],
        }

        # Serialize trick history
        for trick in state.get("trick_history", []):
            serialized_trick = {
                "trick_no": trick.get("trick_no", 0),
                "winner": trick.get("winner", ""),
                "lead_suit": trick.get("lead_suit", ""),
                "plays": []
            }
            for player_name, card in trick.get("plays", []):
                serialized_trick["plays"].append({
                    "player": player_name,
                    "card": self._card_to_dict(card) if isinstance(card, Card) else str(card)
                })
            result["trick_history"].append(serialized_trick)

        # Serialize current trick plays
        for play in state.get("current_trick_plays", []):
            if isinstance(play, tuple) and len(play) == 2:
                player, card = play
                player_name = player.name if hasattr(player, 'name') else str(player)
                result["current_trick_plays"].append({
                    "player": player_name,
                    "card": self._card_to_dict(card) if isinstance(card, Card) else str(card)
                })

        # Serialize sealed cards
        result["sealed_by_player"] = {}
        for player_name, cards in state.get("sealed_by_player", {}).items():
            result["sealed_by_player"][player_name] = [
                self._card_to_dict(c) if isinstance(c, Card) else str(c) for c in cards
            ]

        return result

    def _serialize_pending_input(self, pending) -> Dict[str, Any]:
        """Convert InputRequest to JSON-serializable format."""
        if pending is None:
            return None

        result = {
            "type": pending.type,
            "player_name": pending.player.name if pending.player else None,
            "context": {}
        }

        ctx = pending.context or {}

        # Handle different input types
        if pending.type == "choose_card":
            result["context"]["hand"] = [self._card_to_dict(c) for c in ctx.get("hand", [])]
            result["context"]["legal"] = [self._card_to_dict(c) for c in ctx.get("legal", [])]
            lead = ctx.get("lead_card")
            result["context"]["lead_card"] = self._card_to_dict(lead) if lead else None
            result["context"]["plays_so_far"] = [
                {"player": p, "card": self._card_to_dict(c) if isinstance(c, Card) else str(c)}
                for p, c in ctx.get("plays_so_far", [])
            ]

        elif pending.type == "seal":
            result["context"]["hand"] = [self._card_to_dict(c) for c in ctx.get("hand", [])]

        elif pending.type == "declaration":
            result["context"]["hand"] = [self._card_to_dict(c) for c in ctx.get("hand", [])]
            result["context"]["set_index"] = ctx.get("set_index", 0)

        elif pending.type == "grace_hand_swap":
            result["context"]["hand"] = [self._card_to_dict(c) for c in ctx.get("hand", [])]
            result["context"]["grace_points"] = ctx.get("grace_points", 0)
            result["context"]["cost"] = ctx.get("cost", 3)

        elif pending.type == "upgrade":
            result["context"]["revealed"] = ctx.get("revealed", [])
            result["context"]["already_taken"] = ctx.get("already_taken", [])
            result["context"]["can_take_gold"] = ctx.get("can_take_gold", True)
            result["context"]["gold_amount"] = ctx.get("gold_amount", 2)

        elif pending.type == "upgrade_level_choice":
            result["context"]["upgrade"] = ctx.get("upgrade", "")

        elif pending.type == "fourth_place_bonus":
            result["context"]["gold_option"] = ctx.get("gold_option", 2)
            result["context"]["grace_option"] = ctx.get("grace_option", 2)

        elif pending.type == "ritual_choice":
            result["context"]["grace_amount"] = ctx.get("grace_amount", PERSONAL_RITUAL_GRACE)
            result["context"]["gold_amount"] = ctx.get("gold_amount", PERSONAL_RITUAL_GOLD)

        elif pending.type == "grace_priority":
            result["context"]["cost"] = ctx.get("cost", GRACE_PRIORITY_COST)
            result["context"]["grace"] = ctx.get("grace", 0)

        elif pending.type == "worker_actions":
            # Get worker count from context (main.py sends as num_workers)
            num_workers = ctx.get("num_workers", ctx.get("available_workers", 0))
            result["context"]["available_workers"] = num_workers
            result["context"]["available_actions"] = ctx.get("available_actions", [])
            # Get player info for gold and recruit capability
            player = pending.player
            player_gold = player.gold if player else 0
            recruit_cost = RECRUIT_COST
            result["context"]["gold"] = player_gold
            result["context"]["can_recruit"] = player_gold >= recruit_cost
            result["context"]["recruit_cost"] = recruit_cost
            result["context"]["player_name"] = player.name if player else ""

        return result

    def _card_to_dict(self, card: Card) -> Dict[str, Any]:
        """Convert Card to dictionary."""
        if card is None:
            return None
        return {
            "suit": card.suit,
            "rank": card.rank,
            "is_trump": card.is_trump(),
            "display": str(card)
        }

    def provide_input(self, response: Any) -> bool:
        """Provide input to the game engine."""
        if self.engine is None:
            return False

        pending = self.engine.get_pending_input()
        if pending is None:
            return False

        # Convert input back to appropriate type
        if pending.type == "choose_card":
            # Find the card in the context
            cards = pending.context.get("legal", pending.context.get("hand", []))

            if isinstance(response, dict):
                # Find matching card
                for card in cards:
                    if card.suit == response.get("suit") and card.rank == response.get("rank"):
                        response = card
                        break
            elif isinstance(response, str):
                # Parse string format like "S06" or "T"
                for card in cards:
                    if str(card) == response:
                        response = card
                        break

        elif pending.type == "grace_hand_swap":
            # Convert list of card dicts to single Card object (or None to skip)
            if response is None or (isinstance(response, list) and len(response) == 0):
                response = None  # Skip swap
            elif isinstance(response, list):
                cards = pending.context.get("hand", [])
                # Take first card only (main.py expects single Card or None)
                r = response[0]
                if isinstance(r, dict):
                    for card in cards:
                        if card.suit == r.get("suit") and card.rank == r.get("rank"):
                            response = card
                            break
                elif isinstance(r, str):
                    for card in cards:
                        if str(card) == r:
                            response = card
                            break

        elif pending.type == "upgrade":
            # Normalize upgrade response
            if response in ("TAKE_GOLD", "take_gold"):
                response = "GOLD"

        elif pending.type == "upgrade_level_choice":
            # True = Lv2, False = 別枠
            if isinstance(response, str):
                response = response.lower() in ("true", "lv2", "1")

        elif pending.type == "fourth_place_bonus":
            # Normalize to uppercase
            if isinstance(response, str):
                response = response.upper()

        elif pending.type == "ritual_choice":
            # Normalize to "grace" or "gold"
            if isinstance(response, str):
                response = response.lower()
            if response not in ("grace", "gold"):
                response = "grace"

        elif pending.type == "grace_priority":
            # Convert to boolean
            if isinstance(response, str):
                response = response.lower() in ("true", "yes", "y", "1")
            response = bool(response)

        elif pending.type == "seal":
            # Seal expects a list of cards
            if not isinstance(response, list):
                response = [response]
            cards = pending.context.get("hand", [])
            selected = []
            for r in response:
                if isinstance(r, dict):
                    for card in cards:
                        if card.suit == r.get("suit") and card.rank == r.get("rank"):
                            selected.append(card)
                            break
                elif isinstance(r, str):
                    for card in cards:
                        if str(card) == r:
                            selected.append(card)
                            break
                elif hasattr(r, 'suit'):
                    selected.append(r)
            response = selected

        self.engine.provide_input(response)
        return True

    async def step_until_input_or_end(self) -> Dict[str, Any]:
        """Step the game until input is needed or game ends."""
        if self.engine is None:
            return {"error": "Game not started"}

        max_steps = 10000
        steps = 0
        while steps < max_steps:
            steps += 1

            # Check if waiting for human input
            pending = self.engine.get_pending_input()
            if pending is not None:
                break

            # Check if game is over
            state = self.engine.get_state()
            if state.get("game_over", False):
                break

            # Step the game
            continues = self.engine.step()
            if not continues:
                break

            await asyncio.sleep(0.001)  # Small delay for responsiveness

        return self.get_state()

    async def step_until_input_animated(self):
        """Step game, collecting intermediate states for trick card play animations."""
        if self.engine is None:
            return {"error": "Game not started"}, []

        animation_steps = []

        # If human just played a card, record that state
        if self.engine.trick_play_just_happened:
            self.engine.trick_play_just_happened = False
            animation_steps.append(self._serialize_state(self.engine.get_state()))

        max_steps = 10000
        steps = 0
        while steps < max_steps:
            steps += 1

            pending = self.engine.get_pending_input()
            if pending is not None:
                break

            state = self.engine.get_state()
            if state.get("game_over", False):
                break

            continues = self.engine.step()
            if not continues:
                break

            # Track each card play for animation
            if self.engine.trick_play_just_happened:
                self.engine.trick_play_just_happened = False
                animation_steps.append(self._serialize_state(self.engine.get_state()))

            await asyncio.sleep(0.001)

        final_state = self.get_state()
        return final_state, animation_steps


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Serve the main game page."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/game/new")
async def new_game(seed: Optional[int] = None, ai_bot: bool = False):
    """Create a new game session."""
    session_id = str(uuid.uuid4())[:8]

    session = GameSession(session_id, seed=seed, ai_bot=ai_bot)
    session.create_game()
    game_sessions[session_id] = session

    # Step until first input needed
    state = await session.step_until_input_or_end()

    return {"session_id": session_id, "state": state}


@app.get("/api/game/{session_id}/state")
async def get_state(session_id: str):
    """Get current game state."""
    if session_id not in game_sessions:
        return {"error": "Session not found"}

    return game_sessions[session_id].get_state()


@app.post("/api/game/{session_id}/input")
async def provide_input(session_id: str, response: Dict[str, Any]):
    """Provide input to the game."""
    if session_id not in game_sessions:
        return {"error": "Session not found"}

    session = game_sessions[session_id]
    input_value = response.get("value")

    if not session.provide_input(input_value):
        return {"error": "Failed to provide input"}

    # Step until next input needed, collecting animation steps
    state, animation_steps = await session.step_until_input_animated()

    return {"success": True, "state": state, "animation_steps": animation_steps}


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time updates."""
    await websocket.accept()

    if session_id not in game_sessions:
        await websocket.send_json({"error": "Session not found"})
        await websocket.close()
        return

    session = game_sessions[session_id]
    session.websocket = websocket

    try:
        # Send initial state
        state = session.get_state()
        await websocket.send_json({"type": "state_update", "data": state})

        while True:
            # Wait for input from client
            data = await websocket.receive_json()

            if data.get("type") == "input":
                input_value = data.get("data")
                if session.provide_input(input_value):
                    # Step with animation: send intermediate states for each card play
                    state, animation_steps = await session.step_until_input_animated()
                    # Send each animation step with a delay
                    for step_state in animation_steps:
                        step_state["pending_input"] = None  # Intermediate states have no input
                        await websocket.send_json({"type": "trick_animation", "data": step_state})
                        await asyncio.sleep(0.8)
                    # Send final state
                    await websocket.send_json({"type": "state_update", "data": state})
                else:
                    await websocket.send_json({"type": "error", "message": "Failed to provide input"})

            elif data.get("type") == "get_state":
                state = session.get_state()
                await websocket.send_json({"type": "state_update", "data": state})

    except WebSocketDisconnect:
        session.websocket = None
    except Exception as e:
        await websocket.send_json({"type": "error", "message": str(e)})
        session.websocket = None


# --- Room / Lobby REST endpoints ---

@app.post("/api/room/create")
async def create_room(req: CreateRoomRequest):
    """Create a new room and return room code + host token."""
    room_code = generate_room_code()
    token = str(uuid.uuid4())

    room = Room(room_code=room_code, host_token=token)
    host_player = RoomPlayer(slot=0, token=token, name=req.name)
    room.players[token] = host_player

    rooms[room_code] = room
    player_tokens[token] = room_code

    return {"room_code": room_code, "token": token, "slot": 0}


@app.post("/api/room/{code}/join")
async def join_room(code: str, req: JoinRoomRequest):
    """Join an existing room."""
    code = code.upper()
    if code not in rooms:
        return {"error": "Room not found"}

    room = rooms[code]
    if room.state != "lobby":
        return {"error": "Game already started"}

    # Find next available slot
    occupied_slots = {p.slot for p in room.players.values()}
    next_slot = None
    for s in range(1, 4):
        if s not in occupied_slots:
            next_slot = s
            break

    if next_slot is None:
        return {"error": "Room is full"}

    token = str(uuid.uuid4())
    new_player = RoomPlayer(slot=next_slot, token=token, name=req.name)
    room.players[token] = new_player
    player_tokens[token] = code

    # Broadcast player_joined to all connected websockets in room
    # Mark the new player as connected in the list (WS connection follows immediately)
    player_list = [{"slot": p.slot, "name": p.name, "is_connected": True if p.token == token else p.is_connected}
                   for p in sorted(room.players.values(), key=lambda p: p.slot)]

    for p in room.players.values():
        if p.websocket and p.is_connected and p.token != token:
            try:
                await p.websocket.send_json({
                    "type": "player_joined",
                    "player": {"slot": next_slot, "name": req.name},
                    "players": player_list
                })
            except Exception:
                pass

    return {
        "token": token,
        "slot": next_slot,
        "players": player_list
    }


@app.get("/api/room/{code}/state")
async def get_room_state(code: str, token: str = Query(...)):
    """Get current lobby state."""
    code = code.upper()
    if code not in rooms:
        return {"error": "Room not found"}

    room = rooms[code]
    if token not in room.players:
        return {"error": "Invalid token"}

    player_list = [{"slot": p.slot, "name": p.name, "is_connected": p.is_connected}
                   for p in sorted(room.players.values(), key=lambda p: p.slot)]

    return {
        "room_code": code,
        "state": room.state,
        "players": player_list,
        "is_host": (token == room.host_token)
    }


@app.post("/api/room/{code}/start")
async def start_room_game(code: str, req: StartRoomRequest):
    """Start the game (host only). Empty slots become bots."""
    code = code.upper()
    if code not in rooms:
        return {"error": "Room not found"}

    room = rooms[code]
    if req.token != room.host_token:
        return {"error": "Only the host can start the game"}

    if room.state != "lobby":
        return {"error": "Game already started"}

    # Collect human slots from occupied player slots
    human_slots = sorted([p.slot for p in room.players.values()])

    # Create game session
    session_id = f"room_{code}"
    session = GameSession(session_id, ai_bot=req.ai_bot)
    session.create_game(human_slots=human_slots)
    game_sessions[session_id] = session
    room.session = session
    room.state = "playing"

    # Step until first input
    await session.step_until_input_or_end()

    # Broadcast game_starting, then send filtered state to each player
    for p in room.players.values():
        if p.websocket and p.is_connected:
            try:
                await p.websocket.send_json({"type": "game_starting"})
                filtered = get_filtered_state(session, p.slot)
                await p.websocket.send_json({"type": "state_update", "data": filtered})
            except Exception:
                pass

    return {"success": True}


# --- Room WebSocket endpoint ---

@app.websocket("/ws/room/{room_code}")
async def room_websocket_endpoint(websocket: WebSocket, room_code: str, token: str = Query(...)):
    """WebSocket endpoint for room-based multiplayer."""
    room_code = room_code.upper()
    await websocket.accept()

    # Validate room and token
    if room_code not in rooms:
        await websocket.send_json({"error": "Room not found"})
        await websocket.close()
        return

    room = rooms[room_code]
    if token not in room.players:
        await websocket.send_json({"error": "Invalid token"})
        await websocket.close()
        return

    player = room.players[token]
    player.websocket = websocket
    player.is_connected = True

    # Send initial state based on room state
    if room.state == "lobby":
        player_list = [{"slot": p.slot, "name": p.name, "is_connected": p.is_connected}
                       for p in sorted(room.players.values(), key=lambda p: p.slot)]
        await websocket.send_json({
            "type": "lobby_state",
            "room_code": room_code,
            "players": player_list,
            "is_host": (token == room.host_token)
        })
    elif room.state == "playing" and room.session:
        # Reconnection during game - send filtered state
        filtered = get_filtered_state(room.session, player.slot)
        await websocket.send_json({"type": "state_update", "data": filtered})

    # Broadcast reconnection to others
    for p in room.players.values():
        if p.token != token and p.websocket and p.is_connected:
            try:
                await p.websocket.send_json({
                    "type": "player_reconnected",
                    "player": {"slot": player.slot, "name": player.name}
                })
            except Exception:
                pass

    try:
        while True:
            data = await websocket.receive_json()

            if data.get("type") == "input" and room.state == "playing" and room.session:
                session = room.session
                pending = session.engine.get_pending_input() if session.engine else None

                # Verify it's this player's turn
                if pending is None:
                    await websocket.send_json({"type": "error", "message": "No input pending"})
                    continue

                viewer_name = f"P{player.slot + 1}"
                pending_player = pending.player.name if pending.player else None
                if pending_player != viewer_name:
                    await websocket.send_json({"type": "error", "message": "Not your turn"})
                    continue

                async with room.lock:
                    input_value = data.get("data")
                    if session.provide_input(input_value):
                        state, animation_steps = await session.step_until_input_animated()

                        # Send animation steps to ALL players
                        for step_state in animation_steps:
                            step_state["pending_input"] = None
                            for p in room.players.values():
                                if p.websocket and p.is_connected:
                                    try:
                                        await p.websocket.send_json({"type": "trick_animation", "data": step_state})
                                    except Exception:
                                        pass
                            await asyncio.sleep(0.8)

                        # Check if game is over
                        if state.get("game_over", False):
                            room.state = "finished"

                        # Send filtered final state to each player individually
                        for p in room.players.values():
                            if p.websocket and p.is_connected:
                                try:
                                    filtered = get_filtered_state(session, p.slot)
                                    await p.websocket.send_json({"type": "state_update", "data": filtered})
                                except Exception:
                                    pass
                    else:
                        await websocket.send_json({"type": "error", "message": "Failed to provide input"})

            elif data.get("type") == "get_state":
                if room.state == "playing" and room.session:
                    filtered = get_filtered_state(room.session, player.slot)
                    await websocket.send_json({"type": "state_update", "data": filtered})
                else:
                    player_list = [{"slot": p.slot, "name": p.name, "is_connected": p.is_connected}
                                   for p in sorted(room.players.values(), key=lambda p: p.slot)]
                    await websocket.send_json({
                        "type": "lobby_state",
                        "room_code": room_code,
                        "players": player_list,
                        "is_host": (token == room.host_token)
                    })

    except WebSocketDisconnect:
        player.websocket = None
        player.is_connected = False
        # Broadcast disconnection to others
        for p in room.players.values():
            if p.token != token and p.websocket and p.is_connected:
                try:
                    await p.websocket.send_json({
                        "type": "player_disconnected",
                        "player": {"slot": player.slot, "name": player.name}
                    })
                except Exception:
                    pass
    except Exception:
        player.websocket = None
        player.is_connected = False


# --- Room cleanup background task ---

async def cleanup_old_rooms():
    """Periodically delete rooms older than 2 hours."""
    while True:
        await asyncio.sleep(600)  # Check every 10 minutes
        now = datetime.now()
        to_delete = []
        for code, room in rooms.items():
            age = (now - room.created_at).total_seconds()
            if age > 7200:  # 2 hours
                to_delete.append(code)
        for code in to_delete:
            room = rooms.pop(code, None)
            if room:
                # Clean up player_tokens
                for token in list(room.players.keys()):
                    player_tokens.pop(token, None)
                # Clean up game session
                if room.session and room.session.session_id in game_sessions:
                    game_sessions.pop(room.session.session_id, None)


@app.on_event("startup")
async def startup_event():
    """Start background tasks."""
    asyncio.create_task(cleanup_old_rooms())


def run_server(host: str = "127.0.0.1", port: int = 8080):
    """Run the FastAPI server."""
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()
