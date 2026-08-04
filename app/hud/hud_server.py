"""HUD overlay: websocket event feed + minimal browser frontend.

Phase 1 ships the *data path* (events.py) and a small WebSocket server that
broadcasts skeleton/reticle/status to any connected overlay page. The
transparent multi-monitor Chromium window is a Phase 2 polish item; this
server + ``hud/index.html`` already render a working skeleton + reticle in a
normal browser window so the pipeline is visible end-to-end.

The server owns its own asyncio event loop in a background thread (the
``websockets.serve`` API is async), so the rest of the app stays synchronous.
HTTP GETs to ``/`` are answered with the bundled overlay page via
``process_request``; WebSocket upgrades are registered as event clients.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import webbrowser
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

INDEX_HTML = Path(__file__).resolve().parent.parent.parent / "hud" / "index.html"


@dataclass
class HUDConfig:
    host: str = "127.0.0.1"
    port: int = 8765
    enabled: bool = True


class HUDServer:
    """Run a websocket overlay server in a background thread."""

    def __init__(self, config: HUDConfig | None = None):
        self.config = config or HUDConfig()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._error: Exception | None = None
        self._clients: set = set()
        self._lock = threading.Lock()
        self._stopped = False

    # ------------------------------------------------------------------ #
    # lifecycle
    # ------------------------------------------------------------------ #

    def start(self, open_browser: bool = False) -> bool:
        """Start the server thread. True if it bound successfully."""
        self._ready.clear()
        self._error = None
        self._thread = threading.Thread(target=self._serve_thread, daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout=5.0):
            logger.warning("HUD server did not become ready in time")
            return False
        if self._error is not None:
            logger.warning("HUD server failed to start: %s", self._error)
            return False
        if open_browser:
            webbrowser.open(f"http://{self.config.host}:{self.config.port}")
        logger.info("HUD server on ws://%s:%s (http overlay at same port)",
                    self.config.host, self.config.port)
        return True

    def _serve_thread(self) -> None:  # pragma: no cover - threaded
        import websockets

        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            async def _start():
                return await websockets.serve(
                    self._handler,
                    self.config.host,
                    self.config.port,
                    process_request=self._process_request,
                )

            self._server = self._loop.run_until_complete(_start())
        except Exception as exc:
            self._error = exc
            self._ready.set()
            self._loop.close()
            return
        self._ready.set()
        try:
            self._loop.run_forever()
        finally:
            self._loop.close()

    def stop(self) -> None:
        if self._stopped:
            return
        self._stopped = True
        if self._loop is not None and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        self._thread = None

    # ------------------------------------------------------------------ #
    # handler + broadcast
    # ------------------------------------------------------------------ #

    def _process_request(self, connection, request):
        """Serve the overlay HTML for plain GETs; None defers to websocket."""
        path = getattr(request, "path", "")
        is_upgrade = request.headers.get("Upgrade", "").lower() == "websocket"
        if path in ("/", "/index.html") and not is_upgrade:
            from websockets.asyncio.server import Response
            from websockets.datastructures import Headers

            body = _read_index_html().encode("utf-8")
            return Response(200, "OK",
                            Headers({"Content-Type": "text/html; charset=utf-8"}),
                            body)
        if not is_upgrade:  # plain GET to any other path (e.g. favicon)
            from websockets.asyncio.server import Response
            from websockets.datastructures import Headers

            return Response(404, "Not Found", Headers({}), b"")
        return None

    async def _handler(self, websocket) -> None:  # pragma: no cover - threaded
        with self._lock:
            self._clients.add(websocket)
        try:
            async for _ in websocket:
                pass  # we only push; client keeps the socket open
        finally:
            with self._lock:
                self._clients.discard(websocket)

    def broadcast(self, event) -> None:
        """Push a HUD event (dataclass) to every connected client."""
        if self._loop is None or not self._clients:
            return
        payload = json.dumps(event.to_dict())
        clients = list(self._clients)
        loop = self._loop

        async def _send(ws, msg: str) -> None:
            try:
                await ws.send(msg)
            except Exception:  # pragma: no cover - client dropped
                with self._lock:
                    self._clients.discard(ws)

        for ws in clients:
            loop.call_soon_threadsafe(
                asyncio.ensure_future, _send(ws, payload))

    def client_count(self) -> int:
        with self._lock:
            return len(self._clients)


def _read_index_html() -> str:
    """Serve the bundled overlay page (graceful if it is missing)."""
    if INDEX_HTML.exists():
        return INDEX_HTML.read_text(encoding="utf-8")
    return (
        "<!doctype html><meta charset=utf-8><title>JARVIS HUD</title>"
        "<body><h1>JARVIS HUD</h1><p>overlay page missing: "
        f"{INDEX_HTML}</p></body>"
    )
