"""Regressions for incomplete installs and stale/tampered build provenance."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import locate


def load_script(name):
    spec = importlib.util.spec_from_file_location('claw_test_' + name, ROOT / 'scripts' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    with patch.object(locate, 'project_paths', return_value=SimpleNamespace(
            mods=Path('unused'), pynifly=Path('unused'), blender='', seven_zip=Path('unused'))):
        spec.loader.exec_module(module)
    return module


class BuildSafety(unittest.TestCase):
    def test_partial_install_is_refused_before_writing(self):
        build = load_script('build-all')
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'never-created'
            with self.assertRaises(SystemExit):
                build.main(['--only', 'body', '--install', '--out', str(out)])
            self.assertFalse(out.exists())

    def test_missing_output_cannot_change_installed_mod(self):
        build = load_script('build-all')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'recipes').mkdir()
            spec = dict(mod='CLAW', version='0.1.0.0', sources={}, steps=[],
                        mods={'base':dict(name='CLAW test',under='meshes',files={'body.nif':'body.nif'})})
            (root / 'recipes/build.json').write_text(json.dumps(spec))
            installed = root / 'mods/CLAW test'; installed.mkdir(parents=True)
            (installed / 'sentinel').write_bytes(b'preserve me')
            with (patch.object(build,'ROOT',root), patch.object(build,'P',SimpleNamespace(mods=root/'mods')),
                  patch.object(build.Pipeline,'manifest',return_value={}), contextlib.redirect_stdout(io.StringIO())):
                with self.assertRaises(SystemExit):
                    build.main(['--install','--out',str(root/'out')])
            self.assertEqual(list(installed.iterdir()),[installed/'sentinel'])
            self.assertEqual((installed/'sentinel').read_bytes(),b'preserve me')

    def test_reverification_preserves_original_commit_and_time(self):
        build = load_script('build-all')
        previous = dict(version='0.1',artifacts=[{'sha256':'abc'}],sources=[],
                        recipes={'commit':'old','dirty':False},builtAt='yesterday')
        current = dict(previous,recipes={'commit':'new','dirty':False},builtAt='today')
        self.assertEqual(build.preserve_provenance(previous,current)['recipes']['commit'],'old')
        self.assertEqual(current['builtAt'],'yesterday')
        with self.assertRaises(SystemExit):
            build.preserve_provenance(previous,dict(current,artifacts=[{'sha256':'changed'}]))

    def test_release_detects_tampering_and_unlisted_files(self):
        release = load_script('release')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); folder=root/'CLAW test'; folder.mkdir()
            (root/'build.json').write_text(json.dumps({'mods':{'base':dict(name=folder.name,under='meshes',files={'body.tri':'body.tri'})}}))
            (folder/'meta.ini').write_text('[General]\nversion=0.1\n')
            (folder/'meshes').mkdir(); body=folder/'meshes/body.tri'; body.write_bytes(b'original')
            manifest=dict(version='0.1',recipes={'commit':'head','dirty':False},outputs=[{'state':'совпал'}],
                          artifacts=[dict(mod='base',file='meshes/body.tri',sha256=hashlib.sha256(body.read_bytes()).hexdigest())])
            (folder/'claw-build.json').write_text(json.dumps(manifest))
            with patch.object(release,'RECIPES',root):
                self.assertEqual(release.check(folder,'0.1','head'),[])
                body.write_bytes(b'changed')
                self.assertTrue(any('body.tri' in row for row in release.check(folder,'0.1','head')))
                body.write_bytes(b'original'); (folder/'skeleton.nif').write_bytes(b'unexpected')
                self.assertTrue(release.check(folder,'0.1','head'))


if __name__ == '__main__':
    unittest.main()
