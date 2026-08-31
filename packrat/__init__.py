import io
from typing import Any

from librt.strings import BytesWriter

from packrat.decode import Decoder
from packrat.encode import Encoder
from packrat.tags import Tag
from packrat.types import BinaryReader, BinaryWriter

__version__ = "0.1.0a1"
__all__ = ["packb", "unpackb", "pack", "unpack", "dumps", "loads", "dump", "load"]


def packb(
    obj: Any, tags: list[Tag] | None = None, include_header: bool = False
) -> bytes:
    stream = BytesWriter()
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
