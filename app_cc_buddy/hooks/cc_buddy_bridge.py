#!/usr/bin/env python3
"""
Claude Code Buddy Bridge

Desktop-side script that bridges Claude Code session state to a Picoclaw
CC Buddy device. Sends heartbeat snapshots matching the REFERENCE.md protocol
and forwards permission decisions back.

Usage:
    python cc_buddy_bridge.py --transport serial --port /dev/ttyUSB0
    python cc_buddy_bridge.py --transport websocket --host 192.168.1.100 --port 18800
    python cc_buddy_bridge.py --transport stdio  # for testing with stdin/stdout

Transport is pluggable — implement your connection method and the bridge
handles the protocol layer.

Integration with Claude Code:
    Configure hooks in .claude/settings.json to call this bridge on events.
    See README.md for setup instructions.
"""

import argparse
import asyncio
import json
import logging
import sys
import time
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Transport backends (desktop side)
# ---------------------------------------------------------------------------
class BridgeTransport(ABC):
    @abstractmethod
    async def connect(self) -> None: ...
    @abstractmethod
    async def send(self, data: str) -> None: ...
    @abstractmethod
    async def recv(self) -> str | None: ...
    @abstractmethod
    async def close(self) -> None: ...


class StdioBridgeTransport(BridgeTransport):
    async def connect(self) -> None:
        pass

    async def send(self, data: str) -> None:
        sys.stdout.write(data + "\n")
        sys.stdout.flush()

    async def recv(self) -> str | None:
        loop = asyncio.get_event_loop()
        try:
            line = await asyncio.wait_for(
                loop.run_in_executor(None, sys.stdin.readline), timeout=0.1
            )
            return line.strip() if line.strip() else None
        except asyncio.TimeoutError:
            return None

    async def close(self) -> None:
        pass


class SerialBridgeTransport(BridgeTransport):
    def __init__(self, port: str = "/dev/ttyUSB0", baudrate: int = 115200):
        self._port = port
        self._baudrate = baudrate
        self._serial = None

    async def connect(self) -> None:
        try:
            import serial
            self._serial = serial.Serial(self._port, self._baudrate, timeout=0.1)
            logger.info("Serial connected: %s @ %d", self._port, self._baudrate)
        except ImportError:
            logger.error("pyserial not installed. Run: pip install pyserial")
            raise
        except Exception as e:
            logger.error("Failed to open serial port %s: %s", self._port, e)
            raise

    async def send(self, data: str) -> None:
        if self._serial and self._serial.is_open:
            self._serial.write((data + "\n").encode())

    async def recv(self) -> str | None:
        if self._serial and self._serial.is_open and self._serial.in_waiting:
            line = self._serial.readline().decode(errors="replace").strip()
            return line if line else None
        return None

    async def close(self) -> None:
        if self._serial and self._serial.is_open:
            self._serial.close()


# ---------------------------------------------------------------------------
# Session state tracker
# ---------------------------------------------------------------------------
class SessionState:
    def __init__(self):
        self.total: int = 0
        self.running: int = 0
        self.waiting: int = 0
        self.completed: bool = False
        self.tokens: int = 0
        self.tokens_today: int = 0
        self.msg: str = ""
        self.entries: list[str] = []
        self.prompt: dict | None = None

    def to_heartbeat(self) -> str:
        hb = {
            "total": self.total,
            "running": self.running,
            "waiting": self.waiting,
            "completed": self.completed,
            "tokens": self.tokens,
            "tokens_today": self.tokens_today,
            "msg": self.msg,
            "entries": self.entries,
        }
        if self.prompt:
            hb["prompt"] = self.prompt
        return json.dumps(hb)


# ---------------------------------------------------------------------------
# Bridge main loop
# ---------------------------------------------------------------------------
async def bridge_main(transport: BridgeTransport):
    await transport.connect()
    logger.info("Bridge started")

    state = SessionState()
    last_heartbeat = 0
    heartbeat_interval = 10.0

    # Send initial time sync
    import calendar
    epoch = calendar.timegm(time.gmtime())
    tz_offset = int(time.timezone * -1 if time.daylight == 0 else time.altzone * -1)
    await transport.send(json.dumps({"time": [epoch, tz_offset]}))

    try:
        while True:
            now = time.time()

            # Send heartbeat periodically
            if now - last_heartbeat >= heartbeat_interval:
                await transport.send(state.to_heartbeat())
                last_heartbeat = now

            # Check for responses from device
            response = await transport.recv()
            if response:
                try:
                    doc = json.loads(response)
                    if doc.get("cmd") == "permission":
                        logger.info("Permission decision: id=%s decision=%s",
                                    doc.get("id"), doc.get("decision"))
                        # Forward to Claude Code session manager
                        # (implementation depends on Claude Code API)
                except json.JSONDecodeError:
                    pass

            await asyncio.sleep(0.1)

    except KeyboardInterrupt:
        logger.info("Bridge shutting down")
    finally:
        await transport.close()


# ---------------------------------------------------------------------------
# Hook entry points
# ---------------------------------------------------------------------------
def on_tool_use(tool_name: str, tool_input: str) -> None:
    """Called by Claude Code PreToolUse hook."""
    print(json.dumps({
        "event": "tool_use",
        "tool": tool_name,
        "input_preview": tool_input[:100],
        "timestamp": time.time(),
    }))


def on_notification(message: str) -> None:
    """Called by Claude Code Notification hook."""
    print(json.dumps({
        "event": "notification",
        "message": message,
        "timestamp": time.time(),
    }))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Claude Code Buddy Bridge")
    parser.add_argument("--transport", choices=["serial", "stdio"],
                        default="stdio", help="Transport backend")
    parser.add_argument("--port", default="/dev/ttyUSB0", help="Serial port")
    parser.add_argument("--baudrate", type=int, default=115200, help="Serial baudrate")
    parser.add_argument("--log-level", default="INFO", help="Log level")
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    if args.transport == "serial":
        transport = SerialBridgeTransport(args.port, args.baudrate)
    else:
        transport = StdioBridgeTransport()

    asyncio.run(bridge_main(transport))


if __name__ == "__main__":
    main()
