"""
Simple benchmark against other popular schemaless serialization formats.

Uses the pure python version (when available) for comparison.
"""

import json
import timeit
from pathlib import Path

import cbor2
import msgpack
import ubjson

import packrat

REPEAT = 10


def report(title, data, encoder, decoder):
    print(f"{title:>7}   ", end="")
    try:
        raw = encoder(data)
        min_time = min(
            timeit.repeat(
                "encoder(data)",
                repeat=REPEAT,
                number=1,
                globals={"encoder": encoder, "data": data},
            )
        )
    except Exception as e:
        print(f"{e}")
        return
    print(f"{len(raw):<12}", end="")
    print(f"{min_time:<12.6f}", end="")

    try:
        min_time = min(
            timeit.repeat(
                "decoder(raw)",
                repeat=REPEAT,
                number=1,
                globals={"decoder": decoder, "raw": raw},
            )
        )
    except Exception as e:
        print(f"{e}")
        return
    print(f"{min_time:<12.6f}")


if __name__ == "__main__":
    print(f"Taking the best time out of {REPEAT} enc/dec iterations\n")
    for fname in Path("data/").glob("*.json"):
        print(f"file: {fname} ({fname.stat().st_size})")

        with open(fname) as f:
            data = json.load(f)

        print(f"{' ' * 10}{'Enc Size':<12}{'Enc Time':<12}{'Dec Time':<12}")
        report("JSON", data, json.dumps, json.loads)
        report("ubjson", data, ubjson.dumpb, ubjson.loadb)
        report("cbor2", data, cbor2.dumps, cbor2.loads)
        report("msgpack", data, msgpack.packb, msgpack.unpackb)
        report("packrat", data, packrat.packb, packrat.unpackb)
        print()
