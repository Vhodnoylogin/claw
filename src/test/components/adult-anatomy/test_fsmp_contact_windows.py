import json
import unittest

from fsmp_contact_windows import PHASES, SCRIPT, native_form, verify


def fixture():
    pair = dict(surfaceRef=0xFF000802, surfaceAddon=0xCDD87, probeRef=0xFF000803, probeAddon=0x08000800)
    manifest = {"schema": "claw-fsmp-pair-contact-reads/1", "pair": pair,
                "pid": 4321, "callerEpoch": 7, "frames": 24, "targetDriver": "WWD 2", "windows": {}}
    ledger = []

    def add(function, args, result_type, value):
        ledger.append({"tool": "papyrus", "args": {"action": "call", "script": SCRIPT, "function": function, "args": args},
                       "result": {"called": True, "returnedType": result_type, "returned": value}})
        return len(ledger) - 1

    for number, phase in enumerate(PHASES, 1):
        start = number * 100
        points = [{"step": 2, "qpc": start + 10, "signedDepth": -.31, "surfaceDriver": "WWD 2",
                   "normalToSurface": [0, 0, 1], "surfaceLocal": [-1., 2., 3.],
                   "probeLocal": [.1, 0., 0.]}] if phase == "reciprocal_near" else []
        arm = add("Arm", [*(native_form(value) for value in pair.values()), number, 7, 24], "bool", True)
        describe = add("Describe", [number], "string", json.dumps({
            "schema": "claw-fsmp-pair-contact/1", **pair, "pid": 4321, "callerEpoch": 7, "nonce": number,
            "status": "complete", "frameUnit": "steps", "frames": 24, "requiredFrames": 24,
            "mode": "tag_control" if phase == "tag_control" else "reciprocal",
            "measure": "pre-solve accepted contact point", "qpcFrequency": 10000000,
            "firstQpc": start, "lastQpc": start + 40, "contactRows": len(points)}))
        read = add("Read", [number, 0], "string", json.dumps({
            "status": "complete", "nonce": number, "offset": 0, "total": len(points), "rows": points}))
        manifest["windows"][phase] = {"nonce": number, "arm": arm, "describe": describe, "pages": [read]}
    return manifest, ledger


class FSMPContactWindowTest(unittest.TestCase):
    def test_positive_provider_receipt_is_narrow(self):
        manifest, ledger = fixture()
        result = verify(manifest, ledger)
        self.assertEqual([window["pointCount"] for window in result["windows"].values()], [0, 0, 1, 0])
        self.assertFalse(result["poseControlsVerified"])
        self.assertFalse(result["impulseVerified"])

    def test_unfinished_control_is_not_zero_contact(self):
        manifest, ledger = fixture()
        control = ledger[manifest["windows"]["tag_control"]["describe"]]["result"]
        head = json.loads(control["returned"])
        head["frames"] = 23
        control["returned"] = json.dumps(head)
        with self.assertRaisesRegex(ValueError, "Incomplete or foreign"):
            verify(manifest, ledger)

    def test_contact_must_use_intended_driver_and_come_from_the_armed_window(self):
        for key, value, error in (("surfaceDriver", "WWRB 1", "does not distinguish"),
                                  ("qpc", 401, "Invalid accepted point")):
            with self.subTest(key=key):
                manifest, ledger = fixture()
                read = ledger[manifest["windows"]["reciprocal_near"]["pages"][0]]["result"]
                page = json.loads(read["returned"])
                page["rows"][0][key] = value
                read["returned"] = json.dumps(page)
                with self.assertRaisesRegex(ValueError, error):
                    verify(manifest, ledger)


if __name__ == "__main__":
    unittest.main()
