#!/usr/bin/env python3

from sys import argv
from shlex import quote
from dataclasses import dataclass
from typing import *
from enum import Enum
from argparse import ArgumentParser, RawTextHelpFormatter
from textwrap import dedent
from functools import partial

@dataclass
class DSM:
    dev: str
    guid: str
    rev: int

    @property
    def dsm(self):
        return f"{self.dev}._DSM"

    @property
    def acpi_guid(self):
        perm_ixs = [3,2,1,0,5,4,7,6,8,9,10,11,12,13,14,15]
        str_ixs = [0,2,4,6,9,11,14,16,19,21,24,26,28,30,32,34]
        bys = [
            int(self.guid[ix:ix+2].replace('-', ''),16)
            for ix in str_ixs
        ]
        return bytes(bys[ix] for ix in perm_ixs)

    @staticmethod
    def from_args(dev, guid, rev):
        return DSM(str(dev), str(guid), int(rev))

class IntelHIDFn(Enum):
	INVALID = 0
	BTNL = 1
	HDMM = 2
	HDSM = 3
	HDEM = 4
	BTNS = 5
	BTNE = 6
	HEBC_V1 = 7
	VGBS = 8
	HEBC_V2 = 9
	MAX = 10

INTEL_HID_DSM = DSM(
    "\_SB.HIDD",
    "eeec56b3-4442-408f-a792-4edd4d758054",
    1
)

ARG_STR_TARGET = ["acpi_call", "acpiexec", "invoke"]
def acpi_call_buf_str(arg):
    return 'b' + bytes(arg).hex()

def arg_str(arg, target):
    if target not in ARG_STR_TARGET:
        raise Exception(f"target should be one of {ARG_STR_TARGET}")
    if isinstance(arg, bool):
        arg = int(arg)
    if isinstance(arg, Enum):
        arg = arg.value
    if isinstance(arg, int) and 0 <= arg <= 255:
        return f"0x{arg:02X}"
    if isinstance(arg, list):
        if target == "acpi_call":
            if not all(isinstance(x, int) for x in arg):
                raise Exception("acpi_call does not support package arguments")
            return acpi_call_buf_str(arg)
        if target == "acpiexec":
            inner = ' '.join(arg_str(x, target) for x in arg)
            return f"[{inner}]"
    if isinstance(arg, bytes):
        if target == "acpi_call":
            return acpi_call_buf_str(arg)
        elif target == "acpiexec":
            inner = ' '.join(f"{x:02X}" for x in arg)
            return f'({inner})'
    if isinstance(arg, str):
        return f"\"{arg}\""
    raise Exception("Invalid argument to ACPI call")

def dsm_invoke_str(dsm, fn, arg, target):
    return " ".join([
        dsm.dsm,
        arg_str(dsm.acpi_guid, target),
        arg_str(dsm.rev, target),
        arg_str(fn, target),
        arg_str(arg, target)
    ])

class AcpiCallException(Exception):
    pass

def acpi_call(*args, **kwargs):
    invoke = dsm_invoke_str(*args, **kwargs, target="acpi_call")
    with open("/proc/acpi/call", 'w') as c:
        c.write(invoke)
    with open("/proc/acpi/call", 'r') as c:
        res = c.read()
        prefix = "Error: "
        if res.startswith(prefix):
            raise AcpiCallException(res.lstrip(prefix))
        return res

if __name__ == "__main__":
    parser = ArgumentParser(
        description="Unhinged acpi utility",
        formatter_class=RawTextHelpFormatter
    )
    parser.add_argument("--set", choices=["on", "off"], default="on",
                        help="To enable or disable HDSM")
    parser.add_argument(
        "--target", choices=ARG_STR_TARGET, default="acpi_call",
        help=dedent("""\
            acpi_call - output arguments for acpi_call module
            acpiexec - output the arguments for exec/debug in the acpiexec REPL
            invoke - run acpi call using procfs\
        """))
    parser.add_argument("--dsm", nargs=3)
    parser.add_argument("--fn", default=IntelHIDFn.HDSM, type=int)

    ns = parser.parse_args()
    enable = ns.set == "on"
    target = ns.target
    if ns.dsm:
        dsm = DSM.from_args(*ns.dsm)
    else:
        dsm = INTEL_HID_DSM
    fn = ns.fn
    args = [dsm, fn, [enable]]
    if target == "invoke":
        acpi_call(*args)
    else:
        print(dsm_invoke_str(*args, target=target))
