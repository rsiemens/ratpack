import datetime
import uuid
from typing import Callable, Generic, TypeVar

from .exceptions import PackRatDecodingException, PackRatEncodingException
from .types import RatType

T = TypeVar("T")


class Tag(Generic[T]):
    def __init__(
        self,
        id: int,
        obj_type: type[T],
        encode: Callable[[T], RatType] | None = None,
        decode: Callable[[RatType], T] | None = None,
    ):
        self.id = id
        self.obj_type = obj_type
        self.encoder = encode
        self.decoder = decode

    def encode(self, obj: T) -> RatType:
        if self.encoder is None:
            raise PackRatEncodingException("encode not provided for {self}")
        return self.encoder(obj)

    def decode(self, item: RatType) -> T:
        if self.decoder is None:
            raise PackRatDecodingException("decode not provided for {self}")
        return self.decoder(item)

    def __repr__(self) -> str:
        return f"<Tag({self.id} {self.obj_type})>"


class ISODateTimeTag(Tag):
    def __init__(self) -> None:
        super().__init__(id=0, obj_type=datetime.datetime)

    def encode(self, obj: datetime.datetime) -> RatType:
        return obj.isoformat()

    def decode(self, item: RatType) -> datetime.datetime:
        if not isinstance(item, str):
            raise PackRatDecodingException(
                f"expected str for datetime decoding, got {type(item)}"
            )
        return datetime.datetime.fromisoformat(item)


class UUIDTag(Tag):
    def __init__(self) -> None:
        super().__init__(id=1, obj_type=uuid.UUID)

    def encode(self, obj: uuid.UUID) -> RatType:
        return obj.bytes

    def decode(self, item: RatType) -> uuid.UUID:
        if not isinstance(item, bytes):
            raise PackRatDecodingException(
                f"expected bytes for uuid decoding, got {type(item)}"
            )
        return uuid.UUID(bytes=item)
