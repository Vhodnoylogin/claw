"""Prepare the mirror scene inside an already admitted disposable Skyrim VR run."""

import json
import math
from pathlib import Path
import time


SCENE = json.loads(Path(__file__).with_name('scene.json').read_text(encoding='utf-8'))
CLAW = 'CLAWDistributionNative'
PLAYER = SCENE['player']
PLAYER_BASE = SCENE['playerBase']
MORPH_OWNER = 'CLAW.Distribution'
ROLES = ('human', 'wolf')
RACE_BINDING = {'id': 'morph_race', 'script': 'Actor', 'function': 'SetRace', 'scope': 'member',
                'params': ['race'], 'returnType': 'none', 'effect': 'mutate', 'actorSelf': True,
                'actorArgs': [], 'raceArgs': [0], 'completion': 'actor-race'}


def require(condition, explanation):
    if not condition:
        raise RuntimeError(explanation)


def form(ref):
    return {'form': ref}


def form_id(value):
    candidate = value['formId']
    return f'0x{int(candidate, 16):08X}'


def native_policy(runtime_bases):
    """Freeze this policy in the owned executor configuration before the run."""
    require(set(runtime_bases) == set(ROLES) and len(set(runtime_bases.values())) == 2,
            'Two distinct resolved mirror NPC bases are required')
    return {'schemaVersion': 1, 'fixtureActorBases': [runtime_bases[role] for role in ROLES],
            'allowedRaceForms': [SCENE['nordRace'], SCENE['beastRace']], 'bindings': [RACE_BINDING]}


def visible_source_colours(audit):
    require(audit['schema'] == 1 and 0 <= audit['ageMs'] <= 2000, 'Fresh human material audit required')
    body_maps = {'actors/character/male/malebody_1.dds', 'actors/character/female/femalebody_1.dds'}
    skin, hair = set(), set()
    for row in audit['surfaces']:
        path = row.get('diffusePath', '').replace('\\', '/').casefold().removeprefix('textures/')
        name = row.get('name', '').casefold()
        if row.get('feature') == 5 and 'ovl' not in name and path in body_maps:
            channel = skin
        elif row.get('feature') == 6 and name.startswith('hair'):
            channel = hair
        else:
            continue
        tint = row.get('tint')
        require(type(tint) is list and len(tint) == 3 and all(type(value) in (int, float)
                and math.isfinite(value) for value in tint), 'Human source tint must be an RGB triple')
        channel.add(tuple(round(value, 4) for value in tint))
    require(len(skin) == len(hair) == 1, 'Primary body skin or head hair tint unavailable or ambiguous')
    return {'skin': next(iter(skin)), 'hair': next(iter(hair))}


class Mirrors:
    def __init__(self, session, variant):
        from skyrim_autotest import actor_domain, interactive_bindings, native
        from skyrim_autotest.platform import Backend
        from skyrim_autotest.runner import atomic_json

        self.session, self.variant = session, variant
        self.actor_domain, self.bindings, self.native = actor_domain, interactive_bindings, native
        self.backend, self.atomic_json = Backend, atomic_json
        self.case = SCENE['variants'][variant]
        self.game = session.state['game']
        self.config = session.state['configuration']
        self.policy = self.config['native_session']['nativeBindings']
        self.receipt = session.dir / 'claw-vr-player-mirrors.json'
        require(self.config['game_edition'] == 'vr' and self.config['reuse_test_profile'] is False
                and self.config.get('allow_owned_save_load') is False
                and session.state.get('testProfile') and session.state['gameplayBootstrap']['completed'] is True,
                'Use an admitted disposable VR profile with ownership and an actual ready game')
        require(session.state.get('ownedWorldGeneration', 0) > 0 and not self.receipt.exists()
                and not session.state.get('interactiveActorFixtures'),
                'The mirror scene may be attempted only once in this world')
        self.end = time.monotonic() + 260
        self.result = {'scene': SCENE['schema'], 'run': session.state['id'], 'game': self.game,
                       'variant': variant, 'status': 'preparing', 'headsetVisualVerified': False, 'pending': None}
        self.owned = {}
        self.world = session.state['ownedWorldGeneration']
        self.player = self.read_identity({'reference': PLAYER, 'base': PLAYER_BASE})
        self.cell = SCENE['cell']
        self.guard('player')
        self.save()

    def save(self):
        self.atomic_json(self.receipt, self.result)

    def deadline(self, seconds=12):
        require(self.end > time.monotonic(), 'Mirror phase deadline expired')
        return min(self.end, time.monotonic() + seconds)

    def active(self):
        require(any(row['role'] == 'game' and row['identity'] == self.game for row in self.session.state['owned'])
                and self.native.identity(self.game['pid']) == self.game
                and self.session.state['ownedWorldGeneration'] == self.world,
                'Mirror scene lost the exact owned Skyrim VR instance')

    def pap(self, script, method, args, returns, target=None):
        self.active()
        request = {'action': 'call', 'script': script, 'function': method, 'args': args, 'timeoutMs': 6000}
        if target is not None:
            request['self'] = form(target)
        reply = self.session.tool('papyrus', request, timeout=8, deadline=self.deadline())
        accepted_types = (returns,) if isinstance(returns, str) else returns
        require(reply.get('called') is True and 'returned' in reply
                and reply.get('returnedType', '').casefold() in accepted_types,
                f'Unconfirmed typed callback for {script}.{method}')
        return reply['returned']

    def read_identity(self, spec):
        self.active()
        return self.actor_domain.observe_actor(self.backend(self.session, self.deadline()), spec)

    def guard(self, role):
        if role == 'player':
            spec = {'reference': PLAYER, 'base': PLAYER_BASE}
            current = self.read_identity(spec)
            original = self.player
        else:
            spec, original = self.owned[role]
            current = self.read_identity(spec)
        require(current['incarnation'] == original['incarnation'] and current['actor']['loaded3D'] is True
                and current['providerObservation']['refs'][0]['cellForm'] == self.cell,
                f'Original loaded mirror actor changed: {role}')
        return current['actor']

    def place(self, role, base):
        self.guard('player')
        backend = self.backend(self.session, self.deadline())
        census = backend.call('inspect', {'kind': 'refs', 'formType': 'Actor', 'radius': 0, 'limit': 1024})
        previous = {form_id(row) for row in census['refs']}
        require(census['truncated'] is False and census['count'] == census['returned'] == len(previous)
                == len(census['refs']), 'Exact pre-spawn actor census unavailable')
        destination = SCENE['positions'][role]
        facing = 90.

        def spawn():
            reference = form_id(self.pap('ObjectReference', 'PlaceAtMe', [form(base), 1, False, False],
                                         'objectreference', PLAYER))
            require(0xFF000000 <= int(reference, 16) < 0xFFFFFFFF and reference not in previous,
                    'The scene did not receive a new dynamic actor')
            self.result.setdefault('mirrors', {})[role] = {'reference': reference, 'base': base,
                                                           'requestedPosition': destination}
            return reference

        reference = self.write(f'create {role} mirror', spawn)
        spec = {'reference': reference, 'base': base}
        original = self.poll(lambda: self.read_identity(spec), lambda row: row['actor']['loaded3D'] is True,
                             8, 'A new mirror did not acquire live 3D')
        require(all(original['incarnation'][key] == self.player['incarnation'][key]
                    for key in ('sessionId', 'loadGeneration')), 'Mirror belongs to another game world')
        self.owned[role] = (spec, original)
        self.mutate_actor(role, 'Actor', 'SetRestrained', [True])
        self.mutate_actor(role, 'Actor', 'UnequipAll', [])
        self.mutate_actor(role, 'ObjectReference', 'SetAngle', [0., 0., facing])
        self.mutate_actor(role, 'ObjectReference', 'SetPosition', destination)
        captures = self.result['mirrors'][role].setdefault('placementSamples', [])

        def measure():
            self.active()
            identity, row, observed = self.actor_domain.anchor(self.backend(self.session, self.deadline()), reference)
            require(identity == original['incarnation'] and row['loaded3D'] is True and row['cellForm'] == self.cell,
                    'Mirror identity changed while settling onto the floor')
            sample = {'position': row['position'], 'sampleId': observed['sampleId'], 'time': time.monotonic()}
            captures.append(sample)
            self.save()
            return sample

        def settled(sample):
            landed = sample['position']
            return (len(captures) > 1 and sample['sampleId'] > captures[-2]['sampleId']
                    and sample['time'] - captures[-2]['time'] >= .2
                    and math.dist(landed, captures[-2]['position']) <= 1.
                    and math.dist(landed, destination) <= 4.)

        self.poll(measure, settled, 6., 'A mirror did not settle within its expected lane and floor band')
        observed_heading = self.pap('ObjectReference', 'GetAngleZ', [], 'float', reference)
        require(abs((observed_heading - facing + 180.) % 360. - 180.) <= 1., 'Mirror must face the player')

    def write(self, name, call):
        require(self.result['pending'] is None, 'A previous mirror mutation has unknown outcome')
        self.result['pending'] = name
        self.save()
        value = call()
        self.result['pending'] = None
        self.save()
        return value

    def mutate_actor(self, role, script, method, args, *, global_call=False):
        actor = self.guard(role)
        ref = actor['reference']
        self.write(f'{role}: {method}', lambda: self.pap(script, method, [form(ref), *args] if global_call else args,
                                                         'none', None if global_call else ref))
        self.guard(role)

    def claw(self, actor, method, returns, *args):
        return self.pap(CLAW, method, [form(actor['reference']), *args], returns)

    def poll(self, read, accept, seconds, explanation):
        until = self.deadline(seconds)
        while time.monotonic() < until:
            value = read()
            if accept(value):
                return value
            time.sleep(.25)
        raise RuntimeError(explanation)

    def human_source(self, role):
        actor = self.guard(role)
        require(actor['race'] == SCENE['nordRace'] and actor['sex'] == self.case['sex']
                and abs(actor['weight'] - self.case['weight']) <= 1e-4,
                'Select Nord preset 1 of the fixture sex without changing its appearance or weight')
        base = actor['base']
        count = self.pap('ActorBase', 'GetNumHeadParts', [], 'int', base)
        require(type(count) is int and 0 < count <= 16, 'Human head parts are unavailable')
        parts = sorted(form_id(self.pap('ActorBase', 'GetNthHeadPart', [index], ('headpart', 'form'), base))
                       for index in range(count))
        face = [self.pap('ActorBase', 'GetFaceMorph', [index], 'float', base) for index in (0, 1, 2, 9, 15)]
        require(all(math.isfinite(value) and abs(value) <= 10 for value in face), 'A sampled face morph is unavailable')
        self.result.setdefault('rawFaceOption18', {})[role] = self.pap('ActorBase', 'GetFaceMorph', [18], 'float', base)
        presets = [self.pap('ActorBase', 'GetFacePreset', [index], 'int', base) for index in range(4)]
        height = self.pap('ActorBase', 'GetHeight', [], 'float', base)
        require(self.claw(actor, 'RequestCoatSurfaceAudit', 'bool') is True, 'Human material audit was refused')
        chunks = self.poll(lambda: self.claw(actor, 'GetCoatSurfaceAuditChunks', 'string[]'), bool, 5,
                           'Human material readback did not complete')
        data = json.loads(''.join(chunks))
        self.result.setdefault('rawHumanMaterials', {})[role] = data
        self.save()
        self.guard(role)
        return {'sex': actor['sex'], 'race': actor['race'], 'weight': actor['weight'], 'height': round(height, 4),
                'headParts': parts, 'faceMorphs': [round(value, 5) for value in face], 'facePresets': presets,
                'colours': visible_source_colours(data)}

    def stimulus(self, role):
        actor = self.guard(role)
        ref = form(actor['reference'])
        key = SCENE['morphKey']
        observed = {}
        for name, value in self.case['morphs'].items():
            args = [ref, name, key]
            require(self.pap('NiOverride', 'HasBodyMorph', args, 'bool') is False,
                    'The scene-owned source morph is already present')
            self.mutate_actor(role, 'NiOverride', 'SetBodyMorph', [name, key, value], global_call=True)
            result = self.pap('NiOverride', 'GetBodyMorph', args, 'float')
            require(math.isfinite(result) and abs(result - value) <= 1e-6, 'RaceMenu source coefficient did not round-trip')
            observed[name] = result
        self.mutate_actor(role, 'NiOverride', 'UpdateModelWeight', [], global_call=True)
        return observed

    def ready_wolf(self, role):
        ref_id = PLAYER if role == 'player' else self.owned[role][0]['reference']
        try:
            if form_id(self.pap('Actor', 'GetRace', [], 'race', ref_id)) != SCENE['beastRace']:
                return None
            if role == 'player' and any(self.pap('Actor', 'HasMagicEffect', [form(effect)], 'bool', PLAYER)
                                        for effect in SCENE['startupEffects']):
                return None
            if self.pap(CLAW, 'GetStatus', [form(ref_id)], 'int') != 2:
                return None
        except RuntimeError as error:
            # The ordinary race update can delay new read jobs. Never repeat the cast.
            if str(error).startswith('HTTP 504 api/tool/papyrus:') and 'was not dispatched within' in str(error):
                return None
            raise
        actor = self.guard(role)
        require(actor['race'] == SCENE['beastRace'], 'The loaded actor changed race during wolf readback')
        ref = form(actor['reference'])
        family = self.claw(actor, 'GetMorphFamily', 'string')
        require(family == self.case['matrixProfile'], f'Unexpected {role} wolf family: {family}')
        coefficients = {}
        for name, expected in self.case['expectedWolf'].items():
            authored = self.claw(actor, 'GetOwnMorph', 'float', name)
            stored = self.pap('NiOverride', 'GetBodyMorph', [ref, name, MORPH_OWNER], 'float')
            require(math.isfinite(authored) and math.isfinite(stored) and abs(authored - stored) <= 1e-5,
                    f'CLAW and RaceMenu differ for {role} {name}')
            require(abs(stored - expected) <= 1e-5, f'{role} {name} differs from the pinned conversion: {stored}')
            coefficients[name] = stored
        return {'reference': actor['reference'], 'family': family, 'coefficients': coefficients,
                'coat': self.claw(actor, 'GetAppliedCoatPattern', 'string')}

    def topology(self):
        self.guard('player')
        nonce = time.monotonic_ns() % 0x7FFFFFFE + 1
        reader = 'CLAWVRModelTopology'

        def read(method):
            value = json.loads(self.pap(reader, method, [nonce], 'string'))
            require((value['schema'], value['pid'], value['nonce']) ==
                    ('claw-vr-model-topology/4', self.game['pid'], nonce), 'Unrelated native topology reply')
            return value

        observed = read('Capture')
        if observed['status'] == 'pending':
            observed = self.poll(lambda: read('Read'), lambda row: row['status'] != 'pending', 5.,
                                 'Native avatar topology never settled')
        self.result['avatarTopology'] = observed
        self.save()
        sample = observed.get('sample', {})
        require(observed['status'] == 'ready' and sample['actor'] == int(PLAYER, 16)
                and sample['base'] == int(PLAYER_BASE, 16) and sample['race'] == int(SCENE['beastRace'], 16)
                and sample['runtimeHandle'] == self.player['incarnation']['runtimeHandle'],
                'Native topology does not identify the same player in Beast Form')
        world = sample['roots']['thirdPerson']
        roots = [item for item in sample['distinctRoots'] if item['id'] == world]
        require(world and len(roots) == 1 and any(roots[0]['roleGeometries']), 'No live CLAW wolf body in the world graph')

    def stage(self):
        runtime_bases = {role: form_id(self.pap('Game', 'GetFormFromFile', [int(local, 16), SCENE['fixture']], 'form'))
                         for role, local in self.case['bases'].items()}
        require(self.bindings.validate(self.policy) == self.bindings.validate(native_policy(runtime_bases)),
                'Resolved fixture identities differ from the exact admitted mirror policy')
        player = self.guard('player')
        require(player['race'] == SCENE['nordRace'] and player['sex'] == self.case['sex'],
                'The disposable character must be the selected Nord sex')
        self.mutate_actor('player', 'Actor', 'UnequipAll', [])
        source = {'player': self.human_source('player')}
        for role in ROLES:
            self.place(role, runtime_bases[role])
            source[role] = self.human_source(role)
            self.save()
        self.result['humanSource'] = source
        self.save()
        require(source['player'] == source['human'] == source['wolf'],
                'Head parts, sampled face, weight, height, skin and hair must match before transformation')
        self.result['humanMorphs'] = {role: self.stimulus(role) for role in ('player', *ROLES)}
        self.save()
        self.mutate_actor('wolf', 'Actor', 'SetRace', [form(SCENE['beastRace'])])
        self.result['wolfMirror'] = self.poll(lambda: self.ready_wolf('wolf'), bool, 25,
                                             'The wolf mirror did not receive the actual CLAW morphs')
        self.result['status'] = 'ready-for-ordinary-player-beast-form'
        self.save()

    def transform_player(self):
        quest = SCENE['initializerQuest']
        self.poll(lambda: (self.pap('Quest', 'GetCurrentStageID', [], 'int', quest),
                           self.pap('Quest', 'IsRunning', [], 'bool', quest)),
                  lambda value: value == (1, True), 90, 'The vanilla Companion initializer is unavailable')
        player = self.guard('player')
        require(player['race'] == SCENE['nordRace'] and not any(self.pap('Actor', check, [], 'bool', PLAYER)
                for check in ('IsDead', 'IsInCombat', 'IsOnMount')), 'The owned player cannot use Beast Form now')
        self.write('one ordinary Beast Form cast', lambda: self.pap('Spell', 'Cast', [form(PLAYER), None],
                                                                   'none', SCENE['beastPower']))
        self.result['playerWolf'] = self.poll(lambda: self.ready_wolf('player'),
                                              lambda row: row and row['coat'], 65,
                                              'Player did not settle after ordinary Beast Form')
        require(self.guard('human')['race'] == SCENE['nordRace'], 'The human mirror was transformed by mistake')
        player_values = self.result['playerWolf']['coefficients']
        mirror_values = self.result['wolfMirror']['coefficients']
        require(all(abs(player_values[name] - mirror_values[name]) <= 1e-5 for name in self.case['expectedWolf']),
                'Actual player and wolf mirror coefficients differ')
        desired_coat = self.result['playerWolf']['coat']
        if self.result['wolfMirror']['coat'] != desired_coat:
            mirror = self.guard('wolf')
            patterns = self.pap(CLAW, 'GetCoatPatterns', [], 'string[]')
            match = next((candidate for candidate in (desired_coat, desired_coat.split('/')[-1]) if candidate in patterns), None)
            require(match is not None, 'The applied player coat is outside the installed manual catalog')
            self.result['wolfMirrorAutomaticCoat'] = self.result['wolfMirror']['coat']
            require(self.write('match the NPC mirror coat to the player', lambda: self.claw(
                mirror, 'SetCoatPattern', 'bool', match)) is True, 'The mirror coat override was refused')
            self.result['wolfMirror'] = self.poll(lambda: self.ready_wolf('wolf'),
                                                  lambda row: row and row['coat'] == desired_coat, 15,
                                                  'The mirror did not display the player coat')
        self.topology()
        self.result['status'] = 'ready-for-headset-review'
        self.save()


def run(session, variant):
    """Return with the same live scene available for a headset witness."""
    session.phase('claw-vr-player-mirror', 280)
    mirrors = Mirrors(session, variant)
    mirrors.stage()
    mirrors.transform_player()
    return mirrors.result
