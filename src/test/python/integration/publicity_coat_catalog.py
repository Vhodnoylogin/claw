"""Photograph the original Elegant coats on fresh models at a fixed QASmoke mark."""

from decimal import Decimal
import re
import time
import xml.etree.ElementTree as ET

from coat_regional_readback import expected_paths, inspect_discrete_regions
from coat_regional_scene import require, tag
from publicity_se_scene import PublicityScene


def compact_replacer_library(library):
    """Preserve original materials within the runtime's 64 KiB XML limit."""
    root = ET.parse(library).getroot()
    for row in root.iter():
        row.text = row.tail = None
    for pattern in root.findall('Patterns/Pattern'):
        # Manual selection never reads automatic colour-distance samples.
        for name in ('furR', 'furG', 'furB'):
            pattern.attrib.pop(name, None)
    encoded = ET.tostring(root, encoding='us-ascii', xml_declaration=False)
    require(len(encoded) <= 65536, 'The complete catalog exceeds the runtime XML limit')
    return encoded


def replacer_catalog_mapping(base_mapping, library):
    """Build a test-only mapping which names all original Replacer materials."""
    source = ET.parse(library).getroot()
    namespace = source.attrib['id']
    slugs = sorted(row.attrib['id'] for row in source.findall('Patterns/Pattern'))
    require(namespace == 'elegant-2k-2.1' and len(slugs) == len(set(slugs)) == 34,
            'Expected the complete 34-pattern Elegant Replacer catalog')
    mapping = ET.parse(base_mapping).getroot()
    require(mapping.findall('SkinGroup') and mapping.findall('HairGroup'),
            'The original-colour catalog requires discrete regional mode')
    for row in list(mapping):
        if row.tag in ('Range', 'Alias', 'Manual'):
            mapping.remove(row)
    for i, slug in enumerate(slugs):
        coat = namespace + '/' + slug
        mapping.insert(i, ET.Element('Range', min=str(i / len(slugs)), max=str((i + 1) / len(slugs)),
                                     id=coat, material=coat))
    ET.indent(mapping, space='  ')
    return ET.tostring(mapping, encoding='utf-8') + b'\n'


def stock_coats(appearance):
    ranges = ET.parse(appearance / 'CoatMapping.xml').getroot().findall('Range')
    ranges.sort(key=lambda entry: Decimal(entry.attrib['min']))
    library = ET.parse(appearance / 'CoatLibrary.xml').getroot()
    patterns = {row.attrib['id'] for row in library.findall('Patterns/Pattern')}
    sizes = {'randomized': 10, 'elegant-2k-2.1': 34}
    coats = [entry.attrib['id'] for entry in ranges]
    require(len(coats) == len(set(coats)) == len(patterns) == sizes.get(library.attrib['id'])
            and all(re.fullmatch(r'elegant-2k-2\.1/[a-z]+(?:-[a-z]+)*', coat) for coat in coats)
            and set(coats) == {'elegant-2k-2.1/' + slug for slug in patterns}
            and all(entry.attrib['material'] == library.attrib['id'] + '/' + entry.attrib['id'].split('/')[1]
                    for entry in ranges), 'Expected an exact one-to-one catalog of original Elegant materials')
    return coats


class PublicityCoatCatalog(PublicityScene):
    def __init__(self, session, appearance, *, lighting='single-fill'):
        super().__init__(session, appearance, subject='Angi')
        self.catalog = {coat: expected_paths(appearance, coat) for coat in stock_coats(appearance)}
        self.selected = next(iter(self.catalog))
        self.catalog_lighting = lighting
        self.end = time.monotonic() + 90 + 24 * len(self.catalog)

    def common_coat(self, pair):
        return self.selected

    def inspect_coat(self, audit, pair, pattern):
        require(pattern == self.selected, 'The wolf changed its selected catalog coat')
        paths = self.catalog[pattern]
        return inspect_discrete_regions(audit, pair, paths, paths)

    def _lighting_refs(self):
        refs = {local: self.papyrus('Game', 'GetFormFromFile', [local, self.lighting['plugin']], 'form')['formId']
                for local in self.lighting['references']}
        require(len(set(refs.values())) == len(refs), 'Expected distinct inspection lights')
        return refs

    def _read_lights(self, refs):
        return [self.papyrus('ObjectReference', 'IsDisabled', [], 'bool', ref) for ref in refs.values()]

    def _set_lights(self, refs, desired):
        for ref, off, was_off in zip(refs.values(), desired, self._read_lights(refs), strict=True):
            if off != was_off:
                action = 'DisableNoWait' if off else 'EnableNoWait'
                self.papyrus('ObjectReference', action, [False], 'none', ref, write=True)
        return self.poll(lambda: self._read_lights(refs), lambda actual: actual == desired, 5.,
                         'Catalog lighting state did not settle')

    def photograph(self):
        index, pair = next((i, pair) for i, pair in enumerate(self.pairs)
                           if pair.get('name') == 'Angi' and 'morphs' not in pair)
        wolf = tag(index, 'Wolf')
        self.session.phase('Prepare the joined coat catalog pair and room lighting', 90)
        self.preselected = True
        self.create_pair(index, pair)
        refs = self._lighting_refs()
        original = self._read_lights(refs)
        enabled = self.lighting['modes'][self.catalog_lighting]
        desired = [local not in enabled for local in refs]
        self.data['catalog'] = {}
        try:
            actual = self._set_lights(refs, desired)
            self.data['catalogLighting'] = {'mode': self.catalog_lighting, 'fillReferences': list(refs.values()),
                                            'fillsDisabled': actual}
            self.save()
            time.sleep(1.)
            previous_model = None
            for number, coat in enumerate(self.catalog, 1):
                self.session.phase('Photograph stock coat on a fresh wolf model ' + coat, 80)
                # With a live material swap, the previous wolf can lose its
                # lighting even when every bound texture path is correct.
                if number > 1:
                    self.return_to_human(wolf, pair)
                self.selected = coat
                self.transform(index, pair)
                label = f'catalog-{number:02}-{coat.rsplit("/", 1)[-1]}'
                materials = self.frame(label, pair, index, 90.)
                require(self.claw(wolf, 'GetCoatPattern') == coat, 'Manual catalog selection changed during capture')
                require(self._read_lights(refs) == desired, 'Lighting changed during catalog capture')
                model = self.data['rawAudits'][wolf][label]['before']['modelGeneration']
                require(model != previous_model, 'The catalog reused the previous wolf model')
                self.data['catalog'][coat] = {'label': label, 'materials': materials, 'modelGeneration': model}
                previous_model = model
                self.save()
            self.hide_pair(index)
            self.save()
        finally:
            if not self.data['unknownMutation']:
                self._set_lights(refs, original)
