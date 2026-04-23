import json
import logging
import time

from state import TamaState

logger = logging.getLogger(__name__)


class LineBuf:
    def __init__(self, max_len: int = 1024):
        self._buf: list[str] = []
        self._max = max_len

    def feed(self, data: str) -> list[str]:
        lines = []
        for ch in data:
            if ch in ("\n", "\r"):
                if self._buf:
                    line = "".join(self._buf)
                    self._buf.clear()
                    if line.startswith("{"):
                        lines.append(line)
            elif len(self._buf) < self._max:
                self._buf.append(ch)
        return lines


def apply_json(line: str, state: TamaState) -> str | None:
    try:
        doc = json.loads(line)
    except json.JSONDecodeError:
        return None

    if "cmd" in doc:
        return _handle_command(doc, state)

    state.sessions_total = doc.get("total", state.sessions_total)
    state.sessions_running = doc.get("running", state.sessions_running)
    state.sessions_waiting = doc.get("waiting", state.sessions_waiting)
    state.recently_completed = doc.get("completed", False)

    if "tokens" in doc:
        state.tokens = doc["tokens"]
    state.tokens_today = doc.get("tokens_today", state.tokens_today)

    msg = doc.get("msg")
    if msg is not None:
        state.msg = msg[:24]

    entries = doc.get("entries")
    if entries is not None:
        old_lines = list(state.lines)
        state.lines = [str(e)[:91] for e in entries[:8]]
        if state.lines != old_lines:
            state.line_gen += 1

    prompt = doc.get("prompt")
    if prompt is not None:
        state.prompt_id = str(prompt.get("id", ""))[:80]
        state.prompt_tool = str(prompt.get("tool", ""))[:20]
        state.prompt_hint = str(prompt.get("hint", ""))[:44]
    else:
        state.prompt_id = ""
        state.prompt_tool = ""
        state.prompt_hint = ""

    state.last_updated = time.time()
    state.connected = True
    return None


def _handle_command(doc: dict, state: TamaState) -> str | None:
    cmd = doc.get("cmd", "")

    if cmd == "name":
        name = _safe_str(doc.get("name", ""))
        return json.dumps({"ack": "name", "ok": True})

    if cmd == "owner":
        name = _safe_str(doc.get("name", ""))
        return json.dumps({"ack": "owner", "ok": True}), name

    if cmd == "unpair":
        return json.dumps({"ack": "unpair", "ok": True})

    if cmd == "status":
        return None

    return None


def make_permission_response(prompt_id: str, decision: str) -> str:
    return json.dumps({
        "cmd": "permission",
        "id": prompt_id,
        "decision": decision,
    })


def make_status_response(stats_data: dict) -> str:
    return json.dumps({
        "ack": "status",
        "ok": True,
        "data": stats_data,
    })


def _safe_str(s: str, max_len: int = 32) -> str:
    return "".join(c for c in s[:max_len] if c not in ('"', "\\") and ord(c) >= 0x20)
