"""Resolve the declared palette or choose the stock NPCs for a seeded row."""

from hashlib import sha256
import json


def load_palette(path, seed=None):
    palette = json.loads(path.read_bytes())
    groups = palette.pop('candidateGroups', None)
    if groups is None:
        if seed is not None:
            raise ValueError('An alternate seed requires the unresolved candidate pool')
        return palette

    if palette.get('comparison') != 'random-combos' or len(groups) != 5 or any(not rows for rows in groups.values()):
        raise ValueError('Expected five nonempty hair groups for the seeded fixture')
    seed = palette['selectionSeed'] if seed is None else seed
    if type(seed) is not int or seed < 0:
        raise ValueError('The selection seed must be a nonnegative integer')

    def ranking(label, actor):
        base = actor['base']
        return sha256(f'{seed}:{label}:{base}'.encode('ascii')).digest(), base

    chosen = [min(rows, key=lambda actor: ranking(label, actor)) for label, rows in sorted(groups.items())]
    ordered = sorted(chosen, key=lambda actor: ranking('row', actor))
    if len({row['base'] for row in ordered}) != 5 or len({tuple(row['hair']) for row in ordered}) != 5:
        raise ValueError('The seeded row must use five distinct actors and hair colours')
    if len({tuple(row['skinRecordRGB8']) for row in ordered}) < 3:
        raise ValueError('The seeded row needs at least three skin colours')
    palette['selectionSeed'] = seed
    palette['pairs'] = [dict(actor, humanY=1425. + 140. * index, wolfY=1495. + 140. * index)
                        for index, actor in enumerate(ordered)]
    return palette
