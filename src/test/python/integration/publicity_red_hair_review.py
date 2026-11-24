"""Test dark skin and visibly red hair on a matched pair of Anwen fixtures."""

from contextlib import closing
from hashlib import sha256
from pathlib import Path
from struct import pack, pack_into, unpack_from
import sys
import time

from coat_regional_readback import expected_paths, inspect_discrete_regions, verify_human
from coat_regional_scene import require, tag
from publicity_elegant_review import REVIEW, fixture_inventories, review_data
from publicity_se_scene import PublicityScene, load_scene


PLUGIN = 'test_CLAWAnwenRedHair.esp'
FACEGEN = 'meshes/actors/character/facegendata/facegeom/skyrim.esm/00013386.nif'
FACEGEN_SHA256 = '84a5eacc82a95782864b6883a45a8f8415b8df7f3c872fad13ebe1f9803bc516'
HAIR_TINT_OFFSETS = (218919, 228737)  # HairTint properties of the two stock hair shapes.


def red_hair_pair():
    study = review_data()[0]['redHairStudy']
    _, palette = load_scene(REVIEW)
    pair, = (pair for pair in palette['pairs'] if pair['id'] == study['subject'])
    return dict(pair, hair=study['hair'], inventory=fixture_inventories()[pair['base']])


def build_hair_fixture(master, target):
    """Point Anwen to a private hair colour form in the disposable profile."""
    repo = REVIEW.parents[5]
    sys.path[:0] = [str(repo / 'src/main/python/vr'), str(REVIEW.parent.parent / 'lighting')]
    from build_lighting import grp, rec, sub
    from record_reader import FormKey, PluginFile, zstring

    pair = red_hair_pair()
    npc = int(pair['base'], 16)
    local_colour = 0x0800
    with closing(PluginFile(master)) as source:
        original = source.records[FormKey('Skyrim.esm', npc)]
        require(source.name == 'skyrim.esm' and source.masters == [] and original.signature == 'NPC_'
                and zstring(original.one('EDID')) == 'Anwen'
                and original.ref('RNAM') == FormKey('Skyrim.esm', int(pair['race'], 16))
                and original.ref('HCLF') == FormKey('Skyrim.esm', 0x0A0435), 'Unexpected vanilla Anwen record')
        fields = original.fields()
    override = {'HCLF': pack('<I', 0x01000000 | local_colour), 'FULL': b'Anwen\0'}
    npc_data = b''.join(sub(name, override.get(name, value)) for name, value in fields)
    colour = b''.join((sub('EDID', b'CLAWFixtureCrimsonHair\0'), sub('FULL', b'Crimson\0'),
                       sub('CNAM', bytes([*pair['hair'], 0])), sub('FNAM', pack('<I', 1))))
    header = b''.join((sub('HEDR', pack('<fII', 1.7, 4, local_colour + 1)),
                       sub('CNAM', b'CLAW test scene\0'), sub('MAST', b'Skyrim.esm\0'), sub('DATA', bytes(8))))
    target = Path(target)
    require(target.name == PLUGIN, 'Unexpected name for the disposable hair fixture')
    with target.open('xb') as file:
        file.write(rec('TES4', 0, header) + grp(b'NPC_', 0, rec('NPC_', npc, npc_data))
                   + grp(b'CLFM', 0, rec('CLFM', 0x01000000 | local_colour, colour)))
    with closing(PluginFile(target)) as generated:
        actual = generated.records[FormKey('Skyrim.esm', npc)]
        require(actual.fields() == [(key, override.get(key, value)) for key, value in fields]
                and actual.ref('HCLF') == FormKey(PLUGIN, local_colour), 'Anwen override readback differs')


def build_hair_facegen(source, target):
    """Patch only the baked hair tint values of the exact stock Anwen FaceGen."""
    data = bytearray(Path(source).read_bytes())
    require(sha256(data).hexdigest() == FACEGEN_SHA256, 'Unexpected stock Anwen FaceGen revision')
    pair = red_hair_pair()
    _, palette = load_scene(REVIEW)
    stock, = (subject for subject in palette['pairs'] if subject['id'] == pair['id'])
    colour = tuple(2 * channel / 255 for channel in pair['hair'])
    for offset in HAIR_TINT_OFFSETS:
        measured = [round(channel * 255 / 2) for channel in unpack_from('<fff', data, offset)]
        require(measured == stock['hair'], 'Expected the original blue-black hair material')
        pack_into('<fff', data, offset, *colour)
    with Path(target).open('xb') as file:
        file.write(data)


class PublicityRedHairReview(PublicityScene):
    def __init__(self, session, appearance):
        pair = red_hair_pair()
        super().__init__(session, appearance, REVIEW, subjects=[pair['name']])
        self.pairs[0].update(pair)
        self.study = review_data()[0]['redHairStudy']
        self.body_paths = expected_paths(appearance, self.study['automaticBody'])
        self.hair_paths = expected_paths(appearance, self.study['automaticHair'])
        self.data['redHairStudy'] = dict(self.study, transformations=[])

    def inspect_coat(self, audit, pair, pattern):
        require(pattern == self.study['automaticBody'], 'Automatic body choice differs from the expected palette')
        paths = inspect_discrete_regions(audit, pair, self.body_paths, self.hair_paths)
        require(all(row['materialAlpha'] == 1 for row in audit['surfaces'] if row['name'].casefold() in paths),
                'Automatic coat unexpectedly changes material alpha')
        return paths

    def photograph(self):
        pair, = self.pairs
        refs = self.lighting_refs()
        original = self.lights_disabled(refs)
        desired = [local not in self.lighting['modes']['single-fill'] for local in refs]
        wolf = tag(0, 'Wolf')
        previous_model = None
        try:
            self.set_lights_disabled(refs, desired)
            time.sleep(1.)
            self.session.phase('Photograph Anwen with a crimson hair colour', 135)
            self.create_pair(0, pair)
            for label in ('automatic-first', 'automatic-repeat'):
                if previous_model is not None:
                    self.return_to_human(wolf, pair)
                    verify_human(self.audit(wolf), pair)
                self.transform(0, pair)
                paths = self.frame(label, pair, 0, 90.)
                sample = self.data['rawAudits'][wolf][label]['before']
                model = sample['modelGeneration']
                require(model != previous_model and self.lights_disabled(refs) == desired,
                        'The automatic coat comparison lost its new model or fixed light')
                self.data['redHairStudy']['transformations'].append(dict(frame=label, model=model, paths=paths))
                previous_model = model
                self.save()
            self.hide_pair(0)
        finally:
            if not self.data['unknownMutation']:
                self.set_lights_disabled(refs, original)
