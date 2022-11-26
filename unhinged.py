#!/usr/bin/env python3

from os.path import join
from os import listdir, environ
from collections import deque
from contextlib import contextmanager
from subprocess import run
from sys import stderr

iio_dev = "iio:device4"

sys_iio = join("/sys/bus/iio/devices", iio_dev)

scan_elements = join(sys_iio, "scan_elements")
hinge_channel_enable = join(scan_elements, "in_angl0_en")

buf_len = join(sys_iio, "buffer/length")
buf_en = join(sys_iio, "buffer/enable")

dev_iio = join("/dev", iio_dev)

DRY = False
BUFFER_LEN = 1

HINGE_SW_UP = 200
HINGE_SW_DOWN = 160

def fset(path, value):
    if isinstance(value, bool):
        value = int(value)
    value = str(value)

    print('fset("{}","{}")'.format(path, value))
    if not DRY:
        with open(path, 'w') as f:
            f.write(value)

def channel_enables():
    elems = listdir(scan_elements)
    return [join(scan_elements, elem) for elem in elems if elem.endswith("_en")]

def setup():
    fset(buf_en, False)
    for enable in channel_enables():
        fset(enable, enable == hinge_channel_enable)
    fset(buf_len, BUFFER_LEN)
    fset(buf_en, True)

def gen_hinge_val():
    setup()
    bys = deque()
    with open(dev_iio, 'rb') as f:
        while True:
            bys.extend(f.read(2))
            while len(bys) >= 2:
                yield (bys.popleft() + (bys.popleft() << 8))

def gen_rot_val():
    vals = gen_hinge_val()
    while True:
        yield next(vals)
        next(vals)

def gen_sw_tablet_mode():
    last_mode = None
    mode = 0
    hinge_vals = gen_rot_val()
    for val in hinge_vals:
        if val <= HINGE_SW_DOWN:
            mode = 0
        if val >= HINGE_SW_UP:
            mode = 1
        if mode != last_mode:
            yield mode
        last_mode = mode


class MockDevice:
    def emit(self, *args, **kwargs):
        pass
    def destroy(self, *args, **kwargs):
        pass

def modprobe(module, enable):
    if enable:
        print("Enabling module", module)
        run(["modprobe", module])
    else:
        print("Disabling module", module)
        run(["modprobe", "-r", module])

def main():
    print("PATH:", environ.get('PATH', ""))
    try:
        for mode in gen_sw_tablet_mode():
            print("Tablet mode", ["off","on"][mode])
            modprobe("intel-hid", mode)
    finally:
        modprobe("intel-hid", True)

if __name__ == "__main__":
    main()
