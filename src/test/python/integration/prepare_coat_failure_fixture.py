"""Prepare an isolated coat failure overlay without altering dependency artwork."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[4]


def prepare(output: Path) -> dict:
    output = output.resolve()
    if output.is_relative_to(ROOT) and not output.is_relative_to(ROOT / 'target'):
        raise ValueError('Generated fixture files must be outside source or under target')
    source = ROOT / 'src/main/resources/appearance/CoatLibrary.xml'
    tree = ET.fromstring(source.read_bytes())
    patterns = {item.get('id'): item for item in tree.findall('Patterns/Pattern')}
    if set(patterns) != {'black', 'brown', 'grey', 'timber', 'timber-dark',
                         'valley-black', 'valley-brown', 'valley-grey', 'valley-white', 'white'}:
        raise ValueError('Expected the released ten-coat external catalog')
    output.mkdir(parents=True, exist_ok=False)
    prefix = 'textures/claw-test-coat-fallback/'
    for texture in patterns['black']:
        texture.set('path', prefix + 'absent/' + texture.get('name'))
    for texture in patterns['brown']:
        if texture.get('name') == 'furback.dds':
            texture.set('path', prefix + 'partial/furback.dds')
    corrupt = b'CLAW regression fixture: deliberately invalid DDS header'.ljust(128, b'\0')
    for texture in patterns['grey']:
        if texture.get('name') == 'furback.dds':
            texture.set('path', prefix + 'corrupt/furback.dds')
            texture.set('bytes', str(len(corrupt)))
            texture.set('sha256', hashlib.sha256(corrupt).hexdigest())
    truncated = bytearray(128)
    truncated[:4] = b'DDS '
    for offset, value in ((4, 124), (8, 0xA1007), (12, 2048), (16, 2048),
                          (28, 12), (76, 32), (80, 4), (84, 0x35545844), (108, 0x1000)):
        struct.pack_into('<I', truncated, offset, value)
    for texture in patterns['timber-dark']:
        if texture.get('name') == 'furback.dds':
            texture.set('path', prefix + 'truncated/furback.dds')
            # Its valid DXT5 header declares a full mip payload that is absent.
            # Rejection must come from the actual DDS, not catalog provenance.
    files = {
        'SKSE/Plugins/CLAW/CoatLibrary.xml': ET.tostring(tree, encoding='utf-8'),
        prefix + 'corrupt/furback.dds': corrupt,
        prefix + 'truncated/furback.dds': bytes(truncated),
        'meta.ini': b'[General]\nmodid=0\nversion=1\nnotes=CLAW synthetic coat validation failures\n',
    }
    for name, data in files.items():
        destination = output / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
    result = {
        'schemaVersion': 1,
        'catalogSource': str(source),
        'catalogSourceSha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'output': str(output),
        'dependencyFilesModified': False,
        'artworkCopied': False,
        'cases': [
            {'pattern': 'elegant-2k-2.1/black', 'failure': 'all nine selected DDS paths absent'},
            {'pattern': 'elegant-2k-2.1/brown', 'failure': 'one fur DDS absent, other eight paths retained'},
            {'pattern': 'elegant-2k-2.1/grey', 'failure': 'one synthetic invalid DDS header'},
            {'pattern': 'elegant-2k-2.1/timber-dark', 'failure': 'synthetic header-only DDS has wrong byte length'},
        ],
        'expected': {'appliedCoat': '', 'statusContains': 'DDS missing or header/size mismatch',
                     'material': 'installed base material retained as a complete set',
                     'bodyProjection': 'continues and matches the selected body matrix'},
        'files': {name: hashlib.sha256(data).hexdigest() for name, data in files.items()},
    }
    (output.parent / (output.name + '.json')).write_text(json.dumps(result, indent=2), encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    print(json.dumps(prepare(parser.parse_args().out), indent=2))
