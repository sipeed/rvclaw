import asyncio
import math
import psutil

from maix import app, image

from picoclaw import gateway_running, get_picoclaw_model
from config import (
    DISP_W, DISP_H, ICON_PATH, LINE_H, TEXT_MARGIN, MAX_TEXT_W,
    FONT_NAME, FONT_NAME_LARGE,
)


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


def show_home_icon(disp) -> None:
    global _home_icon
    if _home_icon is None:
        img = image.load(ICON_PATH)

        image.set_default_font(FONT_NAME_LARGE)
        text = "PRESS TO START"
        tw, _ = image.string_size(text)
        x = (DISP_W - tw) // 2
        y = DISP_H - 32

        glow = image.Color.from_rgb(40, 140, 220)
        core = image.Color.from_rgb(125, 225, 255)
        img.draw_string(x - 1, y, text, glow)
        img.draw_string(x + 1, y, text, glow)
        img.draw_string(x, y - 1, text, glow)
        img.draw_string(x, y + 1, text, glow)
        img.draw_string(x, y, text, core)

        image.set_default_font(FONT_NAME)
        _home_icon = img
    disp.display(_home_icon)


def show_boot_choice(disp) -> None:
    img = image.load(ICON_PATH)

    image.set_default_font(FONT_NAME_LARGE)

    blue_glow = image.Color.from_rgb(40, 140, 220)
    blue_core = image.Color.from_rgb(125, 225, 255)
    hot_glow = image.Color.from_rgb(180, 80, 30)
    hot_core = image.Color.from_rgb(255, 180, 120)

    y = DISP_H - 32
    pad = 12

    left = "A: Start"
    lw, _ = image.string_size(left)
    lx = pad
    for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        img.draw_string(lx + dx, y + dy, left, blue_glow)
    img.draw_string(lx, y, left, blue_core)

    right = "B: Buddy"
    rw, _ = image.string_size(right)
    rx = DISP_W - rw - pad
    for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        img.draw_string(rx + dx, y + dy, right, hot_glow)
    img.draw_string(rx, y, right, hot_core)

    image.set_default_font(FONT_NAME)
    disp.display(img)


def show_switching(disp, message: str) -> None:
    img = image.Image(DISP_W, DISP_H, image.Format.FMT_RGB888)
    img.draw_rect(0, 0, DISP_W, DISP_H, image.Color.from_rgb(8, 10, 24), thickness=-1)

    image.set_default_font(FONT_NAME_LARGE)
    tw, th = image.string_size(message)
    img.draw_string((DISP_W - tw) // 2, (DISP_H - th) // 2,
                    message, image.Color.from_rgb(125, 225, 255))

    image.set_default_font(FONT_NAME)
    sub = "please wait..."
    tw2, _ = image.string_size(sub)
    img.draw_string((DISP_W - tw2) // 2, (DISP_H + th) // 2 + 8,
                    sub, image.Color.from_rgb(110, 110, 140))

    disp.display(img)


async def show_no_speech(disp, duration: float = 2.0):
    img = image.Image(DISP_W, DISP_H, image.Format.FMT_RGB888)
    img.draw_rect(0, 0, DISP_W, DISP_H, image.Color.from_rgb(20, 10, 10), thickness=-1)
    cx, cy = DISP_W // 2, 90
    img.draw_circle(cx, cy, 28, image.Color.from_rgb(60, 30, 0), thickness=-1)
    img.draw_circle(cx, cy, 28, image.Color.from_rgb(255, 160, 30), thickness=3)
    tw, _ = image.string_size("No speech detected")
    img.draw_string((DISP_W - tw) // 2, 140,
                    "No speech detected", image.Color.from_rgb(255, 160, 30))
    tw2, _ = image.string_size("Please try again")
    img.draw_string((DISP_W - tw2) // 2, 165,
                    "Please try again", image.Color.from_rgb(120, 120, 150))
    disp.display(img)
    await asyncio.sleep(duration)


async def show_error(disp, message: str = "No response", duration: float = 2.0):
    img = image.Image(DISP_W, DISP_H, image.Format.FMT_RGB888)
    img.draw_rect(0, 0, DISP_W, DISP_H, image.Color.from_rgb(15, 5, 5), thickness=-1)
    cx, cy = DISP_W // 2, 90
    img.draw_circle(cx, cy, 28, image.Color.from_rgb(60, 10, 10), thickness=-1)
    img.draw_circle(cx, cy, 28, image.Color.from_rgb(220, 60, 60), thickness=3)
    d = 12
    img.draw_line(cx - d, cy - d, cx + d, cy + d, image.Color.from_rgb(220, 60, 60), thickness=3)
    img.draw_line(cx + d, cy - d, cx - d, cy + d, image.Color.from_rgb(220, 60, 60), thickness=3)
    tw, _ = image.string_size(message)
    img.draw_string((DISP_W - tw) // 2, 140,
                    message, image.Color.from_rgb(220, 60, 60))
    tw2, _ = image.string_size("Please try again")
    img.draw_string((DISP_W - tw2) // 2, 165,
                    "Please try again", image.Color.from_rgb(120, 120, 150))
    disp.display(img)
    await asyncio.sleep(duration)


def show_info_screen(disp, wifi_speed: str | None = None) -> None:
    def _get_ip() -> str | None:
        try:
            addrs = psutil.net_if_addrs().get('wlan0', [])
            for addr in addrs:
                if addr.family == 2:
                    return addr.address
            return None
        except Exception:
            return None

    ip      = _get_ip()
    wifi_ok = ip is not None
    gw      = gateway_running()
    model   = get_picoclaw_model()

    image.set_default_font(FONT_NAME_LARGE)

    img = image.Image(DISP_W, DISP_H, image.Format.FMT_RGB888)
    img.draw_rect(0, 0, DISP_W, DISP_H, image.Color.from_rgb(8, 10, 24), thickness=-1)

    gray  = image.Color.from_rgb(110, 110, 140)
    green = image.Color.from_rgb(60, 200, 100)
    red   = image.Color.from_rgb(220, 80, 80)
    white = image.Color.from_rgb(215, 215, 195)
    blue  = image.Color.from_rgb(90, 165, 255)

    y = 14
    title = "PicoClaw"
    tw, _ = image.string_size(title)
    img.draw_string((DISP_W - tw) // 2, y, title, blue)
    y += 30
    img.draw_line(12, y, DISP_W - 12, y, image.Color.from_rgb(40, 50, 90), thickness=1)
    y += 12

    ROW_H = 34

    def _row(label: str, value: str, value_color) -> None:
        nonlocal y
        img.draw_string(14, y, label, gray)
        vw, _ = image.string_size(value)
        img.draw_string(DISP_W - 14 - vw, y, value, value_color)
        y += ROW_H

    _row("WiFi",    "Yes" if wifi_ok else "No",  green if wifi_ok else red)
    _row("IP",      ip    if ip      else "---",  white if ip      else gray)
    y += 2
    img.draw_line(12, y, DISP_W - 12, y, image.Color.from_rgb(30, 35, 60), thickness=1)
    y += 12

    _row("Gateway", "Yes" if gw    else "No",   green if gw    else red)
    _row("Model",   model if model else "---",   white if model else gray)

    if wifi_speed is not None:
        y -= 6
        y += 2
        img.draw_line(12, y, DISP_W - 12, y, image.Color.from_rgb(30, 35, 60), thickness=1)
        y += 8

        speed_text = wifi_speed
        max_w = DISP_W - 14 - 14 - 70
        while speed_text:
            tw, _ = image.string_size(speed_text)
            if tw <= max_w:
                break
            speed_text = speed_text[:-1]
        if speed_text != wifi_speed and len(speed_text) >= 3:
            speed_text = speed_text[:-3] + "..."

        _row("Speed", speed_text if speed_text else "---", white)

    disp.display(img)
    image.set_default_font(FONT_NAME)


async def animate_speak_now(disp):
    tw, _ = image.string_size("Listening...")
    tw2, _ = image.string_size("Please speak now")
    frame = 0
    while True:
        t = frame * 0.25
        pulse = (math.sin(t) + 1) / 2          # 0.0 ~ 1.0
        r = int(20 + 12 * pulse)
        v = int(160 + 95 * pulse)
        img = image.Image(DISP_W, DISP_H, image.Format.FMT_RGB888)
        img.draw_rect(0, 0, DISP_W, DISP_H, image.Color.from_rgb(10, 10, 30), thickness=-1)
        img.draw_circle(DISP_W // 2, 90, r, image.Color.from_rgb(v, 50, 50), thickness=-1)
        img.draw_circle(DISP_W // 2, 90, r, image.Color.from_rgb(255, 100, 100), thickness=2)
        img.draw_string((DISP_W - tw) // 2, 140,
                        "Listening...", image.Color.from_rgb(240, 240, 240))
        img.draw_string((DISP_W - tw2) // 2, 165,
                        "Please speak now", image.Color.from_rgb(120, 120, 150))
        disp.display(img)
        frame += 1
        await asyncio.sleep(0.02)


async def animate_transcribing(disp):
    tw, _ = image.string_size("Transcribing...")
    tw2, _ = image.string_size("Recognizing speech")
    _dot_phases = [(3 - i) / 3.0 for i in range(3)]
    _dot_colors = [
        (int(int(60 + 195 * p) * 0.27), int(60 + 195 * p), int(int(60 + 195 * p) * 0.55))
        for p in _dot_phases
    ]
    _dot_radii = [max(3, 6 - i) for i in range(3)]
    frame = 0
    while True:
        angle = frame * 0.30
        img = image.Image(DISP_W, DISP_H, image.Format.FMT_RGB888)
        img.draw_rect(0, 0, DISP_W, DISP_H, image.Color.from_rgb(10, 20, 15), thickness=-1)
        cx, cy, orbit = DISP_W // 2, 90, 28
        img.draw_circle(cx, cy, orbit, image.Color.from_rgb(20, 60, 30), thickness=3)
        for i in range(3):
            a = angle + i * (2 * math.pi / 3)
            dx = int(orbit * math.cos(a))
            dy = int(orbit * math.sin(a))
            r, g, b = _dot_colors[i]
            img.draw_circle(cx + dx, cy + dy, _dot_radii[i],
                            image.Color.from_rgb(r, g, b), thickness=-1)
        img.draw_string((DISP_W - tw) // 2, 140,
                        "Transcribing...", image.Color.from_rgb(60, 220, 120))
        img.draw_string((DISP_W - tw2) // 2, 165,
                        "Recognizing speech", image.Color.from_rgb(120, 120, 150))
        disp.display(img)
        frame += 1
        await asyncio.sleep(0.02)


async def animate_thinking(disp, tool_names: list | None = None):
    tw, _ = image.string_size("Thinking...")
    tw2, _ = image.string_size("Please wait a moment")
    _dot_phases = [(3 - i) / 3.0 for i in range(3)]
    _dot_colors = [
        (int(int(60 + 195 * p) * 0.31), int(int(60 + 195 * p) * 0.63), int(60 + 195 * p))
        for p in _dot_phases
    ]
    _dot_radii = [max(3, 6 - i) for i in range(3)]
    frame = 0
    while True:
        angle = frame * 0.30
        img = image.Image(DISP_W, DISP_H, image.Format.FMT_RGB888)
        img.draw_rect(0, 0, DISP_W, DISP_H, image.Color.from_rgb(10, 10, 30), thickness=-1)
        cx, cy, orbit = DISP_W // 2, 90, 28
        img.draw_circle(cx, cy, orbit, image.Color.from_rgb(40, 40, 80), thickness=3)
        for i in range(3):
            a = angle + i * (2 * math.pi / 3)
            dx = int(orbit * math.cos(a))
            dy = int(orbit * math.sin(a))
            r, g, b = _dot_colors[i]
            img.draw_circle(cx + dx, cy + dy, _dot_radii[i],
                            image.Color.from_rgb(r, g, b), thickness=-1)
        img.draw_string((DISP_W - tw) // 2, 140,
                        "Thinking...", image.Color.from_rgb(80, 160, 255))
        if tool_names:
            tool_text = f"> {tool_names[-1]}"
            twt, _ = image.string_size(tool_text)
            img.draw_string((DISP_W - twt) // 2, 165,
                           tool_text, image.Color.from_rgb(160, 140, 255))
        else:
            img.draw_string((DISP_W - tw2) // 2, 165,
                            "Please wait a moment", image.Color.from_rgb(120, 120, 150))
        disp.display(img)
        frame += 1
        await asyncio.sleep(0.02)


def _strip_emoji(text: str) -> str:
    return "".join(c for c in text if ord(c) <= 0xFFFF and not (0x2600 <= ord(c) <= 0x27BF))


MAX_W = MAX_TEXT_W


def _wrap(text: str, max_lines: int = 0) -> list:
    lines = []
    for para in text.split("\n"):
        if not para:
            continue  # Skip empty lines
        while para and (max_lines == 0 or len(lines) < max_lines):
            lo, hi = 1, len(para)
            while lo < hi:
                mid = (lo + hi + 1) // 2
                w, _ = image.string_size(para[:mid])
                if w <= MAX_W:
                    lo = mid
                else:
                    hi = mid - 1
            lines.append(para[:lo])
            para = para[lo:]
        if max_lines != 0 and len(lines) >= max_lines:
            break
    return lines, bool(text)


def _draw_line_h(img, x: int, y: int, text: str, color) -> int:
    img.draw_string(x, y, text, color)
    _, h = image.string_size(text)
    return max(h + 6, LINE_H)


def _render_frame(question: str, window: list, tool_names: list | None = None) -> image.Image:
    img = image.Image(DISP_W, DISP_H, image.Format.FMT_RGB888)
    img.draw_rect(0, 0, DISP_W, DISP_H, image.Color.from_rgb(8, 8, 24), thickness=-1)

    y = 6
    y += _draw_line_h(img, TEXT_MARGIN, y, "You:", image.Color.from_rgb(120, 180, 255))

    q_lines, _ = _wrap(question, 2)
    for line in q_lines:
        y += _draw_line_h(img, TEXT_MARGIN, y, line, image.Color.from_rgb(200, 200, 200))

    y += 3
    img.draw_line(TEXT_MARGIN, y, DISP_W - TEXT_MARGIN, y, image.Color.from_rgb(50, 50, 80), thickness=1)
    y += 8

    y += _draw_line_h(img, TEXT_MARGIN, y, "PicoClaw:", image.Color.from_rgb(80, 200, 100))

    for line in window:
        if y + LINE_H > DISP_H:
            break
        y += _draw_line_h(img, TEXT_MARGIN, y, line, image.Color.from_rgb(220, 220, 190))

    return img


def render_streaming_frame(disp, question: str, answer: str, tool_names: list | None = None):
    ans = _strip_emoji(answer) if answer else ""
    q_lines, _ = _wrap(question, 2)
    y_est = 6 + LINE_H + len(q_lines) * LINE_H + 3 + 1 + 8 + LINE_H
    max_visible = max(1, (DISP_H - y_est - 4) // LINE_H)
    all_lines, _ = _wrap(ans) if ans else ([], False)
    window = all_lines[-max_visible:] if all_lines else []
    disp.display(_render_frame(question, window, tool_names))


class StreamingRenderer:
    def __init__(self, disp, question: str, line_delay: float = 0.8):
        self.disp = disp
        self.question = question
        self.line_delay = line_delay
        self._revealed = 0  # number of answer lines already shown
        self._last_lines: list[str] = []
        self._last_tools: list[str] | None = None
        q_lines, _ = _wrap(question, 2)
        y_est = 6 + LINE_H + len(q_lines) * LINE_H + 3 + 1 + 8 + LINE_H
        self._max_visible = max(1, (DISP_H - y_est - 4) // LINE_H)

    def _window(self, count: int) -> list[str]:
        end = min(count, len(self._last_lines))
        start = max(0, end - self._max_visible)
        return self._last_lines[start:end]

    def _draw(self, count: int, tool_names: list | None):
        frame = _render_frame(self.question, self._window(count), tool_names)
        self.disp.display(frame)

    async def update(self, answer: str, tool_names: list | None = None):
        ans = _strip_emoji(answer) if answer else ""
        all_lines, _ = _wrap(ans) if ans else ([], False)
        self._last_lines = all_lines
        self._last_tools = tool_names

        total = len(all_lines)
        if total == 0:
            self._revealed = 0
            self._draw(0, tool_names)
            return

        complete = total - 1

        while self._revealed < complete:
            self._revealed += 1
            self._draw(self._revealed + 1, tool_names)
            await asyncio.sleep(self.line_delay)

        self._draw(self._revealed + 1, tool_names)

    async def finalize(self, tool_names: list | None = None):
        if self._last_lines:
            self._revealed = len(self._last_lines)
        self._draw(self._revealed, tool_names if tool_names is not None else self._last_tools)
