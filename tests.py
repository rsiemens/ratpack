import io
import unittest
import ratpack as rp
import timeit
from datetime import datetime
import json


class LEB128TestCase(unittest.TestCase):
    def test_leb128_enc_dec(self) -> None:
        for i in range(128):
            buff = io.BytesIO()
            rp.leb128_enc(i, buff)

            buff.seek(0)
            n = rp.leb128_dec(buff)
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
            buff = io.BytesIO()
            rp.leb128_enc(i, buff)

            buff.seek(0)
            n = rp.leb128_dec(buff)
            self.assertEqual(n, i)

        with self.assertRaises(rp.RatPackException):
            rp.leb128_enc(2**128, io.BytesIO())

        with self.assertRaises(rp.RatPackException):
            rp.leb128_enc(-1, io.BytesIO())


class TypesTestCase(unittest.TestCase):
    def test_uint(self) -> None:
        for i in range(rp.UINT_SMALL_END - rp.UINT_SMALL_START + 1):
            with self.subTest(f"uint({i})"):
                msg = rp.encode(i)
                self.assertEqual(len(msg), 1)
                self.assertEqual(msg, bytes([i]))

        self.assertEqual(rp.decode(rp.encode(0xFFF)), 0xFFF)

    def test_negint(self) -> None:
        for i in range(1, rp.NEG_INT_SMALL_END - rp.NEG_INT_SMALL_START + 1):
            with self.subTest(f"negative({i})"):
                msg = rp.encode(-i)
                self.assertEqual(len(msg), 1)
                self.assertEqual(msg, bytes([rp.NEG_INT_SMALL_START + i]))

        self.assertEqual(rp.decode(rp.encode(-0xFFF)), -0xFFF)

    def test_tag(self) -> None:
        dt_tag = rp.Tag(
            id=9,
            obj_type=datetime,
            encoder=lambda dt: dt.isoformat(),
            decoder=lambda s: datetime.fromisoformat(s),
        )

        dt = datetime.now()
        bites = rp.encode(dt, tags={dt_tag})
        data = rp.decode(bites, tags={dt_tag})
        self.assertEqual(dt, data)


class BenchMarkTestCase(unittest.TestCase):
    benchmarks: list[dict]

    @classmethod
    def setUpClass(cls) -> None:
        cls.benchmarks = [
            {
                "file": "data/canada.json",
                "size": 1055458,
                # time of 10 iterations
                "enc_time": 0.592634,
                "dec_time": 0.416291,
            },
            {
                "file": "data/citm_catalog.json",
                "size": 346063,
                "enc_time": 0.287119,
                "dec_time": 0.216958,
            },
            {
                "file": "data/twitter.json",
                "size": 401637,
                "enc_time": 0.104853,
                "dec_time": 0.075277,
            },
        ]
        return super().setUpClass()

    def test_benchmark(self) -> None:
        for bench in self.benchmarks:
            with self.subTest(file=bench["file"]):
                self._benchmark(bench)

    def _benchmark(self, bench) -> None:
        with open(bench["file"]) as f:
            data = json.load(f)
            timer = timeit.Timer("rp.encode(data)", globals={"rp": rp, "data": data})
            enc_time = timer.repeat(repeat=3, number=10)
            enc_data = rp.encode(data)

            timer = timeit.Timer(
                "rp.decode(enc_data)", globals={"rp": rp, "enc_data": enc_data}
            )
            dec_time = timer.repeat(repeat=3, number=10)
            dec_data = rp.decode(enc_data)

            print(f"{bench['file']}")
            print(f"\tsize: {len(enc_data)} bytes")
            print(f"\tencode time: min({min(enc_time):.6f}) max({max(enc_time):.6f})")
            print(f"\tdecode time: min({min(dec_time):.6f}) max({max(dec_time):.6f})")

            self.assertEqual(dec_data, data)
            self.assertEqual(len(enc_data), bench["size"])
            self.assert_in_range(min(enc_time), bench["enc_time"], 0.1)
            self.assert_in_range(min(dec_time), bench["dec_time"], 0.1)

    def assert_in_range(self, actual_time, time, tolerance) -> None:
        if actual_time > (time + time * tolerance):
            self.fail(f"{actual_time} > {time} +{tolerance * 100}%")
        elif actual_time < (time - time * tolerance):
            self.fail(
                f"{actual_time} < {time} -{tolerance * 100}% (this is good, just update the benchmarks!)"
            )
