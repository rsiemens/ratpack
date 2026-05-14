import io
import unittest
import ratpack as rp
from datetime import datetime


class TestLEB128Case(unittest.TestCase):
    def test_leb128_enc_dec(self):
        for i in range(128):
            buff = io.BytesIO()
            rp.leb128_enc(i, buff)

            buff.seek(0)
            n = rp.leb128_dec(buff)

            self.assertEqual(n, i)

        test_cases = [
            128,
            0xFF,
            0x100,
            0xFFFF,
            0x10000,
            0xFFFFFFFF,
            0x100000000,
            0xFFFFFFFFFFFFFFFF,
            0x10000000000000000,
            0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF,
        ]
        for i in test_cases:
            buff = io.BytesIO()
            rp.leb128_enc(i, buff)

            buff.seek(0)
            n = rp.leb128_dec(buff)

            self.assertEqual(n, i)

        with self.assertRaises(rp.RatPackException):
            rp.leb128_enc(0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF + 1, io.BytesIO())
        with self.assertRaises(rp.RatPackException):
            rp.leb128_enc(-1, io.BytesIO())


class TypesTestCase(unittest.TestCase):
    def test_uint(self):
        for i in range(rp.UINT_SMALL_END - rp.UINT_SMALL_START + 1):
            with self.subTest(f"uint({i})"):
                msg = rp.encode(i)
                self.assertEqual(len(msg), 1)
                self.assertEqual(msg, bytes([i]))

    def test_negint(self):
        for i in range(1, rp.NEG_INT_SMALL_END - rp.NEG_INT_SMALL_START + 1):
            with self.subTest(f"negative({i})"):
                msg = rp.encode(-i)
                self.assertEqual(len(msg), 1)
                self.assertEqual(msg, bytes([rp.NEG_INT_SMALL_START + i]))

    def test_tag(self):
        dt_tag = rp.Tag(
            9, datetime, lambda dt: dt.isoformat(), lambda s: datetime.fromisoformat(s)
        )

        dt = datetime.now()
        bites = rp.encode(dt, tags={dt_tag})
        data = rp.decode(bites, tags={dt_tag})
        self.assertEqual(dt, data)

        class MyModel:
            def __init__(self, name, age):
                self.name = name
                self.age = age

            def as_dict(self):
                return {"name": self.name, "age": self.age}

            @classmethod
            def from_dict(cls, obj):
                return cls(obj["name"], obj["age"])

            def __eq__(self, other):
                return self.name == other.name and self.age == other.age

        my_tag = rp.Tag(
            10, MyModel, lambda m: m.as_dict(), lambda o: MyModel.from_dict(o)
        )
        me = MyModel("Ryan", 36)
        bites = rp.encode(me, tags={dt_tag, my_tag})
        print(bites)
        data = rp.decode(bites, tags={dt_tag, my_tag})
        print(data)
        self.assertEqual(me, data)
