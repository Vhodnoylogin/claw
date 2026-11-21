"""Source-only checks for the scoped, all-joint SE configuration readback."""

import copy
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

if __package__:
    from . import fsmp_rig_config_readback as readback
else:
    import fsmp_rig_config_readback as readback

sys.path.append(str(Path(__file__).resolve().parents[4] / 'src/test/cpp/fsmp_step_witness'))
from test_validate_snapshot import fixture, v4_window


REF = '0xFF000812'
BASE = '0x0D000801'
WOLF = '0x000CDD84'
NONCE = 71
ROTATION = [1., 0., 0., 0., 1., 0., 0., 0., 1.]
VECTORS = {
    'linearLowerLimit': [-.15] * 3, 'linearUpperLimit': [.15] * 3,
    'angularLowerLimit': [-.01] * 3, 'angularUpperLimit': [.01] * 3,
    'linearStiffness': [1] * 3, 'angularStiffness': [.5] * 3,
    'linearDamping': [.4] * 3, 'angularDamping': [.4] * 3,
    'linearEquilibrium': [.1, 0, 0], 'angularEquilibrium': [0, 0, 0],
}
PARAMETERS = {
    'lowerLimit': [-.15] * 3 + [-.01] * 3, 'upperLimit': [.15] * 3 + [.01] * 3,
    'stiffness': [1.] * 3 + [.5] * 3, 'damping': [.4] * 6, 'stopERP': [.2] * 6,
    'springEnabled': [True] * 6, 'stiffnessLimited': [True] * 6, 'dampingLimited': [True] * 6,
}


def symbolic(sex):
    probe = readback.probe
    root = ET.Element('system')
    anchors = tuple(dict.fromkeys(probe.anchors(sex).values()))
    drivers = probe.drivers(sex)
    roles = anchors + drivers
    tokens = {name: i for i, name in enumerate(roles, 1)}
    scene_roles = probe.node_names(sex)
    identity = {'form': REF, 'loadGeneration': 1, 'runtimeHandle': 92}
    root_id = {'firstPerson': False, 'identityBasis': 'sampled_pointer_and_handle_changes_no_object_retention',
               'sampledRootToken': 51}
    def xyz(tag, values):
        return ET.Element(tag, {axis: str(value) for axis, value in zip('xyz', values, strict=True)})
    def transform(name):
        return {'translation': [10. * scene_roles.index(name), 0., 1.],
                'rotationRowMajor': list(ROTATION), 'scale': 1.}
    for name in roles:
        bone = ET.SubElement(root, 'bone', name=name)
        ET.SubElement(bone, 'mass').text = '0' if name in anchors else '.05'
        if name in drivers:
            bone.append(xyz('inertia', [.1, .1, .1]))
    windows = []
    for serial, time, count in ((1, 1000, 30), (2, 1200, 42)):
        native = fixture(serial=serial, count=count, qpc=time)
        native['schema'] = readback.V4_SE
        window = v4_window()
        window.update(status='collecting', pairedSteps=count, lastPreQpc=time - 2, lastPostQpc=time - 1,
                      summedPairedHostTimeStep=.016 * count)
        objects = []
        for name in roles:
            row = transform(name)
            rigid = {'world': row['rotationRowMajor'] + row['translation'], 'rigidBody': True,
                     'inverseMass': 0. if name in anchors else 20., 'flags': 2 if name in anchors else 0,
                     'linearVelocity': [0.] * 3, 'angularVelocity': [0.] * 3, 'inverseLocalInertia': [0.] * 3}
            objects.append({'token': tokens[name], 'initialPre': copy.deepcopy(rigid), 'lastPre': copy.deepcopy(rigid),
                            'lastPost': copy.deepcopy(rigid), 'maximumPairedDifference': 0., 'firstNonzeroStep': 0,
                            'firstNonzeroPair': None, 'minimumPostWorld': list(rigid['world']),
                            'maximumPostWorld': list(rigid['world'])})
        window.update(objectCount=len(objects), objects=objects)
        native['sample']['objectWindow'] = window
        windows.append(native)
    parents = [anchors[0], drivers[0], anchors[0], drivers[2], anchors[1], *drivers[4:8], *anchors[2:]]
    edges = []
    for index, (parent, driver) in enumerate(zip(parents, drivers, strict=True), 1):
        link = ET.SubElement(root, 'generic-constraint', bodyA=parent, bodyB=driver)
        ET.SubElement(link, 'frameInA' if driver in probe.FEMALE[len(probe.MALE):] else 'frameInB')
        link.extend(xyz(tag, vector) for tag, vector in VECTORS.items())
        edges.append({'token': index, 'bodyAToken': tokens[parent], 'bodyBToken': tokens[driver],
                      'type': 12, 'enabled': True, 'status': 'spring2', 'spring2': copy.deepcopy(PARAMETERS)})
    for native in windows:
        native['sample']['objectWindow']['incidentConstraints'].update(
            constraintCount=len(edges), constraints=copy.deepcopy(edges))
    actor = {'status': 'available', 'raceStatus': 'available', 'sex': int(sex == 'female'),
             'baseForm': BASE, 'baseRace': WOLF, 'race': WOLF,
             'weight': {'status': 'available', 'rawNPCWeight': 50.}}
    world = {'ok': True, 'quality': 'complete', 'schemaVersion': 1, 'phase': 'skse_main_thread_task',
             'units': 'skyrim_engine_units', 'space': 'world', 'coherence': probe.OBSERVATION,
             'sessionId': '17-101', 'observerVersion': 'synthetic', 'loadGeneration': 1, 'sampleId': 12,
             'producerMonotonicNs': 1080,
             'refs': [{'status': 'available', 'loaded3D': True, 'deleted': False, 'disabled': False,
                       'identity': identity, 'rootIdentity': root_id, 'actor': actor, 'baseForm': BASE, 'scale': 1.,
                       'position': [0.] * 3, 'anglesRadians': [0.] * 3, 'sceneTransform': transform(scene_roles[0])}],
             'nodes': [{'name': name, 'status': 'available', 'firstPerson': False, 'form': REF,
                        'identity': identity, 'rootIdentity': root_id,
                        'world': transform(name), 'local': transform(name)} for name in scene_roles]}
    return root, world, *windows


def evaluate(case, sex='female'):
    xml, world, before, after = case
    return readback.evaluate(ET.tostring(xml), world, before, after,
                             reference=REF, base=BASE, sex=sex, pid=17, nonce=NONCE)


def object_window(native):
    return native['sample']['objectWindow']


class RigConfigReadbackTests(unittest.TestCase):
    def test_checks_all_joints_and_keeps_equilibrium_declared_only(self):
        for sex, count in (('female', 11), ('male', 9)):
            with self.subTest(sex=sex):
                result = evaluate(symbolic(sex), sex)
                self.assertEqual(result['status'], 'configured-se-rig-observed')
                self.assertEqual(len(result['joints']), count)
                self.assertEqual(set(result['joints']), set(readback.probe.drivers(sex)))
                ear = result['joints'][readback.probe.MALE[0]]
                self.assertEqual(ear['authoredXml']['linearEquilibrium'], [.1, 0., 0.])
                self.assertNotIn('linearEquilibrium', ear['observedSpring2'])

    def test_omitted_declared_equilibrium_and_duplicate_xml_vectors_fail(self):
        for edit in ('missing', 'duplicate'):
            with self.subTest(edit=edit), self.assertRaisesRegex(ValueError, 'constraint element'):
                case = symbolic('female')
                row = case[0].find('generic-constraint')
                if edit == 'missing':
                    row.remove(row.find('angularEquilibrium'))
                else:
                    row.append(copy.deepcopy(row.find('linearUpperLimit')))
                evaluate(case)

    def test_wrong_tail_parameter_or_reversed_edge_fails(self):
        for fault, message in (('damping', 'Configured damping differs: TailBone05'),
                               ('reverse', 'directed rig constraint catalogue')):
            with self.subTest(fault=fault), self.assertRaisesRegex(ValueError, message):
                case = symbolic('female')
                for native in case[2:]:
                    tail = object_window(native)['incidentConstraints']['constraints'][8]
                    if fault == 'damping':
                        tail['spring2']['damping'][4] = .40001
                    else:
                        tail['bodyAToken'], tail['bodyBToken'] = tail['bodyBToken'], tail['bodyAToken']
                evaluate(case)

    def test_unbound_kinematic_and_aliased_dynamic_roles_fail(self):
        for index, role in ((0, 'kinematic'), (4, 'dynamic')):
            with self.subTest(role=role), self.assertRaisesRegex(ValueError, 'ambiguous ' + role):
                case = symbolic('female')
                for native in case[2:]:
                    objects = object_window(native)['objects']
                    objects[index + 1].update({key: copy.deepcopy(value) for key, value in objects[index].items()
                                               if key != 'token'})
                evaluate(case)

    def test_refuses_changed_window_incarnation_and_scale(self):
        for fault, message in (('nonce', 'Window nonce changed'), ('actor', 'incarnation changed'),
                               ('scale', 'Unit SE actor')):
            with self.subTest(fault=fault), self.assertRaisesRegex(ValueError, message):
                case = symbolic('female')
                if fault == 'nonce':
                    object_window(case[3])['nonce'] = 72
                elif fault == 'actor':
                    case[1]['refs'][0]['actor']['race'] = '0x00013746'
                else:
                    case[1]['refs'][0]['scale'] = .98
                evaluate(case)


if __name__ == '__main__':
    unittest.main()
