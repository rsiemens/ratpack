"""
Ratpack is a relatively simple and efficent schemaless binary serialization format.
"""

import io
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

MAX_ENC_INT = 2**64 - 1
u8packer = struct.Struct(">B")
f32packer = struct.Struct(">f")
f64packer = struct.Struct(">d")

_BYTES_TABLE = [u8packer.pack(i) for i in range(0xFF + 1)]


def leb128_enc(n: int, writer: BinaryWriter, max_size: int = MAX_ENC_INT) -> None:
    """Little endian base 128 https://en.wikipedia.org/wiki/LEB128"""
    if n < 0 or n > max_size:
        raise RatPackEncodingException(
            f"leb128_enc only encodes positive numbers up to {max_size}. Was given {n}"
        )
    elif n == 0:
        writer.write(_BYTES_TABLE[0])
        return

    while n:
        byte = n & 0x7F  # mask the lower 7 bits leaving the msb as 0
        n >>= 7
        if n:
            writer.write(_BYTES_TABLE[byte | 0x80])  # msb set to 1 for continuation
        else:
            writer.write(_BYTES_TABLE[byte])
            break


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
        if n > MAX_ENC_INT:
            raise RatPackDecodingException(
                f"Malformed leb128 encoded value. Exceeds max int ({MAX_ENC_INT})"
            )
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

    def __repr__(self):
        return f"<Tag({self.id} {self.obj_type})>"


def encode(obj: Any, tags: list[Tag] | None = None) -> bytes:
    stream = io.BytesIO()
    encoder = Encoder(stream, tags)
    encoder.encode(obj)
    return stream.getvalue()


def decode(bites: bytes, tags: list[Tag] | None = None) -> Any:
    return Decoder(io.BytesIO(bites), tags).decode()


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

    def encode(self, obj: Any):
        if self.include_header:
            self._encode_header()
        self._encode(obj)

    def _encode(self, obj: Any):
        tipe = type(obj).__name__
        dispatch = getattr(self, f"_encode_{tipe}", None)

        # TODO errors on tags[tipe] or dispatch==None
        if dispatch is None:
            tag = self.tags[type(obj)]
            self._encode_tag(tag, obj)
            return

        dispatch(obj)

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
        else:
            self.stream.write(_BYTES_TABLE[UINT_VAR])
            leb128_enc(i, self.stream)

    def _encode_negative_int(self, i: int) -> None:
        i = abs(i)
        if i <= NEG_INT_SMALL_END - NEG_INT_SMALL_START:
            self.stream.write(_BYTES_TABLE[NEG_INT_SMALL_START + i])
        else:
            self.stream.write(_BYTES_TABLE[NEG_INT_VAR])
            leb128_enc(i, self.stream)

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
        can_be_f32 = f32packer.unpack(f32packer.pack(f))[0] == f
        if can_be_f32:
            self.stream.write(struct.pack(">Bf", FLOAT32, f))
        else:
            self.stream.write(struct.pack(">Bd", FLOAT64, f))

    def _encode_bool(self, b: bool) -> None:
        self.stream.write(_BYTES_TABLE[TRUE if b else FALSE])

    def _encode_NoneType(self, _: None) -> None:
        self.stream.write(_BYTES_TABLE[NULL])

    def _encode_tag(self, tag: Tag, obj: RatType) -> None:
        rat_obj = tag.encode(obj)

        if tag.id <= TAG_SMALL_END - TAG_SMALL_START:
            self.stream.write(_BYTES_TABLE[TAG_SMALL_START + tag.id])
        else:
            self.stream.write(_BYTES_TABLE[TAG_VAR])
            leb128_enc(tag.id, self.stream)

        self._encode(rat_obj)


def _not_implemented(obj, marker: int) -> None:
    pos = obj.stream.tell()
    raise NotImplementedError(f"{hex(marker)} not implemented (at position {pos})")


_DECODE_TABLE = [_not_implemented] * 0xFF


class register:
    def __init__(self, start: int, stop: int | None = None):
        self.start = start
        if stop is None:
            self.stop = self.start
        else:
            self.stop = stop

    def __call__(self, func):
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

    def reset_item(self) -> None:
        self.item.truncate()

    def get_and_reset_item(self) -> bytes:
        item = self.item.getvalue()
        self.item.truncate()
        return item


class Decoder:
    def __init__(self, stream: BinaryReader, tags: list[Tag] | None = None):
        self.stream = stream
        self.tags: dict[int, Tag] = {}
        self._first_visit = True

        if tags is not None:
            for tag in tags:
                if tag.id in TAG_RESERVED or tag.id in self.tags:
                    raise RatPackException(
                        f"Tag id {tag.id} is already in use or reserved"
                    )
                self.tags[tag.id] = tag

    def decode(self) -> Any:
        return self._visit()

    def _visit(self) -> Any:
        marker = self.stream.read(1)[0]
        if self._first_visit:
            self._first_visit = False
            if marker == MAGIC_NUMBER_START:
                sig = self.stream.read(3)
                if sig != MAGIC_NUMER_SIG:
                    raise RatPackDecodingException("invalid file signature")
                return self._visit()

        return _DECODE_TABLE[marker](self, marker)

    @register(UINT_SMALL_START, UINT_SMALL_END)
    def _decode_small_uint(self, marker: int) -> int:
        return marker

    @register(UINT_VAR)
    def _decode_uint_var(self, _: int) -> int:
        n = leb128_dec(self.stream)
        if n < UINT_SMALL_END - UINT_SMALL_START:
            raise RatPackDecodingException("small unsigned int encoded as var int")
        return n

    @register(NEG_INT_SMALL_START, NEG_INT_SMALL_END)
    def _decode_small_neg_int(self, marker: int) -> int:
        return -(marker - NEG_INT_SMALL_START)

    @register(NEG_INT_VAR)
    def _decode_neg_int_var(self, _: int) -> int:
        n = leb128_dec(self.stream)
        if n < NEG_INT_SMALL_END - NEG_INT_SMALL_START:
            raise RatPackDecodingException(
                "small negative int encoded as negative var int"
            )
        return -n

    def _read_n_bytes(self, size: int, stream: BinaryReader) -> bytes:
        val = b""
        while size > 0:
            read = stream.read(size)
            size -= len(read)
            val += read
        return val

    @register(BIN_SMALL_START, BIN_SMALL_START)
    def _decode_small_bin(self, marker: int) -> bytes:
        size = marker - BIN_SMALL_START
        return self._read_n_bytes(size, self.stream)

    @register(BIN_VAR)
    def _decode_bin_var(self, _: int) -> bytes:
        size = leb128_dec(self.stream)
        if size < BIN_SMALL_END - BIN_SMALL_START:
            raise RatPackDecodingException("small bin encoded as bin var")
        return self._read_n_bytes(size, self.stream)

    @register(STR_SMALL_NUM_START, STR_SMALL_NUM_END)
    def _decode_small_str(self, marker: int) -> str:
        size = marker - STR_SMALL_NUM_START
        return self._read_n_bytes(size, self.stream).decode("utf8")

    @register(STR_VAR)
    def _decode_str_var(self, _: int) -> str:
        size = leb128_dec(self.stream)
        if size < STR_SMALL_NUM_END - STR_SMALL_NUM_START:
            raise RatPackDecodingException("small str encoded as str var")
        return self._read_n_bytes(size, self.stream).decode("utf8")

    @register(ARR_SMALL_NUM_START, ARR_SMALL_NUM_END)
    def _decode_small_arr(self, marker: int) -> list:
        size = marker - ARR_SMALL_NUM_START
        ctx = [None] * size
        for i in range(size):
            ctx[i] = self._visit()
        return ctx

    @register(ARR_VAR)
    def _decode_arr_var(self, _: int) -> list:
        size = leb128_dec(self.stream)
        if size < ARR_SMALL_NUM_END - ARR_SMALL_NUM_START:
            raise RatPackDecodingException("small array encoded as array var")

        ctx = [None] * size
        for i in range(size):
            ctx[i] = self._visit()
        return ctx

    @register(MAP_SMALL_NUM_START, MAP_SMALL_NUM_END)
    def _decode_small_map(self, marker: int) -> dict:
        size = marker - MAP_SMALL_NUM_START
        return self._decode_map_items(size)

    @register(MAP_VAR)
    def _decode_map_var(self, _: int) -> dict:
        size = leb128_dec(self.stream)
        if size < MAP_SMALL_NUM_END - MAP_SMALL_NUM_START:
            raise RatPackDecodingException("small map encoded as map var")

        return self._decode_map_items(size)

    def _decode_map_items(self, size: int) -> dict:
        ctx = {}
        self.stream = ItemWrappedStream(self.stream)
        last_item = None

        for _ in range(size):
            k = self._visit()

            item = self.stream.get_and_reset_item()
            # transitivity ensures all keys are lexigraphicaly orderd smallest to largest
            if last_item is not None and item < last_item:
                raise RatPackDecodingException("map keys are out of order")
            last_item = item

            ctx[k] = self._visit()
            self.stream.reset_item()

        self.stream = self.stream.stream
        return ctx

    @register(FLOAT32)
    def _decode_f32(self, _: int) -> float:
        bites = self._read_n_bytes(4, self.stream)
        return f32packer.unpack(bites)[0]

    @register(FLOAT64)
    def _decode_f64(self, _: int) -> float:
        bites = self._read_n_bytes(8, self.stream)
        f = f64packer.unpack(bites)[0]

        can_be_f32 = f32packer.unpack(f32packer.pack(f))[0] == f
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
