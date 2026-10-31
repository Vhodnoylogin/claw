"""Patch existing quantized TRIP offsets without reserializing other fields.

This deliberately cannot add records, change scales, or serialize a whole mesh.
The caller owns topology, shape-space conversion and geometric acceptance.
"""
from dataclasses import dataclass
import math
import struct


@dataclass(frozen=True)
class Offset:
    position: int
    scale: float
    packed: tuple


def offsets(data):
    """Return (shape,morph,vertex)->Offset; reject ambiguous/malformed streams."""
    view = memoryview(data)
    cursor = 0

    def take(size):
        nonlocal cursor
        if size < 0 or cursor + size > len(view):
            raise ValueError("truncated TRIP")
        result = view[cursor:cursor + size]
        cursor += size
        return result

    def unpack(fmt):
        return struct.unpack(fmt, take(struct.calcsize(fmt)))

    def name():
        size, = unpack('<B')
        text = bytes(take(size)).decode('iso-8859-15')
        if not text:
            raise ValueError("empty TRIP name")
        return text

    if bytes(take(4)) not in (b'PIRT', b'\0IRT'):
        raise ValueError("not TRIP")
    result = {}
    shapes = set()
    for _ in range(unpack('<H')[0]):
        shape = name()
        if shape in shapes:
            raise ValueError("duplicate shape")
        shapes.add(shape)
        morphs = set()
        for _ in range(unpack('<H')[0]):
            morph = name()
            if morph in morphs:
                raise ValueError("duplicate morph")
            morphs.add(morph)
            scale, count = unpack('<fH')
            if not math.isfinite(scale) or scale <= 0:
                raise ValueError("invalid TRIP scale")
            for _ in range(count):
                vertex, = unpack('<H')
                position = cursor
                packed = unpack('<3h')
                key = (shape, morph, vertex)
                if key in result:
                    raise ValueError("duplicate vertex")
                result[key] = Offset(position, scale, packed)
    # Extensions are deliberately unsupported: never silently reinterpret them.
    if cursor != len(view):
        raise ValueError("unsupported TRIP trailing data")
    return result


def patch(data, replacements):
    """Replace packed signed-int16 triples at existing keys, keeping all else exact.

    Values are already quantized integers; callers must explicitly choose their
    rounding policy and verify geometry using decoded output, not ideal floats.
    """
    records = offsets(data)
    output = bytearray(data)
    for key, packed in replacements.items():
        if key not in records:
            raise ValueError("replacement has no existing TRIP record")
        if len(packed) != 3 or any(type(x) is not int or not -32768 <= x <= 32767 for x in packed):
            raise ValueError("replacement requires three signed int16 values")
        struct.pack_into('<3h', output, records[key].position, *packed)
    return bytes(output)
