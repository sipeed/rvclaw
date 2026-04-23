from dataclasses import dataclass, field
from enum import IntEnum


class PersonaState(IntEnum):
    SLEEP = 0
    IDLE = 1
    BUSY = 2
    ATTENTION = 3
    CELEBRATE = 4
    DIZZY = 5
    HEART = 6


class DisplayMode(IntEnum):
    NORMAL = 0
    PET = 1
    INFO = 2
    COUNT = 3


@dataclass
class TamaState:
    sessions_total: int = 0
    sessions_running: int = 0
    sessions_waiting: int = 0
    recently_completed: bool = False
    tokens: int = 0
    tokens_today: int = 0
    last_updated: float = 0.0
    msg: str = ""
    connected: bool = False
    lines: list[str] = field(default_factory=list)
    line_gen: int = 0
    prompt_id: str = ""
    prompt_tool: str = ""
    prompt_hint: str = ""


def derive(s: TamaState) -> PersonaState:
    if not s.connected:
        return PersonaState.IDLE
    if s.sessions_waiting > 0:
        return PersonaState.ATTENTION
    if s.recently_completed:
        return PersonaState.CELEBRATE
    if s.sessions_running >= 3:
        return PersonaState.BUSY
    return PersonaState.IDLE


STATE_NAMES = ["sleep", "idle", "busy", "attention", "celebrate", "dizzy", "heart"]
