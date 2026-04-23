import json
import logging
import os
import time
from dataclasses import dataclass, field

from config import DATA_DIR, STATS_PATH, SETTINGS_PATH

logger = logging.getLogger(__name__)

TOKENS_PER_LEVEL = 50_000


@dataclass
class Stats:
    nap_seconds: int = 0
    approvals: int = 0
    denials: int = 0
    velocity: list[int] = field(default_factory=lambda: [0] * 8)
    vel_idx: int = 0
    vel_count: int = 0
    level: int = 0
    tokens: int = 0
    pet_name: str = "Buddy"
    owner_name: str = ""
    species_idx: int = 0


@dataclass
class Settings:
    sound: bool = True
    led: bool = True
    hud: bool = True
    clock_rot: int = 0
    brightness: int = 4
    sleep: bool = True


class StatsManager:
    def __init__(self):
        self.stats = Stats()
        self.settings = Settings()
        self._last_bridge_tokens: int = 0
        self._tokens_synced: bool = False
        self._level_up_pending: bool = False
        self._last_nap_end: float = time.time()
        self._energy_at_nap: int = 3
        self._dirty: bool = False

    def load(self) -> None:
        os.makedirs(DATA_DIR, exist_ok=True)
        self._load_stats()
        self._load_settings()

    def _load_stats(self) -> None:
        try:
            with open(STATS_PATH, "r") as f:
                d = json.load(f)
            self.stats.nap_seconds = d.get("nap_seconds", 0)
            self.stats.approvals = d.get("approvals", 0)
            self.stats.denials = d.get("denials", 0)
            vel = d.get("velocity", [0] * 8)
            self.stats.velocity = (vel + [0] * 8)[:8]
            self.stats.vel_idx = d.get("vel_idx", 0) % 8
            self.stats.vel_count = min(d.get("vel_count", 0), 8)
            self.stats.level = d.get("level", 0)
            self.stats.tokens = d.get("tokens", 0)
            self.stats.pet_name = d.get("pet_name", "Buddy")
            self.stats.owner_name = d.get("owner_name", "")
            self.stats.species_idx = d.get("species_idx", 0)
            if self.stats.tokens == 0 and self.stats.level > 0:
                self.stats.tokens = self.stats.level * TOKENS_PER_LEVEL
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            pass

    def _load_settings(self) -> None:
        try:
            with open(SETTINGS_PATH, "r") as f:
                d = json.load(f)
            self.settings.sound = d.get("sound", True)
            self.settings.led = d.get("led", True)
            self.settings.hud = d.get("hud", True)
            self.settings.clock_rot = d.get("clock_rot", 0)
            self.settings.brightness = d.get("brightness", 4)
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            pass

    def save_stats(self) -> None:
        if not self._dirty:
            return
        os.makedirs(DATA_DIR, exist_ok=True)
        d = {
            "nap_seconds": self.stats.nap_seconds,
            "approvals": self.stats.approvals,
            "denials": self.stats.denials,
            "velocity": self.stats.velocity,
            "vel_idx": self.stats.vel_idx,
            "vel_count": self.stats.vel_count,
            "level": self.stats.level,
            "tokens": self.stats.tokens,
            "pet_name": self.stats.pet_name,
            "owner_name": self.stats.owner_name,
            "species_idx": self.stats.species_idx,
        }
        try:
            with open(STATS_PATH, "w") as f:
                json.dump(d, f)
            self._dirty = False
        except OSError as e:
            logger.error("Failed to save stats: %s", e)

    def save_settings(self) -> None:
        os.makedirs(DATA_DIR, exist_ok=True)
        d = {
            "sound": self.settings.sound,
            "led": self.settings.led,
            "hud": self.settings.hud,
            "clock_rot": self.settings.clock_rot,
            "brightness": self.settings.brightness,
        }
        try:
            with open(SETTINGS_PATH, "w") as f:
                json.dump(d, f)
        except OSError as e:
            logger.error("Failed to save settings: %s", e)

    def on_approval(self, seconds_to_respond: int) -> None:
        self.stats.approvals += 1
        self.stats.velocity[self.stats.vel_idx] = min(seconds_to_respond, 65535)
        self.stats.vel_idx = (self.stats.vel_idx + 1) % 8
        if self.stats.vel_count < 8:
            self.stats.vel_count += 1
        self._dirty = True
        self.save_stats()

    def on_denial(self) -> None:
        self.stats.denials += 1
        self._dirty = True
        self.save_stats()

    def on_bridge_tokens(self, bridge_total: int) -> None:
        if not self._tokens_synced:
            self._last_bridge_tokens = bridge_total
            self._tokens_synced = True
            return
        if bridge_total < self._last_bridge_tokens:
            self._last_bridge_tokens = bridge_total
            return
        delta = bridge_total - self._last_bridge_tokens
        self._last_bridge_tokens = bridge_total
        if delta == 0:
            return

        lvl_before = self.stats.tokens // TOKENS_PER_LEVEL
        self.stats.tokens += delta
        lvl_after = self.stats.tokens // TOKENS_PER_LEVEL

        if lvl_after > lvl_before:
            self.stats.level = lvl_after
            self._level_up_pending = True
            self._dirty = True
            self.save_stats()

    def poll_level_up(self) -> bool:
        r = self._level_up_pending
        self._level_up_pending = False
        return r

    def on_nap_end(self, seconds: int) -> None:
        self.stats.nap_seconds += seconds
        self._dirty = True
        self.save_stats()

    def on_wake(self) -> None:
        self._last_nap_end = time.time()
        self._energy_at_nap = 5

    def median_velocity(self) -> int:
        if self.stats.vel_count == 0:
            return 0
        vals = sorted(self.stats.velocity[: self.stats.vel_count])
        return vals[len(vals) // 2]

    def mood_tier(self) -> int:
        vel = self.median_velocity()
        if vel == 0:
            tier = 2
        elif vel < 15:
            tier = 4
        elif vel < 30:
            tier = 3
        elif vel < 60:
            tier = 2
        elif vel < 120:
            tier = 1
        else:
            tier = 0

        a, d = self.stats.approvals, self.stats.denials
        if a + d >= 3:
            if d > a:
                tier -= 2
            elif d * 2 > a:
                tier -= 1
        return max(0, tier)

    def energy_tier(self) -> int:
        hours_since = (time.time() - self._last_nap_end) / 3600
        e = self._energy_at_nap - int(hours_since / 2)
        return max(0, min(5, e))

    def fed_progress(self) -> int:
        return (self.stats.tokens % TOKENS_PER_LEVEL) // (TOKENS_PER_LEVEL // 10)

    def set_pet_name(self, name: str) -> None:
        self.stats.pet_name = _safe_str(name, 24)
        self._dirty = True
        self.save_stats()

    def set_owner_name(self, name: str) -> None:
        self.stats.owner_name = _safe_str(name, 32)
        self._dirty = True
        self.save_stats()

    def set_species_idx(self, idx: int) -> None:
        self.stats.species_idx = idx
        self._dirty = True
        self.save_stats()

    def get_status_data(self) -> dict:
        return {
            "name": self.stats.pet_name,
            "stats": {
                "appr": self.stats.approvals,
                "deny": self.stats.denials,
                "vel": self.median_velocity(),
                "nap": self.stats.nap_seconds,
                "lvl": self.stats.level,
            },
        }

    def factory_reset(self) -> None:
        self.stats = Stats()
        self.settings = Settings()
        self._dirty = True
        self.save_stats()
        self.save_settings()


def _safe_str(s: str, max_len: int = 32) -> str:
    return "".join(c for c in s[:max_len] if c not in ('"', "\\") and ord(c) >= 0x20)
