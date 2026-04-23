import sys
import numbers
import spidev
import numpy as np
from maix import image, gpio, pinmap, time, err

ST7789_NOP = 0x00
ST7789_SWRESET = 0x01
ST7789_RDDID = 0x04
ST7789_RDDST = 0x09
ST7789_SLPIN = 0x10
ST7789_SLPOUT = 0x11
ST7789_PTLON = 0x12
ST7789_NORON = 0x13
ST7789_INVOFF = 0x20
ST7789_INVON = 0x21
ST7789_DISPOFF = 0x28
ST7789_DISPON = 0x29
ST7789_CASET = 0x2A
ST7789_RASET = 0x2B
ST7789_RAMWR = 0x2C
ST7789_RAMRD = 0x2E
ST7789_PTLAR = 0x30
ST7789_MADCTL = 0x36
ST7789_COLMOD = 0x3A
ST7789_FRMCTR1 = 0xB1
ST7789_FRMCTR2 = 0xB2
ST7789_FRMCTR3 = 0xB3
ST7789_INVCTR = 0xB4
ST7789_DISSET5 = 0xB6
ST7789_GCTRL = 0xB7
ST7789_GTADJ = 0xB8
ST7789_VCOMS = 0xBB
ST7789_LCMCTRL = 0xC0
ST7789_IDSET = 0xC1
ST7789_VDVVRHEN = 0xC2
ST7789_VRHS = 0xC3
ST7789_VDVS = 0xC4
ST7789_VMCTR1 = 0xC5
ST7789_FRCTRL2 = 0xC6
ST7789_CABCCTRL = 0xC7
ST7789_RDID1 = 0xDA
ST7789_RDID2 = 0xDB
ST7789_RDID3 = 0xDC
ST7789_RDID4 = 0xDD
ST7789_GMCTRP1 = 0xE0
ST7789_GMCTRN1 = 0xE1
ST7789_PWCTR6 = 0xFC


class ST7789:

    def __init__(self, port: int, dc: str, soft_cs: str = None, backlight: str = None,
                 rst: str = None, width: int = 240, height: int = 240, rotation: int = 90,
                 invert: bool = True, spi_speed_hz: int = 4000000,
                 offset_left: int = 0, offset_top: int = 0, spi_pins: dict = None,
                 spidev_bus: int = 1, spidev_cs: int = 0, spi_mode: int = 0):

        if rotation not in [0, 90, 180, 270]:
            raise ValueError(f"Invalid rotation {rotation}. Must be 0, 90, 180, or 270.")
        if width != height and rotation in [90, 270]:
            raise ValueError(f"Invalid rotation {rotation} for {width}x{height} resolution.")

        from utils import DevMem
        with DevMem() as dm:
            dm.write(0x03001050, 0x3)
            dm.write(0x0300105C, 0x3)
            dm.write(0x03001060, 0x3)
            dm.write(0x03001054, 0x3)

            dm.write(0x0300191C, 0x40)
            dm.write(0x03001928, 0x40)
            dm.write(0x0300192C, 0x40)
            dm.write(0x03001920, 0x40)

            dm.write(0x03001124, 0x6)
            dm.write(0x03001128, 0x6)
            dm.write(0x0300112C, 0x6)
            dm.write(0x03001130, 0x6)

            val = dm.read(0x03009804)
            dm.write(0x03009804, val | 0x1)

            val = dm.read(0x03009808)
            dm.write(0x03009808, (val & ~0x1F) | 0x1)

            val = dm.read(0x03009800)
            dm.write(0x03009800, val | (1 << 2))

            import time as _time; _time.sleep(0.001)

            val = dm.read(0x0300907C)
            dm.write(0x0300907C, (val & ~(0x1F << 8)) | (5 << 8))

            val = dm.read(0x03009078)
            dm.write(0x03009078, (val & ~0xFFF) | 0xF00)

            dm.write(0x03009074, 0x606)
            dm.write(0x03009070, 0x606)

        self._port = port
        self._spidev_bus = spidev_bus
        self._spidev_cs = spidev_cs
        self._spi_mode = spi_mode
        self._soft_cs = soft_cs
        self._spi_pins = spi_pins

        self._spi = spidev.SpiDev()
        self._spi.open(self._spidev_bus, self._spidev_cs)
        self._spi.max_speed_hz = spi_speed_hz
        self._spi.mode = self._spi_mode
        self._spi.bits_per_word = 8

        if 0 != pinmap.set_pin_function(dc, f"GPIO{dc}"):
            raise RuntimeError(f"Failed to set DC pin {dc} to GPIO")
        self._dc = gpio.GPIO(dc, gpio.Mode.OUT)
        self._dc.value(0)

        self._rst = None
        if rst is not None:
            if 0 != pinmap.set_pin_function(rst, f"GPIO{rst}"):
                raise RuntimeError(f"Failed to set Reset pin {rst} to GPIO")
            self._rst = gpio.GPIO(rst, gpio.Mode.OUT)
            self.reset()

        self._backlight = None
        if backlight is not None:
            if 0 != pinmap.set_pin_function(backlight, f"GPIO{backlight}"):
                raise RuntimeError(f"Failed to set Backlight pin {backlight} to GPIO")
            self._backlight = gpio.GPIO(backlight, gpio.Mode.OUT)
            self._backlight.value(0)

        self._width = width
        self._height = height
        self._rotation = rotation
        self._invert = invert
        self._prev_frame = None

        _auto_offset = {
            0:   (0,  0),
            90:  (0,  0),
            180: (0,  80),
            270: (80, 0),
        }.get(rotation, (0, 0))
        self._offset_left = offset_left + _auto_offset[0]
        self._offset_top  = offset_top  + _auto_offset[1]

        self._init()

    def send(self, data, is_data: bool = True, chunk_size: int = 4096):
        self._dc.value(1 if is_data else 0)

        if isinstance(data, numbers.Number):
            self._spi.writebytes2(bytes([data & 0xFF]))
            return
        if not isinstance(data, (bytes, bytearray)):
            data = bytes(data)

        for start in range(0, len(data), chunk_size):
            end = min(start + chunk_size, len(data))
            self._spi.writebytes2(data[start:end])

    def command(self, data):
        self.send(data, False)

    def data(self, data):
        self.send(data, True)

    def _write_register(self, cmd: int, data: list = None):
        self.command(cmd)
        if data is not None:
            self.data(data)

    def set_backlight(self, value: int):
        if self._backlight is not None:
            self._backlight.value(not value)

    @property
    def width(self) -> int:
        return self._width if self._rotation in [0, 180] else self._height

    @property
    def height(self) -> int:
        return self._height if self._rotation in [0, 180] else self._width

    def reset(self):
        if self._rst is not None:
            self._rst.value(1)
            time.sleep_ms(50)
            self._rst.value(0)
            time.sleep_ms(50)
            self._rst.value(1)
            time.sleep_ms(50)

    def _init(self):
        self.set_backlight(0)
        self.command(ST7789_SLPOUT)
        time.sleep_ms(120)

        init_sequence = [
            (ST7789_FRMCTR2, [0x1F, 0x1F, 0x00, 0x33, 0x33]),
            (ST7789_MADCTL, [{
                0:   0x00,
                90:  0x60,
                180: 0xC0,
                270: 0xA0,
            }.get(self._rotation, 0x00)]),
            (ST7789_COLMOD, [0x05]),
            (ST7789_GCTRL, [0x00]),
            (ST7789_VCOMS, [0x36]),
            (ST7789_LCMCTRL, [0x2C]),
            (ST7789_VDVVRHEN, [0x01]),
            (ST7789_VRHS, [0x13]),
            (ST7789_VDVS, [0x20]),
            (ST7789_FRCTRL2, [0x13]),
            (0xD6, [0xA1]),
            (0xD0, [0xA4, 0xA1]),
            (ST7789_GMCTRP1, [0xF0, 0x08, 0x0E, 0x09, 0x08, 0x04, 0x2F, 0x33, 0x45, 0x36, 0x13, 0x12, 0x2A, 0x2D]),
            (ST7789_GMCTRN1, [0xF0, 0x0E, 0x12, 0x0C, 0x0A, 0x15, 0x2E, 0x32, 0x44, 0x39, 0x17, 0x18, 0x2B, 0x2F]),
            (0xE4, [0x1D, 0x00, 0x00])
        ]

        for cmd, cmd_data in init_sequence:
            self._write_register(cmd, cmd_data)

        self.command(ST7789_INVON if self._invert else ST7789_INVOFF)
        self.command(ST7789_SLPOUT)
        self.command(ST7789_DISPON)
        time.sleep_ms(100)

    def set_window(self, x0: int = 0, y0: int = 0, x1: int = None, y1: int = None):
        if x1 is None: x1 = self._width - 1
        if y1 is None: y1 = self._height - 1

        y0 += self._offset_top
        y1 += self._offset_top
        x0 += self._offset_left
        x1 += self._offset_left

        self._write_register(ST7789_CASET, [(x0 >> 8) & 0xFF, x0 & 0xFF, (x1 >> 8) & 0xFF, x1 & 0xFF])
        self._write_register(ST7789_RASET, [(y0 >> 8) & 0xFF, y0 & 0xFF, (y1 >> 8) & 0xFF, y1 & 0xFF])
        self.command(ST7789_RAMWR)

    def _to_rgb565(self, img) -> np.ndarray:
        if isinstance(img, image.Image):
            img_bytes = img.to_bytes()
            np_img = np.frombuffer(img_bytes, dtype=np.uint8).reshape(
                (img.height(), img.width(), 3)
            )
        elif isinstance(img, np.ndarray):
            np_img = img
        else:
            np_img = np.array(img.convert('RGB'))

        rgb16 = np_img.astype(np.uint16)
        return ((rgb16[..., 0] & 0xF8) << 8) | ((rgb16[..., 1] & 0xFC) << 3) | (rgb16[..., 2] >> 3)

    def _region_to_bytes(self, region: np.ndarray) -> bytes:
        flat = region.reshape(-1)
        return flat.byteswap().tobytes()

    def image_to_data(self, img) -> bytes:
        return self._region_to_bytes(self._to_rgb565(img))

    def display(self, img):
        rgb565 = self._to_rgb565(img)

        if self._prev_frame is None:
            x0, y0 = 0, 0
            x1, y1 = self._width - 1, self._height - 1
        else:
            diff = rgb565 != self._prev_frame
            if not diff.any():
                return

            rows = np.where(diff.any(axis=1))[0]
            cols = np.where(diff.any(axis=0))[0]
            y0, y1 = int(rows[0]), int(rows[-1])
            x0, x1 = int(cols[0]), int(cols[-1])

            if (x1 - x0 + 1) % 2 != 0:
                x1 = min(x1 + 1, self._width - 1)

        if self._prev_frame is None:
            self._prev_frame = rgb565.copy()
        else:
            self._prev_frame[y0:y1 + 1, x0:x1 + 1] = rgb565[y0:y1 + 1, x0:x1 + 1]

        pixelbytes = self._region_to_bytes(rgb565[y0:y1 + 1, x0:x1 + 1])
        self.set_window(x0, y0, x1, y1)
        self._dc.value(1)
        self._spi.writebytes2(pixelbytes)

    def turn_off(self):
        self.set_backlight(0)
        self.command(ST7789_DISPOFF)
        self.command(ST7789_SLPIN)
