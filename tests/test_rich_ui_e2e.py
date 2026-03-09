#!/usr/bin/env python
"""
Rich UI E2E Test Script
=======================

This script tests the Rich UI server via HTTP API endpoints,
simulating browser-based gameplay for 100 games.

Usage:
    # First, start the server:
    uv run python run_rich_ui.py --no-browser --port 8080

    # Then run this test:
    uv run python test_rich_ui_e2e.py --count 100
"""

import argparse
import json
import sys
import time
import traceback
from typing import Any, Dict, List, Optional
import urllib.request
import urllib.error


class E2EGameTester:
    """E2E tester that communicates with Rich UI server via HTTP."""

    def __init__(self, base_url: str = "http://127.0.0.1:8080", verbose: bool = False):
        self.base_url = base_url
        self.verbose = verbose
        self.session_id: Optional[str] = None

    def log(self, msg: str):
        if self.verbose:
            print(f"  {msg}")

    def _request(self, method: str, path: str, data: Optional[Dict] = None) -> Dict:
        """Make HTTP request to server."""
        url = f"{self.base_url}{path}"
        headers = {"Content-Type": "application/json"}

        if data is not None:
            body = json.dumps(data).encode("utf-8")
        else:
            body = None

        req = urllib.request.Request(url, data=body, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as e:
            raise Exception(f"Request failed: {e}")
        except json.JSONDecodeError as e:
            raise Exception(f"Invalid JSON response: {e}")

    def start_game(self, seed: Optional[int] = None) -> bool:
        """Start a new game."""
        try:
            path = "/api/game/new"
            if seed is not None:
                path += f"?seed={seed}"

            result = self._request("POST", path)

            if "error" in result:
                self.log(f"Start game error: {result['error']}")
                return False

            self.session_id = result.get("session_id")
            self.log(f"Started game session: {self.session_id}")
            return True

        except Exception as e:
            self.log(f"Failed to start game: {e}")
            return False

    def get_state(self) -> Optional[Dict]:
        """Get current game state."""
        if not self.session_id:
            return None

        try:
            result = self._request("GET", f"/api/game/{self.session_id}/state")
            return result
        except Exception as e:
            self.log(f"Failed to get state: {e}")
            return None

    def send_input(self, value: Any) -> Optional[Dict]:
        """Send input to server."""
        if not self.session_id:
            return None

        try:
            result = self._request("POST", f"/api/game/{self.session_id}/input", {"value": value})
            return result
        except Exception as e:
            self.log(f"Failed to send input: {e}")
            return None

    def auto_respond(self, pending: Dict) -> Any:
        """Generate automatic response based on pending input type."""
        input_type = pending.get("type")
        context = pending.get("context", {})

        if input_type == "declaration":
            return 2  # Declare 2 tricks

        elif input_type == "seal":
            hand = context.get("hand", [])
            if hand:
                return hand[0]  # Seal first card
            return None

        elif input_type == "choose_card":
            legal = context.get("legal", context.get("hand", []))
            if legal:
                return legal[0]  # Play first legal card
            return None

        elif input_type == "grace_hand_swap":
            return None  # Skip swap

        elif input_type == "upgrade":
            revealed = context.get("revealed", [])
            taken = context.get("already_taken", [])
            available = [u for u in revealed if u not in taken]
            if available:
                return available[0]
            return "GOLD"

        elif input_type == "fourth_place_bonus":
            return "GOLD"

        elif input_type == "worker_actions":
            workers = context.get("available_workers", 0)
            return ["TRADE"] * workers

        return None

    def play_game(self, seed: int) -> Dict[str, Any]:
        """Play a complete game automatically."""
        if not self.start_game(seed=seed):
            return {"success": False, "error": "Failed to start game"}

        step_count = 0
        max_steps = 1000

        while step_count < max_steps:
            step_count += 1

            state = self.get_state()
            if state is None:
                return {"success": False, "error": "Failed to get state"}

            if state.get("game_over", False):
                self.log(f"Game completed in {step_count} steps")
                return {
                    "success": True,
                    "steps": step_count,
                    "players": state.get("players", [])
                }

            pending = state.get("pending_input")
            if pending:
                response = self.auto_respond(pending)
                result = self.send_input(response)
                if result is None:
                    return {"success": False, "error": "Failed to send input"}

                if "error" in result:
                    return {"success": False, "error": result["error"]}

            time.sleep(0.01)  # Small delay

        return {"success": False, "error": "Max steps exceeded"}


def run_e2e_tests(base_url: str, count: int, verbose: bool) -> Dict[str, Any]:
    """Run E2E tests."""
    print(f"Running {count} E2E game tests against {base_url}...")

    results = {
        "total": count,
        "passed": 0,
        "failed": 0,
        "errors": []
    }

    for i in range(count):
        seed = i + 1
        tester = E2EGameTester(base_url=base_url, verbose=verbose)

        try:
            result = tester.play_game(seed=seed)

            if result.get("success"):
                results["passed"] += 1
                if verbose:
                    print(f"  Game {i+1}/{count}: PASS (steps: {result.get('steps', '?')})")
            else:
                results["failed"] += 1
                error = result.get("error", "Unknown error")
                results["errors"].append(f"Game {i+1} (seed={seed}): {error}")
                print(f"  Game {i+1}/{count}: FAIL - {error}")

        except Exception as e:
            results["failed"] += 1
            results["errors"].append(f"Game {i+1} (seed={seed}): {e}")
            print(f"  Game {i+1}/{count}: ERROR - {e}")
            if verbose:
                traceback.print_exc()

        # Progress every 10 games
        if (i + 1) % 10 == 0 and not verbose:
            print(f"  Progress: {i+1}/{count} ({results['passed']} passed, {results['failed']} failed)")

    return results


def check_server(base_url: str) -> bool:
    """Check if server is running."""
    try:
        req = urllib.request.Request(f"{base_url}/", method="GET")
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.status == 200
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(description="Rich UI E2E Tests")
    parser.add_argument("--url", default="http://127.0.0.1:8080", help="Server URL")
    parser.add_argument("--count", type=int, default=100, help="Number of games")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()

    print("=" * 50)
    print("Rich UI E2E Tests")
    print("=" * 50)

    # Check server
    print(f"\nChecking server at {args.url}...")
    if not check_server(args.url):
        print("ERROR: Server is not running!")
        print("Please start the server first:")
        print("  uv run python run_rich_ui.py --no-browser --port 8080")
        sys.exit(1)
    print("Server is running.")

    # Run tests
    print()
    results = run_e2e_tests(args.url, args.count, args.verbose)

    # Print results
    print("\n" + "=" * 50)
    print("E2E Test Results")
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

    print("\n" + "=" * 50)
    if results['failed'] == 0:
        print("ALL E2E TESTS PASSED")
        sys.exit(0)
    else:
        print("SOME E2E TESTS FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
