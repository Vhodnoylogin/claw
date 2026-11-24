"""Photograph one human and their werewolf twin at three morph intensities."""

from coat_regional_readback import expected_paths
from coat_regional_scene import ROLES, require, tag
from publicity_se_scene import PublicityScene, SCENE


class PublicityMorphSeries(PublicityScene):
    def __init__(self, session, appearance, coat, scene_path=SCENE):
        super().__init__(session, appearance, scene_path)
        expected_paths(appearance, coat)
        self.morph['coat'] = coat
        self.data['seriesCoat'] = coat
        self.data['series'] = {}

    def return_to_human(self, actor, pair):
        self.guard(actor)
        self.session.state['activeSemanticCommandId'] = 'preview-return-' + actor
        self.mutate('Return the wolf to human form', lambda: self.bindings.guarded_call(self.session,
            {'bindingId': 'morph_race', 'self': self.spec(actor), 'args': [pair['race']]}, self.deadline(), self.policy))
        self.poll(lambda: self.guard(actor)['actor']['race'], lambda race: race == pair['race'], 12.,
                  'The wolf did not return to human form')
        self.poll(lambda: self.claw(actor, 'GetStatus', 'int'), lambda status: status == 5, 12.,
                  'The human retained the old wolf morph state')

    def photograph_morphs(self, case):
        family, _, _ = case.partition('-')
        index, base = next((i, pair) for i, pair in enumerate(self.pairs) if pair['name'] == case)
        stimuli = self.morph['families'][family]
        middle = {'human': {name: value * .5 for name, value in stimuli['human'].items()},
                  'wolf': stimuli['halfWolf']}
        strong = {side: stimuli[side] for side in ('human', 'wolf')}

        self.session.phase('Prepare reusable human and wolf twins for ' + family, 110)
        self.preselected = True
        self.create_pair(index, base)
        human, wolf = (tag(index, role) for role in ROLES)
        original = {actor: self.spec(actor) for actor in (human, wolf)}
        for level, values in (('00', base['morphs']), ('50', middle), ('100', strong)):
            self.session.phase(f'Photograph {family} source morphs at {level} percent', 100)
            pair = dict(base, morphs=values, name=f'{family}-{level}')
            if level != '00':
                self.return_to_human(wolf, pair)
                inputs = {actor: self.write_morph_sources(pair, actor) for actor in (human, wolf)}
            else:
                inputs = {actor: self.data['humanInputs'][actor] for actor in (human, wolf)}
            require(inputs[human] == inputs[wolf], 'Same-stage human twins have different inputs')
            self.transform(index, pair)
            observed = self.verify_morphs(wolf, pair)
            require(all(original[actor] == self.spec(actor) for actor in (human, wolf)),
                    'The series replaced an actor')
            for view, heading in (('front', 90.), ('profile', 0.)):
                self.frame(f'{family}-{level}-{view}', pair, index, heading)
            self.data['series'][level] = {'actors': original, 'humanInputs': inputs, 'wolf': observed}
            self.save()
        self.hide_pair(index)
        self.save()

    def run_series(self, family):
        require(family in self.morph['families'], 'Unknown body family for the photo series')
        return self.run(f'{family}-baseline')
