"""
easy_epd

Speeds up the epd operations by implementing a more efficient getbuffer implementation.

Also, the methods displayPartial and displayPartBaseImage are much faster.

By default the module auto initializes the display, although that can be disabled.

The method display_image allows a program to show an image without explicitily creating a buffer.
It is also possible to specify whether the image should be normal displayed normal or upside down.

Finally, the new_image method can be used to get a monochrome image of the right size, either
horizontal or vertical.

The driver has to be specified in the initialization of EPD, e.g. 
    epd = easy_epd.EPD("epd2in13_V2")

If run on other hardware than a Raspberry Pi, the output will be shown via the .show() method.

The easy_epd module doesn't need epdconfig.py file.


version 0.0.4  2021-04-21
=========================
When there is no change in the buffer passed to displayPartial, that buffer is written at most three times.
The same holds for equal images passed to display_image.
That also meand that in display_image any repeat of more than 3 is essentially (although not explicitely) 3.


version 0.0.3  2021-04-20
=========================
When emulated, all methods of EPD are supported, although most of them are just dummy.


version 0.0.2  2021-04-19
=========================
On non Raspberry Pi's the e-ink display is dynamically emulated.
This includes the ghosting effect when going from black to white.


version 0.0.1  2021-04-18
=========================
Specification of the driver is changed.
The file epdconfig.sys is no longer required.
On non Raspberry Pi's the image will be shown (emulated)


version 0.0.0  2021-04-17
=========================
Initial version
"""
from PIL import Image
import sys
import importlib
import types
import os
import logging
import time

HAS_EPD = False
try:
    import spidev
    has_spidev = True
except ImportError:
    has_spidev = False

if has_spidev:
    try:
        spi = spidev.SpiDev()
        spi.open(0,0)
        HAS_EPD = True
    except FileNotFoundError:
        pass
else:
    find_dirs = [os.path.dirname(os.path.realpath(__file__)), "/usr/local/lib", "/usr/lib"]
    for find_dir in find_dirs:
        so_filename = os.path.join(find_dir, "sysfs_software_spi.so")
        if os.path.exists(so_filename):
            HAS_EPD = True
            break


class DummyModule:
    pass


class RaspberryPi:
    # Pin definition
    RST_PIN = 17
    DC_PIN = 25
    CS_PIN = 8
    BUSY_PIN = 24

    def __init__(self):
        import spidev
        import RPi.GPIO

        self.GPIO = RPi.GPIO
        self.SPI = spidev.SpiDev()

    def digital_write(self, pin, value):
        self.GPIO.output(pin, value)

    def digital_read(self, pin):
        return self.GPIO.input(pin)

    def delay_ms(self, delaytime):
        time.sleep(delaytime / 1000.0)

    def spi_writebyte(self, data):
        self.SPI.writebytes(data)

    def spi_writebyte2(self, data):
        self.SPI.writebytes2(data)

    def module_init(self):
        self.GPIO.setmode(self.GPIO.BCM)
        self.GPIO.setwarnings(False)
        self.GPIO.setup(self.RST_PIN, self.GPIO.OUT)
        self.GPIO.setup(self.DC_PIN, self.GPIO.OUT)
        self.GPIO.setup(self.CS_PIN, self.GPIO.OUT)
        self.GPIO.setup(self.BUSY_PIN, self.GPIO.IN)

        # SPI device, bus = 0, device = 0
        self.SPI.open(0, 0)
        self.SPI.max_speed_hz = 4000000
        self.SPI.mode = 0b00
        return 0

    def module_exit(self):
        logging.debug("spi end")
        self.SPI.close()

        logging.debug("close 5V, Module enters 0 power consumption ...")
        self.GPIO.output(self.RST_PIN, 0)
        self.GPIO.output(self.DC_PIN, 0)

        self.GPIO.cleanup()


class JetsonNano:
    # Pin definition
    RST_PIN = 17
    DC_PIN = 25
    CS_PIN = 8
    BUSY_PIN = 24

    def __init__(self):
        import ctypes

        find_dirs = [os.path.dirname(os.path.realpath(__file__)), "/usr/local/lib", "/usr/lib"]
        self.SPI = None
        for find_dir in find_dirs:
            so_filename = os.path.join(find_dir, "sysfs_software_spi.so")
            if os.path.exists(so_filename):
                self.SPI = ctypes.cdll.LoadLibrary(so_filename)
                break
        if self.SPI is None:
            raise RuntimeError("Cannot find sysfs_software_spi.so")

        import Jetson.GPIO

        self.GPIO = Jetson.GPIO

    def digital_write(self, pin, value):
        self.GPIO.output(pin, value)

    def digital_read(self, pin):
        return self.GPIO.input(self.BUSY_PIN)

    def delay_ms(self, delaytime):
        time.sleep(delaytime / 1000.0)

    def spi_writebyte(self, data):
        self.SPI.SYSFS_software_spi_transfer(data[0])

    def module_init(self):
        self.GPIO.setmode(self.GPIO.BCM)
        self.GPIO.setwarnings(False)
        self.GPIO.setup(self.RST_PIN, self.GPIO.OUT)
        self.GPIO.setup(self.DC_PIN, self.GPIO.OUT)
        self.GPIO.setup(self.CS_PIN, self.GPIO.OUT)
        self.GPIO.setup(self.BUSY_PIN, self.GPIO.IN)
        self.SPI.SYSFS_software_spi_begin()
        return 0

    def module_exit(self):
        logging.debug("spi end")
        self.SPI.SYSFS_software_spi_end()

        logging.debug("close 5V, Module enters 0 power consumption ...")
        self.GPIO.output(self.RST_PIN, 0)
        self.GPIO.output(self.DC_PIN, 0)

        self.GPIO.cleanup()


if HAS_EPD:
    if os.path.exists("/sys/bus/platform/drivers/gpiomem-bcm2835"):
        implementation = RaspberryPi()
    else:
        implementation = JetsonNano()

sys.modules["epdconfig"] = DummyModule()
if HAS_EPD:
    for func in [x for x in dir(implementation) if not x.startswith("_")]:
        setattr(sys.modules["epdconfig"], func, getattr(implementation, func))


if True:  # to prevent flake8 error
    import epdconfig


class EPD:
    """
    creates a EDP instannce

    Parameters
    ----------
    module_name : str
        name of the module (without path and extension) to be used

    auto_init : str
        if True (default), issues required
            self.init(self.FULL_UPDATE)
            self.init(self.PART_UPDATE)
        automatically.
        Otherwise, this has to be done explicitely later.
    """

    def __init__(self, module_name, auto_init=True):

        epdx = importlib.import_module(module_name)
        for v in dir(epdx.EPD):
            if not (v.startswith("__") and v.endswith("__")):
                if not hasattr(self, v) or (HAS_EPD and v not in ("getbuffer", "displayPartial", "displayPartBase")):
                    if callable(getattr(epdx.EPD, v)):
                        setattr(self, v, types.MethodType(getattr(epdx.EPD, v), self))
                    else:
                        setattr(self, v, getattr(epdx.EPD, v))

        setattr(self, "org__init__", types.MethodType(getattr(epdx.EPD, "__init__"), self))

        self.last_buffer = []
        self.last_buffer_count = 0

        if HAS_EPD:
            self.org__init__()

            if auto_init:
                self.init(self.FULL_UPDATE)
                self.init(self.PART_UPDATE)
        else:
            self.width = getattr(epdx, "EPD_WIDTH")
            self.height = getattr(epdx, "EPD_HEIGHT")
            global tkinter
            import tkinter

            global ImageTk
            from PIL import ImageTk

            self.root = tkinter.Tk()
            self.root.title(module_name)
            self.canvas = tkinter.Canvas(self.root, width=self.height, height=self.width)
            self.canvas.configure(background="white")
            self.canvas.pack()
            self.root.update()
            self.last_level = {}
            for x in range(self.height):
                for y in range(self.width):
                    self.last_level[x, y] = 255
            show_image = Image.new("RGBA", (self.height, self.width))
            photo_image = ImageTk.PhotoImage(show_image)

            self.co = self.canvas.create_image(0, 0, image=photo_image, anchor=tkinter.NW)

    def reset(self):
        self.Clear(255)

    def send_command(self, command):
        pass

    def send_data(self, data):
        pass

    def ReadBusy(self):
        pass

    def TurnOnDisplay(self):
        pass

    def TurnOnDisplayPart(self):
        pass

    def init(self, update):
        self.Clear(255)

    def display(self, image):
        return self.display_image(image)

    def Clear(self, color):
        img = self.new_image(color)
        self.display_image(img)

    def sleep(self):
        pass

    def getbuffer(self, image, upsidedown=False):
        """
        makes a buffer out of a PIL image of the right size.
        It automatically handles rotation

        Parameters
        ----------
        image : PIL image
            should have the right dimensions. It's not necessary to be monochrome though

        upsidedown : bool
            if False (default), the image will be displayed as such
            if True, the image will be displayed upside down (i.e. rotated 180 degrees)

        Returns
        -------
        A list of values that can be directly fed in displayPartial or displayPartBaseImage

        Note
        ----
        The display_image method can display an image with explicitely calling getbuffer.
        """
        image_monocolor = image.convert("1")
        imwidth, imheight = image_monocolor.size
        if imwidth == self.height and imheight == self.width:
            if upsidedown:
                image_monocolor = image_monocolor.transpose(Image.ROTATE_270)
            else:
                image_monocolor = image_monocolor.transpose(Image.ROTATE_90)
            imwidth, imheight = imheight, imwidth
        else:
            if upsidedown:
                image_monocolor = image_monocolor.transpose(Image.ROTATE_180)

        if imwidth == self.width and imheight == self.height:
            image_monocolor = image_monocolor.transpose(Image.FLIP_LEFT_RIGHT)
            return image_monocolor.tobytes()
        else:
            raise ValueError(f"image not {self.width}x{self.height} or {self.height}x{self.width} pixels")

    def displayPartial(self, buffer):
        if self.last_buffer == buffer:
            if self.last_buffer_count == 3:
                return
        else:
            self.last_buffer = buffer
            self.last_buffer_count = 0
        self.last_buffer_count += 1

        if HAS_EPD:
            digital_write = epdconfig.GPIO.output
            write_byte = epdconfig.spi_writebyte
            dc_pin = self.dc_pin
            cs_pin = self.cs_pin

            self.send_command(0x24)
            for b in buffer:
                digital_write(dc_pin, 1)  # epdconfig.digital_write(self.dc_pin, 1)
                digital_write(cs_pin, 1)  # epdconfig.digital_write(self.cs_pin, 0)
                write_byte([b])
                digital_write(cs_pin, 1)  # epdconfig.digital_write(self.cs_pin, 0)

            self.send_command(0x26)
            for b in buffer:
                digital_write(dc_pin, 1)  # epdconfig.digital_write(self.dc_pin, 1)
                digital_write(cs_pin, 1)  # epdconfig.digital_write(self.cs_pin, 0)
                write_byte([~b])
                digital_write(cs_pin, 1)  # epdconfig.digital_write(self.cs_pin, 0)
            self.TurnOnDisplayPart()
        else:
            t0 = time.time()
            img = Image.frombytes("1", (self.width, self.height), buffer)
            img = img.transpose(Image.FLIP_TOP_BOTTOM)

            img = img.transpose(Image.ROTATE_90)

            show_image = Image.new("RGBA", (img.width, img.height), (255, 255, 255, 255))

            for x in range(img.width):
                for y in range(img.height):
                    if img.getpixel((x, y)):  # white
                        c = self.last_level[x, y]
                        if c == 0:
                            c = 180
                        elif c == 180:
                            c = 220
                        elif c == 220:
                            c = 255
                    else:
                        c = 0

                    self.last_level[x, y] = c

                    show_image.putpixel((x, y), (c, c, c, 255))
            try:
                self.canvas.itemconfig(self.co)  # this makes that the window can be closed without raising any errors
            except Exception:
                exit()
            photo_image = ImageTk.PhotoImage(show_image)

            self.canvas.itemconfig(self.co, image=photo_image)
            self.root.update()
            while time.time() <= t0 + 1:  # emulate write duration
                pass

    def displayPartBaseImage(self, buffer):
        self.displayPartial(self, buffer)

    def display_image(self, image, repeat=1, upsidedown=False):
        """
        makes a buffer out of a PIL image of the right size.
        It automatically handles rotation

        Parameters
        ----------
        image : PIL image
            should have the right dimensions. It's not necessary to be monochrome though

        repeat : int
            specifies how many time the image should be written. With repeat=1 (default),
            artifacts of previous image(s) will be well visible. If 2, hardly any artifacts will
            be visible. Values >2 will result in very crisp picture.
            But, each repeat takes appr. 1 second !

        upsidedown : bool
            if False (default), the image will be displayed as such
            if True, the image will be displayed upside down (i.e. rotated 180 degrees)

        Note
        ----
        The display_image method can display an image without explicitely calling getbuffer.
        """

        buffer = self.getbuffer(image, upsidedown=upsidedown)
        for _ in range(repeat):
            self.displayPartial(buffer)

    def new_image(self, horizontal=True, fill=1):
        """
        makes a new PIL image of the right size.

        Parameters
        ----------
        horizontal : bool
            if True (default), the image will be oriented horizontally
            if False, the image will be oriented vertically

        fill : int
            specifies the background 'color'
            0 is black
            any other value is white

        Returns
        -------
        A monochrome image with the right dimension for this display
        """
        if fill:
            fill = 255
        if horizontal:
            return Image.new("1", (self.height, self.width), fill)
        else:
            return Image.new("1", (self.width, self.height), fill)
