"""Read and validate the original motion-only FSMP graph shared by CLAW packages."""
import math
import re
import struct
import xml.etree.ElementTree as ET


VECTORS = {'inertia', 'linearLowerLimit', 'linearUpperLimit', 'angularLowerLimit',
           'angularUpperLimit', 'linearStiffness', 'angularStiffness', 'linearDamping',
           'angularDamping', 'linearEquilibrium', 'angularEquilibrium'}
BONE = {'mass', 'inertia', 'linearDamping', 'angularDamping', 'gravity-factor', 'wind-factor'}
JOINT = VECTORS - {'inertia'} | {'frameInA', 'frameInB', 'useLinearReferenceFrameA'}
DECIMAL = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")


def signature(node):
    """Authored identities, parameter tokens and nesting, excluding formatting."""
    return node.tag, tuple(sorted(node.attrib.items())), (node.text or '').strip(), tuple(signature(x) for x in node)


def _finite(value):
    if value is None or not DECIMAL.fullmatch(value.strip()):
        raise ValueError('Finite explicit numeric parameter required')
    try:
        number = struct.unpack("<f", struct.pack("<f", float(value)))[0]
    except OverflowError as error:
        raise ValueError('Finite explicit numeric parameter required') from error
    if not math.isfinite(number):
        raise ValueError('Finite explicit numeric parameter required')
    return number


def _properties(node, allowed):
    seen = set()
    for item in node:
        if item.tag not in allowed or item.tag in seen:
            raise ValueError('Unknown or duplicate motion parameter: '+str(item.tag))
        if (item.tail or '').strip(): raise ValueError('Unexpected motion parameter text')
        seen.add(item.tag)
        if item.tag in ('frameInA', 'frameInB'):
            if item.attrib or (item.text or '').strip():
                raise ValueError('Only original explicit or identity frames admitted')
            if len(item):
                if [x.tag for x in item] != ['basis', 'origin']:
                    raise ValueError('Unknown frame layout')
                for part, keys in zip(item, ({'x','y','z','w'}, {'x','y','z'})):
                    if (set(part.attrib) != keys or len(part) or
                            (part.text or '').strip() or (part.tail or '').strip()):
                        raise ValueError('Unknown frame parameter')
                    for value in part.attrib.values(): _finite(value)
        elif item.tag == 'useLinearReferenceFrameA':
            if item.attrib or len(item) or (item.text or '').strip() not in ('true', 'false'):
                raise ValueError('Explicit reference-frame boolean required')
        elif item.attrib:
            if item.tag not in VECTORS or set(item.attrib) != {'x','y','z'} or len(item) or (item.text or '').strip():
                raise ValueError('Unknown vector parameter')
            for value in item.attrib.values(): _finite(value)
        else:
            if len(item): raise ValueError('Unexpected nested motion parameter')
            if item.tag == 'inertia' or node.tag == 'generic-constraint':
                raise ValueError('Explicit three-axis parameter required')
            _finite(item.text)
    return seen


def inspect_xml(payload, drivers, anchors):
    """Bounded motion-only graph; reject implicit bodies, collisions and globals."""
    if len(drivers) != len(set(drivers)) or len(anchors) != len(set(anchors)) or set(drivers) & set(anchors):
        raise ValueError('Unique disjoint driver and anchor catalogs required')
    if not isinstance(payload, bytes) or len(payload) > 100000:
        raise ValueError('Bounded XML without DTD/entities required')
    try:
        document = payload.decode('utf-8-sig')
    except UnicodeError as error:
        raise ValueError('Motion XML must be UTF-8') from error
    if any(token in document.upper() for token in ('<!DOCTYPE', '<!ENTITY')):
        raise ValueError('Bounded XML without DTD/entities required')
    try:
        root = ET.fromstring(document)
    except ET.ParseError as error:
        raise ValueError('Malformed motion XML') from error
    if root.tag != 'system' or root.attrib or (root.text or '').strip():
        raise ValueError('Only an original local motion system is admitted')
    bones, dynamic, static, incoming, folded = {}, set(), set(), {}, set()
    for item in root:
        if (item.tail or '').strip(): raise ValueError('Unexpected motion text')
        if item.tag == 'bone':
            name = item.get('name')
            if set(item.attrib) != {'name'} or not name or name.casefold() in folded or (item.text or '').strip():
                raise ValueError('Missing or duplicate bone identity')
            folded.add(name.casefold())
            props = _properties(item, BONE)
            if 'mass' not in props: raise ValueError('Missing explicit bone mass')
            mass = _finite(item.findtext('mass'))
            if mass < 0: raise ValueError('Negative bone mass')
            (dynamic if mass > 0 else static).add(name)
            bones[name] = item
        elif item.tag == 'generic-constraint':
            if set(item.attrib) != {'bodyA','bodyB'} or (item.text or '').strip():
                raise ValueError('Only explicit local body constraints admitted')
            a, b = item.get('bodyA'), item.get('bodyB')
            if a not in bones or b not in bones or a == b or b not in dynamic or b in incoming:
                raise ValueError('Duplicate, missing or not-yet-declared constraint driver')
            props = _properties(item, JOINT)
            if len(props & {'frameInA','frameInB'}) != 1 or not VECTORS - {'inertia'} <= props:
                raise ValueError('Complete original constraint parameters required')
            incoming[b] = a
        else:
            raise ValueError('Unknown/global/collision XML record: '+str(item.tag))
    if dynamic != set(drivers) or static != set(anchors) or set(incoming) != dynamic:
        raise ValueError('Missing or unexpected dynamic drivers/anchors')
    for name in dynamic:
        visited = set()
        while name in incoming:
            if name in visited: raise ValueError('Cyclic constraint graph')
            visited.add(name); name = incoming[name]
        if name not in static: raise ValueError('Constraint chain lacks an explicit anchor')
    return root, bones


def core_chains(nodes, breast_nodes=()):
    """The ear and tail chains share the head or tail anchor; P1 is side-specific."""
    left_ear, right_ear, tail = nodes[:2], nodes[2:4], nodes[4:]
    chains = (
        ("NPC Head [Head]", left_ear, "frameInB"),
        ("NPC Head [Head]", right_ear, "frameInB"),
        ("Tails", tail, "frameInB"),
    )
    if breast_nodes:
        chains += tuple((f"NPC {side} PreBreast P1", (node,), "frameInA")
                        for side, node in zip(("L", "R"), breast_nodes, strict=True))
    return chains


def validate_core(payload, chains):
    """Check the packaged core rig while allowing explicit numeric tuning."""
    links = {}
    for anchor, nodes, frame in chains:
        for parent, node in zip((anchor, *nodes[:-1]), nodes, strict=True):
            links[node] = (parent, frame)
    anchors = {anchor for anchor, _, _ in chains}
    try:
        root, bones = inspect_xml(payload, tuple(links), tuple(anchors))
        for name, bone in bones.items():
            fields = BONE if name in links else {"mass"}
            if {item.tag for item in bone} != fields:
                raise ValueError(f"Incomplete core bone parameters for {name}")
        for joint in root.findall("generic-constraint"):
            driver = joint.get("bodyB")
            parent, frame = links[driver]
            pivot = joint.find(frame)
            if joint.get("bodyA") != parent or pivot is None or len(pivot):
                raise ValueError(f"Wrong parent or pivot for {driver}")
            if joint.find("useLinearReferenceFrameA") is not None:
                raise ValueError(f"Unexpected reference-frame override for {driver}")
            for base in ("linear", "angular"):
                lower = joint.find(base + "LowerLimit").attrib
                upper = joint.find(base + "UpperLimit").attrib
                if any(_finite(lower[axis]) > _finite(upper[axis]) for axis in "xyz"):
                    raise ValueError(f"Reversed {base} limits for {driver}")
    except ValueError as error:
        raise ValueError(f"Invalid FSMP motion system: {error}") from error
