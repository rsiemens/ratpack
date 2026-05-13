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


UINT_SMALL_START = 0x00
UINT_SMALL_END = 0x40
UINT_VAR = 0x41

NEG_INT_SMALL_START = 0x42
NEG_INT_SMALL_END = 0x62
NEG_INT_VAR = 0x63

BIN_SMALL_START = 0x64
BIN_SMALL_END = 0x74
BIN_VAR = 0x75

STR_SMALL_NUM_START = 0x76
STR_SMALL_NUM_END = 0x9A
STR_VAR = 0x9B

ARR_SMALL_NUM_START = 0x9C
ARR_SMALL_NUM_END = 0xC0
ARR_VAR = 0xC1

MAP_SMALL_NUM_START = 0xC2
MAP_SMALL_NUM_END = 0xE6
MAP_VAR = 0xE7

# TODO
FLOAT32 = 0xE8
FLOAT64 = 0xE9
TRUE = 0xEA
FALSE = 0xEB
NULL = 0xEC

# TODO
TAG_SMALL_START = 0xED
TAG_SMALL_END = 0xFD
TAG_VAR = 0xFE

# The MAGIC_NUMBER_START is only valid at the very begining of a file or ratpack stream.
# It is not required, but if it is present, it must be immedidiately followed by the ascii encode
# characters "rp" and a version byte 0x00-0xFF.
MAGIC_NUMBER_START = 0xFF
MAGIC_NUMER_TAG = b"rp\x00"

MAX_ENC_INT = 2**128 - 1
u8packer = struct.Struct(">B")


def leb128_enc(n: int, writer: io.BufferedIOBase):
    """Little endian base 128 https://en.wikipedia.org/wiki/LEB128"""
    if n < 0 or n > MAX_ENC_INT:
        raise RatPackException(
            f"leb128_enc only encodes positive numbers up to {MAX_ENC_INT}. Was given {n}"
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
        if n > MAX_ENC_INT:
            raise RatPackException(
                f"Malformed leb128 encoded value. Exceeds max int ({MAX_ENC_INT})"
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
        if i <= UINT_SMALL_END - UINT_SMALL_START:
            self.stream.write(u8packer.pack(UINT_SMALL_START + i))
        else:
            self.stream.write(u8packer.pack(UINT_VAR))
            leb128_enc(i, self.stream)

    def _encode_negative_int(self, i: int):
        i = abs(i)
        if i <= NEG_INT_SMALL_END - NEG_INT_SMALL_START:
            self.stream.write(u8packer.pack(NEG_INT_SMALL_START + i))
        else:
            self.stream.write(u8packer.pack(NEG_INT_VAR))
            leb128_enc(i, self.stream)

    def _encode_bytes(self, b: bytes):
        size = len(b)
        if size <= BIN_SMALL_END - BIN_SMALL_START:
            self.stream.write(u8packer.pack(BIN_SMALL_START + size))
        else:
            self.stream.write(u8packer.pack(BIN_VAR))
            leb128_enc(size, self.stream)

        self.stream.write(b)

    def _encode_str(self, s: str):
        val = s.encode("utf8")
        size = len(val)

        if size <= STR_SMALL_NUM_END - STR_SMALL_NUM_START:
            self.stream.write(u8packer.pack(STR_SMALL_NUM_START + size))
        else:
            self.stream.write(u8packer.pack(STR_VAR))
            leb128_enc(size, self.stream)

        self.stream.write(val)

    def _encode_list(self, l: list):
        size = len(l)
        if size <= ARR_SMALL_NUM_END - ARR_SMALL_NUM_START:
            self.stream.write(u8packer.pack(ARR_SMALL_NUM_START + size))
        else:
            self.stream.write(u8packer.pack(ARR_VAR))
            leb128_enc(size, self.stream)

        for i in l:
            self.encode(i)

    def _encode_dict(self, d: dict):
        size = len(d)
        if size <= MAP_SMALL_NUM_END - MAP_SMALL_NUM_START:
            self.stream.write(u8packer.pack(MAP_SMALL_NUM_START + size))
        else:
            self.stream.write(u8packer.pack(MAP_VAR))
            leb128_enc(size, self.stream)

        for k, v in d.items():
            self.encode(k)
            self.encode(v)

    # TODO float + tag
    def _encode_bool(self, b: bool):
        self.stream.write(u8packer.pack(TRUE if b else FALSE))

    def _encode_NoneType(self, _: None):
        self.stream.write(u8packer.pack(NULL))


def _not_implemented(marker: int, stream: io.BufferedIOBase):
    pos = stream.tell()
    raise NotImplementedError(f"{hex(marker)} not implemented (at position {pos})")


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


@register(UINT_SMALL_START, UINT_SMALL_END)
def _decode_small_int(marker: int, _: io.BufferedIOBase) -> int:
    return marker


@register(UINT_VAR)
def _decode_int_var(_: int, stream: io.BufferedIOBase) -> int:
    return leb128_dec(stream)


@register(NEG_INT_SMALL_START, NEG_INT_SMALL_END)
def _decode_small_neg_int(marker: int, _: io.BufferedIOBase) -> int:
    return -(marker - NEG_INT_SMALL_START)


@register(NEG_INT_VAR)
def _decode_neg_int_var(_: int, stream: io.BufferedIOBase) -> int:
    return -(leb128_dec(stream))


def _read_n_bytes(size: int, stream: io.BufferedIOBase) -> bytes:
    val = b""
    while size > 0:
        read = stream.read(size)
        size -= len(read)
        val += read
    return val


@register(STR_SMALL_NUM_START, STR_SMALL_NUM_END)
def _decode_small_str(marker: int, stream: io.BufferedIOBase) -> str:
    size = marker - STR_SMALL_NUM_START
    return _read_n_bytes(size, stream).decode("utf8")


@register(STR_VAR)
def _decode_str_var(_: int, stream: io.BufferedIOBase) -> str:
    size = leb128_dec(stream)
    return _read_n_bytes(size, stream).decode("utf8")


@register(ARR_SMALL_NUM_START, ARR_SMALL_NUM_END)
def _decode_small_arr(marker: int, stream: io.BufferedIOBase) -> list:
    size = marker - ARR_SMALL_NUM_START
    ctx = [None] * size
    for i in range(size):
        ctx[i] = _visit(stream)
    return ctx


@register(ARR_VAR)
def _decode_arr_var(_: int, stream: io.BufferedIOBase) -> list:
    size = leb128_dec(stream)
    ctx = [None] * size
    for i in range(size):
        ctx[i] = _visit(stream)
    return ctx


@register(MAP_SMALL_NUM_START, MAP_SMALL_NUM_END)
def _decode_small_map(marker: int, stream: io.BufferedIOBase) -> dict:
    size = marker - MAP_SMALL_NUM_START
    ctx = {}
    for _ in range(size):
        k = _visit(stream)
        v = _visit(stream)
        ctx[k] = v
    return ctx


@register(MAP_VAR)
def _decode_map_var(_: int, stream: io.BufferedIOBase) -> dict:
    size = leb128_dec(stream)
    ctx = {}
    for _ in range(size):
        k = _visit(stream)
        ctx[k] = _visit(stream)
    return ctx


@register(TRUE)
def _decode_true(_: int, __: io.BufferedIOBase) -> bool:
    return True


@register(FALSE)
def _decode_false(_: int, __: io.BufferedIOBase) -> bool:
    return False


@register(NULL)
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
