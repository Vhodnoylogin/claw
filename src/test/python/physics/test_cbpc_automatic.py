"""Synthetic automatic-first contracts; no actual provider/game observations."""
import copy
import json
import unittest

from test_cbpc_nominal import fixture, nominal, PINS, f32


def automatic_fixture(sex="female", **kwargs):
    # Generate synthetic observations, never rewrite retained real evidence.
    document = fixture(declared_protocol=nominal.automatic_protocol(), **kwargs)
    reference = "0x0D000900" if sex == "female" else "0x0D000901"
    subject = nominal.human_subject(reference, sex, "synthetic-" + sex)
    document["receipts"].pop("start")  # No invented initial Start receipt.
    document.update(reference=reference, sex=sex, humanOrigin=subject, providerControlBeforeInitial=[])
    document["expectedParents"] = {n: p[0] for n, p in nominal.hierarchy.parent_paths(sex).items()}
    # JSON copy makes each equal before/after sample independent, like transport.
    document = json.loads(json.dumps(document))
    names = set(nominal.scene.node_names(sex))
    def walk(value):
        if isinstance(value, dict):
            if value.get("schemaVersion") == 1 and "refs" in value:
                value.update(loadGeneration=2, sampleId=value["sampleId"]+10,
                             producerMonotonicNs=value["producerMonotonicNs"]+1000000000)
                ref = value["refs"][0]
                identity = ref["identity"]
                identity.update(form=reference, sourcePlugin=subject["sourcePlugin"], localFormId=subject["localReference"], loadGeneration=2)
                ref["baseForm"] = subject["baseForm"]
                ref["scale"] = f32(subject["expectedUniformScale"])
                ref["sceneTransform"]["scale"] = ref["scale"]
                ref["actor"].update(baseForm=subject["baseForm"], baseRace=subject["currentRace"], sex=int(sex == "female"))
                ref["actor"]["weight"]["rawNPCWeight"] = subject["rawNPCWeight"]
                value["nodes"] = [n for n in value["nodes"] if n["name"] in names]
                for node in value["nodes"]:
                    node["form"] = reference
                    node["identity"] = copy.deepcopy(identity)
                    world = node["world"]
                    world["translation"] = [f32(p + ref["scale"] * (x - p)) for x, p in zip(world["translation"], ref["position"])]
                    world["scale"] = ref["scale"]
                return
            if "function" in value and value.get("script") == "CBPCPluginScript":
                value["args"][0]["form"] = reference
            if "self" in value:
                value["self"]["form"] = reference
            for x in value.values():
                walk(x)
        elif isinstance(value, list):
            for x in value:
                walk(x)
    walk(document)
    # Remove only non-selected female P1 control packets from a male simulation.
    for action in ("stop", "restart"):
        document["receipts"][action] = [r for r in document["receipts"][action]
                                        if r["request"]["args"][1] in nominal.scene.drivers(sex)]
    phases = {}
    for i, name in enumerate(("initial-human", "enabled-human", "first-wolf", "refresh", "human-return", "second-wolf", "post-load"), 1):
        raw = copy.deepcopy(document["baseline"])
        human = name in ("initial-human", "enabled-human", "human-return")
        raw.update(loadGeneration=2 if name == "post-load" else 1, sampleId=i, producerMonotonicNs=i*1000000)
        ref = raw["refs"][0]
        ref["identity"]["loadGeneration"] = raw["loadGeneration"]
        ref["actor"].update(race=subject["originalRace"] if human else subject["currentRace"],
                            baseRace=subject["originalRace"] if human else subject["currentRace"])
        ref.update(disabled=name == "initial-human", loaded3D=name != "initial-human")
        phases[name] = raw
    labels = ["place-disabled", "enable-human", "restrain-human", "unequip-owned-outfit", "enable-human-ai", "first-wolf", "refresh", "human-return", "second-wolf", "node-update", "owned-save", "owned-load", "head-tracking-off"]
    document["humanLifecycle"] = {"completed": True, "unknown": False, "providerCalls": [],
        "writes": [{"label": x, "status": "returned"} for x in labels], "phaseWitnesses": phases,
        "humanSource": {"appearanceStatus": "human colours captured", "linkStatus": 5},
        "firstTransformBinding": {"allDeclaredNodes": True, "subject": subject, "providerControlsBeforeThisPrefix": [],
            "ledger": {n: {"insertions": 1, "updates": 1} for n in nominal.scene.drivers(sex)}}}
    return document, subject


class AutomaticNominalTests(unittest.TestCase):
    def score(self, d, subject):
        return nominal.score(d, PINS, declared_protocol=nominal.automatic_protocol(), human_origin=subject)

    def test_both_sexes_actual_control_sequence_and_unchanged_gates(self):
        for sex, count in (("female", 11), ("male", 9)):
            d, subject = automatic_fixture(sex)
            result = self.score(d, subject)
            self.assertEqual(result["status"], "sampled-provider-selective-motion")
            self.assertEqual(len(result["channels"]), count)
            self.assertEqual(set(d["receipts"]), {"stop", "restart"})
            self.assertEqual([len(d["windows"][p]) for p in nominal.PHASES], [25, 25, 25])
            self.assertFalse(result["runtimeQualified"])

    def test_initial_start_reload_or_fake_empty_start_receipt_is_rejected(self):
        for change in (lambda d: d["receipts"].update(start=[]),
                       lambda d: d["providerControlBeforeInitial"].append({"function": "StartPhysics"}),
                       lambda d: d["providerControlBeforeInitial"].append({"function": "ReloadConfig"})):
            d, subject = automatic_fixture()
            change(d)
            with self.assertRaisesRegex(ValueError, "No initial provider control"):
                self.score(d, subject)

    def test_born_beast_wrong_base_weight_or_declared_scale_does_not_pass(self):
        for change in (lambda d: d["baseline"]["refs"][0]["actor"].update(baseRace="0x00013746"),
                       lambda d: d["baseline"]["refs"][0]["actor"].update(baseForm="0x0D000800"),
                       lambda d: d["baseline"]["refs"][0]["actor"]["weight"].update(rawNPCWeight=100),
                       lambda d: d["baseline"]["refs"][0].update(scale=1.2),
                       lambda d: d["baseline"]["nodes"][0]["local"].update(scale=.5)):
            d, subject = automatic_fixture()
            change(d)
            with self.assertRaises(ValueError):
                self.score(d, subject)

    def test_passive_missing_driver_stays_failure_without_repair(self):
        d, subject = automatic_fixture(weak_node="TailBone04")
        result = self.score(d, subject)
        self.assertIn("TailBone04", result["missingDrivers"])
        self.assertEqual(result["status"], "unconfirmed")

    def test_legacy_default_rejects_new_contract_and_keeps_original_output(self):
        d, subject = automatic_fixture()
        with self.assertRaisesRegex(ValueError, "Changed nominal contract"):
            nominal.score(d, PINS)
        self.assertEqual(nominal.score(fixture(), PINS)["status"], "sampled-provider-selective-motion")
        self.assertNotIn("initialControlMode", nominal.protocol())

    def test_male_contract_cannot_silently_change_authored_height(self):
        d, subject = automatic_fixture("male")
        subject["expectedUniformScale"] = 1.
        d["humanOrigin"] = copy.deepcopy(subject)
        with self.assertRaisesRegex(ValueError, "Changed finite"):
            self.score(d, subject)

    def test_initial_nord_ancestry_and_each_actual_race_pair_are_required(self):
        for phase in ("initial-human", "enabled-human", "first-wolf", "human-return", "second-wolf", "post-load"):
            d, subject = automatic_fixture()
            actor = d["humanLifecycle"]["phaseWitnesses"][phase]["refs"][0]["actor"]
            actor["baseRace"] = subject["currentRace"] if phase in ("initial-human", "enabled-human", "human-return") else subject["originalRace"]
            with self.subTest(phase=phase), self.assertRaisesRegex(ValueError, "transition differs"):
                self.score(d, subject)

    def test_provider_log_join_uses_exact_real_base_name_and_sex(self):
        for sex in ("male", "female"):
            ref = "0x0D000900" if sex == "female" else "0x0D000901"
            subject = nominal.human_subject(ref, sex, "Test Unicode Иона")
            nodes = nominal.scene.drivers(sex)
            log = "".join("Adding " + n + " to default list for " + subject["baseForm"][2:].lower() + " -> fixture\n" +
                          subject["providerActorName"] + " - " + sex.title() + " - Thing.update() " + n + " - Diff: .1\n" for n in nodes)
            rows = nominal.provider_ledger(log.encode(), nodes, subject)
            self.assertTrue(all(r == {"insertions": 1, "updates": 1} for r in rows.values()))
            wrong = log.replace(subject["baseForm"][2:].lower(), "0d000800").replace(subject["providerActorName"], "CLAW PHYSICS PROBE A")
            self.assertTrue(all(r == {"insertions": 0, "updates": 0} for r in nominal.provider_ledger(wrong.encode(), nodes, subject).values()))


if __name__ == "__main__":
    unittest.main()
