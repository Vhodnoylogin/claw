"""Prepare local recoloured DDS and catalog entries for the four-pair SE scene."""

import argparse
from hashlib import file_digest
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from coat_harmonized_textures import generate
from coat_regional_readback import expected_paths
from coat_regional_scene import PALETTE


def prepare(installed, appearance, output):
    output = output.resolve()
    if any((parent / '.git').exists() for parent in [output, *output.parents]):
        raise ValueError('The local preview must be generated outside Git')
    if output.is_relative_to(installed.resolve()):
        raise ValueError('The local preview needs a directory outside the installed textures')
    pairs = json.loads(PALETTE.read_bytes())['pairs']
    mapping = ET.parse(appearance / 'CoatMapping.xml')
    library = ET.parse(appearance / 'CoatLibrary.xml')
    entries = library.find('Patterns')
    library_id = library.getroot().get('id')
    names = {surface.attrib['texture'] for surface in library.findall('Surfaces/Surface')}
    prefix = Path('textures/actors/character/werewolf/claw-review')
    output.mkdir(parents=True, exist_ok=False)
    generated = generate(installed, output / prefix, pairs)
    coats, staged = {}, []
    for pair in pairs:
        base = pair['base']
        slug = generated[base]['pattern']
        if slug != f'harmonized-{int(base, 16):08x}' or set(generated[base]['textures']) != names:
            raise ValueError(f'Unexpected texture inventory for {base}')
        manual_id = f'review/{slug}'
        if any(node.get('id') == manual_id for node in mapping.getroot()):
            raise ValueError(f'Duplicate preview coat {manual_id}')
        ET.SubElement(mapping.getroot(), 'Manual', id=manual_id, material=f'{library_id}/{slug}')
        pattern = ET.SubElement(entries, 'Pattern', id=slug, label=f'Harmonized {pair["name"]}')
        for name in sorted(names):
            relative = (prefix / slug / name).as_posix()
            source = output / relative
            with source.open('rb') as stream:
                digest = file_digest(stream, 'sha256').hexdigest()
            ET.SubElement(pattern, 'Texture', name=name, path=relative, sha256=digest, bytes=str(source.stat().st_size))
            staged.append({'destination': relative, 'source': str(source.resolve()), 'sha256': digest})
        coats[base] = manual_id
    for name, tree in [('CoatMapping.xml', mapping), ('CoatLibrary.xml', library)]:
        ET.indent(tree)
        tree.write(output / name, encoding='utf-8')
    for coat in coats.values():
        expected_paths(output, coat)
    for name, value in [('generated-coats.json', coats), ('texture-pins.json', staged), ('colour-metrics.json', generated)]:
        (output / name).write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--installed', required=True, type=Path, help='Local Elegant Randomized texture root')
    parser.add_argument('--appearance', required=True, type=Path, help='Current regional CoatMapping.xml / CoatLibrary.xml')
    parser.add_argument('--output', required=True, type=Path, help='New local folder outside Git')
    args = parser.parse_args()
    prepare(args.installed, args.appearance, args.output)


if __name__ == '__main__':
    main()
