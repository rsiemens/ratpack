from typing import Final

UINT_SMALL_START: Final = 0x00
UINT_SMALL_END: Final = 0x40
UINT8: Final = 0x41
UINT16: Final = 0x42
UINT32: Final = 0x43
UINT64: Final = 0x44

NEG_INT_SMALL_START: Final = 0x45
NEG_INT_SMALL_END: Final = 0x67
NEG_INT8: Final = 0x68
NEG_INT16: Final = 0x69
NEG_INT32: Final = 0x6A
NEG_INT64: Final = 0x6B

BIN_SMALL_START: Final = 0x6C
BIN_SMALL_END: Final = 0x7C
BIN_VAR: Final = 0x7D

STR_SMALL_NUM_START: Final = 0x7E
STR_SMALL_NUM_END: Final = 0xA2
STR_VAR: Final = 0xA3

ARR_SMALL_NUM_START: Final = 0xA4
ARR_SMALL_NUM_END: Final = 0xC4
ARR_VAR: Final = 0xC5

MAP_SMALL_NUM_START: Final = 0xC6
MAP_SMALL_NUM_END: Final = 0xE6
MAP_VAR: Final = 0xE7

FLOAT32: Final = 0xE8
FLOAT64: Final = 0xE9
TRUE: Final = 0xEA
FALSE: Final = 0xEB
NULL: Final = 0xEC

TAG_SMALL_START: Final = 0xED
TAG_SMALL_END: Final = 0xFD
TAG_VAR: Final = 0xFE
# first 9 tags are reserved
TAG_RESERVED: Final = {i for i in range(9)}

# The MAGIC_NUMBER_START is only valid at the very begining of a file or packrat stream.
# It is not required, but if it is present, it must be immedidiately followed by the ascii encode
# characters "rp" and a version byte 0x00-0xFF.
MAGIC_NUMBER_START: Final = 0xFF
MAGIC_NUMER_SIG: Final = b"rp\x00"

BYTES_TABLE: Final = [bytes([i]) for i in range(0xFF + 1)]
