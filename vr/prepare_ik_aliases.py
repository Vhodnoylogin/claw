"""Build an external, names-only XP32 werewolf alias compatibility candidate."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from body_resource import dependencies, safe_output, sha256
from rig_lookup import alias_plan, arm_report, body_influences, finger_report, graph, patch_alias_strings, renamed_graph


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skeleton', required=True, type=Path)
    parser.add_argument('--skeleton-sha256', required=True)
    parser.add_argument('--body', required=True, action='append', type=Path)
    parser.add_argument('--reference', type=Path)
    parser.add_argument('--pynifly')
    parser.add_argument('--morphbench')
    parser.add_argument('--out-dir', required=True, type=Path)
    args = parser.parse_args()
    sources = [args.skeleton, *args.body] + ([args.reference] if args.reference else [])
    pins = {str(p.resolve(strict=True)): sha256(p) for p in sources}
    if sha256(args.skeleton) != args.skeleton_sha256:
        raise ValueError('Skeleton differs from explicit reviewed input pin')
    output = safe_output(args.out_dir, sources)
    api, NifPatch, _, dep_pins = dependencies(args.pynifly, args.morphbench)
    skeleton = api.NifFile(str(args.skeleton))
    bodies = [api.NifFile(str(p)) for p in args.body]
    parents, weights = graph(skeleton), body_influences(bodies)
    plan = alias_plan(parents, weights)
    planned_graph = renamed_graph(parents, plan)
    before, planned = arm_report(parents, weights), arm_report(planned_graph, weights)
    if any(row['selected'] != row['fallback'] or not row['selectedSubtreeInfluences'] for row in planned):
        raise ValueError('Planned arm still misses a weighted beast branch')
    if any(row['selected'] != row['fallback'] or not row['selectedSubtreeInfluences']
           for row in finger_report(planned_graph, weights)):
        raise ValueError('Planned fingers still miss a weighted beast branch')
    patch = NifPatch(args.skeleton)
    raw, ledger = patch_alias_strings(bytes(patch.raw), patch, skeleton.nodes, plan)
    output.mkdir(parents=True)
    path = output / 'skeleton.nif'
    path.write_bytes(raw)
    readback = api.NifFile(str(path))
    if graph(readback) != planned_graph or len(readback.nodes) != len(skeleton.nodes):
        raise ValueError('Serialized names or ancestry differ from the plan')
    for name, node in skeleton.nodes.items():
        new_name = next((row['after'] for row in plan if row['before'] == name), name)
        actual = readback.nodes[new_name]
        if node.id != actual.id or tuple(node.transform.translation) != tuple(actual.transform.translation):
            raise ValueError('Node id/transform changed')
    if {p: sha256(p) for p in pins} != pins:
        raise ValueError('Inputs changed while building')
    if {p: sha256(p) for p in dep_pins} != dep_pins:
        raise ValueError('Dependencies changed while building')
    report = {'schemaVersion': 1, 'status': 'offline-names-only-candidate',
              'inputs': pins, 'dependencies': dep_pins, 'source': str(Path(__file__).resolve()),
              'sourceSha256': sha256(__file__), 'helperSha256': sha256(Path(__file__).with_name('rig_lookup.py')),
              'output': {'path': str(path), 'sha256': sha256(path)},
              'nodeCount': len(readback.nodes), 'aliasEdits': ledger,
              'bodyInfluencesAtRenamedAliases': 0, 'allBlockAndFooterBytesExact': True,
              'changedBytes': sum(a != b for a, b in zip(bytes(patch.raw), raw)),
              'armBefore': before, 'armAfter': arm_report(graph(readback), weights),
              'fingersBefore': finger_report(parents, weights),
              'fingersAfter': finger_report(graph(readback), weights),
              'attachmentNodes': {name: parents[name] for name in parents if name in
                                  ('SHIELD', 'WEAPON', 'NPC L MagicNode [LMag]', 'NPC R MagicNode [RMag]')},
              'runtimeIK': 'not tested', 'engineModelDispatch': 'not qualified',
              'animationAndOtherSkeletonConsumers': 'not qualified; alias name consumers may be affected',
              'installableMod': False}
    if args.reference:
        ref = api.NifFile(str(args.reference))
        report['referenceArm'] = arm_report(graph(ref), weights)
        report['referenceFingers'] = finger_report(graph(ref), weights)
    (output / 'ik-alias-report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'report': str(output / 'ik-alias-report.json'), 'aliases': len(ledger),
                      'status': report['status']}))


if __name__ == '__main__':
    main()
