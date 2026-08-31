from __future__ import annotations

import io
from typing import Any, Callable

from packrat.constants import (
    ARR_SMALL_NUM_END,
    ARR_SMALL_NUM_START,
    ARR_VAR,
    BIN_SMALL_END,
    BIN_SMALL_START,
    BIN_VAR,
    FALSE,
    FLOAT32,
    FLOAT64,
    MAGIC_NUMBER_START,
    MAGIC_NUMER_SIG,
    MAP_SMALL_NUM_END,
    MAP_SMALL_NUM_START,
    MAP_VAR,
    NEG_INT8,
    NEG_INT16,
    NEG_INT32,
    NEG_INT64,
    NEG_INT_SMALL_END,
    NEG_INT_SMALL_START,
    NULL,
    STR_SMALL_NUM_END,
    STR_SMALL_NUM_START,
    STR_VAR,
    TAG_RESERVED,
    TAG_SMALL_END,
    TAG_SMALL_START,
    TAG_VAR,
    TRUE,
    UINT8,
    UINT16,
    UINT32,
    UINT64,
    UINT_SMALL_END,
    UINT_SMALL_START,
)
from packrat.exceptions import PackRatDecodingException, PackRatException
from packrat.tags import ISODateTimeTag, Tag, UUIDTag
from packrat.types import BinaryReader
from packrat.utils import f32, f64, u16, u32, u64, vlq_dec


def _not_implemented(_: Decoder, marker: int) -> None:
    raise NotImplementedError(f"{hex(marker)} not implemented")


_DECODE_TABLE: list[Callable[[Decoder, int], Any]] = [_not_implemented] * 0xFF


def _decode_small_uint(decoder: Decoder, marker: int) -> int:
    return marker


def _decode_fixed_uint(decoder: Decoder, marker: int) -> int:
    if marker == UINT8:
        return decoder.stream.read(1)[0]
    if marker == UINT16:
        return u16.unpack(decoder.stream.read(2))[0]
    if marker == UINT32:
        return u32.unpack(decoder.stream.read(4))[0]
    if marker == UINT64:
        return u64.unpack(decoder.stream.read(8))[0]
    # should be unreachable
    raise PackRatDecodingException(f"unable to deocde fixed size int ({marker})")


def _decode_small_neg_int(decoder: Decoder, marker: int) -> int:
    return -(marker - NEG_INT_SMALL_START + 1)


def _decode_fixed_neg_int(decoder: Decoder, marker: int) -> int:
    if marker == NEG_INT8:
        return -decoder.stream.read(1)[0]
    if marker == NEG_INT16:
        return -u16.unpack(decoder.stream.read(2))[0]
    if marker == NEG_INT32:
        return -u32.unpack(decoder.stream.read(4))[0]
    if marker == NEG_INT64:
        return -u64.unpack(decoder.stream.read(8))[0]
    # should be unreachable
    raise PackRatDecodingException(f"unable to deocde fixed size neg int ({marker})")


def _decode_small_bin(decoder: Decoder, marker: int) -> bytes:
    size = marker - BIN_SMALL_START
    return decoder.stream.read(size)


def _decode_bin_var(decoder: Decoder, _: int) -> bytes:
    size = vlq_dec(decoder.stream)
    if size < BIN_SMALL_END - BIN_SMALL_START:
        raise PackRatDecodingException("small bin encoded as bin var")
    return decoder.stream.read(size)


def _decode_small_str(decoder: Decoder, marker: int) -> str:
    size = marker - STR_SMALL_NUM_START
    return decoder.stream.read(size).decode("utf8")


def _decode_str_var(decoder: Decoder, _: int) -> str:
    size = vlq_dec(decoder.stream)
    if size < STR_SMALL_NUM_END - STR_SMALL_NUM_START:
        raise PackRatDecodingException("small str encoded as str var")
    return decoder.stream.read(size).decode("utf8")


def _decode_arr(decoder: Decoder, marker: int) -> list:
    if marker == ARR_VAR:
        size = vlq_dec(decoder.stream)
        if size < ARR_SMALL_NUM_END - ARR_SMALL_NUM_START:
            raise PackRatDecodingException("small array encoded as array var")
    else:
        size = marker - ARR_SMALL_NUM_START

    ctx = [None] * size
    for i in range(size):
        ctx[i] = decoder._visit()
    return ctx


def _decode_map(decoder: Decoder, marker: int) -> dict:
    if marker == MAP_VAR:
        size = vlq_dec(decoder.stream)
        if size < MAP_SMALL_NUM_END - MAP_SMALL_NUM_START:
            raise PackRatDecodingException("small map encoded as map var")
    else:
        size = marker - MAP_SMALL_NUM_START

    ctx = {}
    last_item = None

    for _ in range(size):
        decoder.stream = ItemWrappedStream(decoder.stream)
        k = decoder._visit()
        item = decoder.stream.item.getvalue()
        # transitivity ensures all keys are lexigraphicaly orderd smallest to largest
        if last_item is not None and item <= last_item:
            raise PackRatDecodingException("map keys are out of order")
        last_item = item
        decoder.stream = decoder.stream.stream

        ctx[k] = decoder._visit()

    return ctx


def _decode_f32(decoder: Decoder, _: int) -> float:
    return f32.unpack(decoder.stream.read(4))[0]


def _decode_f64(decoder: Decoder, _: int) -> float:
    f = f64.unpack(decoder.stream.read(8))[0]

    can_be_f32 = f32.unpack(f32.pack(f))[0] == f
    if can_be_f32:
        raise PackRatDecodingException("f32 representable float encoded as f64")

    return f


def _decode_true(decoder: Decoder, _: int) -> bool:
    return True


def _decode_false(_: Decoder, __: int) -> bool:
    return False


def _decode_null(decoder: Decoder, _: int) -> None:
    return None


def _decode_tag_small(decoder: Decoder, marker: int) -> Any:
    tag_id = marker - TAG_SMALL_START
    tag = decoder.tags[tag_id]
    obj = decoder._visit()
    return tag.decode(obj)


def _decode_tag_var(decoder: Decoder, _: int) -> Any:
    tag_id = vlq_dec(decoder.stream)

    if tag_id < TAG_SMALL_END - TAG_SMALL_START:
        raise PackRatDecodingException("small tag encoded as tag var")

    tag = decoder.tags[tag_id]
    obj = decoder._visit()
    return tag.decode(obj)


def register(
    func: Callable[[Decoder, int], Any], start: int, stop: int | None = None
) -> None:
    if stop is None:
        stop = start

    for i in range(start, stop + 1):
        _DECODE_TABLE[i] = func


register(_decode_small_uint, UINT_SMALL_START, UINT_SMALL_END)
register(_decode_fixed_uint, UINT8, UINT64)
register(_decode_small_neg_int, NEG_INT_SMALL_START, NEG_INT_SMALL_END)
register(_decode_fixed_neg_int, NEG_INT8, NEG_INT64)
register(_decode_small_bin, BIN_SMALL_START, BIN_SMALL_END)
register(_decode_bin_var, BIN_VAR)
register(_decode_small_str, STR_SMALL_NUM_START, STR_SMALL_NUM_END)
register(_decode_str_var, STR_VAR)
register(_decode_arr, ARR_SMALL_NUM_START, ARR_VAR)
register(_decode_map, MAP_SMALL_NUM_START, MAP_VAR)
register(_decode_f32, FLOAT32)
register(_decode_f64, FLOAT64)
register(_decode_true, TRUE)
register(_decode_false, FALSE)
register(_decode_null, NULL)
register(_decode_tag_small, TAG_SMALL_START, TAG_SMALL_END)
register(_decode_tag_var, TAG_VAR)


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

        dt_tag = ISODateTimeTag()
        uuid_tag = UUIDTag()
        self.tags: dict[int, Tag] = {
            dt_tag.id: dt_tag,
            uuid_tag.id: uuid_tag,
        }

        if tags is not None:
            for tag in tags:
                if tag.id in TAG_RESERVED or tag.id in self.tags:
                    raise PackRatException(
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
                raise PackRatDecodingException("invalid file signature")
            return self._visit()
        return _DECODE_TABLE[marker](self, marker)

    def _visit(self) -> Any:
        marker = self.stream.read(1)[0]
        return _DECODE_TABLE[marker](self, marker)
