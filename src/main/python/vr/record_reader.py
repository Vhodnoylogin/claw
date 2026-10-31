"""Small original read-only Skyrim record reader for explicit offline audits.

Supports 24-byte TES4/GRUP/record headers, zlib record payloads and XXXX lengths.
It resolves file-local form IDs through declared masters; it never reads a live
profile, writes a plugin or models engine-specific first-person selection.
"""
from __future__ import annotations

from dataclasses import dataclass
import mmap
from pathlib import Path
import struct
import zlib

MAX_PAYLOAD = 16 * 1024 * 1024
INDEX_TYPES = {'TES4', 'RACE', 'ARMO', 'ARMA', 'NPC_'}


@dataclass(frozen=True)
class FormKey:
    plugin: str
    local_id: int

    def __post_init__(self):
        if not self.plugin or '/' in self.plugin or '\\' in self.plugin or not 0 <= self.local_id <= 0xFFFFFF:
            raise ValueError('Invalid canonical form key')
        object.__setattr__(self, 'plugin', self.plugin.casefold())

    def text(self):
        return '%06X:%s' % (self.local_id, self.plugin)


def subrecords(body):
    result, pos, extended = [], 0, None
    while pos < len(body):
        if pos + 6 > len(body):
            raise ValueError('Truncated subrecord header')
        tag, size = struct.unpack_from('<4sH', body, pos)
        pos += 6
        if tag == b'XXXX':
            if extended is not None or size != 4 or pos + 4 > len(body):
                raise ValueError('Invalid XXXX subrecord')
            extended = struct.unpack_from('<I', body, pos)[0]
            pos += 4
            continue
        if extended is not None:
            size, extended = extended, None
        if size > MAX_PAYLOAD or pos + size > len(body):
            raise ValueError('Truncated or excessive subrecord')
        try:
            name = tag.decode('ascii')
        except UnicodeDecodeError as exc:
            raise ValueError('Invalid subrecord signature') from exc
        result.append((name, bytes(body[pos:pos + size])))
        pos += size
    if extended is not None:
        raise ValueError('Dangling XXXX subrecord')
    return result


def zstring(data):
    if not data or data[-1] != 0 or b'\0' in data[:-1]:
        raise ValueError('Expected a single zero-terminated record string')
    return data[:-1].decode('utf-8')


@dataclass
class Record:
    source: 'PluginFile'
    signature: str
    offset: int
    size: int
    flags: int
    raw_form_id: int

    @property
    def key(self):
        return self.source.form_key(self.raw_form_id)

    def fields(self):
        if self.size > MAX_PAYLOAD:
            raise ValueError('Record payload exceeds audit bound')
        body = bytes(self.source.raw[self.offset + 24:self.offset + 24 + self.size])
        if self.flags & 0x40000:
            if len(body) < 4:
                raise ValueError('Truncated compressed record')
            expected = struct.unpack_from('<I', body)[0]
            if expected > MAX_PAYLOAD:
                raise ValueError('Decompressed record exceeds audit bound')
            inflater = zlib.decompressobj()
            try:
                body = inflater.decompress(body[4:], MAX_PAYLOAD + 1)
            except zlib.error as exc:
                raise ValueError('Invalid compressed record stream') from exc
            if len(body) != expected or not inflater.eof or inflater.unused_data or inflater.unconsumed_tail:
                raise ValueError('Compressed record size/stream mismatch')
        return subrecords(body)

    def values(self, tag):
        return [value for name, value in self.fields() if name == tag]

    def one(self, tag, required=True):
        values = self.values(tag)
        if len(values) > 1 or (required and not values):
            raise ValueError('Expected one %s in %s' % (tag, self.key.text()))
        return values[0] if values else None

    def ref(self, tag, required=True):
        value = self.one(tag, required)
        if value is None:
            return None
        if len(value) != 4:
            raise ValueError('Expected a four-byte form reference: ' + tag)
        raw = struct.unpack('<I', value)[0]
        return self.source.form_key(raw) if raw else None

    def provenance(self):
        return {'formKey': self.key.text(), 'signature': self.signature,
                'file': str(self.source.path), 'recordOffset': self.offset,
                'rawFormId': '%08X' % self.raw_form_id, 'flags': self.flags,
                'editorId': zstring(self.one('EDID'))}


class PluginFile:
    def __init__(self, path):
        self.path = Path(path).resolve(strict=True)
        self.stream = self.path.open('rb')
        self.raw = None
        try:
            if self.path.stat().st_size < 24:
                raise ValueError('Truncated plugin')
            self.raw = mmap.mmap(self.stream.fileno(), 0, access=mmap.ACCESS_READ)
            if self.raw[:4] != b'TES4':
                raise ValueError('Expected TES4 file header')
            self.name = self.path.name.casefold()
            self.masters = []
            header = self._record(0, len(self.raw))
            if header.raw_form_id != 0:
                raise ValueError('Unexpected TES4 form ID')
            self.masters = [zstring(value).casefold() for value in header.values('MAST')]
            if len(self.masters) > 253 or len(set(self.masters)) != len(self.masters) or self.name in self.masters:
                raise ValueError('Invalid or unsupported master list')
            self.records = {}
            self._index(0, len(self.raw), 0)
        except Exception:
            self.close()
            raise

    def close(self):
        if self.raw is not None:
            self.raw.close()
            self.raw = None
        self.stream.close()

    def form_key(self, raw_id):
        index, local = raw_id >> 24, raw_id & 0xFFFFFF
        if index > len(self.masters):
            raise ValueError('File-local master index is outside the declared list')
        return FormKey(self.masters[index] if index < len(self.masters) else self.name, local)

    def _record(self, pos, end):
        if pos + 24 > end:
            raise ValueError('Truncated record header')
        sig, size, flags, fid = struct.unpack_from('<4sIII', self.raw, pos)
        if pos + 24 + size > end:
            raise ValueError('Record exceeds containing group/file')
        try:
            signature = sig.decode('ascii')
        except UnicodeDecodeError as exc:
            raise ValueError('Invalid record signature') from exc
        return Record(self, signature, pos, size, flags, fid)

    def _index(self, start, end, depth):
        if depth > 64:
            raise ValueError('Record group nesting exceeds audit bound')
        pos = start
        while pos < end:
            if pos + 24 > end:
                raise ValueError('Truncated record/group header')
            if self.raw[pos:pos + 4] == b'GRUP':
                size = struct.unpack_from('<I', self.raw, pos + 4)[0]
                if size < 24 or pos + size > end:
                    raise ValueError('Invalid group size')
                self._index(pos + 24, pos + size, depth + 1)
                pos += size
            else:
                record = self._record(pos, end)
                if record.signature in INDEX_TYPES and record.signature != 'TES4':
                    key = record.key
                    if key in self.records:
                        raise ValueError('Duplicate canonical record in a plugin')
                    self.records[key] = record
                pos += 24 + record.size


class DeclaredLoadOrder:
    """Last declared override wins; never claims to be the active game load order."""
    def __init__(self, plugins):
        self.plugins = list(plugins)
        seen = set()
        for plugin in self.plugins:
            if plugin.name in seen or not set(plugin.masters) <= seen:
                raise ValueError('Duplicate plugin or missing/late declared master')
            seen.add(plugin.name)

    def history(self, key):
        return [p.records[key] for p in self.plugins if key in p.records]

    def winner(self, key, signature):
        history = self.history(key)
        if not history:
            raise ValueError('Missing record: ' + key.text())
        winner = history[-1]
        if winner.signature != signature or winner.flags & (0x20 | 0x1000):
            raise ValueError('Winning record has wrong type or is deleted/ignored: ' + key.text())
        return winner
