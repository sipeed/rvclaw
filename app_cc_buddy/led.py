import asyncio
import os
import time
from contextlib import suppress

from config import LED_OFF_GPIO, LED_ON_GPIO


GPIO_BASE_PATH = "/sys/class/gpio"
GPIO_EXPORT_PATH = os.path.join(GPIO_BASE_PATH, "export")
GPIO_UNEXPORT_PATH = os.path.join(GPIO_BASE_PATH, "unexport")


class Led:
    """Control board LEDs via sysfs gpio.

    Board mapping:
      - LED_ON  -> gpio495
      - LED_OFF -> gpio498
    """

    def __init__(self, led_on_gpio: int = LED_ON_GPIO, led_off_gpio: int = LED_OFF_GPIO):
        self.led_on_gpio = led_on_gpio
        self.led_off_gpio = led_off_gpio

        self._on_path = os.path.join(GPIO_BASE_PATH, f"gpio{self.led_on_gpio}")
        self._off_path = os.path.join(GPIO_BASE_PATH, f"gpio{self.led_off_gpio}")

        self._on_value_path = os.path.join(self._on_path, "value")
        self._off_value_path = os.path.join(self._off_path, "value")
        self._on_value_fp = None
        self._off_value_fp = None

        self._setup_pinmux()
        self._setup_gpio(self.led_on_gpio)
        self._setup_gpio(self.led_off_gpio)
        self._open_value_files()

        self.set_off()

        self._blink_task = None

    @staticmethod
    def _setup_pinmux() -> None:
        from utils import DevMem
        with DevMem() as dm:
            dm.write(0x0300103C, 0x00000003)
            dm.write(0x03001908, 0x00000044)
            dm.write(0x03001068, 0x00000003)
            dm.write(0x03001934, 0x00000044)

    def _setup_gpio(self, gpio_num: int) -> None:
        gpio_path = os.path.join(GPIO_BASE_PATH, f"gpio{gpio_num}")
        direction_path = os.path.join(gpio_path, "direction")

        if not os.path.exists(gpio_path):
            with open(GPIO_EXPORT_PATH, "w", encoding="utf-8") as f:
                f.write(str(gpio_num))
            time.sleep(0.02)

        with open(direction_path, "w", encoding="utf-8") as f:
            f.write("out")

    def _open_value_files(self) -> None:
        self._on_value_fp = open(self._on_value_path, "w", encoding="utf-8")
        self._off_value_fp = open(self._off_value_path, "w", encoding="utf-8")

    @staticmethod
    def _write_value(fp, value: int) -> None:
        fp.seek(0)
        fp.write("1" if value else "0")
        fp.flush()

    def set_on(self) -> None:
        """Turn ON-state LED on, OFF-state LED off."""
        self._write_value(self._on_value_fp, 1)
        self._write_value(self._off_value_fp, 0)

    def set_off(self) -> None:
        """Turn OFF-state LED on, ON-state LED off."""
        self._write_value(self._on_value_fp, 0)
        self._write_value(self._off_value_fp, 1)

    def all_off(self) -> None:
        self._write_value(self._on_value_fp, 0)
        self._write_value(self._off_value_fp, 0)

    def blink(self, times: int = 3, interval: float = 0.2) -> None:
        self._write_value(self._off_value_fp, 0)
        for _ in range(max(0, times)):
            self._write_value(self._on_value_fp, 1)
            time.sleep(interval)
            self._write_value(self._on_value_fp, 0)
            time.sleep(interval)

    def start_blink(self, interval: float = 0.3) -> None:
        """Start async background blinking. Call stop_blink() to stop."""
        self.stop_blink()
        self._blink_task = asyncio.ensure_future(self._blink_loop(interval))

    async def _blink_loop(self, interval: float) -> None:
        self._write_value(self._off_value_fp, 0)
        try:
            while True:
                self._write_value(self._on_value_fp, 1)
                await asyncio.sleep(interval)
                self._write_value(self._on_value_fp, 0)
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            pass

    def stop_blink(self) -> None:
        """Stop background blinking if active."""
        if self._blink_task is not None and not self._blink_task.done():
            self._blink_task.cancel()
        self._blink_task = None

    def close(self, unexport: bool = False) -> None:
        self.all_off()

        for fp in (self._on_value_fp, self._off_value_fp):
            with suppress(Exception):
                if fp is not None and not fp.closed:
                    fp.close()

        if unexport:
            for gpio in (self.led_on_gpio, self.led_off_gpio):
                with suppress(Exception):
                    with open(GPIO_UNEXPORT_PATH, "w", encoding="utf-8") as f:
                        f.write(str(gpio))


__all__ = [
    "Led",
    "LED_ON_GPIO",
    "LED_OFF_GPIO",
]
