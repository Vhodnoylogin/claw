"""Fixed-profile archive selection for the VR world-motion overlay."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src/main/components/vr-body"))
from vr_dispatch import ADDON, LEGACY_ALIAS, SEXES, fixed_profile_xml, resource_paths
from world_motion import alias_member


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
