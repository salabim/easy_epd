import sys
import os

import easy_epd
from PIL import Image, ImageDraw, ImageFont

import time

epd = easy_epd.EPD("epd2in13_V2")
epd.init(epd.FULL_UPDATE)
epd.Clear(0xFF)

font24 = ImageFont.truetype("calibri.ttf", 24)

image = epd.new_image(horizontal=True)
draw = ImageDraw.Draw(image)

draw.rectangle((0, 0, 220, 105), fill=255)
for i in range(13):
    image = epd.new_image(horizontal=True)
    draw = ImageDraw.Draw(image)
    draw.text((0, i* 20), f"Test {i} = {i*i}", font=font24, fill=0)
    buffer = epd.getbuffer(image)
    epd.display(buffer)
    time.sleep(1)

y("done")

