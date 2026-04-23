#!/usr/bin/env python3
"""
CC Buddy Daemon — bridges Claude Code CLI hooks to the Picoclaw device.

Runs on your desktop machine. Receives hook events via HTTP, maintains
aggregate session state, pushes heartbeat JSON to the device over TCP,
and returns permission decisions from the device back to Claude Code.

Usage:
    python3 cc_buddy_daemon.py --device 192.168.1.100
    python3 cc_buddy_daemon.py --device 192.168.1.100 --port 9876

Hooks are auto-injected into ~/.claude/settings.json on startup
and removed on shutdown. Use --no-inject to manage hooks manually.
"""

import argparse
import atexit
import json
import logging
import signal
import socket
import sys
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

logger = logging.getLogger("cc_buddy_daemon")

# ---------------------------------------------------------------------------
# Dynamic hook injection into ~/.claude/settings.json
# ---------------------------------------------------------------------------

_CLAUDE_SETTINGS = Path.home() / ".claude" / "settings.json"

_HOOK_EVENTS = [
    "SessionStart", "SessionEnd", "PreToolUse", "PostToolUse",
    "Stop", "PermissionRequest", "PermissionDenied", "PreCompact",
]

_PERMISSION_TIMEOUT = 30


def _hook_url(port: int) -> str:
    return f"http://127.0.0.1:{port}/hook"


def _is_ours(entry: dict, port: int) -> bool:
    url = _hook_url(port)
    return any(h.get("url") == url for h in entry.get("hooks", []))


def inject_hooks(port: int) -> bool:
    try:
        settings: dict = {}
        if _CLAUDE_SETTINGS.exists():
            settings = json.loads(_CLAUDE_SETTINGS.read_text())

        hooks = settings.setdefault("hooks", {})
        url = _hook_url(port)

        for event in _HOOK_EVENTS:
            entries = hooks.setdefault(event, [])
            entries[:] = [e for e in entries if not _is_ours(e, port)]

            hook_def: dict = {"type": "http", "url": url}
            if event == "PermissionRequest":
                hook_def["timeout"] = _PERMISSION_TIMEOUT

            entries.append({"matcher": "", "hooks": [hook_def]})

        _CLAUDE_SETTINGS.parent.mkdir(parents=True, exist_ok=True)
        _CLAUDE_SETTINGS.write_text(json.dumps(settings, indent=2) + "\n")
        logger.info("Injected hooks into %s (port %d)", _CLAUDE_SETTINGS, port)
        return True
    except Exception as e:
        logger.error("Failed to inject hooks: %s", e)
        return False


def remove_hooks(port: int) -> bool:
    try:
        if not _CLAUDE_SETTINGS.exists():
            return True

        settings = json.loads(_CLAUDE_SETTINGS.read_text())
        hooks = settings.get("hooks", {})

        for event in _HOOK_EVENTS:
            entries = hooks.get(event, [])
            entries[:] = [e for e in entries if not _is_ours(e, port)]
            if not entries:
                hooks.pop(event, None)

        if not hooks:
            settings.pop("hooks", None)

        _CLAUDE_SETTINGS.write_text(json.dumps(settings, indent=2) + "\n")
        logger.info("Removed hooks from %s (port %d)", _CLAUDE_SETTINGS, port)
        return True
    except Exception as e:
        logger.error("Failed to remove hooks: %s", e)
        return False


# ---------------------------------------------------------------------------
# Session state tracker
# ---------------------------------------------------------------------------

class SessionInfo:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.running = False
        self.waiting = False
        self.last_tool: str = ""
        self.last_event: float = time.time()
        self.prompt_tool: str = ""
        self.prompt_hint: str = ""
        self.prompt_id: str = ""
        self.entries: list[str] = []
        self.tokens: int = 0


class StateAggregator:
    def __init__(self):
        self._sessions: dict[str, SessionInfo] = {}
        self._lock = threading.Lock()
        self._pending_decisions: dict[str, threading.Event] = {}
        self._decision_results: dict[str, str] = {}
        self._tokens_today: int = 0
        self._total_tokens: int = 0

    def handle_event(self, event: dict) -> dict | None:
        hook = event.get("hook_event_name", "")
        sid = event.get("session_id", "")
        if not sid:
            return None

        with self._lock:
            if hook == "SessionStart":
                self._sessions[sid] = SessionInfo(sid)
                return None

            if hook == "SessionEnd":
                self._sessions.pop(sid, None)
                return None

            s = self._sessions.get(sid)
            if s is None:
                s = SessionInfo(sid)
                self._sessions[sid] = s

            s.last_event = time.time()

            if hook == "PreToolUse":
                s.running = True
                tool = event.get("tool_name", "")
                s.last_tool = tool
                inp = event.get("tool_input", {})
                hint = ""
                if tool == "Bash":
                    hint = inp.get("command", "")[:60]
                elif tool in ("Edit", "Write", "Read"):
                    path = inp.get("file_path", "")
                    hint = path.rsplit("/", 1)[-1] if "/" in path else path
                elif tool == "WebSearch":
                    hint = inp.get("query", "")[:60]
                ts = time.strftime("%H:%M")
                entry = f"{ts} {tool}"
                if hint:
                    entry += f": {hint[:40]}"
                s.entries = ([entry] + s.entries)[:8]
                return None

            if hook == "PostToolUse" or hook == "PostToolUseFailure":
                s.running = False
                return None

            if hook == "Stop":
                s.running = False
                s.waiting = False
                return None

            if hook == "PermissionRequest":
                s.waiting = True
                s.prompt_tool = event.get("tool_name", "")
                inp = event.get("tool_input", {})
                if s.prompt_tool == "Bash":
                    s.prompt_hint = inp.get("command", "")[:44]
                elif s.prompt_tool in ("Edit", "Write"):
                    s.prompt_hint = inp.get("file_path", "")[:44]
                else:
                    s.prompt_hint = str(inp)[:44]
                prompt_id = f"cli_{sid}_{int(time.time()*1000)}"
                s.prompt_id = prompt_id
                return {"wait_for_decision": True, "prompt_id": prompt_id}

            if hook == "PermissionDenied":
                s.waiting = False
                s.prompt_id = ""
                return None

            if hook in ("PreCompact", "PostCompact"):
                tok = event.get("token_count", 0) or event.get("token_count_after", 0)
                if tok:
                    s.tokens = tok
                return None

        return None

    def receive_device_decision(self, prompt_id: str, decision: str) -> None:
        evt = self._pending_decisions.get(prompt_id)
        if evt:
            self._decision_results[prompt_id] = decision
            evt.set()

    def wait_for_decision(self, prompt_id: str, timeout: float = 25.0) -> str | None:
        evt = threading.Event()
        self._pending_decisions[prompt_id] = evt
        try:
            if evt.wait(timeout):
                return self._decision_results.pop(prompt_id, None)
            return None
        finally:
            self._pending_decisions.pop(prompt_id, None)
            with self._lock:
                for s in self._sessions.values():
                    if s.prompt_id == prompt_id:
                        s.waiting = False
                        s.prompt_id = ""

    def build_heartbeat(self) -> dict:
        with self._lock:
            now = time.time()
            total = len(self._sessions)
            running = sum(1 for s in self._sessions.values() if s.running)
            waiting = sum(1 for s in self._sessions.values() if s.waiting)
            tokens = sum(s.tokens for s in self._sessions.values())

            completed = False
            entries = []
            prompt = None
            msg = ""

            for s in self._sessions.values():
                entries.extend(s.entries)
                if s.waiting and s.prompt_id:
                    prompt = {
                        "id": s.prompt_id,
                        "tool": s.prompt_tool,
                        "hint": s.prompt_hint,
                    }
                    msg = f"approve: {s.prompt_tool}"

            if not msg:
                if running:
                    msg = f"{running} session{'s' if running > 1 else ''} running"
                elif total:
                    msg = f"{total} session{'s' if total > 1 else ''} idle"
                else:
                    msg = "No sessions"

            # Stale session cleanup (no event for 5 min)
            stale = [sid for sid, s in self._sessions.items()
                     if now - s.last_event > 300]
            for sid in stale:
                del self._sessions[sid]

            hb = {
                "total": total,
                "running": running,
                "waiting": waiting,
                "completed": completed,
                "tokens": tokens,
                "tokens_today": tokens,
                "msg": msg,
                "entries": entries[:8],
            }
            if prompt:
                hb["prompt"] = prompt
            return hb


# ---------------------------------------------------------------------------
# Device TCP connection
# ---------------------------------------------------------------------------

class DeviceConnection:
    def __init__(self, host: str, port: int = 18800):
        self._host = host
        self._port = port
        self._sock: socket.socket | None = None
        self._lock = threading.Lock()
        self._recv_buf = ""
        self._on_decision = None

    def connect(self) -> bool:
        try:
            self._sock = socket.create_connection((self._host, self._port), timeout=5)
            self._sock.settimeout(0.1)
            logger.info("Connected to device %s:%d", self._host, self._port)
            return True
        except Exception as e:
            logger.error("Cannot connect to device: %s", e)
            self._sock = None
            return False

    def send_heartbeat(self, hb: dict) -> bool:
        if self._sock is None:
            if not self.connect():
                return False
        try:
            data = json.dumps(hb) + "\n"
            with self._lock:
                self._sock.sendall(data.encode("utf-8"))
            return True
        except (OSError, BrokenPipeError):
            logger.warning("Device connection lost, reconnecting...")
            self._sock = None
            return False

    def poll_responses(self) -> list[dict]:
        if self._sock is None:
            return []
        results = []
        try:
            data = self._sock.recv(4096)
            if not data:
                self._sock = None
                return []
            self._recv_buf += data.decode("utf-8", errors="replace")
            while "\n" in self._recv_buf:
                line, self._recv_buf = self._recv_buf.split("\n", 1)
                line = line.strip()
                if line.startswith("{"):
                    try:
                        results.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        except socket.timeout:
            pass
        except (OSError, ConnectionError):
            self._sock = None
        return results

    def close(self):
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None


# ---------------------------------------------------------------------------
# HTTP hook handler
# ---------------------------------------------------------------------------

_aggregator: StateAggregator
_device: DeviceConnection


class HookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b""
        try:
            event = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            return

        hook_name = event.get("hook_event_name", "")
        logger.debug("Hook: %s (session=%s)", hook_name, event.get("session_id", "")[:8])

        result = _aggregator.handle_event(event)

        # Push heartbeat to device on every event
        hb = _aggregator.build_heartbeat()
        _device.send_heartbeat(hb)

        if result and result.get("wait_for_decision"):
            prompt_id = result["prompt_id"]
            logger.info("Waiting for device decision on %s...", prompt_id)
            decision = _aggregator.wait_for_decision(prompt_id, timeout=25.0)

            if decision == "once":
                resp = {
                    "hookSpecificOutput": {
                        "hookEventName": "PermissionRequest",
                        "decision": {
                            "behavior": "allow",
                        },
                    },
                }
            elif decision == "deny":
                resp = {
                    "hookSpecificOutput": {
                        "hookEventName": "PermissionRequest",
                        "decision": {
                            "behavior": "deny",
                            "message": "Denied from CC Buddy device",
                        },
                    },
                }
            else:
                resp = {}

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(resp).encode())
            return

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b"{}")

    def log_message(self, format, *args):
        pass


# ---------------------------------------------------------------------------
# Background threads
# ---------------------------------------------------------------------------

def heartbeat_loop(aggregator: StateAggregator, device: DeviceConnection):
    while True:
        time.sleep(10)
        hb = aggregator.build_heartbeat()
        device.send_heartbeat(hb)


def device_poll_loop(aggregator: StateAggregator, device: DeviceConnection):
    while True:
        responses = device.poll_responses()
        for doc in responses:
            cmd = doc.get("cmd")
            if cmd == "permission":
                pid = doc.get("id", "")
                decision = doc.get("decision", "")
                logger.info("Device decision: id=%s decision=%s", pid, decision)
                aggregator.receive_device_decision(pid, decision)
        time.sleep(0.05)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    global _aggregator, _device

    parser = argparse.ArgumentParser(description="CC Buddy Daemon")
    parser.add_argument("--device", required=True, help="Picoclaw IP address")
    parser.add_argument("--device-port", type=int, default=19000, help="Device TCP port")
    parser.add_argument("--port", type=int, default=9876, help="HTTP listen port for hooks")
    parser.add_argument("--no-inject", action="store_true",
                        help="Skip automatic hook injection into ~/.claude/settings.json")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    if not args.no_inject:
        if not inject_hooks(args.port):
            sys.exit(1)
        atexit.register(remove_hooks, args.port)

    _aggregator = StateAggregator()
    _device = DeviceConnection(args.device, args.device_port)

    logger.info("Connecting to device %s:%d...", args.device, args.device_port)
    _device.connect()

    hb_thread = threading.Thread(target=heartbeat_loop, args=(_aggregator, _device), daemon=True)
    hb_thread.start()

    poll_thread = threading.Thread(target=device_poll_loop, args=(_aggregator, _device), daemon=True)
    poll_thread.start()

    server = HTTPServer(("127.0.0.1", args.port), HookHandler)
    logger.info("Hook server listening on http://127.0.0.1:%d", args.port)

    def _on_sigterm(sig, frame):
        server.shutdown()

    signal.signal(signal.SIGTERM, _on_sigterm)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        _device.close()
        if not args.no_inject:
            remove_hooks(args.port)
        logger.info("Daemon stopped")


if __name__ == "__main__":
    main()
