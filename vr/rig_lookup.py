"""Offline audit of human-first/beast-fallback node lookup on an XP32 graph.

Names describe the inspected lookup contract, not a copied VRIK implementation.
The optional edit changes only unweighted leaf alias names in the NIF header.
It cannot qualify engine model dispatch, animation compatibility or live IK.
"""
from __future__ import annotations

from collections import Counter
import struct


LEFT_ARM = (
    ('NPC L Clavicle [LClv]', 'NPC L Clavicle [RClv]'),
    ('NPC L UpperArm [LUar]', 'NPC L UpperArm [RUar]'),
    ('NPC L Forearm [LLar]', 'NPC L Forearm [RLar]'),
    ('NPC L Hand [LHnd]', 'NPC L Hand [RHnd]'),
)
LEFT_FINGERS = tuple((f'NPC L Finger{finger}{joint} [LF{finger}{joint}]',
                      f'NPC L Finger{finger}{joint} [RF{finger}{joint}]')
                     for finger in range(5) for joint in range(3))
LOOKUP_PAIRS = LEFT_ARM + LEFT_FINGERS


def validate_graph(parents):
    if not parents:
        raise ValueError('Empty skeleton graph')
    for name in parents:
        current, seen = name, set()
        while current is not None:
            if current in seen or current not in parents:
                raise ValueError('Cyclic or incomplete skeleton ancestry')
            seen.add(current)
            current = parents[current]


def descendants(parents, root):
    if root not in parents:
        return set()
    result = {root}
    for name in parents:
        current, seen = name, set()
        while current is not None:
            if current in seen or current not in parents:
                raise ValueError('Cyclic or incomplete skeleton ancestry')
            seen.add(current)
            if current == root:
                result.add(name)
                break
            current = parents[current]
    return result


def choose(parents, root, preferred, fallback=None):
    available = descendants(parents, root)
    return preferred if preferred in available else fallback if fallback in available else None


def trace_left_arm(parents):
    root = 'NPC Spine2 [Spn2]'
    rows = []
    for preferred, fallback in LEFT_ARM:
        selected = choose(parents, root, preferred, fallback) if root else None
        rows.append({'searchRoot': root, 'preferred': preferred, 'fallback': fallback,
                     'selected': selected})
        root = selected
    return rows


def alias_plan(parents, weights):
    """Rename only proven unused aliases directly parented to the weighted bone.

    Refuse a weighted alias instead of moving influences or modifying its tree.
    All positive body influences must have a node in this exact input skeleton.
    """
    if any(name not in parents for name, count in weights.items() if count):
        raise ValueError('Body uses a node absent from the declared skeleton')
    validate_graph(parents)
    plan = []
    for preferred, fallback in LOOKUP_PAIRS:
        if preferred not in parents or fallback not in parents:
            continue
        branch = descendants(parents, preferred)
        if parents[preferred] != fallback:
            raise ValueError('Preferred alias is not a direct child of its beast fallback: ' + preferred)
        if branch != {preferred} or any(weights.get(name, 0) for name in branch):
            raise ValueError('Cannot rename a weighted or non-leaf alias: ' + preferred)
        if not any(weights.get(name, 0) for name in descendants(parents, fallback)):
            raise ValueError('Beast fallback has no observed body influence: ' + fallback)
        # Same byte length, distinct name; preserve all block and string offsets.
        new = preferred.replace('[L', '[X')
        if new == preferred or new in parents or len(new.encode('ascii')) != len(preferred.encode('ascii')):
            raise ValueError('Alias rename is ambiguous')
        plan.append({'before': preferred, 'after': new, 'fallback': fallback})
    if not plan:
        raise ValueError('No qualifying empty aliases in the declared skeleton')
    return plan


def renamed_graph(parents, plan):
    names = {p['before']: p['after'] for p in plan}
    return {names.get(n, n): names.get(p, p) for n, p in parents.items()}


def patch_alias_strings(raw, patch, nodes, plan):
    """Only fixed-length unique header strings change; blocks/footer stay exact.

    Morphbench supplies the block table; native PyNifly supplies each node id/name.
    Every located string is checked against the native node's name table index.
    No replacement string, block, node, transform or reference is added/deleted.
    """
    if not patch.consistent() or not patch.offsets:
        raise ValueError('Invalid NIF block table')
    header_end = min(patch.offsets.values())
    result, ledger = bytearray(raw), []
    for row in plan:
        old, new = row['before'].encode('ascii'), row['after'].encode('ascii')
        if len(old) != len(new):
            raise ValueError('Alias names must have equal byte lengths')
        needle = struct.pack('<I', len(old)) + old
        starts = [i for i in range(header_end) if raw.startswith(needle, i)]
        if len(starts) != 1:
            raise ValueError('Alias string is not unique in the NIF header')
        node = nodes[row['before']]
        if patch.types[node.id] != 'NiNode':
            raise ValueError('Alias is not an ordinary NiNode')
        # The native API independently resolves the stored string index.
        name_index = struct.unpack_from('<I', raw, patch.offsets[node.id])[0]
        if node.name != row['before'] or node.file.get_string(name_index) != row['before']:
            raise ValueError('Native alias name differs from edit plan')
        off = starts[0] + 4
        if off + len(old) > header_end:
            raise ValueError('Alias string crosses into block data')
        result[off:off + len(old)] = new
        ledger.append(dict(row, offset=off, size=len(old), nodeId=node.id,
                           nameIndex=name_index))
    expected = bytearray(raw)
    for row in ledger:
        expected[row['offset']:row['offset'] + row['size']] = row['after'].encode('ascii')
    if expected != result or raw[header_end:] != result[header_end:]:
        raise ValueError('Unplanned NIF change')
    if len(raw) != len(result):
        raise ValueError('NIF length changed')
    return bytes(result), ledger


def body_influences(bodies):
    counts = Counter()
    for body in bodies:
        for shape in body.shapes:
            for bone, rows in shape.bone_weights.items():
                counts[bone] += sum(weight > 0 for _, weight in rows)
    return dict(counts)


def graph(nif):
    return {name: node.parent.name if node.parent else None for name, node in nif.nodes.items()}


def arm_report(parents, weights):
    rows = trace_left_arm(parents)
    for row in rows:
        row['selectedSubtreeInfluences'] = sum(weights.get(n, 0) for n in
                                               descendants(parents, row['selected']))
    return rows


def finger_report(parents, weights):
    """Preferred name anywhere on root precedes the beast fallback in this contract."""
    rows = []
    for preferred, fallback in LEFT_FINGERS:
        selected = preferred if preferred in parents else fallback if fallback in parents else None
        rows.append({'preferred': preferred, 'fallback': fallback, 'selected': selected,
                     'selectedSubtreeInfluences': sum(weights.get(n, 0) for n in descendants(parents, selected))})
    return rows
