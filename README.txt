                                   Ratpack

Ratpack is a relatively simple and efficent schemaless binary serialization format. It takes much
inspiration from msgpack, cbor, and protobuf.

Some notable features:
    - Intentionally chosen small values. For example small strings can encode a length up to 36
      which covers common JSON string representations like uuids and ISO 8601 timestamps.
    - Deterministic ordering allowing for content adressable storage[1].
    - Simple extension type via tags.

Ratpack splits it's types across a one byte number range (0-255) and assigns types to different
ranges. For example small strings cover 0x76 - 0x9A while variable length strings are assigned 0x9B.

The full set of types and there ranges are as follows:

    - unsigned small int 0x00-0x40 (unsigned ints 0 to 64)
    - unsigned var int 0x41 (unsigned ints > 64)
    - negative small int 0x42-0x62 (neg ints -1 to -33)
    - negative var int 0x63 (neg ints < -33)
    - small len binary 0x64-0x74 (lengths 0 to 16)
    - var len binary 0x75 (lengths > 16)
    - small utf8 enc str 0x76-0x9A (lengths 0 to 36)
    - var len utf8 enc str 0x9B (lengths > 36)
    - small array 0x9C-0xC0 (lengths 0 to 36)
    - var len array 0xC1-0xC2 (lengths > 36)
    - small map 0xC2-0xE6 (lengths 0 to 36)
    - var len map 0xE7 (lengths > 36)
    - IEEE 754 float32 0xE8
    - IEEE 754 float64 0xE9
    - true 0xEA
    - false 0xEB
    - null 0xEC
    - small tag 0xED-0xFD (tag ids 0 to 16)
    - var tag 0xFE (tag ids > 16)
    - start of file signature magic number 0xFF (more on this further down)

Variable size ints and length are implemented using unsigned LEB128[2] encoding which allows storing
arbitrary length ints and sizes.

Encoders should always use the smallest reprsentable type that can store that value. This means a
strongly typed language should always use a unsigned small int to store a int32 of value 8. For
floats a simple cast can be performed to see if a f64 can be encoded as a f32 without loss of
precision.

Map keys must be sorted from smallest to largest based on their encoded lexigraphical order.

Tags [todo]

The file signature magic number start (0xFF) is only valid at the very begining of a ratpack encoded
document or stream. It is optional, but if it is included, it must be immediately followed by three
bytes 0x72 0x70 and a version byte 0x00-0xFF. For the current verions (0x00) the full header would
look like b"\xffrp\x00".


1: https://en.wikipedia.org/wiki/Content-addressable_storage
2: https://en.wikipedia.org/wiki/LEB128
