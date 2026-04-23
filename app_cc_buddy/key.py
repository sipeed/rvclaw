import os
import time
import threading

GPIO_BASE_PATH = "/sys/class/gpio"
GPIO_EXPORT_PATH = os.path.join(GPIO_BASE_PATH, "export")
GPIO_UNEXPORT_PATH = os.path.join(GPIO_BASE_PATH, "unexport")


class Key:
    DIRECTION_IN = "in"
    DIRECTION_OUT = "out"

    EDGE_NONE = "none"
    EDGE_RISING = "rising"
    EDGE_FALLING = "falling"
    EDGE_BOTH = "both"

    def __init__(self, gpio_num: int = 504, active_low: bool = False, debounce_ms: int = 20):
        self.gpio_num = gpio_num
        self.active_low = active_low
        self.debounce_ms = debounce_ms

        self._gpio_path = os.path.join(GPIO_BASE_PATH, f"gpio{self.gpio_num}")
        self._value_path = os.path.join(self._gpio_path, "value")
        self._direction_path = os.path.join(self._gpio_path, "direction")
        self._edge_path = os.path.join(self._gpio_path, "edge")
        self._active_low_path = os.path.join(self._gpio_path, "active_low")

        self._callback = None
        self._watch_thread = None
        self._running = False

        from utils import DevMem
        with DevMem() as dm:
            dm.write(0x03001060, 0x00000003)
            dm.write(0x0300192C, 0x00000044)
            dm.write(0x03001074, 0x00000003)
            dm.write(0x03001940, 0x00000044)

        self._export()
        self._set_direction(self.DIRECTION_IN)
        self._set_active_low(self.active_low)

    def _write(self, path: str, value: str) -> None:
        with open(path, "w") as f:
            f.write(value)

    def _read(self, path: str) -> str:
        with open(path, "r") as f:
            return f.read().strip()

    def _export(self) -> None:
        if not os.path.exists(self._gpio_path):
            self._write(GPIO_EXPORT_PATH, str(self.gpio_num))
            timeout = 1.0
            start = time.time()
            while not os.path.exists(self._value_path):
                if time.time() - start > timeout:
                    raise RuntimeError(f"Timeout while exporting GPIO{self.gpio_num}. Please check kernel support.")
                time.sleep(0.01)

    def _unexport(self) -> None:
        if os.path.exists(self._gpio_path):
            self._write(GPIO_UNEXPORT_PATH, str(self.gpio_num))

    def _set_direction(self, direction: str) -> None:
        self._write(self._direction_path, direction)

    def _set_active_low(self, active_low: bool) -> None:
        self._write(self._active_low_path, "1" if active_low else "0")

    def _set_edge(self, edge: str) -> None:
        self._write(self._edge_path, edge)

    def read_raw(self) -> int:
        return int(self._read(self._value_path))

    def is_pressed(self) -> bool:
        return self.read_raw() == 0

    def wait_for_press(self, timeout: float = None) -> bool:
        start = time.time()
        while True:
            if self.is_pressed():
                time.sleep(self.debounce_ms / 1000.0)
                if self.is_pressed():
                    return True
            if timeout is not None and (time.time() - start) >= timeout:
                return False
            time.sleep(0.005)

    def wait_for_release(self, timeout: float = None) -> bool:
        start = time.time()
        while True:
            if not self.is_pressed():
                time.sleep(self.debounce_ms / 1000.0)
                if not self.is_pressed():
                    return True
            if timeout is not None and (time.time() - start) >= timeout:
                return False
            time.sleep(0.005)

    def register_callback(self, callback, edge: str = EDGE_FALLING) -> None:
        self._callback = callback
        self._set_edge(edge)
        self._running = True
        self._watch_thread = threading.Thread(
            target=self._poll_loop, daemon=True, name=f"key-gpio{self.gpio_num}"
        )
        self._watch_thread.start()

    def unregister_callback(self) -> None:
        self._running = False
        if self._watch_thread and self._watch_thread.is_alive():
            self._watch_thread.join(timeout=1.0)
        self._set_edge(self.EDGE_NONE)
        self._callback = None

    def _poll_loop(self) -> None:
        import select

        fd = os.open(self._value_path, os.O_RDONLY | os.O_NONBLOCK)
        try:
            os.lseek(fd, 0, os.SEEK_SET)
            last_stable = int(os.read(fd, 1).decode().strip())

            p = select.poll()
            p.register(fd, select.POLLPRI | select.POLLERR)
            p.poll(0)

            while self._running:
                events = p.poll(200)
                if not events:
                    continue

                time.sleep(self.debounce_ms / 1000.0)

                while True:
                    pending = p.poll(0)
                    if not pending:
                        break
                    os.lseek(fd, 0, os.SEEK_SET)
                    os.read(fd, 1)

                os.lseek(fd, 0, os.SEEK_SET)
                stable = int(os.read(fd, 1).decode().strip())

                if stable != last_stable:
                    last_stable = stable
                    if self._callback:
                        self._callback(self.gpio_num, stable)
        finally:
            os.close(fd)

    def close(self) -> None:
        self.unregister_callback()
        self._unexport()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __repr__(self):
        return (
            f"<Key gpio={self.gpio_num} "
            f"active_low={self.active_low} "
            f"debounce={self.debounce_ms}ms>"
        )
