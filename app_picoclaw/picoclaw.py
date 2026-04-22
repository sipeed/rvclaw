import asyncio
import json
import logging
import os
import re
import socket
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import websockets

logger = logging.getLogger(__name__)

GATEWAY_HOST = "127.0.0.1"
GATEWAY_PORT = 18790
SECURITY_YML_PATH = Path(os.environ.get("PICOCLAW_SECURITY_YML", "/root/.picoclaw/.security.yml"))
PID_FILE_PATH = Path(os.environ.get("PICOCLAW_PID_FILE", "/root/.picoclaw/.picoclaw.pid"))


def _load_pid_token() -> str:
    try:
        if not PID_FILE_PATH.exists():
            return ""
        data = json.loads(PID_FILE_PATH.read_text(encoding="utf-8"))
        return str(data.get("token", "")).strip()
    except Exception:
        return ""


def _load_pico_token_from_yml() -> str:
    env_token = os.environ.get("PICO_TOKEN", "").strip()
    if env_token:
        return env_token

    try:
        if not SECURITY_YML_PATH.exists():
            return ""

        lines = SECURITY_YML_PATH.read_text(encoding="utf-8").splitlines()
        in_channels = False
        in_pico = False

        for raw in lines:
            line = raw.rstrip()
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            indent = len(line) - len(line.lstrip(" "))

            if not in_channels:
                if indent == 0 and stripped == "channels:":
                    in_channels = True
                continue

            if in_channels and indent == 0 and stripped != "channels:":
                break

            if not in_pico:
                if indent == 2 and stripped == "pico:":
                    in_pico = True
                continue

            if in_pico and indent <= 2:
                in_pico = False
                continue

            if in_pico and indent >= 4 and stripped.startswith("token:"):
                token = stripped.split(":", 1)[1].strip().strip('"').strip("'")
                return token
    except Exception:
        pass

    return ""


def _load_pico_token() -> str:
    pid_token = _load_pid_token()
    pico_token = _load_pico_token_from_yml()
    if not pid_token and not pico_token:
        return ""
    return f"pico-{pid_token}{pico_token}"


@dataclass
class ToolCall:
    name: str
    args: str


@dataclass
class PicoResponse:
    tool_calls: list[ToolCall] = field(default_factory=list)
    text: str = ""


# Parse tool call format: 🔧 `tool_name`\n```\nargs\n```
_TOOL_RE = re.compile(r'^🔧\s*`([^`]+)`\s*\n```\n(.*?)\n```\s*$', re.DOTALL)


def _parse_message(content: str) -> ToolCall | None:
    m = _TOOL_RE.match(content.strip())
    if m:
        return ToolCall(name=m.group(1), args=m.group(2).strip())
    return None


# ─────────────────────────────────────────────────────────────────────────────


class PicoclawAgent:
    def __init__(
        self,
        host: str = GATEWAY_HOST,
        port: int = GATEWAY_PORT,
        token: str | None = None,
        timeout: float = 120.0,
    ):
        self.ws_base   = f"ws://{host}:{port}/pico/ws"
        self._token    = token
        self.timeout   = timeout
        self._ws       = None
        self._session_id = None
        self._lock     = asyncio.Lock()

    @property
    def token(self) -> str:
        if self._token is not None:
            return self._token
        return _load_pico_token()

    async def _ensure_connected(self):
        if self._ws is not None and not self._ws.closed:
            return
        self._session_id = str(uuid.uuid4())
        url     = f"{self.ws_base}?session_id={self._session_id}"
        headers = {"Authorization": f"Bearer {self.token}"}
        self._ws = await websockets.connect(url, extra_headers=headers)
        logger.info("Connected session=%s", self._session_id)

    async def close(self):
        if self._ws and not self._ws.closed:
            await self._ws.close()
        self._ws = None

    async def _do_ask(self, question: str, on_tool_call=None) -> PicoResponse:
        ws         = self._ws
        session_id = self._session_id
        response   = PicoResponse()

        logger.debug("Send: %s", question)

        await ws.send(json.dumps({
            "type":       "message.send",
            "id":         str(uuid.uuid4()),
            "session_id": session_id,
            "timestamp":  int(time.time() * 1000),
            "payload":    {"content": question},
        }, ensure_ascii=False))

        async def _recv_loop():
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                except Exception:
                    continue

                ev_type = msg.get("type", "")
                payload = msg.get("payload") or {}

                if ev_type == "message.create":
                    content = payload.get("content", "")
                    tool_call = _parse_message(content)
                    if tool_call:
                        response.tool_calls.append(tool_call)
                        logger.debug("Tool: %s(%s)", tool_call.name, tool_call.args)
                        if on_tool_call:
                            await on_tool_call(tool_call)
                    else:
                        response.text = content.strip()
                        logger.info("Response: %s%s", response.text[:80],
                                     '...' if len(response.text) > 80 else '')
                        break

                elif ev_type == "error":
                    logger.error("Error: %s – %s", payload.get('code'),
                                 payload.get('message'))
                    break

        await asyncio.wait_for(_recv_loop(), timeout=self.timeout)
        return response

    async def ask(
        self,
        question: str,
        on_tool_call=None,  # async callable(ToolCall)
    ) -> PicoResponse:
        async with self._lock:
            for attempt in range(2):
                try:
                    await self._ensure_connected()
                    return await self._do_ask(question, on_tool_call)
                except asyncio.TimeoutError:
                    logger.warning("Timeout (%ss)", self.timeout)
                    return PicoResponse()
                except (
                    websockets.exceptions.ConnectionClosed,
                    websockets.exceptions.ConnectionClosedError,
                    OSError,
                ) as e:
                    logger.warning("Connection closed (%s): %s",
                                   'reconnecting' if attempt == 0 else 'give up', e)
                    self._ws = None
                    if attempt > 0:
                        return PicoResponse()
                except Exception as e:
                    logger.error("Exception: %s", e)
                    self._ws = None
                    return PicoResponse()
        return PicoResponse()


def gateway_running(host: str = GATEWAY_HOST, port: int = GATEWAY_PORT) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


def get_picoclaw_model() -> str:
    try:
        env = dict(os.environ)
        env["HOME"] = "/root"
        result = subprocess.run(
            ["picoclaw", "status"],
            capture_output=True, text=True, timeout=5,
            env=env, cwd="/root",
        )
        for line in result.stdout.splitlines():
            if line.startswith("Model:"):
                return line.split(":", 1)[1].strip()
    except Exception:
        pass
    return ""


if __name__ == "__main__":
    from config import setup_logging
    setup_logging()

    async def _test():
        agent = PicoclawAgent()

        async def _on_tool(tc: ToolCall):
            logger.info("Tool: %s args=%s", tc.name, tc.args)

        for q in ["Hello, introduce yourself.", "What's the weather in Shenzhen today?"]:
            resp = await agent.ask(q, on_tool_call=_on_tool)
            logger.info("=" * 60)
            if resp.tool_calls:
                logger.info("Tool calls: %s", ", ".join(tc.name for tc in resp.tool_calls))
            logger.info("Answer:\n%s", resp.text)
            logger.info("=" * 60)
            await asyncio.sleep(1)
        await agent.close()

    asyncio.run(_test())
