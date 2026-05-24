# Ratpack Specification (WIP)

> This is a WIP - everything should be considered quite unstable at the moment!

## Overview

Ratpack is a simple and efficent schemaless binary serialization format.

## Data Types

Ratpack consits of a few of primary data types. All data types are represented by a range of values
over a one byte, 0-255, range. The data types and there ranges are as follows:

 1. uint: 0x00-0x44
    - uint-small: 0x00-0x40 (0 to 64)
    - uint8: 0x41 (65 to 2^8-1)
    - uint16: 0x42 (2^8 to 2^16-1)
    - uint32: 0x43 (2^16 to 2^32-1)
    - uint64: 0x44 (2^32 to 2^64-1)
 2. nint: 0x45-0x6B
    - nint-small: 0x45-0x67 (-1 to -35)
    - nint8: 0x68 (-36 to -(2^8-1))
    - nint16: 0x69 (-2^8 to -(2^16-1))
    - nint32: 0x6A (-2^16 to -(2^32-1))
    - nint64: 0x6B (-2^32 to -(2^64-1))
 3. bin: 0x6C-0x7D
    - bin-small: 0x6C-0x7C (lengths 0 to 16)
    - bin-var: 0x7D (lengths >16)
 4. str: 0x7E-0xA3
    - str-small: 0x7E-0xA2 (lengths 0 to 36)
    - str-var: 0xA3 (lengths >36)
 5. array: 0xA4-0xC5
    - array-small: 0xA4-0xC4 (lengths 0 to 32)
    - array-var: 0xC5 (lengths >32)
 6. map: 0xC6-0xE7
    - map-small: 0xC6-0xE6 (lengths 0 to 32)
    - map-var: 0xE7 (lengths >32)
 7. float: 0xE8-0xE9
    - float32: 0xE8
    - float64: 0xE9
 8. bool: 0xEA-0xEB
    - true: 0xEA
    - false: 0xEB
 9. null: 0xEC
10. tag: 0xED-0xFE
    - tag-small: 0xED-0xFD (tag id 0 to 16)
    - tag-var: 0xFE (tag ids >16)

The final value, 0xFF, is used only at the begining of a file or stream to mark the start of the
optional header.

### uint (0x00-0x44)

The uint (unsigned integer) type, represents whole numbers from 0 to 2^64-1.

Bytes 0x00 to 0x40 represent the values 0 to 64 directly. Bytes 0x41, 0x42, 0x43, and 0x44
represent uint8, uint16, uint32, and uint64 respectively and are followed by the 1, 2, 4, or 8
bytes which make up the value. The values are all big-endian encoded.

Implementations must always choose the smallest possible representation to encode a value
irrispective of language type. For example a `uint32_t` in C storing the value `4096` must encode
the value as a uint16 (byte 0x42) which would produce the hex values `42 10 00`. For more details
on why this is the case, see the section on Deterministic Encoding.

### nint (0x45-0x6B)

The nint (negative integer) type, represent negative whole numbers from -1 to -(2^64-1).

Bytes 0x45 to 0x67 represent the values -1 to -35 directly. Bytes 0x68, 0x69, 0x6A, and 0x6B
represent nint8, nint16, nint32, and nint64 respectively and are followed by the 1, 2, 4, or 8
bytes which make up the value. Like the uint type, values are all big-endian encoded.

Similar to the uint, implementations must always choose the smallest possible representation to
encode the value.

### bin (0x6C-0x7D)

The bin type, represents byte arrays.

Bytes 0x6C to 0x7C represent byte arrays with lengths 0 to 16 directly. It is then followed by that
many bytes making up the byte array. Byte 0x7D represent a [Variable-length_quantity](https://en.wikipedia.org/wiki/Variable-length_quantity) (VLQ).
VLQ encoding can encode arbitrary lengths by using the most significant bit of the following byte to
signal continuation. No limit on length is imposed by the specification, but implementations may
wish to enforce limits as dictated by the language or for security reasons.

Implementations must always choose the smallest possible reprsentation to encode the length.

### str (0x7E-0xA3)

The str type represents utf8 encoded text.

Bytes 0x7E to 0xA2 represent strings with length 0 to 36 directly. It is then followed by that many
bytes making up the utf8 encoded text. Byte 0xA3 represents a VLQ encoded length. Similar to the bin
type, no limit on length is imposed.

The str type must only contain valid utf8 encoded text. Support for other encodings can be achieved
using a combination of the tag type and bin type.

### array (0xA4-0xC5)

### map (0xC6-0xE7)

### float (0xE8-0xE9)

### bool (0xEA-0xEB)

### null (0xEC)

### tag (0xED-0xFE)

## Deterministic Encoding

## Grammar

The following is the grammar for Ratpack, in EBNF notation.

```
(*
The following EBNF special sequences, "?...?" are as follows:
    - ?BE uintN? - An unsigned big-endian encoded integer of size N bits. Capable of representing values from 0 to 2^N-1.
    - ?unisnged VLQ? - Unsigned big-endian base 128 variable size integer (https://en.wikipedia.org/wiki/Variable-length_quantity).
    - ?BE IEEE 754 format? - Big endian encoded IEEE 754 floating point number, where "format" is single (32bit) or double (64bit).
*)

ratpack = [header], item;
header = magic-start, magic-signature;
magic-start = ?0xFF?;
magic-signature = ?0x72?, ?0x70?, magic-version;
magic-version = ?0x00?; (* This value should map to the specification version number, v0. *)

item = uint
     | nint
     | bin
     | str
     | array
     | map
     | float
     | bool
     | null
     | tag;

uint = uint-small | uint8 | uint16 | uint32 | uint64;
uint-small = ?0x00? | ?0x01? | ... | ?0x40?;
uint8 = ?0x41?, ?BE uint8?;
uint16 = ?0x42?, ?BE uint16?;
uint32 = ?0x43?, ?BE uint32?;
uint64 = ?0x44?, ?BE uint64?;

nint = nint-small | nint8 | nint16 | nint32 | nint64;
nint-small = ?0x45? | ?0x46? | ... | ?0x67?;
nint8 = ?0x68?, ?BE uint8?;
nint16 = ?0x69?, ?BE uint16?;
nint32 = ?0x6A?, ?BE uint32?;
nint64 = ?0x6B?, ?BE uint64?;

bin = (bin-small | bin-var), {byte};
bin-small = ?0x6C? | ?0x6D? | ... | ?0x7C?;
bin-var = ?0x7D?, ?unsigned VLQ?;

str = (str-small | str-var), {byte}; (* Byte must be a valid utf8 encoded byte. *)
str-small = ?0x7E? | ?0x7F? | ... | ?0xA2?;
str-var = ?0xA3?, ?unsigned VLQ?;

array = (array-small | array-var), {item};
array-small = ?0xA4? | ?0xA5? | ... | ?0xC4?;
array-var = ?0xC5?, ?unsigned VLQ?;

map = (map-small | map-var), {item, item};
map-small = ?0xC6? | ?0xC7? | ... | ?0xE6?;
map-var = ?0xE7?, ?unsigned VLQ?;

float = float32 | float64;
float32 = ?0xE8?, ?BE IEEE 754 single?;
float64 = ?0xE9?, ?BE IEEE 754 double?;

bool = true | false;
true = ?0xEA?;
false = ?0xEB?;

null = ?0xEC?;

tag = (tag-small | tag-var), item;
tag-small = ?0xED? | ?0xEF? | ... | ?0xFD?;
tag-var = ?0xFE?, ?unsigned VLQ?;

byte = ?0x00? | ?0x01? | ... | ?0xFF?;
```

The name Ratpack is inspired by the [Rat Pack](https://en.wikipedia.org/wiki/Rat_Pack) group from
the 1950s.
