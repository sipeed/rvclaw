#!/usr/bin/env python3
"""
Offline tests — run on any machine (no maix SDK, no hardware).
Validates: state machine, protocol parsing, stats persistence, transport stub, species data.

Usage (from app_cc_buddy/):
    python3 tests/test_offline.py
"""

import json
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PASS = 0
FAIL = 0

def check(name, condition):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}")


def test_state():
    print("\n=== state.py ===")
    from state import TamaState, PersonaState, derive, DisplayMode

    s = TamaState()
    check("default derive -> IDLE", derive(s) == PersonaState.IDLE)

    s.connected = True
    s.sessions_waiting = 1
    check("waiting -> ATTENTION", derive(s) == PersonaState.ATTENTION)

    s.sessions_waiting = 0
    s.recently_completed = True
    check("completed -> CELEBRATE", derive(s) == PersonaState.CELEBRATE)

    s.recently_completed = False
    s.sessions_running = 3
    check("3 running -> BUSY", derive(s) == PersonaState.BUSY)

    s.sessions_running = 1
    check("1 running -> IDLE", derive(s) == PersonaState.IDLE)

    check("DisplayMode cycles 0-2", DisplayMode.COUNT == 3)

    check("PersonaState has 7 values", len(PersonaState) == 7)


def test_protocol():
    print("\n=== protocol.py ===")
    from protocol import LineBuf, apply_json, make_permission_response
    from state import TamaState

    lb = LineBuf()
    check("LineBuf empty feed", lb.feed("") == [])
    check("LineBuf partial", lb.feed('{"x":1') == [])
    check("LineBuf complete", lb.feed("}\n") == ['{"x":1}'])
    check("LineBuf ignores non-json", lb.feed("hello\n") == [])

    s = TamaState()
    hb = json.dumps({
        "total": 3, "running": 1, "waiting": 2,
        "completed": False, "tokens": 50000, "tokens_today": 12000,
        "msg": "test msg",
        "entries": ["line1", "line2"],
        "prompt": {"id": "req_001", "tool": "Bash", "hint": "rm -rf /tmp"}
    })
    result = apply_json(hb, s)
    check("heartbeat: total", s.sessions_total == 3)
    check("heartbeat: running", s.sessions_running == 1)
    check("heartbeat: waiting", s.sessions_waiting == 2)
    check("heartbeat: tokens", s.tokens == 50000)
    check("heartbeat: msg", s.msg == "test msg")
    check("heartbeat: lines", s.lines == ["line1", "line2"])
    check("heartbeat: prompt_id", s.prompt_id == "req_001")
    check("heartbeat: prompt_tool", s.prompt_tool == "Bash")
    check("heartbeat: prompt_hint", s.prompt_hint == "rm -rf /tmp")
    check("heartbeat: connected", s.connected is True)

    hb2 = json.dumps({"total": 1, "running": 0, "waiting": 0})
    apply_json(hb2, s)
    check("no prompt clears prompt_id", s.prompt_id == "")

    perm = make_permission_response("req_001", "once")
    doc = json.loads(perm)
    check("permission cmd", doc["cmd"] == "permission")
    check("permission id", doc["id"] == "req_001")
    check("permission decision", doc["decision"] == "once")

    check("bad json returns None", apply_json("not json", s) is None)


def test_stats():
    print("\n=== stats.py ===")

    import config
    with tempfile.TemporaryDirectory() as td:
        config.DATA_DIR = td
        config.STATS_PATH = os.path.join(td, "stats.json")
        config.SETTINGS_PATH = os.path.join(td, "settings.json")

        # Re-import after patching config
        if "stats" in sys.modules:
            del sys.modules["stats"]
        from stats import StatsManager

        sm = StatsManager()
        sm.load()
        check("default pet_name", sm.stats.pet_name == "Buddy")
        check("default level", sm.stats.level == 0)
        check("default mood", sm.mood_tier() == 2)
        check("default energy", sm.energy_tier() in range(0, 6))

        sm.on_approval(5)
        check("approval increments", sm.stats.approvals == 1)
        check("velocity recorded", sm.stats.velocity[0] == 5)

        sm.on_denial()
        check("denial increments", sm.stats.denials == 1)

        sm.on_bridge_tokens(30000)
        check("first bridge tokens synced (no add)", sm.stats.tokens == 0)
        sm.on_bridge_tokens(80000)
        check("delta added", sm.stats.tokens == 50000)
        check("level up to 1", sm.stats.level == 1)
        check("level_up_pending", sm.poll_level_up() is True)
        check("level_up_pending cleared", sm.poll_level_up() is False)

        sm.on_bridge_tokens(10000)  # bridge restarted (lower)
        check("bridge restart: no add", sm.stats.tokens == 50000)

        check("fed_progress", sm.fed_progress() == 0)

        sm.set_pet_name("Clawd")
        check("pet name set", sm.stats.pet_name == "Clawd")

        sm.set_owner_name("Alice")
        check("owner name set", sm.stats.owner_name == "Alice")

        check("stats file exists", os.path.isfile(config.STATS_PATH))

        sm2 = StatsManager()
        sm2.load()
        check("stats persist: approvals", sm2.stats.approvals == 1)
        check("stats persist: pet_name", sm2.stats.pet_name == "Clawd")
        check("stats persist: level", sm2.stats.level == 1)

        sm.settings.sound = False
        sm.save_settings()
        sm3 = StatsManager()
        sm3.load()
        check("settings persist: sound", sm3.settings.sound is False)

        sm.factory_reset()
        check("factory reset: level", sm.stats.level == 0)
        check("factory reset: approvals", sm.stats.approvals == 0)

        sm.get_status_data()
        check("status_data runs", True)


def test_transport():
    print("\n=== transport.py ===")
    import asyncio
    from transport import StubTransport
    from state import TamaState

    async def _run():
        st = StubTransport()
        check("stub connected", st.is_connected())

        st._next_switch = 0
        line = await st.read_line()
        check("stub produces JSON", line is not None and line.startswith("{"))

        doc = json.loads(line)
        check("stub has total", "total" in doc)
        check("stub has msg", "msg" in doc)

        await st.write_line('{"cmd":"permission","id":"x","decision":"once"}')
        check("write_line no error", True)

        tama = TamaState()
        st._next_switch = 0
        await st.poll(tama)
        check("poll updates tama", tama.sessions_total >= 0)

        await st.close()
        check("close no error", True)

    asyncio.run(_run())


def test_species_data():
    print("\n=== species data ===")
    from buddy import Species, BuddyRenderer, COLOR_CAPYBARA, COLOR_ROBOT
    from buddies.capybara import SPECIES as cap
    from buddies.cat import SPECIES as cat
    from buddies.robot import SPECIES as rob

    for sp in [cap, cat, rob]:
        check(f"{sp.name}: has 7 states", len(sp.states) == 7)
        check(f"{sp.name}: all callables",
              all(callable(fn) for fn in sp.states))
        check(f"{sp.name}: has body_color",
              isinstance(sp.body_color, tuple) and len(sp.body_color) == 3)

    check("capybara name", cap.name == "capybara")
    check("cat name", cat.name == "cat")
    check("robot name", rob.name == "robot")

    r = BuddyRenderer()
    r.register_species(cap)
    r.register_species(cat)
    r.register_species(rob)
    check("renderer: 3 species", r.species_count == 3)
    check("renderer: default idx 0", r.species_idx == 0)
    check("renderer: species name", r.species_name == "capybara")

    r.next_species()
    check("renderer: next -> cat", r.species_name == "cat")

    r.set_species_by_name("robot")
    check("renderer: set by name", r.species_name == "robot")

    r.set_species_idx(0)
    check("renderer: set by idx", r.species_name == "capybara")


def test_buddy_colors():
    print("\n=== buddy colors ===")
    from buddy import (
        _rgb565_to_888, BUDDY_BG, BUDDY_HEART, BUDDY_WHITE,
        BUDDY_RED, BUDDY_GREEN, BUDDY_BLUE, BUDDY_YEL, BUDDY_CYAN,
    )

    check("BG is black", BUDDY_BG == (0, 0, 0))
    check("WHITE is white", BUDDY_WHITE == (255, 255, 255))

    r, g, b = BUDDY_RED
    check("RED is red-ish", r > 200 and g < 20 and b < 20)

    r, g, b = BUDDY_GREEN
    check("GREEN is green-ish", r < 20 and g > 200 and b < 20)

    r, g, b = BUDDY_HEART
    check("HEART has red", r > 200)

    check("rgb565 round-trip 0x0000", _rgb565_to_888(0x0000) == (0, 0, 0))
    check("rgb565 round-trip 0xFFFF",
          all(c >= 248 for c in _rgb565_to_888(0xFFFF)))


if __name__ == "__main__":
    test_state()
    test_protocol()
    test_stats()
    test_transport()
    test_species_data()
    test_buddy_colors()

    print(f"\n{'='*40}")
    print(f"  {PASS} passed, {FAIL} failed")
    print(f"{'='*40}")
    sys.exit(1 if FAIL > 0 else 0)
