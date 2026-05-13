"""
Ratpack is fast and efficent schemaless binary serialization format.

It takes inspiration from both msgpack and cbor.

Ratpack splits it's types across a one byte number range (0-255) and assigns types to different
ranges. For example small strings cover 0x6C - 0x90 while 32 bit length arrays are assigned 0xBB.

Features:
    - Natural ordering within types (small strings < str8 < str16 < str32)
    - Intentional small values. For example small strings can encode a length up to 36 which covers common string representations like uuids and iso8601 timestamps.
    - Simple extension type via tags
    - Unknown length strings, binary blobs, arrays, and dicts

    - ?deterministic ordering and content adressable id
        - follows https://datatracker.ietf.org/doc/html/rfc8949#section-4.2
        - floats?
        - sort by major_type < small_type < type_varlen/int < len_n < len_n+1 < lexigraphical
"""

import io
import struct
from typing import TypeAlias, Union

RatPrimitive: TypeAlias = Union[
    int,
    float,
    bool,
    str,
    bytes,
    None,
]

RatType: TypeAlias = Union[
    RatPrimitive,
    list["RatType"],
    dict[RatPrimitive, "RatType"],
]


class RatPackException(Exception):
    pass


_INT_SMALL_NUM_START = 0x00
_INT_SMALL_NUM_END = 0x40

_INT8 = 0x41
_INT16 = 0x42
_INT32 = 0x43
_INT64 = 0x44
_INT128 = 0x45

_NEG_INT_SMALL_NUM_START = 0x46
_NEG_INT_SMALL_NUM_END = 0x66
_NEG_INT8 = 0x67
_NEG_INT16 = 0x68
_NEG_INT32 = 0x69
_NEG_INT64 = 0x6A
_NEG_INT128 = 0x6B

_STR_SMALL_NUM_START = 0x6C
_STR_SMALL_NUM_END = 0x90
_STR8 = 0x91
_STR16 = 0x92
_STR32 = 0x93

_ARR_SMALL_NUM_START = 0x94
_ARR_SMALL_NUM_END = 0xB8
_ARR8 = 0xB9
_ARR16 = 0xBA
_ARR32 = 0xBB

_MAP_SMALL_NUM_START = 0xBC
_MAP_SMALL_NUM_END = 0xE0
_MAP8 = 0xE1
_MAP16 = 0xE2
_MAP32 = 0xE3

# TODO
# _FLOAT16?
_FLOAT32 = 0xE4
_FLOAT64 = 0xE5
_TRUE = 0xE6
_FALSE = 0xE7
_NULL = 0xE8

_BIN_SMALL_START = 0xE9
_BIN_SMALL_END = 0xF1  # bump this from 8 to 16 to encode uuid
_BIN8 = 0xF2
_BIN16 = 0xF3
_BIN32 = 0xF4

# TODO
_TAG_SMALL_START = 0xF5
_TAG_SMALL_END = 0xFD
_TAG8 = 0xFE
_TAG16 = 0xFF

# 0Xff for stream terminator
# ext: 0-9(10) +1 (8bit) +1 (16bit)

u8packer = struct.Struct(">B")


MAX_INT = 2**128 - 1


def leb128_enc(n: int, writer: io.BufferedIOBase):
    """Little endian base 128 https://en.wikipedia.org/wiki/LEB128"""
    if n < 0 or n > MAX_INT:
        raise RatPackException(
            f"leb128_enc only encodes positive numbers up to {MAX_INT}. Was given {n}"
        )
    elif n == 0:
        writer.write(u8packer.pack(0))
        return

    while n:
        byte = n & 0x7F  # mask the lower 7 bits leaving the msb as 0
        n >>= 7
        if n:
            writer.write(u8packer.pack(byte | 0x80))  # msb set to 1 for continuation
        else:
            writer.write(u8packer.pack(byte))
            break


def leb128_dec(reader: io.BufferedIOBase) -> int:
    n = 0
    shift = 0

    while True:
        try:
            byte = reader.read(1)[0]
        except IndexError:
            raise RatPackException("Malformed leb128 encoded payload")

        n |= (byte & 0x7F) << shift
        shift += 7
        if byte & 0x80 == 0:
            break
        if n > MAX_INT:
            raise RatPackException(
                f"Malformed leb128 encoded value. Exceeds max int ({MAX_INT})"
            )
    return n


class Tag:
    pass


def encode(obj: RatType) -> bytes:
    encoder = Encoder(io.BytesIO())
    encoder.encode(obj)
    return encoder.stream.getvalue()


def decode(bites: bytes) -> RatType:
    return Decoder(io.BytesIO(bites)).decode()


# TODO: inherhitance should work. ex `class MyInt(int): ...`
class Encoder:
    def __init__(self, stream: io.BufferedIOBase):
        self.stream = stream

    def encode(self, obj: RatType):
        tipe = type(obj).__name__
        dispatch = getattr(self, f"_encode_{tipe}")
        dispatch(obj)

    def _encode_int(self, i: int):
        if i >= 0:
            return self._encode_positive_int(i)
        return self._encode_negative_int(i)

    def _encode_positive_int(self, i: int):
        if i <= _INT_SMALL_NUM_END - _INT_SMALL_NUM_START:
            self.stream.write(struct.pack(">B", _INT_SMALL_NUM_START + i))
        elif i <= 0xFF:
            self.stream.write(struct.pack(">BB", _INT8, i))
        elif i <= 0xFFFF:
            self.stream.write(struct.pack(">BH", _INT16, i))
        elif i <= 0xFFFFFFFF:
            self.stream.write(struct.pack(">BI", _INT32, i))
        elif i <= 0xFFFFFFFFFFFFFFFF:
            self.stream.write(struct.pack(">BQ", _INT64, i))
        elif i <= 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF:
            self.stream.write(
                struct.pack(">BQQ", _INT128, i >> 64, i & 0xFFFFFFFFFFFFFFFF)
            )

    def _encode_negative_int(self, i: int):
        i = abs(i)
        if i <= _NEG_INT_SMALL_NUM_END - _NEG_INT_SMALL_NUM_START:
            self.stream.write(struct.pack(">B", _NEG_INT_SMALL_NUM_START + i))
        elif i <= 0xFF:
            self.stream.write(struct.pack(">BB", _NEG_INT8, i))
        elif i <= 0xFFFF:
            self.stream.write(struct.pack(">BH", _NEG_INT16, i))
        elif i <= 0xFFFFFFFF:
            self.stream.write(struct.pack(">BI", _NEG_INT32, i))
        elif i <= 0xFFFFFFFFFFFFFFFF:
            self.stream.write(struct.pack(">BQ", _NEG_INT64, i))
        elif i <= 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF:
            self.stream.write(
                struct.pack(">BQQ", _NEG_INT128, i >> 64, i & 0xFFFFFFFFFFFFFFFF)
            )

    def _encode_str(self, s: str):
        val = s.encode("utf8")
        size = len(val)

        if size <= _STR_SMALL_NUM_END - _STR_SMALL_NUM_START:
            self.stream.write(struct.pack(">B", _STR_SMALL_NUM_START + size))
        elif size <= 0xFF:
            self.stream.write(struct.pack(">BB", _STR8, size))
        elif size <= 0xFFFF:
            self.stream.write(struct.pack(">BH", _STR16, size))
        elif size <= 0xFFFFFFFF:
            self.stream.write(struct.pack(">BI", _STR32, size))
        else:
            raise Exception("str to large")

        self.stream.write(val)

    def _encode_list(self, l: list):
        size = len(l)
        if size <= _ARR_SMALL_NUM_END - _ARR_SMALL_NUM_START:
            self.stream.write(struct.pack(">B", _ARR_SMALL_NUM_START + size))
        elif size <= 0xFF:
            self.stream.write(struct.pack(">BB", _ARR8, size))
        elif size <= 0xFFFF:
            self.stream.write(struct.pack(">BH", _ARR16, size))
        elif size <= 0xFFFFFFFF:
            self.stream.write(struct.pack(">BI", _ARR32, size))

        for i in l:
            self.encode(i)

    def _encode_dict(self, d: dict):
        size = len(d)
        if size <= _MAP_SMALL_NUM_END - _MAP_SMALL_NUM_START:
            self.stream.write(struct.pack(">B", _MAP_SMALL_NUM_START + size))
        elif size <= 0xFF:
            self.stream.write(struct.pack(">BB", _MAP8, size))
        elif size <= 0xFFFF:
            self.stream.write(struct.pack(">BH", _MAP16, size))
        elif size <= 0xFFFFFFFF:
            self.stream.write(struct.pack(">BI", _MAP32, size))

        for k, v in d.items():
            self.encode(k)
            self.encode(v)

    def _encode_bool(self, b: bool):
        if b:
            self.stream.write(struct.pack(">B", _TRUE))
        else:
            self.stream.write(struct.pack(">B", _FALSE))

    def _encode_NoneType(self, _: None):
        self.stream.write(struct.pack(">B", _NULL))

    def _encode_bytes(self, b: bytes):
        size = len(b)
        if size <= _BIN_SMALL_END - _BIN_SMALL_START:
            self.stream.write(struct.pack(">B", _BIN_SMALL_START + size))
        elif size <= 0xFF:
            self.stream.write(struct.pack(">BB", _BIN8, size))
        elif size <= 0xFFFF:
            self.stream.write(struct.pack(">BH", _BIN16, size))
        elif size <= 0xFFFFFFFF:
            self.stream.write(struct.pack(">BI", _BIN32, size))
        else:
            raise Exception("bytes to large")

        self.stream.write(b)


def _not_implemented(marker: int, _: io.BufferedIOBase):
    raise NotImplementedError(f"{hex(marker)} not implemented")


_DECODE_TABLE = [_not_implemented] * 0xFF


# inclusive
def register(start: int, stop: int | None = None):
    if stop is None:
        stop = start

    def wrapper(func):
        for i in range(start, stop + 1):
            _DECODE_TABLE[i] = func
        return func

    return wrapper


@register(_INT_SMALL_NUM_START, _INT_SMALL_NUM_END)
def _decode_small_int(marker: int, _: io.BufferedIOBase) -> int:
    return marker


@register(_INT8)
def _decode_int8(_: int, stream: io.BufferedIOBase) -> int:
    return struct.unpack(">B", stream.read(1))[0]


@register(_INT16)
def _decode_int16(_: int, stream: io.BufferedIOBase) -> int:
    return struct.unpack(">H", stream.read(2))[0]


@register(_INT32)
def _decode_int32(_: int, stream: io.BufferedIOBase) -> int:
    return struct.unpack(">I", stream.read(4))[0]


@register(_INT64)
def _decode_int64(_: int, stream: io.BufferedIOBase) -> int:
    return struct.unpack(">Q", stream.read(8))[0]


@register(_INT128)
def _decode_int128(_: int, stream: io.BufferedIOBase) -> int:
    vals = struct.unpack(">QQ", stream.read(16))
    num = vals[0] << 64
    return num | vals[1]


@register(_NEG_INT_SMALL_NUM_START, _NEG_INT_SMALL_NUM_END)
def _decode_small_neg_int(marker: int, _: io.BufferedIOBase) -> int:
    return -(marker - _NEG_INT_SMALL_NUM_START)


@register(_NEG_INT8)
def _decode_neg_int8(_: int, stream: io.BufferedIOBase) -> int:
    return -(struct.unpack(">B", stream.read(1))[0])


@register(_NEG_INT16)
def _decode_neg_int16(_: int, stream: io.BufferedIOBase) -> int:
    return -struct.unpack(">H", stream.read(2))[0]


@register(_NEG_INT32)
def _decode_neg_int32(_: int, stream: io.BufferedIOBase) -> int:
    return -struct.unpack(">I", stream.read(4))[0]


@register(_NEG_INT64)
def _decode_neg_int64(_: int, stream: io.BufferedIOBase) -> int:
    return -struct.unpack(">Q", stream.read(8))[0]


@register(_NEG_INT128)
def _decode_neg_int128(_: int, stream: io.BufferedIOBase) -> int:
    vals = struct.unpack(">QQ", stream.read(16))
    num = vals[0] << 64
    return -(num | vals[1])


def _read_n_bytes(size: int, stream: io.BufferedIOBase) -> bytes:
    val = b""
    while size > 0:
        read = stream.read(size)
        size -= len(read)
        val += read
    return val


@register(_STR_SMALL_NUM_START, _STR_SMALL_NUM_END)
def _decode_small_str(marker: int, stream: io.BufferedIOBase) -> str:
    size = marker - _STR_SMALL_NUM_START
    return _read_n_bytes(size, stream).decode("utf8")


@register(_STR8)
def _decode_str8(_: int, stream: io.BufferedIOBase) -> str:
    size = stream.read(1)[0]
    return _read_n_bytes(size, stream).decode("utf8")


@register(_STR16)
def _decode_str16(_: int, stream: io.BufferedIOBase) -> str:
    size = struct.unpack(">H", stream.read(2))[0]
    return _read_n_bytes(size, stream).decode("utf8")


@register(_STR32)
def _decode_str32(_: int, stream: io.BufferedIOBase) -> str:
    size = struct.unpack(">I", stream.read(4))[0]
    return _read_n_bytes(size, stream).decode("utf8")


@register(_ARR_SMALL_NUM_START, _ARR_SMALL_NUM_END)
def _decode_small_arr(marker: int, stream: io.BufferedIOBase) -> list:
    size = marker - _ARR_SMALL_NUM_START
    ctx = [None] * size
    for i in range(size):
        ctx[i] = _visit(stream)
    return ctx


@register(_ARR8)
def _decode_arr8(_: int, stream: io.BufferedIOBase) -> list:
    size = stream.read(1)[0]
    ctx = [None] * size
    for i in range(size):
        ctx[i] = _visit(stream)
    return ctx


@register(_ARR16)
def _decode_arr16(_: int, stream: io.BufferedIOBase) -> list:
    size = struct.unpack(">H", stream.read(2))[0]
    ctx = [None] * size
    for i in range(size):
        ctx[i] = _visit(stream)
    return ctx


@register(_ARR32)
def _decode_arr32(_: int, stream: io.BufferedIOBase) -> list:
    size = struct.unpack(">I", stream.read(4))[0]
    ctx = [None] * size
    for i in range(size):
        ctx[i] = _visit(stream)
    return ctx


@register(_MAP_SMALL_NUM_START, _MAP_SMALL_NUM_END)
def _decode_small_map(marker: int, stream: io.BufferedIOBase) -> dict:
    size = marker - _MAP_SMALL_NUM_START
    ctx = {}
    for _ in range(size):
        k = _visit(stream)
        v = _visit(stream)
        ctx[k] = v
    return ctx


@register(_MAP8)
def _decode_map8(_: int, stream: io.BufferedIOBase) -> dict:
    size = stream.read(1)[0]
    ctx = {}
    for _ in range(size):
        k = _visit(stream)
        ctx[k] = _visit(stream)
    return ctx


@register(_MAP16)
def _decode_map16(_: int, stream: io.BufferedIOBase) -> dict:
    size = struct.unpack(">H", stream.read(2))[0]
    ctx = {}
    for _ in range(size):
        k = _visit(stream)
        ctx[k] = _visit(stream)
    return ctx


@register(_MAP32)
def _decode_map32(_: int, stream: io.BufferedIOBase) -> dict:
    size = struct.unpack(">I", stream.read(4))[0]
    ctx = {}
    for _ in range(size):
        k = _visit(stream)
        ctx[k] = _visit(stream)
    return ctx


@register(_TRUE)
def _decode_true(_: int, __: io.BufferedIOBase) -> bool:
    return True


@register(_FALSE)
def _decode_false(_: int, __: io.BufferedIOBase) -> bool:
    return False


@register(_NULL)
def _decode_null(_: int, __: io.BufferedIOBase) -> None:
    return None


def _visit(stream: io.BufferedIOBase):
    marker = stream.read(1)[0]
    return _DECODE_TABLE[marker](marker, stream)


class Decoder:
    def __init__(self, stream: io.BufferedIOBase):
        self.stream = stream

    def decode(self):
        return _visit(self.stream)


if __name__ == "__main__":
    # for r in _DECODE_RANGES:
    #     print(f"{r.tipe} {hex(r.start)} - {hex(r.end)}")

    import json
    import json.scanner

    # Patch the default decoder to use pure Python scanner
    _py_decoder = json.JSONDecoder()
    _py_decoder.scan_once = json.scanner.py_make_scanner(_py_decoder)
    json._default_decoder = _py_decoder
    import time
    import msgpack

    # test_val = ["hello", 0, 10, 259, -10, -9449554]
    # print(json.dumps(test_val))
    # print()

    def report(title, data, encoder, decoder):
        print(f"=={title}")
        start = time.perf_counter()
        raw = encoder(data)
        end = time.perf_counter()
        print(f"\tEncoding size: {len(raw)}")
        print(f"\tEncoding time: {end - start:.6f} seconds")

        start = time.perf_counter()
        data = decoder(raw)
        end = time.perf_counter()
        print(f"\tDecoding time: {end - start:.6f} seconds")

    data = None
    for fname in [
        "DeckList.json",
        "nepse-listed-companies-2021.json",
        "nobel-prize-winners-by-year.json",
    ]:
        print(f"file: {fname}")

        with open(fname) as f:
            data = json.load(f)

        report("JSON", data, json.dumps, json.loads)
        report("msgpack", data, msgpack.dumps, msgpack.loads)
        report("ratpack", data, encode, decode)
        print()
