from __future__ import annotations

from typing import Any

from librt.strings import BytesWriter

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


class ItemWrappedStream:
    def __init__(self, stream: BinaryReader):
        self.stream = stream
        self.item = BytesWriter()

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
        return self._visit(marker)

    def _visit(self, marker: int | None = None) -> Any:
        if marker is None:
            marker = self.stream.read(1)[0]
        if UINT_SMALL_START <= marker <= UINT_SMALL_END:
            return marker
        if UINT8 <= marker <= UINT64:
            return self._decode_fixed_uint(marker)
        if NEG_INT_SMALL_START <= marker <= NEG_INT_SMALL_END:
            return -(marker - NEG_INT_SMALL_START + 1)
        if NEG_INT8 <= marker <= NEG_INT64:
            return self._decode_fixed_neg_int(marker)
        if BIN_SMALL_START <= marker <= BIN_SMALL_END:
            return self.stream.read(marker - BIN_SMALL_START)
        if marker == BIN_VAR:
            return self._decode_bin_var(marker)
        if STR_SMALL_NUM_START <= marker <= STR_SMALL_NUM_END:
            return self.stream.read(marker - STR_SMALL_NUM_START).decode("utf8")
        if marker == STR_VAR:
            return self._decode_str_var(marker)
        if ARR_SMALL_NUM_START <= marker <= ARR_VAR:
            return self._decode_arr(marker)
        if MAP_SMALL_NUM_START <= marker <= MAP_VAR:
            return self._decode_map(marker)
        if marker == FLOAT32:
            return f32.unpack(self.stream.read(4))[0]
        if marker == FLOAT64:
            return self._decode_f64(marker)
        if marker == TRUE:
            return True
        if marker == FALSE:
            return False
        if marker == NULL:
            return None
        if TAG_SMALL_START <= marker <= TAG_SMALL_END:
            return self._decode_tag_small(marker)
        if marker == TAG_VAR:
            return self._decode_tag_var(marker)

        raise PackRatDecodingException(f"Unknown marker: {marker}")

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
        raise PackRatDecodingException(f"unable to deocde fixed size int ({marker})")

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
        raise PackRatDecodingException(
            f"unable to deocde fixed size neg int ({marker})"
        )

    def _decode_bin_var(self, _: int) -> bytes:
        size = vlq_dec(self.stream)
        if size < BIN_SMALL_END - BIN_SMALL_START:
            raise PackRatDecodingException("small bin encoded as bin var")
        return self.stream.read(size)

    def _decode_str_var(self, _: int) -> str:
        size = vlq_dec(self.stream)
        if size < STR_SMALL_NUM_END - STR_SMALL_NUM_START:
            raise PackRatDecodingException("small str encoded as str var")
        return self.stream.read(size).decode("utf8")

    def _decode_arr(self, marker: int) -> list:
        if marker == ARR_VAR:
            size = vlq_dec(self.stream)
            if size < ARR_SMALL_NUM_END - ARR_SMALL_NUM_START:
                raise PackRatDecodingException("small array encoded as array var")
        else:
            size = marker - ARR_SMALL_NUM_START

        ctx = [None] * size
        for i in range(size):
            ctx[i] = self._visit()
        return ctx

    def _decode_map(self, marker: int) -> dict:
        if marker == MAP_VAR:
            size = vlq_dec(self.stream)
            if size < MAP_SMALL_NUM_END - MAP_SMALL_NUM_START:
                raise PackRatDecodingException("small map encoded as map var")
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
                raise PackRatDecodingException("map keys are out of order")
            last_item = item
            self.stream = self.stream.stream

            ctx[k] = self._visit()

        return ctx

    def _decode_f64(self, _: int) -> float:
        f = f64.unpack(self.stream.read(8))[0]

        can_be_f32 = f32.unpack(f32.pack(f))[0] == f
        if can_be_f32:
            raise PackRatDecodingException("f32 representable float encoded as f64")

        return f

    def _decode_tag_small(self, marker: int) -> Any:
        tag_id = marker - TAG_SMALL_START
        tag = self.tags[tag_id]
        obj = self._visit()
        return tag.decode(obj)

    def _decode_tag_var(self, _: int) -> Any:
        tag_id = vlq_dec(self.stream)

        if tag_id < TAG_SMALL_END - TAG_SMALL_START:
            raise PackRatDecodingException("small tag encoded as tag var")

        tag = self.tags[tag_id]
        obj = self._visit()
        return tag.decode(obj)
