import logging
import os

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_LEVEL = os.environ.get("LOG_LEVEL", "DEBUG").upper()


def setup_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL, logging.DEBUG),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------
DISP_W = 240
DISP_H = 240
ICON_PATH = "img/icon.png"

# ---------------------------------------------------------------------------
# SPI LCD (ST7789)
# ---------------------------------------------------------------------------
SPI_PORT = 1
SPI_DC = "A28"
SPI_RST = "A27"
SPI_BACKLIGHT = "A19"
SPI_SPEED_HZ = 50_000_000
SPI_ROTATION = 180

# ---------------------------------------------------------------------------
# GPIO
# ---------------------------------------------------------------------------
KEY_GPIO = 504
BACK_KEY_GPIO = 509
LED_ON_GPIO = 495
LED_OFF_GPIO = 498
KEY_ACTIVE_LOW = False
KEY_DEBOUNCE_MS = 50

# ---------------------------------------------------------------------------
# Fonts
# ---------------------------------------------------------------------------
FONT_PATH = "/maixapp/share/font/SourceHanSansCN-Regular.otf"
FONT_NAME = "sourcehansans"
FONT_SIZE = 14
FONT_NAME_LARGE = "sourcehansans17"
FONT_SIZE_LARGE = 17
FONT_NAME_ART = "sourcehansans_art"
FONT_SIZE_ART = 14

# ---------------------------------------------------------------------------
# Buddy layout (adapted for 240x240)
#   Buddy animation occupies the upper portion.
#   HUD / approval / info occupies the lower portion.
#   The split is at BUDDY_AREA_H.
# ---------------------------------------------------------------------------
BUDDY_AREA_H = 92
HUD_TOP = BUDDY_AREA_H

# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------
DATA_DIR = "/root/.cc_buddy"
STATS_PATH = os.path.join(DATA_DIR, "stats.json")
SETTINGS_PATH = os.path.join(DATA_DIR, "settings.json")

# ---------------------------------------------------------------------------
# Timing
# ---------------------------------------------------------------------------
SCREEN_OFF_MS = 30_000
TICK_MS = 200
LONG_PRESS_MS = 600

# ---------------------------------------------------------------------------
# UI layout — line heights derived from font size
#   FONT_SIZE 14 → draw height ~14px → line height 18px (14 + 4px gap)
#   FONT_SIZE_LARGE 17 → draw height ~17px → line height 22px
#   FONT_SIZE_ART 14 → draw height ~14px → line height 16px
# ---------------------------------------------------------------------------
UI_LH = 18
UI_LH_LARGE = 22
ART_LH = 16
TEXT_MARGIN = 8
MAX_TEXT_W = DISP_W - TEXT_MARGIN * 2
LINE_H = UI_LH
