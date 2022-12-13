#!/usr/bin/env python3

from subprocess import run
from iio import IIO, iio_zip
from acpi import INTEL_HID_DSM, IntelHIDFn, acpi_call
from contextlib import contextmanager
from futil import fset
from os.path import join
from pyquaternion import Quaternion
from math import pi

def hist_states(
        vals,
        hist_hinge_lte, hist_hinge_gte,
        hist_pitch_lte, hist_pitch_gte):
    last_mode = None
    tablet = False
    side = False
    for val in vals:
        [[_, [hinge]], [_, q_rot]] = val
        _, pitch, _ = Quaternion(q_rot).yaw_pitch_roll
        if hinge <= hist_hinge_lte:
            tablet = False
        if hinge >= hist_hinge_gte:
            tablet = True
        if abs(pitch) <= hist_pitch_lte:
            side = False
        if abs(pitch) >= hist_pitch_gte:
            side = True
        mode = (tablet, side)
        if mode != last_mode:
            yield mode
        last_mode = mode

def int33d5_hdsm(enable):
    acpi_call(INTEL_HID_DSM, IntelHIDFn.HDSM, [enable])

@contextmanager
def iio_hinge(ctxt):
    dev = ctxt.devices_by_name['hinge']
    ts_chan = dev.channels_by_name['in_timestamp']
    h_chan = dev.channels_by_label['hinge']
    with dev.buffer.open([ts_chan, h_chan], 1) as gen:
        yield gen

@contextmanager
def iio_rot(ctxt):
    dev = ctxt.devices_by_name['dev_rotation']
    ts_chan = dev.channels_by_name['in_timestamp']
    q_chan = dev.channels_by_name['in_rot_quaternion']
    with dev.buffer.open([ts_chan, q_chan], 1) as gen:
        yield gen

@contextmanager
def iio_inp(ctxt):
    with iio_hinge(ctxt) as hinge, iio_rot(ctxt) as rot:
        yield iio_zip([hinge, rot])

def inhibit_dev(path, en):
    fset(join(path, "inhibited"), int(bool(en)))

def run_service():
    ctxt = IIO()
    input_dev = "/sys/class/input/event1/device"
    try:
        with iio_inp(ctxt) as vals:
            for tablet, side in hist_states(vals, 160, 200, pi/4, pi/4):
                hdsm = not side or tablet
                print(f"HDSM: {hdsm}, Tablet: {tablet}, Side: {side}")
                int33d5_hdsm(hdsm)
                inhibit_dev(input_dev, tablet)
    finally:
        inhibit_dev(input_dev, False)

def main():
    run_service()


if __name__ == "__main__":
    main()
