from __future__ import annotations

import io
from typing import Any, Callable

from .constants import *
from .exceptions import RatPackDecodingException, RatPackException
from .tags import ISODateTimeTag, Tag, UUIDTag
from .types import BinaryReader, RatType
from .utils import f32, f64, u16, u32, u64, vlq_dec


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

        dt_tag = ISODateTimeTag()
        uuid_tag = UUIDTag()
        self.tags: dict[int, Tag] = {
            dt_tag.id: dt_tag,
            uuid_tag.id: uuid_tag,
        }

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
            return u16.unpack(self.stream.read(2))[0]
        if marker == UINT32:
            return u32.unpack(self.stream.read(4))[0]
        if marker == UINT64:
            return u64.unpack(self.stream.read(8))[0]
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
            return -u16.unpack(self.stream.read(2))[0]
        if marker == NEG_INT32:
            return -u32.unpack(self.stream.read(4))[0]
        if marker == NEG_INT64:
            return -u64.unpack(self.stream.read(8))[0]
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
        size = vlq_dec(self.stream)
        if size < BIN_SMALL_END - BIN_SMALL_START:
            raise RatPackDecodingException("small bin encoded as bin var")
        return self.stream.read(size)

    @register(STR_SMALL_NUM_START, STR_SMALL_NUM_END)
    def _decode_small_str(self, marker: int) -> str:
        size = marker - STR_SMALL_NUM_START
        return self.stream.read(size).decode("utf8")

    @register(STR_VAR)
    def _decode_str_var(self, _: int) -> str:
        size = vlq_dec(self.stream)
        if size < STR_SMALL_NUM_END - STR_SMALL_NUM_START:
            raise RatPackDecodingException("small str encoded as str var")
        return self.stream.read(size).decode("utf8")

    @register(ARR_SMALL_NUM_START, ARR_VAR)
    def _decode_arr(self, marker: int) -> list:
        if marker == ARR_VAR:
            size = vlq_dec(self.stream)
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
            size = vlq_dec(self.stream)
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
            if last_item is not None and item <= last_item:
                raise RatPackDecodingException("map keys are out of order")
            last_item = item
            self.stream = self.stream.stream

            ctx[k] = self._visit()

        return ctx

    @register(FLOAT32)
    def _decode_f32(self, _: int) -> float:
        return f32.unpack(self.stream.read(4))[0]

    @register(FLOAT64)
    def _decode_f64(self, _: int) -> float:
        f = f64.unpack(self.stream.read(8))[0]

        can_be_f32 = f32.unpack(f32.pack(f))[0] == f
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
        tag_id = vlq_dec(self.stream)

        if tag_id < TAG_SMALL_END - TAG_SMALL_START:
            raise RatPackDecodingException("small tag encoded as tag var")

        tag = self.tags[tag_id]
        obj = self._visit()
        return tag.decode(obj)
