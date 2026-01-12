"""
Rich UI Server - FastAPI + WebSocket based game server
"""

import asyncio
import json
import random
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

# Import game engine from main.py
from main import GameEngine, GameConfig, Card

app = FastAPI(title="Coven - Rich UI")

# Static files and templates
BASE_DIR = Path(__file__).parent
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

# Game sessions storage
game_sessions: Dict[str, "GameSession"] = {}


class GameSession:
    """Manages a single game session with WebSocket connections."""

    def __init__(self, session_id: str, seed: Optional[int] = None, config: Optional[GameConfig] = None):
        self.session_id = session_id
        self.seed = seed if seed is not None else random.randint(0, 999999)
        self.config = config or GameConfig()
        self.engine: Optional[GameEngine] = None
        self.websocket: Optional[WebSocket] = None
        self.is_running = False

    def create_game(self) -> None:
        """Create a new game instance."""
        self.engine = GameEngine(seed=self.seed, config=self.config, all_bots=False)
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
            result["context"]["cost"] = ctx.get("cost", 1)

        elif pending.type == "upgrade":
            result["context"]["revealed"] = ctx.get("revealed", [])
            result["context"]["already_taken"] = ctx.get("already_taken", [])
            result["context"]["can_take_gold"] = ctx.get("can_take_gold", True)
            result["context"]["gold_amount"] = ctx.get("gold_amount", 2)

        elif pending.type == "fourth_place_bonus":
            result["context"]["gold_option"] = ctx.get("gold_option", 2)
            result["context"]["grace_option"] = ctx.get("grace_option", 2)

        elif pending.type == "worker_actions":
            # Get worker count from context (main.py sends as num_workers)
            num_workers = ctx.get("num_workers", ctx.get("available_workers", 0))
            result["context"]["available_workers"] = num_workers
            result["context"]["available_actions"] = ctx.get("available_actions", [])
            # Get player info for gold and recruit capability
            player = pending.player
            player_gold = player.gold if player else 0
            recruit_cost = 2  # UPGRADE_WORKER_COST
            result["context"]["gold"] = player_gold
            result["context"]["can_recruit"] = player_gold >= recruit_cost
            result["context"]["recruit_cost"] = recruit_cost

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

        elif pending.type == "fourth_place_bonus":
            # Normalize to uppercase
            if isinstance(response, str):
                response = response.upper()

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


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Serve the main game page."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/game/new")
async def new_game(seed: Optional[int] = None):
    """Create a new game session."""
    import uuid
    session_id = str(uuid.uuid4())[:8]

    session = GameSession(session_id, seed=seed)
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

    # Step until next input needed
    state = await session.step_until_input_or_end()

    return {"success": True, "state": state}


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
                    # Step until next input needed
                    state = await session.step_until_input_or_end()
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


def run_server(host: str = "127.0.0.1", port: int = 8080):
    """Run the FastAPI server."""
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()
