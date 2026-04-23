import asyncio
import json
import logging
import time
from abc import ABC, abstractmethod

from state import TamaState
from protocol import LineBuf, apply_json

logger = logging.getLogger(__name__)


class Transport(ABC):
    @property
    def name(self) -> str:
        return self.__class__.__name__

    @abstractmethod
    async def read_line(self) -> str | None:
        ...

    @abstractmethod
    async def write_line(self, data: str) -> None:
        ...

    @abstractmethod
    def is_connected(self) -> bool:
        ...

    @abstractmethod
    async def close(self) -> None:
        ...

    def drain(self) -> None:
        """Discard any queued data. Called when this transport loses active status."""
        pass

    async def poll(self, state: TamaState) -> str | None:
        line = await self.read_line()
        if line is None:
            return None
        return apply_json(line, state)


# ---------------------------------------------------------------------------
# TransportManager — exclusive-connection arbiter
# ---------------------------------------------------------------------------

class TransportManager:
    """Manages multiple transport backends. At most one is active at a time.

    All backends run and listen for connections simultaneously.
    The first to report is_connected() becomes active.
    While one is active, data from others is discarded.
    When the active connection drops, all backends compete again.
    """

    def __init__(self):
        self._backends: list[Transport] = []
        self._active: Transport | None = None

    def add(self, t: Transport) -> None:
        self._backends.append(t)

    @property
    def active(self) -> Transport | None:
        return self._active

    @property
    def active_name(self) -> str:
        return self._active.name if self._active else ""

    def is_connected(self) -> bool:
        return self._active is not None and self._active.is_connected()

    async def poll(self, state: TamaState) -> str | None:
        if self._active is not None:
            if self._active.is_connected():
                self._drain_others()
                return await self._drain_active(state)
            logger.info("Transport '%s' disconnected", self._active.name)
            self._active = None

        for t in self._backends:
            if t.is_connected():
                self._active = t
                logger.info("Transport '%s' connected — now active", t.name)
                self._drain_others()
                return await self._drain_active(state)

        return None

    async def _drain_active(self, state: TamaState) -> str | None:
        """Process all queued messages at once, return last response."""
        last_response = None
        while True:
            line = await self._active.read_line()
            if line is None:
                break
            r = apply_json(line, state)
            if r is not None:
                last_response = r
        return last_response

    async def write_line(self, data: str) -> None:
        if self._active is not None:
            await self._active.write_line(data)

    def _drain_others(self) -> None:
        for t in self._backends:
            if t is not self._active:
                t.drain()

    async def close(self) -> None:
        for t in self._backends:
            try:
                await t.close()
            except Exception:
                pass
        self._active = None


# ---------------------------------------------------------------------------
# StubTransport — demo mode only
# ---------------------------------------------------------------------------

class StubTransport(Transport):
    _FAKES = [
        {"name": "asleep",    "total": 0, "running": 0, "waiting": 0, "completed": False, "tokens": 0},
        {"name": "one idle",  "total": 1, "running": 0, "waiting": 0, "completed": False, "tokens": 12000},
        {"name": "busy",      "total": 4, "running": 3, "waiting": 0, "completed": False, "tokens": 89000},
        {"name": "attention", "total": 2, "running": 1, "waiting": 1, "completed": False, "tokens": 45000,
         "prompt": {"id": "demo_req_001", "tool": "Bash", "hint": "rm -rf /tmp/demo"}},
        {"name": "completed", "total": 1, "running": 0, "waiting": 0, "completed": True,  "tokens": 142000},
    ]

    def __init__(self):
        self._idx = 0
        self._next_switch = time.time()

    async def read_line(self) -> str | None:
        now = time.time()
        if now >= self._next_switch:
            self._idx = (self._idx + 1) % len(self._FAKES)
            self._next_switch = now + 8.0
            fake = self._FAKES[self._idx]
            heartbeat = {
                "total": fake["total"],
                "running": fake["running"],
                "waiting": fake["waiting"],
                "completed": fake["completed"],
                "tokens": fake["tokens"],
                "tokens_today": fake["tokens"],
                "msg": f"demo: {fake['name']}",
                "entries": [f"  demo scenario: {fake['name']}"],
            }
            if "prompt" in fake:
                heartbeat["prompt"] = fake["prompt"]
            return json.dumps(heartbeat)
        return None

    async def write_line(self, data: str) -> None:
        logger.debug("StubTransport TX: %s", data)

    def is_connected(self) -> bool:
        return True

    async def close(self) -> None:
        pass


# ---------------------------------------------------------------------------
# NetworkTransport — TCP server for CLI hook daemon
# ---------------------------------------------------------------------------

class NetworkTransport(Transport):
    def __init__(self, host: str = "0.0.0.0", port: int = 19000):
        self._host = host
        self._port = port
        self._server: asyncio.Server | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._rx_queue: asyncio.Queue[str] = asyncio.Queue()
        self._line_buf = LineBuf()
        self._connected = False

    async def start(self) -> None:
        self._server = await asyncio.start_server(
            self._on_connect, self._host, self._port,
        )
        addr = self._server.sockets[0].getsockname()
        logger.info("NetworkTransport listening on %s:%d", addr[0], addr[1])

    async def _on_connect(self, reader: asyncio.StreamReader,
                          writer: asyncio.StreamWriter) -> None:
        peer = writer.get_extra_info("peername")
        logger.info("Desktop daemon connected from %s", peer)
        if self._writer is not None:
            try:
                self._writer.close()
            except Exception:
                pass
        self._writer = writer
        self._connected = True
        try:
            while True:
                data = await reader.read(4096)
                if not data:
                    break
                text = data.decode("utf-8", errors="replace")
                for line in self._line_buf.feed(text):
                    self._rx_queue.put_nowait(line)
        except (asyncio.CancelledError, ConnectionError):
            pass
        finally:
            logger.info("Desktop daemon disconnected")
            self._connected = False
            self._writer = None

    async def read_line(self) -> str | None:
        try:
            return self._rx_queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

    async def write_line(self, data: str) -> None:
        if self._writer is None:
            return
        try:
            self._writer.write((data + "\n").encode("utf-8"))
        except (ConnectionError, OSError) as e:
            logger.warning("NetworkTransport write failed: %s", e)
            self._connected = False
            self._writer = None

    def is_connected(self) -> bool:
        return self._connected

    def drain(self) -> None:
        while not self._rx_queue.empty():
            try:
                self._rx_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

    async def close(self) -> None:
        if self._writer:
            try:
                self._writer.close()
            except Exception:
                pass
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        self._connected = False
        logger.info("NetworkTransport closed")
