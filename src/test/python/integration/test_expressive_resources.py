"""Contract tests for the authored opposed fields and exact quantization."""
import json
import os
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[4]/'src/main/python/build-tools'))
import expressive_body as body


class ExpressiveResourceIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.recipe = json.loads((body.ROOT/'src/main/resources/recipes/expressive-body-v1.json').read_text())
        cls.parameters = cls.recipe['parameters']

    def test_frozen_six_resource_hash_inventory(self):
        import hashlib
        base = Path(os.environ.get('CLAW_INTEGRATION_BODY_ROOT', body.ROOT/'target/bodies/fresh'))/'repaired/Meshes/Actors/WerewolfBeast/Character Assets'
        self.assertEqual(len(self.recipe['baselineSha256']), 6)
        for name, digest in self.recipe['baselineSha256'].items():
            self.assertEqual(hashlib.sha256((base/name).read_bytes()).hexdigest(), digest)


if __name__ == "__main__":
    unittest.main()
