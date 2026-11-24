"""Fixed-profile archive selection for the VR world-motion overlay."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src/main/components/vr-body"))
from vr_dispatch import ADDON, LEGACY_ALIAS, SEXES, fixed_profile_xml, resource_paths
from core_archive import anatomy_visibility, read_core_archive, require_reviewed_body, static_routes
from core_package_input import core_version
from world_motion import alias_member


class CoreArchiveAdmissionTests(unittest.TestCase):
    def test_core_version_comes_from_the_serialized_installer(self):
        editions = ('0.10.0', '0.11.0')
        for version in editions:
            with self.subTest(version=version):
                info = f'<fomod><Version>{version}</Version></fomod>'.encode()
                self.assertEqual(core_version({'fomod/info.xml': info}), version)
        with self.assertRaisesRegex(ValueError, 'one version'):
            core_version({'fomod/info.xml': b'<fomod><Version>0.10</Version><Version>0.11</Version></fomod>'})

    def test_build_receipt_must_bind_archive_bytes_inventory_and_choices(self):
        raw = b'current core archive'
        members = {'model.nif': b'geometry'}
        plans = [{'physics': 'none', 'files': [{'path': 'model.nif', 'source': 'model.nif'}]}]
        digest = lambda payload: sha256(payload).hexdigest()
        pack = SimpleNamespace(sha=digest, read_zip=lambda _: members, selection_audit=lambda _: plans)
        commit = 'a' * 40
        valid = {'schemaVersion': 1, 'sourceCommit': commit, 'sourceCheckoutHead': commit,
                 'sourceWorktreeHasTrackedChanges': False, 'sha256': digest(raw), 'bytes': len(raw),
                 'payloads': {'model.nif': {'bytes': len(members['model.nif']), 'sha256': digest(members['model.nif'])}},
                 'selections': plans}
        with TemporaryDirectory() as temp:
            archive = Path(temp) / 'core.zip'
            archive.write_bytes(raw)
            receipt = Path(temp) / 'build-receipt.json'
            receipt.write_text(json.dumps(valid))
            self.assertEqual(read_core_archive(pack, archive, receipt_path=receipt)[:2], (members, plans))
            self.assertEqual(read_core_archive(pack, archive, known_digest=digest(raw))[:2], (members, plans))
            with self.assertRaisesRegex(ValueError, 'reviewed core archive'):
                read_core_archive(pack, archive, known_digest='0' * 64)
            for mutation in ({'sha256': '0' * 64}, {'sourceWorktreeHasTrackedChanges': True},
                             {'payloads': {}}, {'selections': []}):
                with self.subTest(mutation=mutation):
                    receipt.write_text(json.dumps(valid | mutation))
                    with self.assertRaisesRegex(ValueError, 'receipt'):
                        read_core_archive(pack, archive, receipt_path=receipt)

    def test_body_routes_must_be_shared_by_every_physics_off_choice(self):
        route = {'path': 'body.nif', 'source': 'static/body.nif'}
        plans = [{'physics': 'none', 'files': [route]}, {'files': [route]},
                 {'physics': 'fsmp', 'files': [route | {'source': 'fsmp/body.nif'}]}]
        self.assertEqual(static_routes(plans, {'body.nif'}), {'body.nif': 'static/body.nif'})
        plans[1]['files'] = [route | {'source': 'another/body.nif'}]
        with self.assertRaisesRegex(ValueError, 'must share'):
            static_routes(plans, {'body.nif'})
        with self.assertRaisesRegex(ValueError, 'must share'):
            static_routes(plans[-1:], {'body.nif'})

    def test_a_new_receipt_does_not_admit_different_reviewed_body_bytes(self):
        pack = SimpleNamespace(MESH='meshes', sha=lambda payload: sha256(payload).hexdigest())
        original = b'unchanged body data'
        paths = {'static/body.nif': original}
        plans = [{'physics': 'none', 'files': [{'path': 'meshes/body.nif', 'source': 'static/body.nif'}]}]
        profile = {'inputSha256': {'body.nif': pack.sha(original)}}
        require_reviewed_body(pack, paths, plans, profile)
        with self.assertRaisesRegex(ValueError, 'differ from the reviewed VR resource profile'):
            require_reviewed_body(pack, {'static/body.nif': b'another body'}, plans, profile)

    def test_both_installed_male_endpoints_must_match_one_reviewed_visibility(self):
        digest = lambda data: sha256(data).hexdigest()
        pack = SimpleNamespace(MESH='meshes', sha=digest)
        visible = b'reviewed visible male'
        hidden = b'reviewed hidden male'
        original = {'malebodywerewolf_0.nif': visible, 'malebodywerewolf_1.nif': visible,
                    'malebodywerewolf.tri': b'male TRI', 'femalebodywerewolf_0.nif': b'female NIF',
                    'femalebodywerewolf_1.nif': b'female NIF', 'femalebodywerewolf.tri': b'female TRI'}
        male_names = ('malebodywerewolf_0.nif', 'malebodywerewolf_1.nif')
        endpoints = dict.fromkeys(male_names, hidden)
        plans = [{'physics': 'none', 'files': [{'path': 'meshes/' + name, 'source': name} for name in original]}]
        profile = {'inputSha256': {name: digest(data) for name, data in original.items()}}
        self.assertEqual(require_reviewed_body(pack, original, plans, profile), (profile['inputSha256'], False))
        with patch.object(anatomy_visibility, 'reviewed_visible_anatomy', return_value=visible) as restore:
            files = original | endpoints
            digests, hidden_selected = require_reviewed_body(pack, files, plans, profile)
            self.assertTrue(hidden_selected)
            self.assertEqual(digests, {name: digest(data) for name, data in files.items()})
            self.assertEqual(restore.call_count, 2)
            restore.assert_called_with(hidden, digest(visible))
        for altered in ({male_names[0]: hidden}, endpoints | {'malebodywerewolf.tri': b'different'},
                        endpoints | {'femalebodywerewolf_0.nif': b'different'}):
            with self.subTest(paths=list(altered)), self.assertRaisesRegex(ValueError, 'body and TRI bytes differ'):
                require_reviewed_body(pack, original | altered, plans, profile)
        with patch.object(anatomy_visibility, 'reviewed_visible_anatomy', side_effect=ValueError('flag proof failed')):
            with self.assertRaisesRegex(ValueError, 'flag proof failed'):
                require_reviewed_body(pack, original | endpoints, plans, profile)


class AliasMemberTests(unittest.TestCase):
    def setUp(self):
        self.sources = {sex: f"profiles/{sex}/{Path(LEGACY_ALIAS).name}" for sex in SEXES}
        carriers = {sex: resource_paths(sex, 1) for sex in SEXES}
        common = {path: f"shared/{path}" for path in (*carriers.values(), ADDON)}
        self.files = {common[ADDON]: b"unrelated common ESP"}
        for sex, source in self.sources.items():
            self.files[source] = self.files[common[carriers[sex]]] = sex.encode("ascii")
        metadata = fixed_profile_xml(common, self.sources)
        self.config = ET.fromstring(metadata["fomod/ModuleConfig.xml"])
        self.group = self.config.find("./installSteps/installStep/optionalFileGroups/group")
        self.male_option = self.group.find("./plugins/plugin[@name='Male player profile']")
        self.male_files = self.male_option.find("files")

    def test_follows_each_sexs_installer_selection(self):
        for sex, source in self.sources.items():
            with self.subTest(sex=sex):
                self.assertEqual(alias_member(self.config, self.files, sex), source)

    def test_rejects_nonexclusive_group(self):
        self.group.set("type", "SelectAny")
        with self.assertRaises(ValueError):
            alias_member(self.config, self.files, "male")

    def test_rejects_duplicate_sex_selection(self):
        plugins = self.group.find("plugins")
        plugins.append(deepcopy(plugins.find("plugin[@name='Male player profile']")))
        with self.assertRaises(ValueError):
            alias_member(self.config, self.files, "male")

    def test_rejects_wrong_alias(self):
        self.male_files.find("file").set("destination", "Meshes/ActorWrongRoute.nif")
        with self.assertRaises(ValueError):
            alias_member(self.config, self.files, "male")

    def test_rejects_missing_selected_file_list(self):
        self.male_option.remove(self.male_files)
        with self.assertRaises(ValueError):
            alias_member(self.config, self.files, "male")

    def test_rejects_additional_selected_file(self):
        extra = "profiles/male/extra.nif"
        self.files[extra] = b"extra"
        ET.SubElement(self.male_files, "file", source=extra, destination="Meshes/OtherBody.nif", priority="0")
        with self.assertRaises(ValueError):
            alias_member(self.config, self.files, "male")

    def test_rejects_shared_or_conditional_alias_collision(self):
        for name in ("requiredInstallFiles", "conditionalFileInstalls"):
            with self.subTest(name=name):
                config = deepcopy(self.config)
                parent = config.find(name)
                if parent is None:
                    parent = ET.SubElement(config, name)
                ET.SubElement(parent, "file", source=self.sources["male"], destination=LEGACY_ALIAS.upper())
                with self.assertRaisesRegex(ValueError, "must be selected only"):
                    alias_member(config, self.files, "male")

    def test_rejects_swapped_sex_source(self):
        self.male_files.find("file").set("source", self.sources["female"])
        with self.assertRaises(ValueError):
            alias_member(self.config, self.files, "male")

    def test_rejects_missing_archive_member(self):
        del self.files[self.sources["male"]]
        with self.assertRaises(ValueError):
            alias_member(self.config, self.files, "male")

    def test_rejects_alias_bytes_from_a_different_carrier(self):
        self.files[self.sources["male"]] = self.files[self.sources["female"]]
        with self.assertRaises(ValueError):
            alias_member(self.config, self.files, "male")


if __name__ == "__main__":
    unittest.main()
