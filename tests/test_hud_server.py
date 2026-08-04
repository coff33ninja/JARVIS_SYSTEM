"""HUD websocket server: end-to-end broadcast with a real websocket client."""

from __future__ import annotations

import asyncio
import socket

import pytest
import websockets

from app.hud.events import ReticleEvent, SkeletonEvent, StatusEvent
from app.hud.hud_server import HUDConfig, HUDServer


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def server():
    srv = HUDServer(HUDConfig(port=_free_port()))
    assert srv.start() is True
    yield srv
    srv.stop()


def _recv(server: HUDServer, count: int = 1):
    async def run():
        uri = f"ws://{server.config.host}:{server.config.port}"
        async with websockets.connect(uri) as ws:
            server.broadcast(StatusEvent(mode="control"))
            server.broadcast(ReticleEvent(x=1, y=2))
            server.broadcast(SkeletonEvent(hands=[]))
            out = []
            for _ in range(count):
                out.append(await asyncio.wait_for(ws.recv(), timeout=5))
            return out

    return asyncio.new_event_loop().run_until_complete(run())


def test_server_broadcasts_events(server):
    msgs = _recv(server, 3)
    assert len(msgs) == 3
    kinds = [__import__("json").loads(m)["type"] for m in msgs]
    assert kinds == ["status", "reticle", "skeleton"]


def test_server_serves_index_html(server):
    async def run():
        uri = f"http://{server.config.host}:{server.config.port}/"
        import urllib.request

        with urllib.request.urlopen(uri, timeout=5) as resp:
            body = resp.read().decode()
        return body

    body = asyncio.new_event_loop().run_until_complete(run())
    assert "JARVIS HUD" in body


def test_client_count_reflects_connections(server):
    async def run():
        uri = f"ws://{server.config.host}:{server.config.port}"
        async with websockets.connect(uri) as ws:
            await asyncio.sleep(0.2)
            assert server.client_count() >= 1
        await asyncio.sleep(0.2)
        return server.client_count()

    count = asyncio.new_event_loop().run_until_complete(run())
    assert count == 0


def test_stop_is_idempotent(server):
    server.stop()
    server.stop()
