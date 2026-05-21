import struct

from .exceptions import RatPackDecodingException
from .types import BinaryReader, BinaryWriter

u16 = struct.Struct(">H")
u32 = struct.Struct(">I")
u64 = struct.Struct(">Q")
f32 = struct.Struct(">f")
f64 = struct.Struct(">d")


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
            raise RatPackDecodingException("Malformed vlq encoded payload")

        n = (n << 7) | (byte & 0x7F)
        if byte & 0x80 == 0:
            break
    return n
