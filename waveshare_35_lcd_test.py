"""Demo script for Waveshare 3.5" SPI LCD on Raspberry Pi Pico.

The wiring follows the mapping:
    LCD VCC  -> VSYS
    LCD GND  -> GND
    LCD SDIO_CLK -> GP5 (not used here)
    LCD LCD_DC   -> GP8
    LCD LCD_CS   -> GP9
    LCD LCD_CLK  -> GP10
    LCD MOSI     -> GP11
    LCD MISO     -> GP12 (not used here)
    LCD LCD_BL   -> GP13
    LCD LCD_RST  -> GP15
    LCD TP_CS    -> GP16 (not used here)
    LCD TP_IRQ   -> GP17 (not used here)
    LCD SDIO_CMD -> GP18 (not used here)
    LCD D0-D3    -> GP19-GP22 (not used here)

Copy this file to the Pico (running MicroPython 1.19+), then import and run
```
import waveshare_35_lcd_test
waveshare_35_lcd_test.main()
```
The script will cycle background colours and render a simple test pattern
with text so you can verify that the panel, SPI wiring, and backlight work.
"""

from array import array
import framebuf
import struct
import time

from machine import Pin, SPI


class ILI9488:
    """Minimal driver for the Waveshare 3.5" (ILI9488) SPI LCD."""

    _INIT_CMDS = (
        (0xE0, b"\x00\x03\x09\x08\x16\x0A\x3F\x78\x4C\x09\x0A\x08\x16\x1A\x0F"),
        (0xE1, b"\x00\x16\x19\x03\x0F\x05\x32\x45\x46\x04\x0E\x0D\x35\x37\x0F"),
        (0xC0, b"\x17\x15"),
        (0xC1, b"\x41"),
        (0xC5, b"\x00\x12\x80"),
        (0x36, b"\x48"),  # Memory access control: MX + BGR
        (0x3A, b"\x55"),  # 16-bit colour (RGB565)
        (0xB0, b"\x00"),
        (0xB1, b"\xA0"),
        (0xB4, b"\x02"),
        (0xB6, b"\x02\x02"),
        (0xE9, b"\x00"),
        (0xF7, b"\xA9\x51\x2C\x82"),
        (0x11, None),  # Exit sleep
        ("delay", 0.12),
        (0x29, None),  # Display ON
        ("delay", 0.02),
    )

    def __init__(self, spi, dc, cs, rst, width=480, height=320):
        self.spi = spi
        self.dc = dc
        self.cs = cs
        self.rst = rst
        self.width = width
        self.height = height

        self.dc.init(Pin.OUT, value=0)
        self.cs.init(Pin.OUT, value=1)
        self.rst.init(Pin.OUT, value=1)

        self._hardware_reset()
        self._init_display()

    def _hardware_reset(self):
        self.rst.value(0)
        time.sleep_ms(20)
        self.rst.value(1)
        time.sleep_ms(120)

    def _write_cmd(self, cmd):
        self.dc.value(0)
        self.cs.value(0)
        self.spi.write(bytearray([cmd]))
        self.cs.value(1)

    def _write_data(self, data):
        self.dc.value(1)
        self.cs.value(0)
        self.spi.write(data)
        self.cs.value(1)

    def _init_display(self):
        for entry, payload in self._INIT_CMDS:
            if entry == "delay":
                time.sleep(payload)
                continue
            self._write_cmd(entry)
            if payload:
                self._write_data(payload)

    def set_window(self, x0, y0, x1, y1):
        self._write_cmd(0x2A)
        self._write_data(struct.pack(">HH", x0, x1))
        self._write_cmd(0x2B)
        self._write_data(struct.pack(">HH", y0, y1))
        self._write_cmd(0x2C)

    def blit(self, buffer, x=0, y=0, w=None, h=None):
        if w is None:
            w = self.width
        if h is None:
            h = self.height
        self.set_window(x, y, x + w - 1, y + h - 1)
        self.dc.value(1)
        self.cs.value(0)
        self.spi.write(buffer)
        self.cs.value(1)

    def fill(self, colour):
        line = array("H", [colour] * self.width)
        self.set_window(0, 0, self.width - 1, self.height - 1)
        self.dc.value(1)
        self.cs.value(0)
        row_bytes = memoryview(line)
        for _ in range(self.height):
            self.spi.write(row_bytes)
        self.cs.value(1)


def main():
    spi = SPI(1, baudrate=40_000_000, polarity=0, phase=0, sck=Pin(10), mosi=Pin(11), miso=Pin(12))
    dc = Pin(8, Pin.OUT)
    cs = Pin(9, Pin.OUT)
    rst = Pin(15, Pin.OUT)
    bl = Pin(13, Pin.OUT)

    bl.value(1)  # Enable backlight

    lcd = ILI9488(spi, dc, cs, rst)

    colours = {
        "CZERWONY": 0xF800,
        "ZIELONY": 0x07E0,
        "NIEBIESKI": 0x001F,
        "BIAŁY": 0xFFFF,
        "CZARNY": 0x0000,
    }

    for name, value in colours.items():
        lcd.fill(value)
        time.sleep(0.4)

    buffer = bytearray(lcd.width * lcd.height * 2)
    fb = framebuf.FrameBuffer(buffer, lcd.width, lcd.height, framebuf.RGB565)

    fb.fill(colours["CZARNY"])

    fb.fill_rect(0, 0, lcd.width, 40, colours["NIEBIESKI"])
    fb.text("Waveshare 3.5\" LCD", 10, 12, colours["BIAŁY"])

    fb.fill_rect(0, lcd.height - 60, lcd.width, 60, colours["ZIELONY"])
    fb.text("Raspberry Pi Pico", 10, lcd.height - 50, colours["CZARNY"])
    fb.text("Test ekranu", 10, lcd.height - 30, colours["CZARNY"])

    for i, (name, value) in enumerate(colours.items()):
        fb.fill_rect(40 + i * 80, 80, 60, 120, value)
        fb.text(name, 40 + i * 80 - 10, 210, colours["BIAŁY"] if value != colours["BIAŁY"] else colours["CZARNY"])

    fb.text("Dotknij ekran (jeśli masz kontroler dotyku)", 10, 250, colours["BIAŁY"])
    fb.text("Aby zakończyć, naciśnij Ctrl+C", 10, 270, colours["BIAŁY"])

    lcd.blit(buffer)

    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()
