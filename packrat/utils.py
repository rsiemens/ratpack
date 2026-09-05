import struct

from librt.strings import (
    BytesWriter,
    read_f32_be,
    read_f64_be,
    write_f32_be,
    write_f64_be,
)

from packrat.exceptions import PackRatDecodingException
from packrat.types import BinaryReader, BinaryWriter

u16 = struct.Struct(">H")
u32 = struct.Struct(">I")
u64 = struct.Struct(">Q")


def pack_f32(f: float) -> bytes:
    buff = BytesWriter()
    write_f32_be(buff, f)
    return buff.getvalue()


def unpack_f32(b: bytes) -> float:
    return read_f32_be(b, 0)


def pack_f64(f: float) -> bytes:
    buff = BytesWriter()
    write_f64_be(buff, f)
    return buff.getvalue()


def unpack_f64(b: bytes) -> float:
    return read_f64_be(b, 0)


def vlq_enc(n: int, writer: BinaryWriter) -> None:
    """Variable-length quantity https://en.wikipedia.org/wiki/Variable-length_quantity"""
    bites = bytearray([n & 0x7F])  # mask the lower 7 bits leaving the msb as 0
    n >>= 7

    while n:
        bites.append((n & 0x7F) | 0x80)
        n >>= 7
    writer.write(bites[::-1])


def vlq_dec(reader: BinaryReader) -> int:
    n = 0

    while True:
        try:
            byte = reader.read(1)[0]
        except IndexError:
            raise PackRatDecodingException("Malformed vlq encoded payload")

        n = (n << 7) | (byte & 0x7F)
        if byte & 0x80 == 0:
            break
    return n
