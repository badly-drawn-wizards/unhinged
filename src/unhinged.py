#!/usr/bin/env python3

from subprocess import run
from iio import IIO
from acpi import INTEL_HID_DSM, IntelHIDFn, acpi_call
from contextlib import contextmanager
from futil import fset
from os.path import join

def gen_sw_tablet_mode(hinge_vals, hist_down, hist_up):
    last_mode = None
    mode = False
    for val in hinge_vals:
        if val <= hist_down:
            mode = False
        if val >= hist_up:
            mode = True
        if mode != last_mode:
            yield mode
        last_mode = mode

def int33d5_hdsm_disable():
    acpi_call(INTEL_HID_DSM, IntelHIDFn.HDSM, [False])

@contextmanager
def iio_hinge():
    ctxt = IIO()
    dev = ctxt.devices_by_name()['hinge']
    chan = dev.channels_by_label()['hinge']
    with dev.buffer.open([chan], 1) as gen:
        def extract(val):
            [[hinge]] = val
            # print("Hinge: ", hinge)
            return hinge
        yield map(extract, gen)

def inhibit_dev(path, en):
    fset(join(path, "inhibited"), int(bool(en)))

def run_service():
    input_dev = "/sys/class/input/input1"
    int33d5_hdsm_disable()
    try:
        with iio_hinge() as vals:
            for mode in gen_sw_tablet_mode(vals, 160, 200):
                print("Tablet mode", ["off","on"][int(mode)])
                inhibit_dev(input_dev, mode)
    finally:
        inhibit_dev(input_dev, False)

def main():
    run_service()

if __name__ == "__main__":
    main()
