#!/usr/bin/env python
"""
Rich UI Test Script
===================

This script tests the Rich UI server and GameEngine integration.

Usage:
    uv run python test_rich_ui.py [--count N] [--verbose]
"""

import asyncio
import json
import sys
import traceback
from typing import Dict, Any, List, Optional

# Add project root to path
sys.path.insert(0, '.')

from main import GameEngine, GameConfig, Card


class GameTester:
    """Test harness for GameEngine with Rich UI integration."""

    def __init__(self, seed: int = 42, verbose: bool = False):
        self.seed = seed
        self.verbose = verbose
        self.errors: List[str] = []

    def log(self, msg: str):
        if self.verbose:
            print(msg)

    def run_game(self) -> Dict[str, Any]:
        """Run a single game and return results."""
        try:
            engine = GameEngine(seed=self.seed, all_bots=True)

            step_count = 0
            max_steps = 10000  # Safety limit

            while step_count < max_steps:
                step_count += 1

                # Get state for validation
                state = engine.get_state()

                # Validate state is serializable
                try:
                    json.dumps(state, default=str)
                except Exception as e:
                    self.errors.append(f"State serialization error at step {step_count}: {e}")
                    return {"success": False, "error": str(e)}

                # Check for game over
                if state.get("game_over", False):
                    self.log(f"Game over at step {step_count}")
                    break

                # Step the game
                needs_input = engine.step()

                if needs_input:
                    # Bot games shouldn't need input
                    pending = engine.get_pending_input()
                    if pending:
                        self.errors.append(f"Unexpected input request in bot game: {pending.type}")
                        return {"success": False, "error": f"Unexpected input: {pending.type}"}

            # Validate final state
            final_state = engine.get_state()

            # Check players have valid VP values
            for player in final_state.get("players", []):
                vp = player.get("vp", 0)
                if vp < 0:
                    self.errors.append(f"Player {player.get('name')} has negative VP: {vp}")

            # Check game completed properly
            if not final_state.get("game_over"):
                self.errors.append("Game did not complete properly")
                return {"success": False, "error": "Game incomplete"}

            return {
                "success": True,
                "steps": step_count,
                "players": final_state.get("players", []),
                "round": final_state.get("round_no", 0) + 1
            }

        except Exception as e:
            error_msg = f"Exception in game: {e}\n{traceback.format_exc()}"
            self.errors.append(error_msg)
            return {"success": False, "error": str(e)}


def run_tests(count: int = 100, verbose: bool = False) -> Dict[str, Any]:
    """Run multiple game tests."""
    print(f"Running {count} game tests...")

    results = {
        "total": count,
        "passed": 0,
        "failed": 0,
        "errors": []
    }

    for i in range(count):
        seed = i + 1
        tester = GameTester(seed=seed, verbose=verbose)
        result = tester.run_game()

        if result.get("success"):
            results["passed"] += 1
            if verbose:
                print(f"  Game {i+1}/{count}: PASS (steps: {result.get('steps', '?')})")
        else:
            results["failed"] += 1
            error = result.get("error", "Unknown error")
            results["errors"].append(f"Game {i+1} (seed={seed}): {error}")
            print(f"  Game {i+1}/{count}: FAIL - {error}")

        # Show progress every 10 games
        if (i + 1) % 10 == 0 and not verbose:
            print(f"  Progress: {i+1}/{count} ({results['passed']} passed, {results['failed']} failed)")

    return results


def test_serialization():
    """Test that all game states can be serialized."""
    print("\nTesting state serialization...")

    engine = GameEngine(seed=42, all_bots=True)
    serialization_errors = []

    step = 0
    while step < 1000:
        step += 1
        state = engine.get_state()

        try:
            # Test JSON serialization
            json_str = json.dumps(state, default=str)
            # Test round-trip
            parsed = json.loads(json_str)
        except Exception as e:
            serialization_errors.append(f"Step {step}, phase {state.get('phase')}: {e}")

        if state.get("game_over"):
            break

        engine.step()

    if serialization_errors:
        print(f"  FAIL: {len(serialization_errors)} serialization errors")
        for err in serialization_errors[:5]:
            print(f"    - {err}")
        return False
    else:
        print(f"  PASS: All {step} states serialized successfully")
        return True


def test_pending_input_serialization():
    """Test that pending input requests can be serialized."""
    print("\nTesting pending input serialization...")

    # Test with human player to get pending inputs
    engine = GameEngine(seed=42, all_bots=False)
    input_types_tested = set()
    errors = []

    step = 0
    while step < 1000:
        step += 1
        state = engine.get_state()

        if state.get("game_over"):
            break

        needs_input = engine.step()

        if needs_input:
            pending = engine.get_pending_input()
            if pending:
                input_types_tested.add(pending.type)

                # Test context serialization
                try:
                    context = pending.context or {}
                    json.dumps(context, default=str)
                except Exception as e:
                    errors.append(f"Input type {pending.type}: {e}")

                # Auto-respond to continue game
                auto_respond(engine, pending)

    if errors:
        print(f"  FAIL: {len(errors)} errors")
        for err in errors:
            print(f"    - {err}")
        return False
    else:
        print(f"  PASS: Tested input types: {', '.join(sorted(input_types_tested))}")
        return True


def auto_respond(engine: GameEngine, pending):
    """Automatically respond to input requests for testing."""
    ctx = pending.context or {}

    if pending.type == "declaration":
        engine.provide_input(2)  # Declare 2 tricks

    elif pending.type == "seal":
        hand = ctx.get("hand", [])
        if hand:
            engine.provide_input([hand[0]])  # Seal first card

    elif pending.type == "choose_card":
        legal = ctx.get("legal", ctx.get("hand", []))
        if legal:
            engine.provide_input(legal[0])  # Play first legal card

    elif pending.type == "grace_hand_swap":
        engine.provide_input(None)  # Skip swap (None means skip)

    elif pending.type == "upgrade":
        revealed = ctx.get("revealed", [])
        taken = ctx.get("already_taken", [])
        available = [u for u in revealed if u not in taken]
        if available:
            engine.provide_input(available[0])
        else:
            engine.provide_input("GOLD")  # Take gold instead of upgrade

    elif pending.type == "fourth_place_bonus":
        engine.provide_input("GOLD")

    elif pending.type == "worker_actions":
        workers = ctx.get("available_workers", 0)
        actions = ["TRADE"] * workers
        engine.provide_input(actions)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Test Rich UI integration")
    parser.add_argument("--count", type=int, default=100, help="Number of games to test")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()

    print("=" * 50)
    print("Rich UI Integration Tests")
    print("=" * 50)

    all_passed = True

    # Test 1: Serialization
    if not test_serialization():
        all_passed = False

    # Test 2: Pending input serialization
    if not test_pending_input_serialization():
        all_passed = False

    # Test 3: Run multiple games
    print(f"\nRunning {args.count} game tests...")
    results = run_tests(count=args.count, verbose=args.verbose)

    print("\n" + "=" * 50)
    print("Test Results")
    print("=" * 50)
    print(f"Total: {results['total']}")
    print(f"Passed: {results['passed']}")
    print(f"Failed: {results['failed']}")

    if results['errors']:
        print("\nErrors:")
        for err in results['errors'][:10]:
            print(f"  - {err}")
        if len(results['errors']) > 10:
            print(f"  ... and {len(results['errors']) - 10} more")

    if results['failed'] > 0:
        all_passed = False

    print("\n" + "=" * 50)
    if all_passed:
        print("ALL TESTS PASSED")
        sys.exit(0)
    else:
        print("SOME TESTS FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
