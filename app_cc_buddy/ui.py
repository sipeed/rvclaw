import asyncio
import fcntl
import socket
import struct
import time

from maix import image

from config import (
    DISP_W, DISP_H, ICON_PATH, TEXT_MARGIN, MAX_TEXT_W,
    FONT_NAME, FONT_NAME_LARGE, FONT_NAME_ART,
    BUDDY_AREA_H, HUD_TOP,
    UI_LH, UI_LH_LARGE,
)
from state import TamaState, PersonaState, STATE_NAMES, DisplayMode
from stats import StatsManager, TOKENS_PER_LEVEL

# ---------------------------------------------------------------------------
# Colors
# ---------------------------------------------------------------------------
BG = (8, 8, 24)
HOT = (255, 80, 30)
PANEL_BG = (16, 16, 32)
GREEN = (60, 200, 100)
RED = (220, 60, 60)
WHITE = (215, 215, 195)
DIM = (110, 110, 140)
BLUE = (90, 165, 255)

_C = image.Color.from_rgb


# ---------------------------------------------------------------------------
# Font context helpers
# ---------------------------------------------------------------------------
def _use_font():
    image.set_default_font(FONT_NAME)

def _use_font_large():
    image.set_default_font(FONT_NAME_LARGE)


# ---------------------------------------------------------------------------
# Animation task management
# ---------------------------------------------------------------------------
_anim_task: asyncio.Task | None = None
_home_icon = None


def start_anim(coro) -> None:
    global _anim_task
    if _anim_task and not _anim_task.done():
        _anim_task.cancel()
    _anim_task = asyncio.create_task(coro)


def stop_anim() -> None:
    global _anim_task
    if _anim_task and not _anim_task.done():
        _anim_task.cancel()
    _anim_task = None


# ---------------------------------------------------------------------------
# Boot splash
# ---------------------------------------------------------------------------
def draw_boot_splash(img: image.Image, owner: str, pet_name: str, body_color: tuple) -> None:
    img.draw_rect(0, 0, DISP_W, DISP_H, _C(*BG), thickness=-1)
    _use_font_large()
    cx = DISP_W // 2
    cy = DISP_H // 2
    if owner:
        line1 = f"{owner}'s"
        tw1, th1 = image.string_size(line1)
        img.draw_string(cx - tw1 // 2, cy - th1 - 4, line1, _C(*WHITE))
        tw2, _ = image.string_size(pet_name)
        img.draw_string(cx - tw2 // 2, cy + 4, pet_name, _C(*body_color))
    else:
        tw, th = image.string_size("Hello!")
        img.draw_string(cx - tw // 2, cy - th - 4, "Hello!", _C(*body_color))
        _use_font()
        tw2, _ = image.string_size("a buddy appears")
        img.draw_string(cx - tw2 // 2, cy + 4, "a buddy appears", _C(*DIM))
    _use_font()


# ---------------------------------------------------------------------------
# Home icon
# ---------------------------------------------------------------------------
def show_home_icon(disp) -> None:
    global _home_icon
    if _home_icon is None:
        img = image.load(ICON_PATH)
        _use_font_large()
        text = "CC BUDDY"
        tw, th = image.string_size(text)
        x = (DISP_W - tw) // 2
        y = DISP_H - th - 10
        glow = _C(40, 140, 220)
        core = _C(125, 225, 255)
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            img.draw_string(x + dx, y + dy, text, glow)
        img.draw_string(x, y, text, core)
        _use_font()
        _home_icon = img
    disp.display(_home_icon)


# ---------------------------------------------------------------------------
# Word-wrap using actual pixel width
# ---------------------------------------------------------------------------
def _wrap(text: str, max_w: int = MAX_TEXT_W, max_lines: int = 0) -> list[str]:
    lines = []
    for para in text.split("\n"):
        if not para:
            continue
        while para and (max_lines == 0 or len(lines) < max_lines):
            lo, hi = 1, len(para)
            while lo < hi:
                mid = (lo + hi + 1) // 2
                w, _ = image.string_size(para[:mid])
                if w <= max_w:
                    lo = mid
                else:
                    hi = mid - 1
            lines.append(para[:lo])
            para = para[lo:]
        if max_lines != 0 and len(lines) >= max_lines:
            break
    return lines


def _greedy_wrap(text: str, max_px: int = MAX_TEXT_W) -> list[str]:
    words = text.split()
    if not words:
        return [""]
    lines = [words[0]]
    for word in words[1:]:
        candidate = lines[-1] + " " + word
        w, _ = image.string_size(candidate)
        if w <= max_px:
            lines[-1] = candidate
        else:
            lines.append(word)
    result = []
    for line in lines:
        w, _ = image.string_size(line)
        if w <= max_px:
            result.append(line)
        else:
            while line:
                lo, hi = 1, len(line)
                while lo < hi:
                    mid = (lo + hi + 1) // 2
                    mw, _ = image.string_size(line[:mid])
                    if mw <= max_px:
                        lo = mid
                    else:
                        hi = mid - 1
                result.append(line[:lo])
                line = line[lo:]
    return result if result else [""]


# ---------------------------------------------------------------------------
# HUD (transcript display)
# ---------------------------------------------------------------------------
def draw_hud(img: image.Image, tama: TamaState, msg_scroll: int, body_color: tuple) -> None:
    _use_font()
    lh = UI_LH
    area_h = DISP_H - HUD_TOP
    img.draw_rect(0, HUD_TOP, DISP_W, area_h, _C(*BG), thickness=-1)

    show_lines = area_h // lh

    if not tama.lines:
        img.draw_string(TEXT_MARGIN, DISP_H - lh, tama.msg, _C(*WHITE))
        return

    disp_lines = []
    src_of = []
    hud_px_w = DISP_W - TEXT_MARGIN * 2
    for idx, line in enumerate(tama.lines):
        wrapped = _greedy_wrap(line, hud_px_w)
        for wl in wrapped:
            disp_lines.append(wl)
            src_of.append(idx)

    n_disp = len(disp_lines)
    max_scroll = max(0, n_disp - show_lines)
    scroll = min(msg_scroll, max_scroll)

    start = scroll
    end = min(scroll + show_lines, n_disp)

    for i in range(start, end):
        row_y = HUD_TOP + 2 + (i - start) * lh
        if row_y + lh > DISP_H:
            break
        fresh = src_of[i] == 0 and scroll == 0
        color = WHITE if fresh else DIM
        img.draw_string(TEXT_MARGIN, row_y, disp_lines[i], _C(*color))

    if scroll > 0:
        label = f"+{scroll}"
        tw, _ = image.string_size(label)
        img.draw_string(DISP_W - tw - TEXT_MARGIN, DISP_H - lh, label, _C(*body_color))


# ---------------------------------------------------------------------------
# Approval prompt
# ---------------------------------------------------------------------------
def draw_approval(img: image.Image, tama: TamaState, prompt_arrived_ms: float,
                  response_sent: bool, body_color: tuple, top: int = HUD_TOP) -> None:
    _use_font()
    lh = UI_LH
    img.draw_rect(0, top, DISP_W, DISP_H - top, _C(*BG), thickness=-1)
    img.draw_line(0, top, DISP_W, top, _C(*DIM), thickness=1)

    y = top + 4
    waited = int(time.time() - prompt_arrived_ms)
    wait_color = HOT if waited >= 10 else DIM
    img.draw_string(TEXT_MARGIN, y, f"approve? {waited}s", _C(*wait_color))
    y += lh

    _use_font_large()
    tool_text = tama.prompt_tool
    tw_tool, th_tool = image.string_size(tool_text)
    if tw_tool > DISP_W - TEXT_MARGIN * 2:
        _use_font()
    img.draw_string(TEXT_MARGIN, y, tool_text, _C(*WHITE))
    y += th_tool + 4

    _use_font()
    hint = tama.prompt_hint
    if hint:
        hint_lines = _greedy_wrap(hint, DISP_W - TEXT_MARGIN * 2)
        for hl in hint_lines[:2]:
            img.draw_string(TEXT_MARGIN, y, hl, _C(*DIM))
            y += lh

    btn_y = DISP_H - lh
    if response_sent:
        img.draw_string(TEXT_MARGIN, btn_y, "sent...", _C(*DIM))
    else:
        img.draw_string(TEXT_MARGIN, btn_y, "A: approve", _C(*GREEN))
        tw, _ = image.string_size("B: deny")
        img.draw_string(DISP_W - tw - TEXT_MARGIN, btn_y, "B: deny", _C(*HOT))


# ---------------------------------------------------------------------------
# Info pages
# ---------------------------------------------------------------------------
INFO_PAGES = 6


def draw_info(img: image.Image, page: int, tama: TamaState, sm: StatsManager,
              active_state: int, body_color: tuple, top: int = HUD_TOP) -> None:
    _use_font()
    lh = UI_LH
    img.draw_rect(0, top, DISP_W, DISP_H - top, _C(*BG), thickness=-1)
    y = top + 4

    def _header(section: str):
        nonlocal y
        img.draw_string(TEXT_MARGIN, y, "Info", _C(*WHITE))
        pg = f"{page+1}/{INFO_PAGES}"
        tw, _ = image.string_size(pg)
        img.draw_string(DISP_W - tw - TEXT_MARGIN, y, pg, _C(*DIM))
        y += lh
        img.draw_string(TEXT_MARGIN, y, section, _C(*body_color))
        y += lh

    def _ln(text: str, color: tuple = DIM):
        nonlocal y
        if y + lh > DISP_H:
            return
        img.draw_string(TEXT_MARGIN, y, text, _C(*color))
        y += lh

    def _gap(px: int = 6):
        nonlocal y
        y += px

    if page == 0:
        _header("ABOUT")
        _ln("I watch your Claude")
        _ln("Code sessions.")
        _gap()
        _ln("I sleep when nothing's")
        _ln("happening, wake when")
        _ln("you start working,")
        _ln("get impatient when")
        _ln("approvals pile up.")

    elif page == 1:
        _header("BUTTONS")
        _ln("A   front", WHITE)
        _ln("    next screen")
        _ln("    approve prompt")
        _gap()
        _ln("B   right side", WHITE)
        _ln("    next page")
        _ln("    deny prompt")
        _gap()
        _ln("hold A", WHITE)
        _ln("    menu")

    elif page == 2:
        _header("CLAUDE")
        _ln(f"  sessions  {tama.sessions_total}")
        _ln(f"  running   {tama.sessions_running}")
        _ln(f"  waiting   {tama.sessions_waiting}")
        _gap()
        _ln("LINK", WHITE)
        _ln(f"  connected {tama.connected}")
        _ln(f"  state     {STATE_NAMES[active_state] if active_state < 7 else '?'}")

    elif page == 3:
        _header("DEVICE")
        _ln("SYSTEM", WHITE)
        if sm.stats.owner_name:
            _ln(f"  owner    {sm.stats.owner_name}")
        _ln(f"  pet      {sm.stats.pet_name}")
        _ln(f"  level    {sm.stats.level}")
        _gap()
        _ln(f"  approved {sm.stats.approvals}")
        _ln(f"  denied   {sm.stats.denials}")

    elif page == 4:
        _header("NETWORK")
        ip = _get_ip()
        wifi_ok = ip is not None
        _ln(f"  WiFi     {'Yes' if wifi_ok else 'No'}", GREEN if wifi_ok else RED)
        _ln(f"  IP       {ip or '---'}", WHITE if ip else DIM)

    elif page == 5:
        _header("CREDITS")
        _ln("based on")
        _ln("claude-desktop-buddy", WHITE)
        _ln("by Felix Rieseberg")
        _gap()
        _ln("ported to Picoclaw")
        _ln("for LicheeRV Nano")


def _get_ip() -> str | None:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        ip = socket.inet_ntoa(fcntl.ioctl(
            s.fileno(), 0x8915, struct.pack("256s", b"wlan0"),
        )[20:24])
        s.close()
        return ip
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Pet stats
# ---------------------------------------------------------------------------
PET_PAGES = 2


def draw_pet_stats(img: image.Image, sm: StatsManager, body_color: tuple,
                   top: int = HUD_TOP) -> None:
    _use_font()
    lh = UI_LH
    img.draw_rect(0, top, DISP_W, DISP_H - top, _C(*BG), thickness=-1)
    y = top + lh + 2

    def _bar_label(label: str):
        nonlocal y
        img.draw_string(TEXT_MARGIN, y, label, _C(*DIM))

    _bar_label("mood")
    mood = sm.mood_tier()
    mood_col = RED
    bar_x = 70
    cw, _ = image.string_size("\u2665")
    sp = cw + 2
    for i in range(4):
        ch = "\u2665" if i < mood else "\u2661"
        img.draw_string(bar_x + i * sp, y, ch, _C(*mood_col) if i < mood else _C(*DIM))
    y += lh

    _bar_label("fed")
    fed = sm.fed_progress()
    cw2, _ = image.string_size("\u25cf")
    sp2 = cw2 + 1
    for i in range(10):
        ch = "\u25cf" if i < fed else "\u25cb"
        img.draw_string(bar_x + i * sp2, y, ch, _C(*body_color) if i < fed else _C(*DIM))
    y += lh

    _bar_label("energy")
    en = sm.energy_tier()
    en_col = (0, 255, 255) if en >= 4 else ((255, 255, 0) if en >= 2 else HOT)
    cw3, _ = image.string_size("\u25a0")
    sp3 = cw3 + 2
    for i in range(5):
        ch = "\u25a0" if i < en else "\u25a1"
        img.draw_string(bar_x + i * sp3, y, ch, _C(*en_col) if i < en else _C(*DIM))
    y += lh

    val_x = bar_x + 20
    img.draw_string(TEXT_MARGIN, y, "approved", _C(*DIM))
    img.draw_string(val_x, y, str(sm.stats.approvals), _C(*DIM))
    y += lh
    img.draw_string(TEXT_MARGIN, y, "denied", _C(*DIM))
    img.draw_string(val_x, y, str(sm.stats.denials), _C(*DIM))
    y += lh
    nap = sm.stats.nap_seconds
    img.draw_string(TEXT_MARGIN, y, "napped", _C(*DIM))
    img.draw_string(val_x, y, f"{nap // 3600}h{(nap // 60) % 60:02d}m", _C(*DIM))
    y += lh

    def _tok_fmt(label, v):
        nonlocal y
        if y + lh > DISP_H:
            return
        if v >= 1_000_000:
            s = f"{label}{v // 1_000_000}.{(v // 100_000) % 10}M"
        elif v >= 1000:
            s = f"{label}{v // 1000}.{(v // 100) % 10}K"
        else:
            s = f"{label}{v}"
        img.draw_string(TEXT_MARGIN, y, s, _C(*DIM))
        y += lh

    _tok_fmt("tokens   ", sm.stats.tokens)


def draw_pet_howto(img: image.Image, body_color: tuple, top: int = HUD_TOP) -> None:
    _use_font()
    lh = UI_LH
    img.draw_rect(0, top, DISP_W, DISP_H - top, _C(*BG), thickness=-1)
    y = top + lh + 4

    def _ln(text, color=DIM):
        nonlocal y
        if y + lh > DISP_H:
            return
        img.draw_string(TEXT_MARGIN, y, text, _C(*color))
        y += lh

    def _gap(px=6):
        nonlocal y
        y += px

    _ln("MOOD", body_color)
    _ln(" approve fast = up")
    _ln(" deny lots = down")
    _gap()
    _ln("FED", body_color)
    _ln(" 50K tokens =")
    _ln(" level up + confetti")
    _gap()
    _ln("ENERGY", body_color)
    _ln(" face-down to nap")
    _ln(" refills to full")


def draw_pet(img: image.Image, page: int, sm: StatsManager, body_color: tuple,
             top: int = HUD_TOP) -> None:
    if page == 0:
        draw_pet_stats(img, sm, body_color, top=top)
    else:
        draw_pet_howto(img, body_color, top=top)

    _use_font()
    y = top + 2
    if sm.stats.owner_name:
        title = f"{sm.stats.owner_name}'s {sm.stats.pet_name}"
    else:
        title = sm.stats.pet_name
    img.draw_string(TEXT_MARGIN, y, title, _C(*WHITE))
    pg = f"{page+1}/{PET_PAGES}"
    tw_pg, _ = image.string_size(pg)
    img.draw_string(DISP_W - tw_pg - TEXT_MARGIN, y, pg, _C(*DIM))
    lv = f"Lv{sm.stats.level}"
    tw_lv, _ = image.string_size(lv)
    img.draw_string(DISP_W - tw_pg - TEXT_MARGIN - tw_lv - 8, y, lv, _C(*body_color))


# ---------------------------------------------------------------------------
# Menu overlay
# ---------------------------------------------------------------------------
MENU_ITEMS = ["settings", "help", "about", "demo", "to picoclaw", "close"]
MENU_N = len(MENU_ITEMS)
MENU_SWITCH_IDX = MENU_ITEMS.index("to picoclaw")


def draw_menu(img: image.Image, sel: int, demo_on: bool, body_color: tuple) -> None:
    _use_font()
    lh = UI_LH
    mw = 180
    mh = lh + MENU_N * lh + 8
    mx = (DISP_W - mw) // 2
    my = (DISP_H - mh) // 2
    img.draw_rect(mx, my, mw, mh, _C(*PANEL_BG), thickness=-1)
    img.draw_rect(mx, my, mw, mh, _C(*DIM), thickness=1)

    for i in range(MENU_N):
        is_sel = i == sel
        color = WHITE if is_sel else DIM
        prefix = "> " if is_sel else "  "
        label = MENU_ITEMS[i]
        if label == "demo":
            label += "  on" if demo_on else "  off"
        item_y = my + 4 + i * lh
        img.draw_string(mx + TEXT_MARGIN, item_y, prefix + label, _C(*color))


# ---------------------------------------------------------------------------
# Settings overlay
# ---------------------------------------------------------------------------
SETTINGS_ITEMS = ["brightness", "sound", "led", "transcript", "ascii pet", "sleep", "reset stats", "back"]
SETTINGS_N = len(SETTINGS_ITEMS)


def draw_settings(img: image.Image, sel: int, sm: StatsManager,
                  buddy_renderer, body_color: tuple) -> None:
    _use_font()
    lh = UI_LH
    mw = 210
    mh = lh + SETTINGS_N * lh + 8
    mx = (DISP_W - mw) // 2
    my = (DISP_H - mh) // 2
    img.draw_rect(mx, my, mw, mh, _C(*PANEL_BG), thickness=-1)
    img.draw_rect(mx, my, mw, mh, _C(*DIM), thickness=1)

    s = sm.settings
    for i in range(SETTINGS_N):
        is_sel = i == sel
        color = WHITE if is_sel else DIM
        prefix = "> " if is_sel else "  "
        item_y = my + 4 + i * lh
        img.draw_string(mx + TEXT_MARGIN, item_y, prefix + SETTINGS_ITEMS[i], _C(*color))

        val_x = mx + mw - 42
        if i == 0:
            img.draw_string(val_x, item_y, f"{s.brightness}/4", _C(*DIM))
        elif i == 1:
            v = s.sound
            img.draw_string(val_x, item_y, " on" if v else "off",
                           _C(*GREEN) if v else _C(*DIM))
        elif i == 2:
            v = s.led
            img.draw_string(val_x, item_y, " on" if v else "off",
                           _C(*GREEN) if v else _C(*DIM))
        elif i == 3:
            v = s.hud
            img.draw_string(val_x, item_y, " on" if v else "off",
                           _C(*GREEN) if v else _C(*DIM))
        elif i == 4:
            total = buddy_renderer.species_count
            pos = buddy_renderer.species_idx + 1
            img.draw_string(val_x, item_y, f"{pos}/{total}", _C(*DIM))
        elif i == 5:
            v = s.sleep
            img.draw_string(val_x, item_y, " on" if v else "off",
                           _C(*GREEN) if v else _C(*DIM))


# ---------------------------------------------------------------------------
# Clock face (portrait only)
# ---------------------------------------------------------------------------
def draw_clock(img: image.Image, body_color: tuple, top: int = HUD_TOP) -> None:
    img.draw_rect(0, top, DISP_W, DISP_H - top, _C(*BG), thickness=-1)

    import datetime
    now = datetime.datetime.now()
    hm = now.strftime("%H:%M")
    ss = now.strftime(":%S")
    dl = now.strftime("%b %d")

    _use_font_large()
    tw, th = image.string_size(hm)
    img.draw_string((DISP_W - tw) // 2, top + 8, hm, _C(*WHITE))

    _use_font()
    tw2, th2 = image.string_size(ss)
    img.draw_string((DISP_W - tw2) // 2, top + 8 + th + 6, ss, _C(*DIM))

    tw3, _ = image.string_size(dl)
    img.draw_string((DISP_W - tw3) // 2, top + 8 + th + 6 + th2 + 6, dl, _C(*DIM))
