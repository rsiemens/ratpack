# Ratpack

Ratpack is a simple and efficent schemaless binary serialization format.

Features:

- Lexigraphically sortable
- Deterministic ordering allowing for [content adressable storage](https://en.wikipedia.org/wiki/Content-addressable_storage).
- Intentionally chosen small values. For example small strings can encode a length up to 36
  which covers common JSON string representations like UUIDs and ISO 8601 timestamps. This keeps
  it competitive, and often [smaller](https://github.com/rsiemens/ratpack/blob/main/benchmarks/chart.png),
  than similar binary formats.
- Simple extension types via tags.

Checkout the [spec](https://github.com/rsiemens/ratpack/blob/main/spec/README.md) (WIP).
