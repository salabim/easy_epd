import sys
import os
import datetime

import easy_epd
from PIL import Image, ImageDraw, ImageFont

epd = easy_epd.EPD(module_name="epd2in13_V2")

font = ImageFont.truetype("7segment.ttf", 75)
last_second = -1

while True:
    now = datetime.datetime.now()
    while (now.second % 5 != 0) or (last_second == now.second):
        now = datetime.datetime.now()
    last_second = now.second

    image = epd.new_image(horizontal=True)
    draw = ImageDraw.Draw(image)

    draw.text((0, 0), f"{now.hour:02d}:{now.minute:02d}:{now.second:02d}", font=font, fill=0)

    epd.display_image(image, repeat=3, upsidedown=False)


