"""Photograph the ten stock coats on one wolf at a fixed QASmoke mark."""

from decimal import Decimal
import re
import time
import xml.etree.ElementTree as ET

from coat_regional_readback import expected_paths, inspect_discrete_regions
from coat_regional_scene import require, tag
from publicity_se_scene import PublicityScene


def stock_coats(appearance):
    ranges = ET.parse(appearance / 'CoatMapping.xml').getroot().findall('Range')
    ranges.sort(key=lambda entry: Decimal(entry.attrib['min']))
    coats = [entry.attrib['id'] for entry in ranges]
    require(len(coats) == len(set(coats)) == 10
            and all(re.fullmatch(r'elegant-2k-2\.1/[a-z]+(?:-[a-z]+)*', coat) for coat in coats),
            'Expected all ten canonical Elegant coat ranges')
    return coats


class PublicityCoatCatalog(PublicityScene):
    def __init__(self, session, appearance):
        super().__init__(session, appearance)
        self.catalog = {coat: expected_paths(appearance, coat) for coat in stock_coats(appearance)}
        self.selected = next(iter(self.catalog))

    def common_coat(self, pair):
        return self.selected

    def inspect_coat(self, audit, pair, pattern):
        require(pattern == self.selected, 'The wolf changed its selected catalog coat')
        paths = self.catalog[pattern]
        return inspect_discrete_regions(audit, pair, paths, paths)

    def _room_lighting(self):
        refs = [self.papyrus('Game', 'GetFormFromFile', [local, self.lighting['plugin']], 'form')['formId']
                for local in self.lighting['references']]
        require(len(set(refs)) == len(refs), 'Expected distinct inspection lights')

        def observed():
            return [self.papyrus('ObjectReference', 'IsDisabled', [], 'bool', ref) for ref in refs]

        original = observed()
        for ref, was_disabled in zip(refs, original, strict=True):
            if not was_disabled:
                self.papyrus('ObjectReference', 'DisableNoWait', [False], 'none', ref, write=True)
        self.poll(observed, all, 5., 'Inspection fills did not switch off')
        self.data['catalogLighting'] = {'mode': 'room', 'fillReferences': refs, 'fillsDisabled': observed()}
        self.save()
        time.sleep(1.)
        return refs, original

    def photograph(self):
        index, pair = next((i, pair) for i, pair in enumerate(self.pairs)
                           if pair.get('name') == 'Angi' and 'morphs' not in pair)
        wolf = tag(index, 'Wolf')
        self.session.phase('Prepare the joined coat catalog pair and room lighting', 90)
        self.preselected = True
        self.create_pair(index, pair)
        self.transform(index, pair)
        refs, original = self._room_lighting()
        self.data['catalog'] = {}
        try:
            for number, coat in enumerate(self.catalog, 1):
                self.session.phase('Photograph stock coat ' + coat, 65)
                if number > 1:
                    require(self.claw(wolf, 'SetCoatPattern', 'bool', coat, write=True) is True,
                            'The manual catalog coat was refused: ' + coat)
                    self.selected = coat
                self.poll(lambda: self.claw(wolf, 'GetAppliedCoatPattern'), lambda value: value == coat,
                          12, 'The manual catalog coat did not bind: ' + coat)
                require(self.claw(wolf, 'GetCoatPattern') == coat, 'Manual catalog selection differs: ' + coat)
                label = f'catalog-{number:02}-{coat.rsplit("/", 1)[-1]}'
                materials = self.frame(label, pair, index, 90.)
                require(self.claw(wolf, 'GetCoatPattern') == coat, 'Manual catalog selection changed during capture')
                self.data['catalog'][coat] = {'label': label, 'materials': materials}
                self.save()
            self.hide_pair(index)
            self.save()
        finally:
            if not self.data['unknownMutation']:
                for ref, was_disabled in zip(refs, original, strict=True):
                    if not was_disabled:
                        self.papyrus('ObjectReference', 'EnableNoWait', [False], 'none', ref, write=True)
                self.poll(lambda: [self.papyrus('ObjectReference', 'IsDisabled', [], 'bool', ref)
                                   for ref in refs],
                          lambda flags: flags == original, 5., 'Inspection fill restoration differs')
