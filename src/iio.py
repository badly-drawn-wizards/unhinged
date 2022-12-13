from dataclasses import dataclass, field
from functools import reduce
from itertools import accumulate
from os.path import join, isdir
from os import listdir
from contextlib import contextmanager
from textwrap import dedent
import re
from futil import fset, fget
from lazy import lazy
from queue import PriorityQueue
from typing import *

@dataclass
class IIO:
    iio_path: str = "/sys/bus/iio/devices"
    char_dev_path: str = "/dev/char"

    @property
    @lazy
    def device_fs_names(self):
        return [name for name in listdir(self.iio_path) if name.startswith("iio:")]

    @property
    @lazy
    def devices(self):
        return [IIODevice(self, fs_name) for fs_name in self.device_fs_names]

    @property
    @lazy
    def devices_by_name(self):
        return {device.name: device for device in self.devices}

@dataclass
class IIODevice:
    ctxt: IIO = field(repr=False, hash=False, compare=False)
    fs_name: str

    @property
    @lazy
    def buffer(self):
        return IIOBuffer(self, 'buffer')

    @property
    def path(self):
        return join(self.ctxt.iio_path, self.fs_name)

    @property
    def el_path(self):
        return join(self.path, "scan_elements")

    @property
    @lazy
    def name(self):
        return fget(join(self.path, "name"))

    @property
    @lazy
    def channel_names(self):
        suf = "_en"
        return [name[:-len(suf)]
                for name in listdir(self.el_path)
                if name.endswith(suf)]

    @property
    @lazy
    def channels(self):
        return [IIOChannel(self, name) for name in self.channel_names]

    @property
    @lazy
    def channels_by_label(self):
        return {channel.label: channel
                for channel in self.channels
                if channel.label}

    @property
    @lazy
    def channels_by_name(self):
        return {channel.name: channel
                for channel in self.channels
                if channel.name}

    @property
    @lazy
    def dev(self):
        return fget(join(self.path, "dev"))

    @property
    def char_path(self):
        return join(self.ctxt.char_dev_path, self.dev)

@dataclass(order=True)
class IIOBufferData:
    timestamp: int
    data: List[int] = field(compare=False)

    def __iter__(self):
        yield from self.data



TIMESTAMP_NAME = "in_timestamp"

class IIOBufferParser:
    def __init__(self, channels):
        assert len(channels) > 0, \
            "There should be at least one channel"
        assert len(set(chan.index for chan in channels)) == len(channels), \
            "Channel indices should be unique"
        self.channels = channels

    @property
    @lazy
    def perm(self):
        return sorted(
            range(len(self.channels)),
            key=lambda i: self.channels[i].index)

    @property
    @lazy
    def _ixs_and_consumes(self):
        res = []
        off = 0
        for j in self.perm:
            ty = self.channels[j].type
            off = -(-off // ty.consumes) * ty.consumes
            res.append(off)
            off += ty.phantom_consumes
        return (res, off)

    @property
    def ixs(self):
        res, _ = self._ixs_and_consumes
        return res

    @property
    def consumes(self):
        _, off = self._ixs_and_consumes
        return off

    def _read(self, bs):
        res = [None]*len(self.channels)
        for i, j in enumerate(self.perm):
            ix = self.ixs[i]
            ty = self.channels[j].type
            chbs = bs[ix:ix+ty.consumes]
            res[j] = ty.read(chbs)
        return res

    def read(self, bs):
        data = self._read(bs)
        try:
            ts_ix = [chan.name for chan in self.channels].index(TIMESTAMP_NAME)
            ts = data[ts_ix]
        except ValueError:
            ts = None
        return IIOBufferData(ts, data)

@dataclass
class IIOChannel:
    dev: IIODevice = field(repr=False, hash=False, compare=False)
    name: str

    def enable(self, en):
        fset(join(self.dev.el_path, f"{self.name}_en"), en)

    @property
    @lazy
    def type(self):
        return IIOChannelType.from_str(
            self,
            fget(join(self.dev.el_path, f"{self.name}_type"))
        )

    @property
    @lazy
    def index(self):
        return fget(join(self.dev.el_path, f"{self.name}_index"), int)

    @property
    @lazy
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

    @property
    def phantom_consumes(self):
        # Hack with one known example, unable to see if it generalizes
        # to other repeating iio channels.
        return self.consumes + int(self.repeat > 1)

    def read1(self, bs):
        assert len(bs) == self.consumes1
        bo = 'big' if self.be else 'little'
        raw = int.from_bytes(bs, bo, signed=False) >> self.shift
        sgn = (1 << (self.bits-1))
        return (raw & sgn-1) + (-1)**int(self.signed) * (raw & sgn)

    def read(self, bs):
        assert len(bs) == self.consumes
        d = self.consumes1
        return [self.read1(bs[i*d:(i+1)*d]) for i in range(self.repeat)]


@dataclass
class IIOBuffer:
    dev: IIODevice = field(repr=False, hash=False, compare=False)
    name: str

    @property
    @lazy
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
        with open(self.dev.char_path, 'rb') as char:
            # Clear the buffer
            self.enable(False)
            self.length(length)
            for channel in self.dev.channels:
                channel.enable(False)
            for channel in channels:
                channel.enable(True)
            try:
                self.enable(True)
                yield char
            finally:
                pass
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

def iio_zip(its):
    assert len(its) > 0, "argument should be non-empty"
    q = PriorityQueue()
    r = [next(it) for it in its]
    ts = max(v.timestamp for v in r)
    for i, v in enumerate(r):
        q.put((v, i))
    while True:
        yield IIOBufferData(ts, [*r])
        _, i = q.get_nowait()
        v = next(its[i])
        r[i] = v
        ts = max(ts, v.timestamp)
        q.put((v, i))
