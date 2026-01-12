#!/usr/bin/env python
"""
Run Rich UI Server
==================

This script starts the FastAPI-based Rich UI server for Coven.

Usage:
    uv run python run_rich_ui.py [--host HOST] [--port PORT]

Options:
    --host HOST  Host to bind to (default: 127.0.0.1)
    --port PORT  Port to bind to (default: 8080)
"""

import argparse
import webbrowser
import threading
import time


def open_browser(url: str, delay: float = 1.0):
    """Open browser after a short delay."""
    time.sleep(delay)
    webbrowser.open(url)


def main():
    parser = argparse.ArgumentParser(description='Run Coven Rich UI Server')
    parser.add_argument('--host', default='127.0.0.1', help='Host to bind to')
    parser.add_argument('--port', type=int, default=8080, help='Port to bind to')
    parser.add_argument('--no-browser', action='store_true', help='Do not open browser automatically')
    args = parser.parse_args()

    print(f"""
    ============================================
              Coven - Rich UI
    ============================================
      Starting server...
      URL: http://{args.host}:{args.port}

      Press Ctrl+C to stop
    ============================================
    """)

    # Open browser automatically
    if not args.no_browser:
        url = f'http://{args.host}:{args.port}'
        browser_thread = threading.Thread(target=open_browser, args=(url,), daemon=True)
        browser_thread.start()

    # Import and run server
    from rich_ui_server import run_server
    run_server(host=args.host, port=args.port)


if __name__ == '__main__':
    main()
