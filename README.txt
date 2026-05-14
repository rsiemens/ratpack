Ratpack is a relatively simple and efficent schemaless binary serialization format.

It takes inspiration from msgpack, cbor, and protobuf.

Ratpack splits it's types across a one byte number range (0-255) and assigns types to different
ranges. For example small strings cover 0x76 - 0x9A while variable length strings are assigned 0x9B.

The full set of types and there ranges are as follows:
    - unsigned small int 0x00-0x40
    - unsigned var int 0x41
    - negative small int 0x42-0x62
    - negative var int 0x63
    - small byte str 0x64-0x74
    - var len byte str 0x75
    - small utf8 enc str 0x76-0x9A
    - var len utf8 enc str 0x9B
    - small array 0x9C-0xC0
    - var len array 0xC1-0xC2
    - small map 0xC2-0xE6
    - var len map 0xE7
    - IEEE 754 float32 0xE8
    - IEEE 754 float64 0xE9
    - true 0xEA
    - false 0xEB
    - null 0xEC
    - small tag 0xED-0xFD
    - var tag 0xFE

Variable size ints and length are implemented using unsigned [LEB128](https://en.wikipedia.org/wiki/LEB128)
encoding which allows storing arbitrary length ints.

Some notable features (not yet all implemented):
    - Easily comparable. All types are simply compared lexigraphical. This means a unsigned small int < unsigned var int < ... < var len map < ... < var tag
    - Intentional small values. For example small strings can encode a length up to 36 which covers common string representations like uuids and ISO 8601 timestamps.
    - Simple extension type via tags.
    - [TODO] Deterministic ordering allowing for content adressable storage.
