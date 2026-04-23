import time
import logging
from dataclasses import dataclass
from typing import Callable

try:
    from maix import image
except ImportError:
    image = None

from config import DISP_W, BUDDY_AREA_H, FONT_NAME_ART, FONT_SIZE_ART, FONT_PATH

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Geometry — adapted from buddy.cpp for 240x240 display
# ---------------------------------------------------------------------------
BUDDY_X_CENTER = DISP_W // 2
BUDDY_CANVAS_W = DISP_W
BUDDY_Y_BASE = 12
BUDDY_Y_OVERLAY = 8

# ---------------------------------------------------------------------------
# Colors (RGB888 tuples) — converted from RGB565
# ---------------------------------------------------------------------------
def _rgb565_to_888(c: int) -> tuple[int, int, int]:
    r = ((c >> 11) & 0x1F) << 3
    g = ((c >> 5) & 0x3F) << 2
    b = (c & 0x1F) << 3
    return (r, g, b)


BUDDY_BG = (0, 0, 0)
BUDDY_HEART = _rgb565_to_888(0xF810)
BUDDY_DIM = _rgb565_to_888(0x8410)
BUDDY_YEL = _rgb565_to_888(0xFFE0)
BUDDY_WHITE = (255, 255, 255)
BUDDY_CYAN = _rgb565_to_888(0x07FF)
BUDDY_GREEN = _rgb565_to_888(0x07E0)
BUDDY_PURPLE = _rgb565_to_888(0xA01F)
BUDDY_RED = _rgb565_to_888(0xF800)
BUDDY_BLUE = _rgb565_to_888(0x041F)

COLOR_CAPYBARA = _rgb565_to_888(0xC2A6)
COLOR_ROBOT = _rgb565_to_888(0xC618)

# ---------------------------------------------------------------------------
# Species data structure
# ---------------------------------------------------------------------------
StateFn = Callable[["BuddyRenderer", int], None]


@dataclass
class Species:
    name: str
    body_color: tuple[int, int, int]
    states: list[StateFn]


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------
class BuddyRenderer:
    def __init__(self):
        self._species_table: list[Species] = []
        self._current_idx: int = 0
        self._tick_count: int = 0
        self._next_tick_at: float = 0
        self._last_drawn_state: int = -1
        self._last_drawn_species: int = -1
        self._scale: int = 1
        self._img = None
        self._char_w: int = 9
        self._char_h: int = 16
        self._font_ready: bool = False

    def init_font(self) -> None:
        if image is None:
            return
        image.load_font(FONT_NAME_ART, FONT_PATH, size=FONT_SIZE_ART)
        image.set_default_font(FONT_NAME_ART)
        w, h = image.string_size("M")
        self._char_w = w
        self._char_h = h + 2
        self._font_ready = True
        logger.info("Art font: char_w=%d char_h=%d", self._char_w, self._char_h)

    def _use_art_font(self) -> None:
        if self._font_ready and image is not None:
            image.set_default_font(FONT_NAME_ART)

    def register_species(self, species: Species) -> None:
        self._species_table.append(species)

    @property
    def species_count(self) -> int:
        return len(self._species_table)

    @property
    def species_idx(self) -> int:
        return self._current_idx

    @property
    def species_name(self) -> str:
        if not self._species_table:
            return "none"
        return self._species_table[self._current_idx].name

    def set_species_idx(self, idx: int) -> None:
        if 0 <= idx < len(self._species_table):
            self._current_idx = idx

    def set_species_by_name(self, name: str) -> None:
        for i, sp in enumerate(self._species_table):
            if sp.name == name:
                self._current_idx = i
                return

    def next_species(self) -> None:
        if self._species_table:
            self._current_idx = (self._current_idx + 1) % len(self._species_table)

    def invalidate(self) -> None:
        self._last_drawn_state = -1

    def set_peek(self, peek: bool) -> None:
        s = 1 if peek else 1
        if s != self._scale:
            self._scale = s
            self.invalidate()

    def is_tick_due(self) -> bool:
        return time.time() >= self._next_tick_at

    def tick(self, img, persona_state: int) -> bool:
        now = time.time()
        ticked = False
        if now >= self._next_tick_at:
            self._next_tick_at = now + 0.2
            self._tick_count += 1
            ticked = True

        if persona_state > 6:
            persona_state = 1

        if (not ticked
                and persona_state == self._last_drawn_state
                and self._current_idx == self._last_drawn_species):
            return False

        self._last_drawn_state = persona_state
        self._last_drawn_species = self._current_idx
        self._img = img

        self._use_art_font()

        img.draw_rect(0, 0, BUDDY_CANVAS_W, BUDDY_AREA_H,
                       image.Color.from_rgb(*BUDDY_BG), thickness=-1)

        if not self._species_table:
            return True

        sp = self._species_table[self._current_idx]
        if persona_state < len(sp.states) and sp.states[persona_state]:
            sp.states[persona_state](self, self._tick_count)

        return True

    # --- Rendering helpers (called by species state functions) ---

    def print_sprite(self, lines: list[str], n_lines: int, y_offset: int,
                     color: tuple[int, int, int], x_off: int = 0) -> None:
        if self._img is None:
            return
        img = self._img
        cw = self._char_w
        ch = self._char_h
        col = image.Color.from_rgb(*color)
        y_base = BUDDY_Y_BASE

        for i in range(n_lines):
            line = lines[i]
            if not line.strip():
                continue
            total_w = len(line) * cw
            start_x = BUDDY_X_CENTER - total_w // 2 + x_off
            y = y_base + y_offset + i * ch
            for j, c in enumerate(line):
                if c == ' ':
                    continue
                img.draw_string(start_x + j * cw, y, c, col)

    def print_at(self, x: int, y: int, text: str, color: tuple[int, int, int]) -> None:
        if self._img is None or not text:
            return
        cw = self._char_w
        px = BUDDY_X_CENTER + (x - BUDDY_X_CENTER)
        py = y
        col = image.Color.from_rgb(*color)
        for j, c in enumerate(text):
            if c == ' ':
                continue
            self._img.draw_string(px + j * cw, py, c, col)


# Global renderer instance
renderer = BuddyRenderer()
