import copy
import json
import unittest

from test_validate_snapshot import fixture, v4_window
from validate_trace import parse_trace


TOKENS = [3, 1, 4, 2]


def trace_fixture():
    snapshot = fixture()
    snapshot['schema'] = 'claw-fsmp-step-witness/4'
    window = v4_window()
    for token in (3, 4):
        body = copy.deepcopy(window['objects'][0])
        body['token'] = token
        body['lastPost']['world'][9] += token
        body['maximumPostWorld'][9] += token
        window['objects'].append(body)
    window['objectCount'] = 4
    snapshot['sample']['objectWindow'] = window
    header = {'schema': 'claw-fsmp-paired-trace/1', 'status': 'ready', 'nonce': 71,
              'pid': 17, 'loadEpoch': 2, 'qpcFrequency': 100, 'firstPair': 884,
              'total': 17, 'tokens': TOKENS}
    samples = []
    for pair in range(884, 901):
        tick = 2999 + 3*(pair-900)
        samples.append({'pair': pair, 'preQpc': tick, 'postQpc': tick+1, 'hostTimeStep': .016,
                        'pre': [window['objects'][t-1]['lastPre'] for t in TOKENS],
                        'post': [window['objects'][t-1]['lastPost'] for t in TOKENS]})
    return snapshot, [{**header, 'offset': 0, 'samples': samples[:16]},
                      {**header, 'offset': 16, 'samples': samples[16:]}]


class TraceTests(unittest.TestCase):
    def decode(self, snapshot, pages):
        return parse_trace(map(json.dumps, pages), json.dumps(snapshot), TOKENS)

    def test_two_pages_bind_first_and_last_to_one_ordered_catalog(self):
        snapshot, pages = trace_fixture()
        rows = self.decode(snapshot, pages)
        self.assertEqual([row['pair'] for row in rows], list(range(884, 901)))
        self.assertNotEqual(rows[-1]['post'][0], rows[-1]['post'][1])

    def test_missing_or_repeated_page_is_not_complete(self):
        snapshot, pages = trace_fixture()
        for invalid in (pages[:1], pages + pages[1:], pages[::-1]):
            with self.assertRaises(ValueError):
                self.decode(snapshot, invalid)

    def test_wrong_owner_and_bool_aliases_are_refused(self):
        for key, value in [('pid', 18), ('nonce', 72), ('loadEpoch', 3), ('qpcFrequency', 101),
                           ('offset', False), ('tokens', [3, True, 4, 2])]:
            snapshot, pages = trace_fixture()
            pages[0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.decode(snapshot, pages)

    def test_overlap_bad_pose_and_pointer_fields_are_refused(self):
        for field, value in [('preQpc', 2952), ('hostTimeStep', 0), ('pair', 884), ('key', 900), ('pre', [])]:
            snapshot, pages = trace_fixture()
            pages[0]['samples'][1][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.decode(snapshot, pages)

    def test_end_must_match_final_snapshot_and_captured_metadata(self):
        snapshot, pages = trace_fixture()
        pages[1]['samples'] = copy.deepcopy(pages[1]['samples'])
        pages[1]['samples'][0]['post'][0]['world'][9] = 17
        with self.assertRaisesRegex(ValueError, 'Trace end'):
            self.decode(snapshot, pages)
        pages[1]['samples'][0]['post'][0]['inverseMass'] = 0
        with self.assertRaisesRegex(ValueError, 'metadata'):
            self.decode(snapshot, pages)
