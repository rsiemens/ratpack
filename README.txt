                                   Ratpack

Ratpack is a relatively simple and efficent schemaless binary serialization format. It takes much
inspiration from msgpack, cbor, and protobuf.

Some notable features:
    - Intentionally chosen small values. For example small strings can encode a length up to 36
      which covers common JSON string representations like uuids and ISO 8601 timestamps. This
      keeps it competitive, and often smaller[1], than similar formats.
    - Deterministic ordering allowing for content adressable storage[2].
    - Simple extension type via tags.

Ratpack splits it's types across a one byte number range (0-255) and assigns types to different
ranges. For example small strings cover 0x7E - 0xA2 while variable length strings are assigned 0xA3.

The full set of types and there ranges are as follows:

    - unsigned small int 0x00-0x40 (unsigned ints 0 to 64)
    - unsigned int8 0x41 (unsigned ints 64 to 255)
    - litte-endian unsigned int16 0x42 (unsigned ints 256 to 2**16-1)
    - litte-endian unsigned int32 0x43 (unsigned ints 2**16 to 2**32-1)
    - litte-endian unsigned int64 0x44 (unsigned ints 2**32 to 2**64-1)
    - negative small int 0x45-0x67 (neg ints -1 to -35)
    - negative int8 0x68 (neg ints -36 to -255)
    - litte-endian negative int16 0x69 (neg ints -256 to -(2**16-1))
    - litte-endian negative int32 0x6A (neg ints -2**16 to -(2**32-1))
    - litte-endian negative int64 0x6B (neg ints -2**32 to -(2**64-1))
    - small len binary 0x6C-0x7C (lengths 0 to 16)
    - var len binary 0x7D (lengths > 16)
    - small utf8 enc str 0x7E-0xA2 (lengths 0 to 36)
    - var len utf8 enc str 0xA3 (lengths > 36)
    - small array 0xA4-0xC4 (lengths 0 to 32)
    - var len array 0xC5 (lengths > 32)
    - small map 0xC6-0xE6 (lengths 0 to 32)
    - var len map 0xE7 (lengths > 32)
    - little-endian IEEE 754 single precision 0xE8
    - little-endian IEEE 754 double precision 0xE9
    - true 0xEA
    - false 0xEB
    - null 0xEC
    - small tag 0xED-0xFD (tag ids 0 to 16)
    - var tag 0xFE (tag ids > 16)
    - start of file signature magic number 0xFF (more on this further down)

Variable size ints and length are implemented using unsigned LEB128[3] encoding which allows storing
arbitrary length ints and sizes.

In order to maintain deterministic map ordering, encoders should always use the smallest
reprsentable type that can store that value. This means a strongly typed language should always use
a unsigned small int to store a int32 of value 8. For floats a simple cast can be performed to see
if a f64 can be encoded as a f32 without loss of precision.

Map keys must be sorted from smallest to largest based on their encoded lexigraphical order.

Tags work the same way in ratpack as they do in cbor. The tag number wraps the single data item that
follows after the tag. Tag numbers 0-8 are reserved for the specification to define. All other tag
numbers are free for user/implementation to define.

The file signature magic number start (0xFF) is only valid at the very begining of a ratpack encoded
document or stream. It is optional, but if it is included, it must be immediately followed by three
bytes 0x72 0x70 and a version byte 0x00-0xFF. For the current verions (0x00) the full header would
look like b"\xffrp\x00".


1: https://github.com/rsiemens/ratpack/blob/main/chart.png
2: https://en.wikipedia.org/wiki/Content-addressable_storage
3: https://en.wikipedia.org/wiki/LEB128
