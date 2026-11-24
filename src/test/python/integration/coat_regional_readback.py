"""Check the four-pair scene's material readbacks without contacting Skyrim."""

import math
from pathlib import Path
import xml.etree.ElementTree as ET

if __package__:
    from .coat_turnover_readback import positive_token, read_audit, require, stock_path
else:
    from coat_turnover_readback import positive_token, read_audit, require, stock_path


BLENDED_FUR = {'chestblend', 'furfaceblend', 'scalpfurblend'}
CONTROL_SURFACES = {'body', 'head', 'fur_back'} | BLENDED_FUR
LUMA = (.2126, .7152, .0722)
SAME_SKIN = ((0, 2), (1, 3))
SAME_HAIR = ((0, 1), (2, 3))


def expected_paths(appearance_dir, fixed_coat):
    """Resolve a canonical coat's managed surface paths from CLAW's catalog."""
    directory = Path(appearance_dir)
    mapping = ET.parse(directory / 'CoatMapping.xml').getroot()
    library = ET.parse(directory / 'CoatLibrary.xml').getroot()
    materials = [row.get('material', '') for row in mapping.findall('Range') if row.get('id') == fixed_coat]
    require(len(materials) == 1, f'Expected one canonical coat range for {fixed_coat!r}')
    library_id, _, pattern_id = materials[0].partition('/')
    require(pattern_id and library_id == library.get('id'), f'No coat library for {fixed_coat!r}')
    patterns = [node for node in library.findall('Patterns/Pattern') if node.get('id') == pattern_id]
    require(len(patterns) == 1, f'Expected one library pattern for {fixed_coat!r}')
    textures = {}
    for row in patterns[0].findall('Texture'):
        name, path = row.get('name', ''), row.get('path', '')
        require(name and path and name not in textures, 'Invalid or duplicate catalog texture')
        textures[name] = path
    paths = {}
    for row in library.findall('Surfaces/Surface'):
        name, texture = row.get('name', '').casefold(), row.get('texture')
        require(name and name not in paths and texture in textures, 'Invalid or duplicate catalog surface')
        paths[name] = textures[texture]
    require(len(paths) == 12 and CONTROL_SURFACES <= paths.keys(),
            'Expected the comparison scene\'s twelve managed surfaces')
    return paths


def luma(rgb):
    return sum(value * weight for value, weight in zip(rgb, LUMA, strict=True))


def expected_tint(rgb8, *, hair):
    rgb = [value / 255 for value in rgb8]
    bright = luma(rgb)
    saturation = .5 + .5 * (max(rgb) - min(rgb)) if hair else .55
    toned = [.5 + .55 * (bright - .5) + saturation * (value - bright) for value in rgb]
    return [math.floor(max(0., min(1., value)) * 255 + .5) / 255 for value in toned]


def rgb_within(value, upper):
    return (type(value) is list and len(value) == 3 and
            all(type(channel) in (int, float) and 0 <= channel <= upper for channel in value))


def verify_human(audit, pair):
    """Verify both palette inputs on the still-human reference and wolf source."""
    require(isinstance(audit, dict) and type(audit.get('schema')) is int and audit['schema'] == 1
            and audit.get('stringEncoding') == 'bytes-u00xx'
            and type(audit.get('ageMs')) in (int, float) and 0 <= audit['ageMs'] <= 2000
            and all(positive_token(audit.get(key)) for key in ('sample', 'modelGeneration')),
            'Fresh human coat audit required')
    surfaces = audit.get('surfaces')
    require(isinstance(surfaces, list) and all(isinstance(row, dict) for row in surfaces),
            'Human surface inventory unavailable')
    observed = {}
    for name, feature, upper, field in (('hair', 6, 2, 'hair'), ('skin', 5, 1, 'skinRecordRGB8')):
        rows = [row.get('tint') for row in surfaces if row.get('feature') == feature]
        require(rows and all(rgb_within(rgb, upper) for rgb in rows),
                f'{pair["name"]}: actual human {name} tint unavailable')
        palettes = {tuple(math.floor(channel * 255 / upper + .5) for channel in rgb) for rgb in rows}
        require(palettes == {tuple(pair[field])}, f'{pair["name"]}: actual human {name} tint differs')
        observed[f'{name}RGB8'] = list(next(iter(palettes)))
    return observed


def inspect_regions(audit, pair, paths):
    """Read actual bound tint/alpha after verifying the fixed donor's DDS on every surface."""
    _, surfaces, _ = read_audit({'audit': audit}, paths)
    measured = {}
    for name, surface in surfaces.items():
        context = f'{pair["name"]} {name}'
        require(surface.get('healthyLease') is True and surface.get('ownDiffuse') is True,
                f'{context}: actual coat lease or resource is unhealthy')
        for field in ('diffusePath', 'diffuseResource'):
            value = surface.get(field)
            require(isinstance(value, str) and stock_path(value) == stock_path(paths[name]),
                    f'{context}: {field} differs from the fixed donor')
        hair = name != 'body'
        want = expected_tint(pair['hair'] if hair else pair['skinRecordRGB8'], hair=hair)
        tint = surface.get('tint')
        require(surface.get('feature') == 5 and rgb_within(tint, 1)
                and all(abs(value - expected) <= 1.1 / 255 for value, expected in zip(tint, want, strict=True)),
                f'{context}: regional tint differs, measured {tint!r}, expected {want!r}')
        alpha = surface.get('materialAlpha')
        require(type(alpha) in (int, float) and 0 <= alpha <= 1,
                f'{context}: final material alpha unavailable')
        measured[name] = {'tint': tint, 'expectedFromRecord': want, 'materialAlpha': alpha,
                          'source': 'hair' if hair else 'skin', 'diffuseResource': surface['diffuseResource']}
    return measured


def inspect_discrete_regions(audit, pair, skin_paths, hair_paths):
    """Check the original-colour DDS chosen for each actual wolf surface."""
    paths = dict(hair_paths, body=skin_paths['body'])
    _, surfaces, _ = read_audit({'audit': audit}, paths)
    for name, surface in surfaces.items():
        require(surface.get('feature') == 0 and surface.get('tint') is None
                and surface.get('healthyLease') is True and surface.get('ownDiffuse') is True
                and isinstance(surface.get('diffuseResource'), str)
                and stock_path(surface['diffuseResource']) == stock_path(paths[name]),
                f'{pair["name"]} {name}: expected the assigned skin or hair DDS on the original-colour shader')
    return {name: surface['diffuseResource'] for name, surface in surfaces.items()}


def compare_pairs(groups, pairs):
    """Confirm skin and hair contrasts independently on every measured surface."""
    require(len(groups) == len(pairs) == 4, 'Expected four complete material comparison groups')
    names = groups[0].keys()
    require(CONTROL_SURFACES <= names and all(row.keys() == names for row in groups),
            'Managed surface sets differ across the four groups')
    factors = [.86 + .14 * luma([channel / 255 for channel in pair['hair']]) for pair in pairs]
    alpha_rows, changed = {}, set()
    for name in names:
        tints = [group[name]['tint'] for group in groups]
        same, different = (SAME_SKIN, SAME_HAIR) if name == 'body' else (SAME_HAIR, SAME_SKIN)
        require(all(math.dist(tints[a], tints[b]) <= .01 for a, b in same)
                and all(math.dist(tints[a], tints[b]) >= .06 for a, b in different),
                f'{name}: tint contrast failed across the controlled pairs')
        alpha = [group[name]['materialAlpha'] for group in groups]
        require(abs(alpha[0] - alpha[1]) <= .002 and abs(alpha[2] - alpha[3]) <= .002,
                f'{name}: alpha varies across the skin-only comparisons')
        alpha_rows[name] = alpha
        if abs(alpha[0] - alpha[2]) > .002 or abs(alpha[1] - alpha[3]) > .002:
            changed.add(name)
    require(changed == BLENDED_FUR,
            f'Expected alpha changes only on {sorted(BLENDED_FUR)}, observed {sorted(changed)}')
    for name in changed:
        estimates = [alpha / factor for alpha, factor in zip(alpha_rows[name], factors, strict=True)]
        require(max(estimates) - min(estimates) <= .002, f'{name}: fitted donor alpha differs across controls')
    return {'bodyTints': [group['body']['tint'] for group in groups],
            'furBackTints': [group['fur_back']['tint'] for group in groups],
            'alphaBySurface': alpha_rows, 'alphaRowsThatChanged': sorted(changed), 'alphaInputFactors': factors,
            'alphaMethod': 'Observed material alpha checked against the expected blended surface set.'}
