from typing import Protocol, TypeAlias, Union

RatPrimitive: TypeAlias = Union[
    int,
    float,
    bool,
    str,
    bytes,
    None,
]

RatType: TypeAlias = Union[
    RatPrimitive,
    list["RatType"],
    dict[RatPrimitive, "RatType"],
]


class BinaryReader(Protocol):
    def read(self, size: int | None = -1, /) -> bytes: ...


class BinaryWriter(Protocol):
    def write(self, bites: bytes | bytearray, /) -> None: ...
