import io
import json
import math
import random as rand
import string
import timeit
import unittest
import uuid
from librt.strings import BytesWriter
from datetime import datetime, timezone
from typing import cast

import packrat as rp
from packrat.constants import (
    MAGIC_NUMBER_START,
    MAGIC_NUMER_SIG,
    MAP_SMALL_NUM_START,
    UINT_SMALL_START,
)
from packrat.exceptions import (
    PackRatDecodingException,
    PackRatEncodingException,
    PackRatException,
)
from packrat.utils import vlq_dec, vlq_enc


def randstr() -> str:
    size = rand.randrange(256)
    return "".join(rand.choices(string.printable, k=size))


def randkeys(n_keys: int) -> list[str | bytes | int | float]:
    keys: list[str | bytes | int | float] = []
    for i in range(n_keys):
        match i % 4:
            case 0:
                keys.append(rand.randint(0, 2**64 - 1))
            case 1:
                keys.append(rand.random())
            case 2:
                keys.append(rand.randbytes(rand.randint(0, 255)))
            case 3:
                keys.append(randstr())
    return keys


class VLQTestCase(unittest.TestCase):
    def test_vql_enc_dec(self) -> None:
        for i in range(128):
            buff = BytesWriter()
            vlq_enc(i, buff)

            n = vlq_dec(io.BytesIO(buff.getvalue()))
            self.assertEqual(n, i)

        test_cases = [
            2**7,
            2**8 - 1,
            2**8,
            2**16 - 1,
            2**16,
            2**32 - 1,
            2**32,
            2**64 - 1,
            2**64,
            2**128 - 1,
        ]
        for i in test_cases:
            buff = BytesWriter()
            vlq_enc(i, buff)

            n = vlq_dec(io.BytesIO(buff.getvalue()))
            self.assertEqual(n, i)


class TypesTestCase(unittest.TestCase):
    def test_header(self) -> None:
        header = bytes([MAGIC_NUMBER_START]) + MAGIC_NUMER_SIG
        obj = [123, "abc"]
        stream = BytesWriter()
        rp.Encoder(stream, include_header=True).encode(obj)

        bites = bytearray(stream.getvalue())
        self.assertEqual(bites[: len(header)], header)

        decoded = rp.Decoder(io.BytesIO(bites)).decode()
        self.assertEqual(decoded, obj)

        with self.assertRaises(PackRatDecodingException):
            # corrupt header signature
            bites[1] = 0x01
            rp.Decoder(io.BytesIO(bites)).decode()

    def test_uint(self) -> None:
        for i in range(0, 64):
            bites = rp.packb(i)
            self.assertEqual(len(bites), 1)
            self.assertEqual(rp.unpackb(bites), i)

        bites = rp.packb(65)
        self.assertEqual(len(bites), 2)
        self.assertEqual(rp.unpackb(bites), 65)

        for i, size in [(2**8 - 1, 1), (2**16 - 1, 2), (2**32 - 1, 4), (2**64 - 1, 8)]:
            bites = rp.packb(i)
            self.assertEqual(len(bites), size + 1)
            self.assertEqual(rp.unpackb(bites), i)

        with self.assertRaises(PackRatEncodingException):
            rp.packb(2**64)

    def test_negint(self) -> None:
        for i in range(1, 36):
            bites = rp.packb(-i)
            self.assertEqual(len(bites), 1)
            self.assertEqual(rp.unpackb(bites), -i)

        bites = rp.packb(-36)
        self.assertEqual(len(bites), 2)
        self.assertEqual(rp.unpackb(bites), -36)

        for i, size in [(2**8 - 1, 1), (2**16 - 1, 2), (2**32 - 1, 4), (2**64 - 1, 8)]:
            bites = rp.packb(-i)
            self.assertEqual(len(bites), size + 1)
            self.assertEqual(rp.unpackb(bites), -i)

        with self.assertRaises(PackRatEncodingException):
            rp.packb(-(2**64))

    def test_binary(self) -> None:
        for i in range(0, 17):
            bin_str = b"x" * i
            bites = rp.packb(bin_str)
            self.assertEqual(len(bites), i + 1)
            self.assertEqual(rp.unpackb(bites), bin_str)

        bin_str = b"x" * 17
        bites = rp.packb(bin_str)
        self.assertEqual(len(bites), len(bin_str) + 2)
        self.assertEqual(rp.unpackb(bites), bin_str)

    def test_str(self) -> None:
        for i in range(0, 37):
            s = "x" * i
            bites = rp.packb(s)
            self.assertEqual(len(bites), i + 1)
            self.assertEqual(rp.unpackb(bites), s)

        s = "📦🐀 is great!"
        bites = rp.packb(s)
        self.assertEqual(len(bites), len(s.encode("utf8")) + 1)
        self.assertEqual(rp.unpackb(bites), s)

        s = "x" * 37
        bites = rp.packb(s)
        self.assertEqual(len(bites), len(s) + 2)
        self.assertEqual(rp.unpackb(bites), s)

    def test_array(self) -> None:
        for i in range(0, 33):
            # None encodes as a single byte
            arr = [None] * i
            bites = rp.packb(arr)
            self.assertEqual(len(bites), i + 1)
            self.assertEqual(rp.unpackb(bites), arr)

        arr = [None] * 33
        bites = rp.packb(arr)
        self.assertEqual(len(bites), len(arr) + 2)
        self.assertEqual(rp.unpackb(bites), arr)

    def test_map(self) -> None:
        for i in range(0, 33):
            d = {i: None for i in range(i)}
            bites = rp.packb(d)

            # each key is 1 byte (small int) and each None is 1 byte
            self.assertEqual(len(bites), i * 2 + 1)
            self.assertEqual(rp.unpackb(bites), d)

        d = {i: None for i in range(33)}
        bites = rp.packb(d)
        self.assertEqual(len(bites), 33 * 2 + 2, bites.hex(" "))
        self.assertEqual(rp.unpackb(bites), d)

    def test_map_deterministic_ordering(self) -> None:
        n_keys = rand.randint(18, 72)
        keys = randkeys(n_keys)
        nested_key = rand.choice(keys)
        nested_keys = randkeys(n_keys)

        d1: dict = {k: None for k in keys}
        d1[nested_key] = {k: None for k in nested_keys}

        rand.shuffle(keys)
        rand.shuffle(nested_keys)
        d2: dict = {k: None for k in keys}
        d2[nested_key] = {k: None for k in nested_keys}

        d1_enc = rp.packb(d1)
        d2_enc = rp.packb(d2)
        self.assertEqual(d1_enc, d2_enc)
        self.assertEqual(rp.unpackb(d1_enc), d1)
        self.assertEqual(rp.unpackb(d2_enc), d1)

    def test_map_duplicate_keys(self) -> None:
        # map of size 2 with duplicate keys (uint(0))
        # literally would be {0: 1, 0: 2}
        bites = bytes(
            [
                MAP_SMALL_NUM_START + 2,
                UINT_SMALL_START,
                UINT_SMALL_START + 1,
                UINT_SMALL_START,
                UINT_SMALL_START + 2,
            ]
        )
        with self.assertRaises(PackRatDecodingException):
            rp.unpackb(bites)

    def test_float(self) -> None:
        for i in [math.nan, math.inf, -math.inf, 0.0, 1.0, -1.0, 0.5, 2.0]:
            bites = rp.packb(i)
            self.assertEqual(len(bites), 5)

            if math.isnan(i):
                self.assertTrue(math.isnan(rp.unpackb(bites)))
            else:
                self.assertEqual(rp.unpackb(bites), i)

        for i in [math.pi, math.tau, math.e]:
            bites = rp.packb(i)
            self.assertEqual(len(bites), 9)
            self.assertEqual(rp.unpackb(bites), i)

    def test_bool_none(self) -> None:
        for i in [True, False, None]:
            bites = rp.packb(i)
            self.assertEqual(len(bites), 1)
            self.assertEqual(rp.unpackb(bites), i)

    def test_built_in_tags(self) -> None:
        today = datetime.now(tz=timezone.utc)
        event_id = uuid.uuid4()
        event = {"date": today, "id": event_id, "type": "some_event"}

        bites = rp.packb(event)
        self.assertEqual(len(bites), 77)
        self.assertEqual(rp.unpackb(bites), event)

    def test_custom_tag(self) -> None:
        def tuple_tag(i: int) -> rp.Tag:
            return rp.Tag(id=i, obj_type=tuple, encode=list, decode=tuple)  # type: ignore

        for i in range(9):
            with self.assertRaises(PackRatException):
                rp.packb((1, "two"), tags=[tuple_tag(i)])

        for i in range(9, 17):
            bites = rp.packb((1, "two"), tags=[tuple_tag(i)])
            # 7 = 1 small tag byte + 1 small array + 1 small int + 1 small str byte + 3 str content
            self.assertEqual(len(bites), 7)
            data = rp.unpackb(bites, tags=[tuple_tag(i)])
            self.assertEqual(data, (1, "two"))

        bites = rp.packb((1, "two"), tags=[tuple_tag(17)])
        # 8 = same as above, but an extra byte for the var tag
        self.assertEqual(len(bites), 8)
        data = rp.unpackb(bites, tags=[tuple_tag(17)])
        self.assertEqual(data, (1, "two"))

    def test_tag_compound_type(self) -> None:
        set_tag = rp.Tag(
            id=2026,
            obj_type=set,
            encode=lambda s: list(s),  # noqa: PLW0108
            decode=lambda l: set(cast(list, l)),
        )

        rgb = {"red", "green", "blue"}
        bites = rp.packb(rgb, tags=[set_tag])
        data = rp.unpackb(bites, tags=[set_tag])
        self.assertEqual(data, rgb)


class BenchMarkTestCase(unittest.TestCase):
    benchmarks: list[dict]

    @classmethod
    def setUpClass(cls) -> None:
        cls.benchmarks = [
            {
                "file": "benchmarks/data/canada.json",
                "size": 1055469,
                # time of 10 iterations
                "enc_time": 0.303404,
                "dec_time": 0.404910,
            },
            {
                "file": "benchmarks/data/citm_catalog.json",
                "size": 342109,
                "enc_time": 0.104647,
                "dec_time": 0.158774,
            },
            {
                "file": "benchmarks/data/twitter.json",
                "size": 401002,
                "enc_time": 0.053942,
                "dec_time": 0.073348,
            },
            {
                "file": "benchmarks/data/sample.json",
                "size": 147291,
                "enc_time": 0.014367,
                "dec_time": 0.016160,
            },
        ]
        return super().setUpClass()

    def test_benchmark(self) -> None:
        for bench in self.benchmarks:
            with self.subTest(file=bench["file"]):
                self._benchmark(bench)

    def _benchmark(self, bench: dict) -> None:
        with open(bench["file"]) as f:
            data = json.load(f)
            timer = timeit.Timer("rp.packb(data)", globals={"rp": rp, "data": data})
            enc_time = timer.repeat(repeat=3, number=10)
            enc_data = rp.packb(data)

            timer = timeit.Timer(
                "rp.unpackb(enc_data)", globals={"rp": rp, "enc_data": enc_data}
            )
            dec_time = timer.repeat(repeat=3, number=10)
            dec_data = rp.unpackb(enc_data)

            print(f"{bench['file']}")
            print(f"\tsize: {len(enc_data)} bytes")
            print(f"\tencode time: min({min(enc_time):.6f}) max({max(enc_time):.6f})")
            print(f"\tdecode time: min({min(dec_time):.6f}) max({max(dec_time):.6f})")

            self.assertEqual(dec_data, data)
            self.assertEqual(len(enc_data), bench["size"])
            self.assert_in_range(min(enc_time), bench["enc_time"], 0.1)
            self.assert_in_range(min(dec_time), bench["dec_time"], 0.1)

    def assert_in_range(
        self, actual_time: float, time: float, tolerance: float
    ) -> None:
        if actual_time > (time + time * tolerance):
            self.fail(f"{actual_time} > {time} +{tolerance * 100}%")
        elif actual_time < (time - time * tolerance):
            self.fail(
                f"{actual_time} < {time} -{tolerance * 100}% (this is good, just update the benchmarks!)"
            )
