"""Review selected combinations of original Elegant body, head and fur textures."""

from copy import deepcopy
import json
import time
import xml.etree.ElementTree as ET

from coat_regional_readback import expected_paths, inspect_discrete_regions
from coat_regional_scene import require, tag
from publicity_se_scene import SCENE, PublicityScene, load_scene


REVIEW = SCENE.with_name('elegant-review.json')
CATALOG_ID = 'elegant-review'


def review_data():
    review = json.loads(REVIEW.read_bytes())
    cases = [case for group in review['cases'].values() for case in group]
    ids = {case['id'] for case in cases}
    rejected = {case['id'] for case in review['rejectedCombinations']}
    require(len(cases) == len(ids), 'Duplicate Elegant review case')
    require(ids.isdisjoint(rejected), 'Rejected Elegant combination is still active')
    return review, cases


def review_pairs(batch):
    review, _ = review_data()
    _, palette = load_scene(REVIEW)
    subjects = review['batches'][batch]
    pairs = [pair for pair in palette['pairs'] if pair['id'] in subjects]
    require(len(pairs) == len(subjects) and subjects, 'Invalid Elegant review batch')
    return pairs


def review_projection(original_library):
    """Write only material references and source hashes. The installed DDS stay untouched."""
    review, cases = review_data()
    source = ET.parse(original_library).getroot()
    sources = {row.attrib['id']: row for row in source.findall('Patterns/Pattern')}
    require(source.get('id') == 'elegant-2k-2.1' and len(sources) == 34,
            'Use the complete original Elegant Replacer catalog, without aliases')
    for choices in (review['skinChoices'], review['hairChoices'], review['headOnlyChoices']):
        require(all(set(names) <= sources.keys() for names in choices.values()), 'Unknown Elegant review donor')
    library = ET.Element('CoatLibrary', schemaVersion='2', id=CATALOG_ID,
                         sourceArchiveSha256=source.attrib['sourceArchiveSha256'])
    surfaces = source.find('Surfaces')
    library.append(deepcopy(surfaces))
    textures = sorted({surface.attrib['texture'] for surface in surfaces})
    patterns = ET.SubElement(library, 'Patterns')
    mapping = ET.Element('CoatMapping', schemaVersion='1', output='coat.selector')
    for index, case in enumerate(cases):
        pattern = ET.SubElement(patterns, 'Pattern', id=case['id'], label=case['id'])
        for name in textures:
            donor = {'body.dds': case['body'], 'head.dds': case.get('head', case['fur'])}.get(name, case['fur'])
            matches = sources[donor].findall(f'Texture[@name="{name}"]')
            require(len(matches) == 1, f'Expected one original {donor}/{name}')
            pattern.append(deepcopy(matches[0]))
        identity = f'{CATALOG_ID}/{case["id"]}'
        if index == 0:
            ET.SubElement(mapping, 'Range', id=identity, material=identity, min='0', max='1')
        else:
            ET.SubElement(mapping, 'Manual', id=identity, material=identity)
    files = {name: ET.tostring(root, encoding='us-ascii', xml_declaration=False)
             for name, root in (('CoatLibrary.xml', library), ('CoatMapping.xml', mapping))}
    require(all(len(payload) <= 65536 for payload in files.values()), 'The review exceeds the runtime XML limit')
    return files


def fixture_inventories():
    folder = REVIEW.parent.parent / 'regional-coats'
    skin_pairs = json.loads((folder / 'skin-pairs.json').read_bytes())['pairs']
    other_pairs = json.loads((folder / 'random-pairs.json').read_bytes())['candidateGroups']
    return {pair['base']: pair['inventory'] for pairs in [*other_pairs.values(), skin_pairs] for pair in pairs}


class PublicityElegantReview(PublicityScene):
    def __init__(self, session, appearance, batch):
        subjects = [pair['name'] for pair in review_pairs(batch)]
        super().__init__(session, appearance, REVIEW, subjects=subjects)
        review, cases = review_data()
        self.cases = review['cases']
        self.paths = {case['id']: expected_paths(appearance, f'{CATALOG_ID}/{case["id"]}') for case in cases}
        inventories = fixture_inventories()
        for pair in self.pairs:
            pair['inventory'] = inventories[pair['base']]
        self.preselected = True
        self.data['elegantReview'] = {}

    def common_coat(self, pair):
        return f'{CATALOG_ID}/{self.selected}'

    def inspect_coat(self, audit, pair, pattern):
        require(pattern == self.common_coat(pair), 'Unexpected applied Elegant review composite')
        paths = self.paths[self.selected]
        textures = inspect_discrete_regions(audit, pair, paths, paths)
        return {'paths': textures, 'alpha': {row['name']: row['materialAlpha'] for row in audit['surfaces']
                                             if row['name'].casefold() in textures}}

    def photograph(self):
        refs = self.lighting_refs()
        original = self.lights_disabled(refs)
        desired = [local not in self.lighting['modes']['single-fill'] for local in refs]
        try:
            self.set_lights_disabled(refs, desired)
            time.sleep(1.)
            for index, pair in enumerate(self.pairs):
                cases = [(group, case) for group, rows in self.cases.items() for case in rows
                         if case['subject'] == pair['id']]
                require(cases, 'No review case for ' + pair['name'])
                previous_model = None
                for group, case in cases:
                    self.session.phase('Photograph Elegant review coat: ' + case['id'], 90)
                    wolf = tag(index, 'Wolf')
                    if previous_model is None:
                        self.create_pair(index, pair)
                    else:
                        self.return_to_human(wolf, pair)
                    self.selected = case['id']
                    self.transform(index, pair)
                    label = f'{group}-{self.selected}'
                    materials = self.frame(label, pair, index, 90.)
                    model = self.data['rawAudits'][wolf][label]['before']['modelGeneration']
                    require(model != previous_model and self.lights_disabled(refs) == desired,
                            'Elegant review lost its new model or fixed light')
                    self.data['elegantReview'][label] = dict(case, modelGeneration=model, materials=materials)
                    previous_model = model
                    self.save()
                self.hide_pair(index)
                self.save()
        finally:
            if not self.data['unknownMutation']:
                self.set_lights_disabled(refs, original)
