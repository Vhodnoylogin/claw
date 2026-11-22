"""Male12-specific graph/readback checks; actual archive replay is opt-in."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parent))
import male12_readback as readback

sys.path.insert(0, str(readback.REPO/'src/test/cpp/fsmp_step_witness'))
from test_validate_snapshot import fixture, v4_window

REF, BASE = '0x0E000900', '0x0E000800'
ROTATION = [1., 0., 0., 0., 1., 0., 0., 0., 1.]


def symbolic(xml):
    """Synthetic contract fixture only; no claim of retained native execution."""
    probe, rig, _, _ = readback.shared()
    profile = readback.source_profile(xml)
    roles = (*readback.anchors(), *readback.roles())
    tokens = {name: i for i, name in enumerate(roles, 1)}
    names = readback.node_names()

    def transform(name, local=False):
        return {'translation': [20. * names.index(name), 0., 1.],
                'rotationRowMajor': list(ROTATION), 'scale': 1. if local else readback.SCALE}

    identity = {'form': REF, 'loadGeneration': 1, 'runtimeHandle': 92}
    root = {'firstPerson': False, 'identityBasis': 'sampled_pointer_and_handle_changes_no_object_retention',
            'sampledRootToken': 51}
    actor = {'status': 'available', 'raceStatus': 'available', 'sex': 0, 'baseForm': BASE,
             'baseRace': rig.WOLF_RACE, 'race': rig.WOLF_RACE,
             'weight': {'status': 'available', 'rawNPCWeight': 50.}}
    world = {'ok': True, 'quality': 'complete', 'schemaVersion': 1, 'phase': 'skse_main_thread_task',
             'units': 'skyrim_engine_units', 'space': 'world', 'coherence': probe.OBSERVATION,
             'sessionId': '17-101', 'observerVersion': 'synthetic-male12', 'loadGeneration': 1,
             'sampleId': 12, 'producerMonotonicNs': 1080,
             'refs': [{'status': 'available', 'loaded3D': True, 'deleted': False, 'disabled': False,
                       'identity': identity, 'rootIdentity': root, 'actor': actor, 'baseForm': BASE,
                       'scale': readback.SCALE, 'position': [0.]*3, 'anglesRadians': [0.]*3,
                       'sceneTransform': transform(names[0])}],
             'nodes': [{'name': name, 'status': 'available', 'firstPerson': False, 'form': REF,
                        'identity': identity, 'rootIdentity': root, 'world': transform(name),
                        'local': transform(name, True)} for name in names]}
    edges = []
    for index, (driver, config) in enumerate(profile.items(), 1):
        values = {}
        for key, (linear, angular) in rig.PARAMETER_PAIRS.items():
            ls, rs = ((readback.SCALE, 1) if key in ('lowerLimit', 'upperLimit')
                      else (readback.SCALE**3, readback.SCALE**5) if key == 'stiffness' else (1, 1))
            values[key] = [x*ls for x in config['declared'][linear]] + [x*rs for x in config['declared'][angular]]
        values.update(springEnabled=[True]*6, stopERP=[.2]*6, stiffnessLimited=[True]*6, dampingLimited=[True]*6)
        edges.append({'token': index, 'bodyAToken': tokens[config['parent']], 'bodyBToken': tokens[driver],
                      'type': 12, 'enabled': True, 'status': 'spring2', 'spring2': values})
    natives = []
    for serial, time, count in ((1, 1000, 30), (2, 1200, 42)):
        native = fixture(serial=serial, count=count, qpc=time)
        native['schema'] = rig.V4_SE
        window = v4_window()
        window.update(status='collecting', pairedSteps=count, lastPreQpc=time-2, lastPostQpc=time-1,
                      summedPairedHostTimeStep=.016*count)
        objects = []
        for name in roles:
            dynamic = name in profile
            row = transform(name)
            rigid = {'world': row['rotationRowMajor'] + row['translation'], 'rigidBody': True,
                     'inverseMass': 1/(profile[name]['mass']*readback.SCALE**3) if dynamic else 0.,
                     'flags': 0 if dynamic else 2, 'linearVelocity': [0.]*3, 'angularVelocity': [0.]*3,
                     'inverseLocalInertia': [1/(x*readback.SCALE**5) for x in profile[name]['inertia']] if dynamic else [0.]*3}
            objects.append({'token': tokens[name], 'initialPre': copy.deepcopy(rigid), 'lastPre': copy.deepcopy(rigid),
                            'lastPost': copy.deepcopy(rigid), 'maximumPairedDifference': 0., 'firstNonzeroStep': 0,
                            'firstNonzeroPair': None, 'minimumPostWorld': list(rigid['world']),
                            'maximumPostWorld': list(rigid['world'])})
        window.update(objectCount=len(objects), objects=objects)
        window['incidentConstraints'].update(constraintCount=len(edges), constraints=copy.deepcopy(edges))
        native['sample']['objectWindow'] = window
        natives.append(native)
    return world, *natives


class Male12ReadbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        composition = readback.shared()[3]
        anatomy, fsmp = composition.modules()
        profile = anatomy.load_profile()
        cls.xml = composition.compose_xml(fsmp.render_xml(False), anatomy.render_xml(profile),
            fsmp.common.source.NODES, profile['drivers'], ('NPC Head [Head]', 'Tails'), (profile['anchor'],))
        cls.case = symbolic(cls.xml)

    def evaluate(self, case=None):
        return readback.evaluate_configuration(self.xml, *(self.case if case is None else case),
                                               reference=REF, base=BASE, pid=17, nonce=71)

    def test_exact_twelve_graph_keeps_canonical_role_lists(self):
        probe, rig, _, _ = readback.shared()
        result = self.evaluate()
        self.assertEqual(len(result['joints']), 12)
        self.assertEqual(len(result['tokens']), 15)
        self.assertEqual(len(probe.MALE), 9)
        self.assertEqual(len(probe.FEMALE), 11)
        self.assertFalse(result['runtimeQualified'])
        self.assertFalse(result['contactQualified'])
        self.assertEqual(result['joints']['WWRB 1']['parent'], 'WWD 2')
        with self.assertRaises(ValueError):
            rig.rig.source_profile(self.xml, 'male')

    def test_wrong_graph_collision_and_changed_authored_mass_rejected(self):
        for change in ('parent', 'collision', 'mass'):
            xml = ET.fromstring(self.xml)
            if change == 'parent':
                next(x for x in xml.findall('generic-constraint') if x.get('bodyB') == 'WWRB 1').set('bodyA', 'WWD 1')
            elif change == 'collision':
                ET.SubElement(xml, 'per-triangle-shape', name='foreign')
            else:
                xml.find("bone[@name='WWD 2']/mass").text = '.03'
            with self.subTest(change=change), self.assertRaises(ValueError):
                readback.source_profile(ET.tostring(xml))

    def test_missing_actual_native_observation_cannot_be_replaced_by_binding(self):
        for before in (None, {'called': True, 'returned': [True]*12}, {}):
            with self.subTest(before=before), self.assertRaises(ValueError):
                self.evaluate((self.case[0], before, self.case[2]))

    def test_wrong_native_mass_and_inertia_rejected(self):
        for field in ('inverseMass', 'inverseLocalInertia'):
            case = copy.deepcopy(self.case)
            for native in case[1:]:
                body = native['sample']['objectWindow']['objects'][-1]
                for stage in readback.shared()[1].joint.STAGES:
                    if field == 'inverseMass':
                        body[stage][field] += 1
                    else:
                        body[stage][field][0] += 1
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'mass|inertia'):
                self.evaluate(case)

    def test_wrong_directed_constraint_and_foreign_extra_node_rejected(self):
        case = copy.deepcopy(self.case)
        for native in case[1:]:
            native['sample']['objectWindow']['incidentConstraints']['constraints'][-1]['bodyAToken'] = 1
        with self.assertRaisesRegex(ValueError, 'directed'):
            self.evaluate(case)
        case = copy.deepcopy(self.case)
        row = next(x for x in case[0]['nodes'] if x['name'] == 'WWLB 1')
        row['identity'] = {**row['identity'], 'runtimeHandle': 99}
        with self.assertRaisesRegex(ValueError, 'identity'):
            self.evaluate(case)

    def test_coincident_solver_roles_cannot_be_disambiguated_by_order(self):
        case = copy.deepcopy(self.case)
        for native in case[1:]:
            objects = native['sample']['objectWindow']['objects']
            for stage in readback.shared()[1].joint.STAGES:
                objects[-1][stage]['world'] = list(objects[-2][stage]['world'])
                objects[-1]['minimumPostWorld'] = list(objects[-2]['minimumPostWorld'])
                objects[-1]['maximumPostWorld'] = list(objects[-2]['maximumPostWorld'])
        with self.assertRaisesRegex(ValueError, 'ambiguous'):
            self.evaluate(case)

    def test_missing_changed_skin_resource_pin_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'male.nif'
            with self.assertRaises(FileNotFoundError):
                readback.capture(folder, {'male.nif': '0'*64})
            path.write_bytes(b'original packed skin weights')
            pin = readback.digest(path.read_bytes())
            path.write_bytes(b'changed packed skin weights')
            with self.assertRaisesRegex(ValueError, 'Pinned input differs'):
                readback.capture(folder, {'male.nif': pin})

    def test_configured_rig_with_only_common_translation_is_not_motion(self):
        configured = self.evaluate()
        final = copy.deepcopy(self.case[2])
        final['sample']['sampledQpc'] = 1500
        window = final['sample']['objectWindow']
        window.update(status='complete', pairedSteps=900, lastPreQpc=1470, lastPostQpc=1480,
                      summedPairedHostTimeStep=.016*900)
        for body in window['objects']:
            body['lastPost']['world'][9] += 3.
            body['maximumPostWorld'][9] = body['lastPost']['world'][9]
        result = readback.evaluate_motion(configured, final)
        self.assertEqual(result['status'], 'incomplete')
        self.assertEqual(result['observedJointCount'], 0)


class ActualMale12Replay(unittest.TestCase):
    def test_exact_archived_diagnostic_and_failed_motion_preserved(self):
        case, candidate = (os.environ.get(name) for name in ('CLAW_MALE12_CASE_ROOT', 'CLAW_MALE12_CANDIDATE'))
        if case is None and candidate is None:
            self.skipTest('Explicit retained male12 case and candidate not selected')
        self.assertTrue(case and candidate, 'Set both explicit male12 evidence paths')
        result = readback.replay(Path(case), Path(candidate), readback.json_object(readback.CATALOGUE.read_bytes()))
        self.assertEqual(result['historicalResult'], 'failed')
        self.assertEqual(result['diagnostic']['status'], 'unconfirmed')
        self.assertEqual(result['diagnostic']['missingDrivers'], list(readback.roles()))
        self.assertEqual(result['diagnostic']['actualWorldFollowChecks'], 75)
        self.assertEqual(result['configurationReadback']['status'], 'unavailable')
        self.assertFalse(result['runtimeQualified'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
