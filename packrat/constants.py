UINT_SMALL_START = 0x00
UINT_SMALL_END = 0x40
UINT8 = 0x41
UINT16 = 0x42
UINT32 = 0x43
UINT64 = 0x44

NEG_INT_SMALL_START = 0x45
NEG_INT_SMALL_END = 0x67
NEG_INT8 = 0x68
NEG_INT16 = 0x69
NEG_INT32 = 0x6A
NEG_INT64 = 0x6B

BIN_SMALL_START = 0x6C
BIN_SMALL_END = 0x7C
BIN_VAR = 0x7D

STR_SMALL_NUM_START = 0x7E
STR_SMALL_NUM_END = 0xA2
STR_VAR = 0xA3

ARR_SMALL_NUM_START = 0xA4
ARR_SMALL_NUM_END = 0xC4
ARR_VAR = 0xC5

MAP_SMALL_NUM_START = 0xC6
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
# first 9 tags are reserved
TAG_RESERVED = {i for i in range(9)}

# The MAGIC_NUMBER_START is only valid at the very begining of a file or packrat stream.
# It is not required, but if it is present, it must be immedidiately followed by the ascii encode
# characters "rp" and a version byte 0x00-0xFF.
MAGIC_NUMBER_START = 0xFF
MAGIC_NUMER_SIG = b"rp\x00"

BYTES_TABLE = [bytes([i]) for i in range(0xFF + 1)]
