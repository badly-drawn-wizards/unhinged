from dataclasses import dataclass, field
from functools import reduce
from itertools import accumulate
from os.path import join, isdir
from os import listdir
from contextlib import contextmanager
from textwrap import dedent
import re
from futil import fset, fget

@dataclass
class IIO:
    iio_path: str = "/sys/bus/iio/devices"
    char_dev_path: str = "/dev/char"

    def device_fs_names(self):
        return [name for name in listdir(self.iio_path) if name.startswith("iio:")]

    def devices(self):
        return [IIODevice(self, fs_name) for fs_name in self.device_fs_names()]

    def devices_by_name(self):
        return {device.name(): device for device in self.devices()}

@dataclass
class IIODevice:
    ctxt: IIO = field(repr=False, hash=False, compare=False)
    fs_name: str
    buffer: 'IIOBuffer' = field(init=False)

    def __post_init__(self):
        self.buffer = IIOBuffer(self, "buffer")

    @property
    def path(self):
        return join(self.ctxt.iio_path, self.fs_name)

    @property
    def el_path(self):
        return join(self.path, "scan_elements")

    def name(self):
        return fget(join(self.path, "name"))

    def channel_names(self):
        suf = "_en"
        return [name[:-len(suf)]
                for name in listdir(self.el_path)
                if name.endswith(suf)]

    def channels(self):
        return [IIOChannel(self, name) for name in self.channel_names()]

    def channels_by_label(self):
        return {channel.label(): channel
                for channel in self.channels()
                if channel.label}

    def dev(self):
        return fget(join(self.path, "dev"))

    def char_path(self):
        return join(self.ctxt.char_dev_path, self.dev())

class IIOBufferParser:
    def __init__(self, channels):
        self.types = [channel.type() for channel in sorted(channels, key=lambda chan: chan.index)]
        self.ixs = list(accumulate((ty.consumes for ty in self.types), initial=0))

    @property
    def consumes(self):
        return self.ixs[-1]

    def read(self, bs):
        return [
            ty.read(bs[self.ixs[i]:self.ixs[i+1]])
            for i, ty in enumerate(self.types)
        ]

@dataclass
class IIOChannel:
    dev: IIODevice = field(repr=False, hash=False, compare=False)
    name: str

    def enable(self, en):
        fset(join(self.dev.el_path, f"{self.name}_en"), en)

    def type(self):
        return IIOChannelType.from_str(
            self,
            fget(join(self.dev.el_path, f"{self.name}_type"))
        )

    def index(self):
        return fget(join(self.dev.el_path, f"{self.name}_index"), int)

    def label(self):
        return fget(join(self.dev.path, f"{self.name}_label"))

@dataclass
class IIOChannelType:
    channel: IIOChannel = field(repr=False, hash=False, compare=False)
    be: bool
    signed: bool
    bits: int
    storagebits: int
    repeat: int
    shift: int

    RE_TYPE = re.compile(dedent("""\
        (?P<endian>be|le):
        (?P<sign>s|u)
        (?P<bits>[0-9]+)/
        (?P<storagebits>[0-9]+)
        (X(?P<repeat>[0-9]+))?
        (>>(?P<shift>[0-9]+))?
        """).replace("\n", ""))

    @staticmethod
    def from_str(channel, str):
        match = IIOChannelType.RE_TYPE.fullmatch(str)
        if not match:
            raise Exception("Unable to parse channel type")
        try:
            g = match.groupdict()
            return IIOChannelType(channel,
                be = 'be' == g['endian'],
                signed = 's' == g['sign'],
                **{ k: int(g[k]) if g[k] else {'repeat': 1, 'shift': 0}[k]
                    for k in ['bits', 'storagebits', 'repeat', 'shift'] }
            )
        except ValueError:
            raise Exception("Unable to parse channel type")

    @property
    def consumes1(self):
        return -(-self.storagebits // 8)

    @property
    def consumes(self):
        return self.consumes1 * self.repeat

    def read1(self, bs):
        assert len(bs) == self.consumes1
        bo = 'big' if self.be else 'little'
        raw = int.from_bytes(bs, bo, signed=False) >> self.shift
        sgn = (1 << (self.bits-1))
        return (raw & sgn-1) - (raw & sgn)

    def read(self, bs):
        assert len(bs) == self.consumes
        d = self.consumes1
        return [self.read1(bs[i*d:(i+1)*d]) for i in range(self.repeat)]


@dataclass
class IIOBuffer:
    dev: IIODevice = field(repr=False, hash=False, compare=False)
    name: str

    @property
    def path(self):
        return join(self.dev.path, self.name)

    def enable(self, en):
        return fset(join(self.path, "enable"), en)

    def length(self, n):
        return fset(join(self.path, "length"), n)

    def watermark(self):
        return fget(join(self.path, "watermark"), int)

    def data_available(self):
        return fget(join(self.path, "data_available"), int)

    @contextmanager
    def open_char(self, channels, length):
        # Use char device as mutex as it has exclusive read
        with open(self.dev.char_path(), 'rb') as char:
            # Clear the buffer
            # TODO: check if necesary
            char.read(self.data_available())
            self.enable(False)
            self.length(length)
            for channel in self.dev.channels():
                channel.enable(False)
            for channel in channels:
                channel.enable(True)
            try:
                self.enable(True)
                yield char
            finally:
                self.enable(False)

    @contextmanager
    def open(self, channels, length):
        with self.open_char(channels, length) as char:
            parser = IIOBufferParser(channels)
            n = parser.consumes
            def gen():
                while True:
                    bs = char.read(n)
                    if bs and len(bs) == n:
                        yield parser.read(bs)
            yield gen()
