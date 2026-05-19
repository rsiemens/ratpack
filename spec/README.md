# Ratpack Specification (WIP)

> This is a WIP - everything should be considered quite unstable at the moment!

## Overview

Ratpack is a simple and efficent schemaless binary serialization format.

## Data Types

Ratpack consits of a few of primary data types. All data types are represented by a range of values
over a one byte, 0-255, range. The data types and there ranges are as follows:

 1. uint  - 0x00-0x44
 2. nint  - 0x45-0x6B
 3. bin   - 0x6C-0x7D
 4. str   - 0x7E-0xA3
 5. array - 0xA4-0xC5
 6. map   - 0xC6-0xE7
 7. float - 0xE8-0xE9
 8. bool  - 0xEA-0xEB
 9. null  - 0xEC
10. tag   - 0xED-0xFE

The final value, 0xFF, is used only at the begining of a file or stream to mark the start of a
header.

### uint (0x00-0x44)

The uint (unsigned integer) type, represents whole numbers from 0 to 2^64-1.

### nint (0x45-0x6B)

nint (negative integer), represent negative whole numbers from -1 to -(2^64-1).

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
