"""Adapt generated SSE CLAW diffuse paths to separately installed PlayerOnly art.

This narrow final resource stage changes only BSShaderTextureSet slot zero. It
does not load or copy artwork, change donors, rewrite geometry, or rename TRI.
The block-table layout follows the existing head_split.Nif adapter; keeping this
stdlib-only avoids importing its DCC/geometry dependencies into the packager.
"""
from __future__ import annotations

import hashlib
import struct

BASE = 'textures\\actors\\character\\werewolf\\elegant\\'
DIFFUSES = frozenset(('body.dds', 'head.dds', 'eyes.dds', 'furarms.dds',
                     'furback.dds', 'furbelly.dds', 'furchest.dds', 'furface.dds',
                     'furshoulders.dds', 'furtail.dds'))


class Reader:
    def __init__(self, data):
        self.data, self.pos = data, 0

    def take(self, count):
        if count < 0 or count > len(self.data) - self.pos:
            raise ValueError('Truncated SSE material resource')
        result = self.data[self.pos:self.pos + count]
        self.pos += count
        return result

    def unpack(self, fmt):
        return struct.unpack(fmt, self.take(struct.calcsize(fmt)))

    def string(self):
        return self.take(self.unpack('<I')[0])


def container(data):
    """Read only the reviewed SSE block directory; retain all header bytes."""
    reader = Reader(data)
    header = b'Gamebryo File Format, Version 20.2.0.7\n'
    if reader.take(len(header)) != header or reader.unpack('<IBI') != (0x14020007, 1, 12):
        raise ValueError('Only reviewed little-endian SSE NIFs are supported')
    count, bs_version = reader.unpack('<II')
    if bs_version != 100 or not 1 <= count <= 65535:
        raise ValueError('Only reviewed SSE BS100 block layout is supported')
    for _ in range(3):
        reader.take(reader.unpack('<B')[0])
    type_count = reader.unpack('<H')[0]
    if not 1 <= type_count <= count:
        raise ValueError('Invalid SSE block type directory')
    types = [reader.string().decode('ascii') for _ in range(type_count)]
    if len(set(types)) != type_count:
        raise ValueError('Ambiguous SSE block type directory')
    indices = reader.unpack('<' + str(count) + 'H')
    if any(index >= type_count for index in indices):
        raise ValueError('Invalid SSE block type index')
    sizes_start = reader.pos
    sizes = reader.unpack('<' + str(count) + 'I')
    sizes_end = reader.pos
    strings, maximum = reader.unpack('<II')
    if strings > len(data) // 4:
        raise ValueError('Invalid SSE string table size')
    stored_strings = [reader.string() for _ in range(strings)]
    if maximum < max(map(len, stored_strings), default=0) or reader.unpack('<I') != (0,):
        raise ValueError('Unsupported SSE string/group table')
    block_start = reader.pos
    blocks = [reader.take(size) for size in sizes]
    footer = reader.take(len(data) - reader.pos)
    if footer != struct.pack('<II', 1, 0):
        raise ValueError('Expected one SSE Scene Root')
    return data[:sizes_start], data[sizes_end:block_start], types, indices, blocks, footer


def texture_slots(data):
    reader = Reader(data)
    if reader.unpack('<I') != (9,):
        raise ValueError('Expected nine SSE BSShaderTextureSet slots')
    slots = [reader.string() for _ in range(9)]
    if reader.pos != len(data):
        raise ValueError('Unexpected texture-set trailing bytes')
    return slots


def adapt_nif(data):
    prefix, middle, types, indices, blocks, footer = container(data)
    replacements, observed, styles = [], set(), set()
    output = list(blocks)
    for index, block in enumerate(blocks):
        if types[indices[index]] != 'BSShaderTextureSet':
            continue
        slots = texture_slots(block)
        diffuse = slots[0].decode('ascii')
        normalized = diffuse.replace('/', '\\').casefold()
        if not normalized.startswith(BASE):
            continue
        filename = normalized[len(BASE):]
        prefixed = filename.startswith('player') and filename[6:] in DIFFUSES
        original = filename in DIFFUSES
        if not original and not prefixed:
            if filename not in ('claws.dds', 'teeth.dds'):
                raise ValueError('Unknown Elegant base diffuse: ' + filename)
            continue  # claws and teeth retain their separately installed shared maps.
        observed.add(filename[6:] if prefixed else filename)
        styles.add('player' if prefixed else 'main')
        if prefixed:
            continue
        # Preserve directory spelling/separators and every non-diffuse slot.
        split_at = max(diffuse.rfind('\\'), diffuse.rfind('/')) + 1
        changed = (diffuse[:split_at] + 'player' + diffuse[split_at:]).encode('ascii')
        slots[0] = changed
        output[index] = struct.pack('<I', 9) + b''.join(struct.pack('<I', len(s)) + s for s in slots)
        replacements.append({'block': index, 'before': diffuse, 'after': changed.decode('ascii')})
    if observed != DIFFUSES or len(styles) != 1:
        raise ValueError('Incomplete or mixed Main/PlayerOnly base diffuse set')
    result = (prefix + struct.pack('<' + str(len(output)) + 'I', *map(len, output))
              + middle + b''.join(output) + footer)
    # A second parse verifies sizes/offsets; untouched blocks stay byte-identical.
    after = container(result)
    if (prefix, middle, types, indices, footer) != (after[0], after[1], after[2], after[3], after[5]):
        raise ValueError('Material adaptation changed the NIF directory')
    changed_ids = {row['block'] for row in replacements}
    for index, (before, changed) in enumerate(zip(blocks, after[4])):
        if index not in changed_ids and before != changed:
            raise ValueError('Material adaptation changed an unrelated NIF block')
        if index in changed_ids and texture_slots(before)[1:] != texture_slots(changed)[1:]:
            raise ValueError('Material adaptation changed a non-diffuse texture slot')
    return result, {'inputSha256': hashlib.sha256(data).hexdigest(),
                    'outputSha256': hashlib.sha256(result).hexdigest(),
                    'changedTextureSets': replacements,
                    'nonTextureBlocksUnchanged': True,
                    'bodytriPathsUnchanged': True,
                    'artworkCopied': False}
