import io
from typing import Any

from .decode import Decoder
from .encode import Encoder
from .tags import Tag
from .types import BinaryReader, BinaryWriter


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
