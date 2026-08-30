import io
import math
from typing import Any

from .constants import *
from .exceptions import PackRatEncodingException, PackRatException
from .tags import ISODateTimeTag, Tag, UUIDTag
from .types import BinaryWriter, RatType
from .utils import f32, f64, u16, u32, u64, vlq_enc


class Encoder:
    def __init__(
        self,
        stream: BinaryWriter,
        tags: list[Tag] | None = None,
        include_header: bool = False,
    ):
        self.stream = stream

        dt_tag = ISODateTimeTag()
        uuid_tag = UUIDTag()
        self.tags: dict[Any, Tag] = {
            dt_tag.obj_type: dt_tag,
            uuid_tag.obj_type: uuid_tag,
        }
        self.include_header = include_header

        if tags is not None:
            tag_ids = TAG_RESERVED.copy()
            for tag in tags:
                if tag.id in tag_ids:
                    raise PackRatException(
                        f"Tag id {tag.id} is already in use or reserved"
                    )
                elif tag.obj_type in self.tags:
                    existing_tag = self.tags[tag.obj_type]
                    raise PackRatException(
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
            self.stream.write(BYTES_TABLE[TRUE if obj else FALSE])
        elif obj is None:
            self.stream.write(BYTES_TABLE[NULL])
        else:
            try:
                tag = self.tags[type(obj)]
            except KeyError:
                raise PackRatEncodingException(f"unable to encode {type(obj)}")
            self._encode_tag(tag, obj)

    def _encode_header(self) -> None:
        self.stream.write(BYTES_TABLE[MAGIC_NUMBER_START] + MAGIC_NUMER_SIG)

    def _encode_int(self, i: int) -> None:
        if i >= 0:
            return self._encode_positive_int(i)
        return self._encode_negative_int(i)

    def _encode_positive_int(self, i: int) -> None:
        if i <= UINT_SMALL_END - UINT_SMALL_START:
            self.stream.write(BYTES_TABLE[UINT_SMALL_START + i])
        elif i <= 0xFF:
            self.stream.write(BYTES_TABLE[UINT8] + BYTES_TABLE[i])
        elif i <= 0xFFFF:
            self.stream.write(BYTES_TABLE[UINT16] + u16.pack(i))
        elif i <= 0xFFFFFFFF:
            self.stream.write(BYTES_TABLE[UINT32] + u32.pack(i))
        elif i <= 0xFFFFFFFFFFFFFFFF:
            self.stream.write(BYTES_TABLE[UINT64] + u64.pack(i))
        else:
            raise PackRatEncodingException(
                "unable to encode numbers larger than 2**64-1"
            )

    def _encode_negative_int(self, i: int) -> None:
        i = -i
        if i <= NEG_INT_SMALL_END - NEG_INT_SMALL_START + 1:
            self.stream.write(BYTES_TABLE[NEG_INT_SMALL_START + i - 1])
        elif i <= 0xFF:
            self.stream.write(BYTES_TABLE[NEG_INT8] + BYTES_TABLE[i])
        elif i <= 0xFFFF:
            self.stream.write(BYTES_TABLE[NEG_INT16] + u16.pack(i))
        elif i <= 0xFFFFFFFF:
            self.stream.write(BYTES_TABLE[NEG_INT32] + u32.pack(i))
        elif i <= 0xFFFFFFFFFFFFFFFF:
            self.stream.write(BYTES_TABLE[NEG_INT64] + u64.pack(i))
        else:
            raise PackRatEncodingException(
                "unable to encode numbers smaller than -(2**64-1)"
            )

    def _encode_bytes(self, b: bytes) -> None:
        size = len(b)
        if size <= BIN_SMALL_END - BIN_SMALL_START:
            self.stream.write(BYTES_TABLE[BIN_SMALL_START + size])
        else:
            self.stream.write(BYTES_TABLE[BIN_VAR])
            vlq_enc(size, self.stream)

        self.stream.write(b)

    def _encode_str(self, s: str) -> None:
        val = s.encode("utf8")
        size = len(val)

        if size <= STR_SMALL_NUM_END - STR_SMALL_NUM_START:
            self.stream.write(BYTES_TABLE[STR_SMALL_NUM_START + size])
        else:
            self.stream.write(BYTES_TABLE[STR_VAR])
            vlq_enc(size, self.stream)

        self.stream.write(val)

    def _encode_list(self, items: list) -> None:
        size = len(items)
        if size <= ARR_SMALL_NUM_END - ARR_SMALL_NUM_START:
            self.stream.write(BYTES_TABLE[ARR_SMALL_NUM_START + size])
        else:
            self.stream.write(BYTES_TABLE[ARR_VAR])
            vlq_enc(size, self.stream)

        for i in items:
            self._encode(i)

    def _encode_dict(self, d: dict) -> None:
        size = len(d)
        if size <= MAP_SMALL_NUM_END - MAP_SMALL_NUM_START:
            self.stream.write(BYTES_TABLE[MAP_SMALL_NUM_START + size])
        else:
            self.stream.write(BYTES_TABLE[MAP_VAR])
            vlq_enc(size, self.stream)

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
        f32packed = f32.pack(f)

        if f32.unpack(f32packed)[0] == f or math.isnan(f):
            self.stream.write(BYTES_TABLE[FLOAT32] + f32packed)
        else:
            self.stream.write(BYTES_TABLE[FLOAT64] + f64.pack(f))

    def _encode_tag(self, tag: Tag, obj: RatType) -> None:
        rat_obj = tag.encode(obj)

        if tag.id <= TAG_SMALL_END - TAG_SMALL_START:
            self.stream.write(BYTES_TABLE[TAG_SMALL_START + tag.id])
        else:
            self.stream.write(BYTES_TABLE[TAG_VAR])
            vlq_enc(tag.id, self.stream)

        self._encode(rat_obj)
