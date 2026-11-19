"""Check a completed trace against the corresponding final witness snapshot."""
if __package__:
    from .validate_snapshot import integer, number, parse, pose, read_json
else:
    from validate_snapshot import integer, number, parse, pose, read_json


PAGE_FIELDS = {'schema', 'status', 'nonce', 'pid', 'qpcFrequency', 'loadEpoch',
               'tokens', 'firstPair', 'total', 'offset', 'samples'}
PAIR_FIELDS = {'pair', 'preQpc', 'postQpc', 'hostTimeStep', 'pre', 'post'}
PAGE_SIZE = 16


def parse_trace(pages, final_snapshot, tokens):
    """Return contiguous witnessed pairs. These arrays do not establish causality."""
    snapshot = parse(final_snapshot)
    if snapshot['schema'] != 'claw-fsmp-step-witness/4' or snapshot['status'] != 'ready':
        raise ValueError('Expected a completed v4 snapshot')
    window = snapshot['sample']['objectWindow']
    if window['status'] != 'complete' or window['pairedSteps'] != 900:
        raise ValueError('Expected the complete original provider window')
    objects = window['objects']
    tokens = list(tokens)
    if len(tokens) != 4 or not all(integer(t, 1) and t <= len(objects) for t in tokens) or len(set(tokens)) != 4:
        raise ValueError('Expected four distinct catalog tokens')
    selected = [objects[t-1] for t in tokens]
    if not all(row['initialPre']['rigidBody'] is True for row in selected):
        raise ValueError('Trace token is not a rigid body')
    identity = {'pid': snapshot['pid'], 'qpcFrequency': snapshot['qpcFrequency'],
                'nonce': window['nonce'], 'loadEpoch': window['loadEpoch']}
    rows = []
    begin, total, end_qpc = None, None, window['firstPreQpc']-1
    for raw in pages:
        page = read_json(raw)
        if set(page) != PAGE_FIELDS or page['schema'] != 'claw-fsmp-paired-trace/1' or page['status'] != 'ready':
            raise ValueError('Trace page refused or malformed')
        if any(not integer(page[k], 1) or page[k] != val for k, val in identity.items()):
            raise ValueError('Trace owner, clock or window differs')
        if type(page['tokens']) is not list or page['tokens'] != tokens or any(type(t) is not int for t in page['tokens']):
            raise ValueError('Trace token order differs')
        if not integer(page['firstPair'], 1) or not integer(page['total'], 1) or page['firstPair']+page['total'] != 901:
            raise ValueError('Trace length does not end at pair 900')
        if begin is None:
            begin, total = page['firstPair'], page['total']
        if page['firstPair'] != begin or page['total'] != total or not integer(page['offset']) or page['offset'] != len(rows):
            raise ValueError('Trace pages are not contiguous')
        expected_count = min(PAGE_SIZE, total-len(rows))
        if expected_count <= 0 or type(page['samples']) is not list or len(page['samples']) != expected_count:
            raise ValueError('Invalid trace page length')
        for pair in page['samples']:
            if type(pair) is not dict or set(pair) != PAIR_FIELDS or not integer(pair['pair'], 1) or pair['pair'] != begin+len(rows):
                raise ValueError('Trace pair is missing or out of order')
            before, after = pair['preQpc'], pair['postQpc']
            if not integer(before, 1) or not integer(after, 1) or not end_qpc < before < after:
                raise ValueError('Trace callback clocks overlap or regress')
            if not number(pair['hostTimeStep']) or pair['hostTimeStep'] <= 0:
                raise ValueError('Expected a positive finite host timestep')
            for moment in ('pre', 'post'):
                if type(pair[moment]) is not list or len(pair[moment]) != 4:
                    raise ValueError('Expected one pose per selected token')
                for entry, body in zip(pair[moment], selected):
                    pose(entry, 4)
                    anchor = body['initialPre']
                    if entry['rigidBody'] is not True or (entry['flags'], entry['inverseMass']) != (anchor['flags'], anchor['inverseMass']):
                        raise ValueError('Trace object metadata differs from its catalog')
            end_qpc = after
            rows.append(pair)
    if not rows or len(rows) != total:
        raise ValueError('Incomplete trace')
    last = rows[-1]
    if ((last['preQpc'], last['postQpc'], last['hostTimeStep']) != (window['lastPreQpc'], window['lastPostQpc'], window['lastTimeStep'])
            or last['pre'] != [r['lastPre'] for r in selected] or last['post'] != [r['lastPost'] for r in selected]):
        raise ValueError('Trace end does not match the final snapshot')
    return rows
