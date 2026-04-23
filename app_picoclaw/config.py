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
# Default config
# ---------------------------------------------------------------------------
DISP_W = 240
DISP_H = 240
ICON_PATH = "img/icon.png"

# ---------------------------------------------------------------------------
# SPI LCD (ST7789)
# ---------------------------------------------------------------------------
SPI_PORT = 4
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
FONT_SIZE = 17
FONT_NAME_LARGE = "sourcehansans20"
FONT_SIZE_LARGE = 20

# ---------------------------------------------------------------------------
# Audio
# ---------------------------------------------------------------------------
SAMPLE_RATE = 16000
AUDIO_CHANNELS = 1
RECORDER_VOLUME = 100


def _env_bool(name: str, default: bool = False) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in {"1"}

TEST_MODE = _env_bool("TEST_MODE", default=False)
IPERF_SERVER = os.environ.get("IPERF_SERVER", "").strip()

# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------
AGENT_TIMEOUT = 120.0

# ---------------------------------------------------------------------------
# UI layout
# ---------------------------------------------------------------------------
LINE_H = 24        # Line height
TEXT_MARGIN = 8     # Left/right text margin
MAX_TEXT_W = DISP_W - TEXT_MARGIN * 2   # Max pixel width per line
