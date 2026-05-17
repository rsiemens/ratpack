"""
Ratpack is a relatively simple and efficent schemaless binary serialization format.
"""

from __future__ import annotations

import io
import math
import struct
from collections.abc import Buffer
from typing import Any, Callable, Generic, Protocol, TypeAlias, TypeVar, Union

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


class BinaryReader(Protocol):
    def read(self, size: int | None = -1, /) -> bytes: ...


class BinaryWriter(Protocol):
    def write(self, bites: Buffer, /) -> int: ...


class RatPackException(Exception):
    pass


class RatPackEncodingException(RatPackException):
    pass


class RatPackDecodingException(RatPackException):
    pass


UINT_SMALL_START = 0x00
UINT_SMALL_END = 0x40
UINT8 = 0x41
UINT16 = 0x42
UINT32 = 0x43
UINT64 = 0x44

NEG_INT_SMALL_START = 0x45
NEG_INT_SMALL_END = 0x67
NEG_INT8 = 0x68
NEG_INT16 = 0x69
NEG_INT32 = 0x6A
NEG_INT64 = 0x6B

BIN_SMALL_START = 0x6C
BIN_SMALL_END = 0x7C
BIN_VAR = 0x7D

STR_SMALL_NUM_START = 0x7E
STR_SMALL_NUM_END = 0xA2
STR_VAR = 0xA3

ARR_SMALL_NUM_START = 0xA4
ARR_SMALL_NUM_END = 0xC4
ARR_VAR = 0xC5

MAP_SMALL_NUM_START = 0xC6
MAP_SMALL_NUM_END = 0xE6
MAP_VAR = 0xE7

FLOAT32 = 0xE8
FLOAT64 = 0xE9
TRUE = 0xEA
FALSE = 0xEB
NULL = 0xEC

TAG_SMALL_START = 0xED
TAG_SMALL_END = 0xFD
TAG_VAR = 0xFE
# first 8 tags are reserved
TAG_RESERVED = {i for i in range(8)}

# The MAGIC_NUMBER_START is only valid at the very begining of a file or ratpack stream.
# It is not required, but if it is present, it must be immedidiately followed by the ascii encode
# characters "rp" and a version byte 0x00-0xFF.
MAGIC_NUMBER_START = 0xFF
MAGIC_NUMER_SIG = b"rp\x00"

_u16 = struct.Struct("<H")
_u32 = struct.Struct("<I")
_u64 = struct.Struct("<Q")
_f32 = struct.Struct("<f")
_f64 = struct.Struct("<d")
_BYTES_TABLE = [bytes([i]) for i in range(0xFF + 1)]


def leb128_enc(n: int, writer: BinaryWriter) -> None:
    """Little endian base 128 https://en.wikipedia.org/wiki/LEB128"""
    byte = n & 0x7F  # mask the lower 7 bits leaving the msb as 0
    n >>= 7
    while n:
        writer.write(_BYTES_TABLE[byte | 0x80])
        byte = n & 0x7F
        n >>= 7
    writer.write(_BYTES_TABLE[byte])


def leb128_dec(reader: BinaryReader) -> int:
    n = 0
    shift = 0

    while True:
        try:
            byte = reader.read(1)[0]
        except IndexError:
            raise RatPackDecodingException("Malformed leb128 encoded payload")

        n |= (byte & 0x7F) << shift
        shift += 7
        if byte & 0x80 == 0:
            break
    return n


T = TypeVar("T")


class Tag(Generic[T]):
    def __init__(
        self,
        id: int,
        obj_type: type[T],
        encoder: Callable[[T], RatType],
        decoder: Callable[[RatType], T],
    ):
        self.id = id
        self.obj_type = obj_type
        self.encoder = encoder
        self.decoder = decoder

    def encode(self, obj: T) -> RatType:
        return self.encoder(obj)

    def decode(self, item: RatType) -> T:
        return self.decoder(item)

    def __repr__(self) -> str:
        return f"<Tag({self.id} {self.obj_type})>"


def packb(
    obj: Any, tags: list[Tag] | None = None, include_header: bool = False
) -> bytes:
    stream = io.BytesIO()
    encoder = Encoder(stream, tags, include_header=include_header)
    encoder.encode(obj)
    return stream.getvalue()


def unpackb(bites: bytes, tags: list[Tag] | None = None) -> Any:
    return Decoder(io.BytesIO(bites), tags).decode()


def pack(
    obj: Any,
    fp: BinaryWriter,
    tags: list[Tag] | None = None,
    include_header: bool = False,
) -> None:
    encoder = Encoder(fp, tags, include_header=include_header)
    encoder.encode(obj)


def unpack(fp: BinaryReader, tags: list[Tag] | None = None) -> Any:
    return Decoder(fp, tags).decode()


dumps = packb
loads = unpackb
dump = pack
load = unpack


class Encoder:
    def __init__(
        self,
        stream: BinaryWriter,
        tags: list[Tag] | None = None,
        include_header: bool = False,
    ):
        self.stream = stream
        self.tags: dict[Any, Tag] = {}
        self.include_header = include_header

        if tags is not None:
            tag_ids = TAG_RESERVED.copy()
            for tag in tags:
                if tag.id in tag_ids:
                    raise RatPackException(
                        f"Tag id {tag.id} is already in use or reserved"
                    )
                elif tag.obj_type in self.tags:
                    existing_tag = self.tags[tag.obj_type]
                    raise RatPackException(
                        f"Tag for {tag.obj_type} is already in use by {existing_tag}"
                    )
                tag_ids.add(tag.id)
                self.tags[tag.obj_type] = tag

    def encode(self, obj: Any) -> None:
        if self.include_header:
            self._encode_header()
        self._encode(obj)

    def _encode(self, obj: Any) -> None:
        if isinstance(obj, int):
            self._encode_int(obj)
        elif isinstance(obj, bytes):
            self._encode_bytes(obj)
        elif isinstance(obj, str):
            self._encode_str(obj)
        elif isinstance(obj, list):
            self._encode_list(obj)
        elif isinstance(obj, dict):
            self._encode_dict(obj)
        elif isinstance(obj, float):
            self._encode_float(obj)
        elif isinstance(obj, bool):
            self.stream.write(_BYTES_TABLE[TRUE if obj else FALSE])
        elif obj is None:
            self.stream.write(_BYTES_TABLE[NULL])
        else:
            try:
                tag = self.tags[type(obj)]
            except KeyError:
                raise RatPackEncodingException(f"unable to encode {type(obj)}")
            self._encode_tag(tag, obj)

    def _encode_header(self) -> None:
        self.stream.write(_BYTES_TABLE[MAGIC_NUMBER_START])
        self.stream.write(MAGIC_NUMER_SIG)

    def _encode_int(self, i: int) -> None:
        if i >= 0:
            return self._encode_positive_int(i)
        return self._encode_negative_int(i)

    def _encode_positive_int(self, i: int) -> None:
        if i <= UINT_SMALL_END - UINT_SMALL_START:
            self.stream.write(_BYTES_TABLE[UINT_SMALL_START + i])
        elif i <= 0xFF:
            self.stream.write(_BYTES_TABLE[UINT8])
            self.stream.write(_BYTES_TABLE[i])
        elif i <= 0xFFFF:
            self.stream.write(_BYTES_TABLE[UINT16])
            self.stream.write(_u16.pack(i))
        elif i <= 0xFFFFFFFF:
            self.stream.write(_BYTES_TABLE[UINT32])
            self.stream.write(_u32.pack(i))
        elif i <= 0xFFFFFFFFFFFFFFFF:
            self.stream.write(_BYTES_TABLE[UINT64])
            self.stream.write(_u64.pack(i))
        else:
            raise RatPackEncodingException(
                "unable to encode numbers larger than 2**64-1"
            )

    def _encode_negative_int(self, i: int) -> None:
        i = -i
        if i <= NEG_INT_SMALL_END - NEG_INT_SMALL_START + 1:
            self.stream.write(_BYTES_TABLE[NEG_INT_SMALL_START + i - 1])
        elif i <= 0xFF:
            self.stream.write(_BYTES_TABLE[NEG_INT8])
            self.stream.write(_BYTES_TABLE[i])
        elif i <= 0xFFFF:
            self.stream.write(_BYTES_TABLE[NEG_INT16])
            self.stream.write(_u16.pack(i))
        elif i <= 0xFFFFFFFF:
            self.stream.write(_BYTES_TABLE[NEG_INT32])
            self.stream.write(_u32.pack(i))
        elif i <= 0xFFFFFFFFFFFFFFFF:
            self.stream.write(_BYTES_TABLE[NEG_INT64])
            self.stream.write(_u64.pack(i))
        else:
            raise RatPackEncodingException(
                "unable to encode numbers smaller than -(2**64-1)"
            )

    def _encode_bytes(self, b: bytes) -> None:
        size = len(b)
        if size <= BIN_SMALL_END - BIN_SMALL_START:
            self.stream.write(_BYTES_TABLE[BIN_SMALL_START + size])
        else:
            self.stream.write(_BYTES_TABLE[BIN_VAR])
            leb128_enc(size, self.stream)

        self.stream.write(b)

    def _encode_str(self, s: str) -> None:
        val = s.encode("utf8")
        size = len(val)

        if size <= STR_SMALL_NUM_END - STR_SMALL_NUM_START:
            self.stream.write(_BYTES_TABLE[STR_SMALL_NUM_START + size])
        else:
            self.stream.write(_BYTES_TABLE[STR_VAR])
            leb128_enc(size, self.stream)

        self.stream.write(val)

    def _encode_list(self, items: list) -> None:
        size = len(items)
        if size <= ARR_SMALL_NUM_END - ARR_SMALL_NUM_START:
            self.stream.write(_BYTES_TABLE[ARR_SMALL_NUM_START + size])
        else:
            self.stream.write(_BYTES_TABLE[ARR_VAR])
            leb128_enc(size, self.stream)

        for i in items:
            self._encode(i)

    def _encode_dict(self, d: dict) -> None:
        size = len(d)
        if size <= MAP_SMALL_NUM_END - MAP_SMALL_NUM_START:
            self.stream.write(_BYTES_TABLE[MAP_SMALL_NUM_START + size])
        else:
            self.stream.write(_BYTES_TABLE[MAP_VAR])
            leb128_enc(size, self.stream)

        parent_stream = self.stream
        kv_pairs: list[tuple[bytes, Any]] = []
        for k, v in d.items():
            key_stream = io.BytesIO()
            self.stream = key_stream
            self._encode(k)
            kv_pairs.append((key_stream.getvalue(), v))

        self.stream = parent_stream
        kv_pairs.sort(key=lambda p: p[0])

        for k, v in kv_pairs:
            self.stream.write(k)
            self._encode(v)

    def _encode_float(self, f: float) -> None:
        f32packed = _f32.pack(f)

        if _f32.unpack(f32packed)[0] == f or math.isnan(f):
            self.stream.write(_BYTES_TABLE[FLOAT32])
            self.stream.write(f32packed)
        else:
            self.stream.write(_BYTES_TABLE[FLOAT64])
            self.stream.write(_f64.pack(f))

    def _encode_tag(self, tag: Tag, obj: RatType) -> None:
        rat_obj = tag.encode(obj)

        if tag.id <= TAG_SMALL_END - TAG_SMALL_START:
            self.stream.write(_BYTES_TABLE[TAG_SMALL_START + tag.id])
        else:
            self.stream.write(_BYTES_TABLE[TAG_VAR])
            leb128_enc(tag.id, self.stream)

        self._encode(rat_obj)


def _not_implemented(_: Decoder, marker: int) -> None:
    raise NotImplementedError(f"{hex(marker)} not implemented")


_DECODE_TABLE = [_not_implemented] * 0xFF


class register:
    def __init__(self, start: int, stop: int | None = None):
        self.start = start
        if stop is None:
            self.stop = self.start
        else:
            self.stop = stop

    def __call__(self, func: Callable) -> Callable:
        # inclusive
        for i in range(self.start, self.stop + 1):
            _DECODE_TABLE[i] = func

        return func


class ItemWrappedStream:
    def __init__(self, stream: BinaryReader):
        self.stream = stream
        self.item = io.BytesIO()

    def read(self, size: int | None = -1) -> bytes:
        bites = self.stream.read(size)
        self.item.write(bites)
        return bites


class Decoder:
    def __init__(self, stream: BinaryReader, tags: list[Tag] | None = None):
        self.stream = stream
        self.tags: dict[int, Tag] = {}

        if tags is not None:
            for tag in tags:
                if tag.id in TAG_RESERVED or tag.id in self.tags:
                    raise RatPackException(
                        f"Tag id {tag.id} is already in use or reserved"
                    )
                self.tags[tag.id] = tag

    def decode(self) -> Any:
        return self._visit_first()

    def _visit_first(self) -> Any:
        marker = self.stream.read(1)[0]
        if marker == MAGIC_NUMBER_START:
            sig = self.stream.read(3)
            if sig != MAGIC_NUMER_SIG:
                raise RatPackDecodingException("invalid file signature")
            return self._visit()
        return _DECODE_TABLE[marker](self, marker)

    def _visit(self) -> Any:
        marker = self.stream.read(1)[0]
        return _DECODE_TABLE[marker](self, marker)

    @register(UINT_SMALL_START, UINT_SMALL_END)
    def _decode_small_uint(self, marker: int) -> int:
        return marker

    @register(UINT8, UINT64)
    def _decode_fixed_uint(self, marker: int) -> int:
        if marker == UINT8:
            return self.stream.read(1)[0]
        if marker == UINT16:
            return _u16.unpack(self.stream.read(2))[0]
        if marker == UINT32:
            return _u32.unpack(self.stream.read(4))[0]
        if marker == UINT64:
            return _u64.unpack(self.stream.read(8))[0]
        # should be unreachable
        raise RatPackDecodingException(f"unable to deocde fixed size int ({marker})")

    @register(NEG_INT_SMALL_START, NEG_INT_SMALL_END)
    def _decode_small_neg_int(self, marker: int) -> int:
        return -(marker - NEG_INT_SMALL_START + 1)

    @register(NEG_INT8, NEG_INT64)
    def _decode_fixed_neg_int(self, marker: int) -> int:
        if marker == NEG_INT8:
            return -self.stream.read(1)[0]
        if marker == NEG_INT16:
            return -_u16.unpack(self.stream.read(2))[0]
        if marker == NEG_INT32:
            return -_u32.unpack(self.stream.read(4))[0]
        if marker == NEG_INT64:
            return -_u64.unpack(self.stream.read(8))[0]
        # should be unreachable
        raise RatPackDecodingException(
            f"unable to deocde fixed size neg int ({marker})"
        )

    @register(BIN_SMALL_START, BIN_SMALL_END)
    def _decode_small_bin(self, marker: int) -> bytes:
        size = marker - BIN_SMALL_START
        return self.stream.read(size)

    @register(BIN_VAR)
    def _decode_bin_var(self, _: int) -> bytes:
        size = leb128_dec(self.stream)
        if size < BIN_SMALL_END - BIN_SMALL_START:
            raise RatPackDecodingException("small bin encoded as bin var")
        return self.stream.read(size)

    @register(STR_SMALL_NUM_START, STR_SMALL_NUM_END)
    def _decode_small_str(self, marker: int) -> str:
        size = marker - STR_SMALL_NUM_START
        return self.stream.read(size).decode("utf8")

    @register(STR_VAR)
    def _decode_str_var(self, _: int) -> str:
        size = leb128_dec(self.stream)
        if size < STR_SMALL_NUM_END - STR_SMALL_NUM_START:
            raise RatPackDecodingException("small str encoded as str var")
        return self.stream.read(size).decode("utf8")

    @register(ARR_SMALL_NUM_START, ARR_VAR)
    def _decode_arr(self, marker: int) -> list:
        if marker == ARR_VAR:
            size = leb128_dec(self.stream)
            if size < ARR_SMALL_NUM_END - ARR_SMALL_NUM_START:
                raise RatPackDecodingException("small array encoded as array var")
        else:
            size = marker - ARR_SMALL_NUM_START

        ctx = [None] * size
        for i in range(size):
            ctx[i] = self._visit()
        return ctx

    @register(MAP_SMALL_NUM_START, MAP_VAR)
    def _decode_map(self, marker: int) -> dict:
        if marker == MAP_VAR:
            size = leb128_dec(self.stream)
            if size < MAP_SMALL_NUM_END - MAP_SMALL_NUM_START:
                raise RatPackDecodingException("small map encoded as map var")
        else:
            size = marker - MAP_SMALL_NUM_START

        ctx = {}
        last_item = None

        for _ in range(size):
            self.stream = ItemWrappedStream(self.stream)
            k = self._visit()
            item = self.stream.item.getvalue()
            # transitivity ensures all keys are lexigraphicaly orderd smallest to largest
            if last_item is not None and item < last_item:
                raise RatPackDecodingException("map keys are out of order")
            last_item = item
            self.stream = self.stream.stream

            ctx[k] = self._visit()

        return ctx

    @register(FLOAT32)
    def _decode_f32(self, _: int) -> float:
        return _f32.unpack(self.stream.read(4))[0]

    @register(FLOAT64)
    def _decode_f64(self, _: int) -> float:
        f = _f64.unpack(self.stream.read(8))[0]

        can_be_f32 = _f32.unpack(_f32.pack(f))[0] == f
        if can_be_f32:
            raise RatPackDecodingException("f32 representable float encoded as f64")

        return f

    @register(TRUE)
    def _decode_true(self, _: int) -> bool:
        return True

    @register(FALSE)
    def _decode_false(self, _: int) -> bool:
        return False

    @register(NULL)
    def _decode_null(self, _: int) -> None:
        return None

    @register(TAG_SMALL_START, TAG_SMALL_END)
    def _decode_tag_small(self, marker: int) -> RatType:
        tag_id = marker - TAG_SMALL_START
        tag = self.tags[tag_id]
        obj = self._visit()
        return tag.decode(obj)

    @register(TAG_VAR)
    def _decode_tag_var(self, _: int) -> RatType:
        tag_id = leb128_dec(self.stream)

        if tag_id < TAG_SMALL_END - TAG_SMALL_START:
            raise RatPackDecodingException("small tag encoded as tag var")

        tag = self.tags[tag_id]
        obj = self._visit()
        return tag.decode(obj)
