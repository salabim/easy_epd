easy_epd
========
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

Refer to the test files for examples.


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
