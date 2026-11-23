"""Bind the isolated contact replay to measured MO2 winners and mapped modules."""

from hashlib import sha256
from io import BytesIO
import ntpath
from zipfile import ZipFile

from cbpc_event_readback import positive_int, require


CONFIG_SHA = "878f2a30362ab51dcc8f8cd963713801f03644569865ed1938b21b137b6181db"
BODY_SHA = "4122c056e07054d456ffbc45bb380411581928568be8f8592c96b6573a3dbb2a"
HOST_ESP = "CLAW - Physics.esp"
PLUGINS = "SKSE/Plugins/"
ISOLATED_ABSENCES = (HOST_ESP, PLUGINS + "hdtSMP64.dll")
SKELETON_PATH = "Meshes/Actors/WerewolfBeast/Character Assets/skeleton.nif"
SKELETON_SHA = "b64b614d06eb854512ef4a9d6b08777fe0f9580f47d495d20db16dabb9fc2dd0"
BODY_DIR = "Meshes/Actors/WerewolfBeast/CLAW/FirstPerson"
BODY_PLUGIN = "test_CLAW - VR Player Body32.esp"
BODY_MEMBERS = ("Body.tri", "Body_0.nif", "Body_1.nif", "EarWorldTrial.nif", "EarWorldTrial.tri")
MODULES = {
    "cbp.dll": "9585f78b2e4f1e09a3a33e1c7789e353caecd368738939b70ecd832b7792d729",
    "clawvrplayercbpcevents.dll": "0c5e00ae3af337928e04e24739438f374b9f910dbac2395414f1bb1b22ffbdbf",
    "clawvrmodeltopology.dll": "8e43caecd591813e156a4a3ed9f5d41f1374d95966c838ac46ba53b6d49310a0",
    "skyrimworldobserver.dll": "60956a5afcab2c17e61956e05b144244b7bcf1158850744e54518fe5d523c1e1",
}
SCRIPTS = {
    "Scripts/CBPCPluginScript.pex": "d779a91232b130647ff5dc462e8f86a727ac995a5dd12d7c8a518f1df482e271",
    "Scripts/CLAWVRPlayerCBPCEvents.pex": "14d6e812304cf387039ab202ec541f2587bf6a3a5b22b4dfb34bb4b6018c2282",
    "Scripts/CLAWVRModelTopology.pex": "1ad765108079a7b3b9c36c58b70f96cddd779e55836f82224bd7a93f7ea3a3c0",
}
INHERITED_CONFIGS = {
    "CBPCBounceinterpolationconfig_Test.txt": "49412007c800e56db1ce5646c5c4af1ef20f4411a4ba2ffb90fc134ef08a6d52",
    "CBPCCollisioninterpolationconfig_Test.txt": "0ecdbf456d22f8bb81f593f6715e7cd3102298affb0b28dee439018fc7d49227",
    "CBPConfig.txt": "f4777444e68ba00495d74758ca4a2696a41879efc19a889017cb07c7761176a0",
    "CBPConfig_BellyAmplitude.txt": "db4261f3442c78a1621015421e321ceae53abb64073e06c791c74fd25691d645",
    "CBPConfig_BreastAmplitude.txt": "336fc8c9d2ff951dfe86ea72a1067b742fdcecd4915d1a39e8c8c10576b15689",
    "CBPConfig_ButtAmplitude.txt": "240f0903ff76c522ec2fc9960dfbd4f428a4fb2102198c2fb64e2b18c2f57e43",
    "CBPConfig_gravity.txt": "0995373f6696c016d52f52c5f7eb16b67e8e668c16733f824a8d518c1e88f7e1",
}


def physical_path(path):
    return ntpath.normcase(path.removeprefix("\\\\?\\"))


def resources(config, body, arm, sex):
    configs = {**INHERITED_CONFIGS, **config["arms"][arm]["files"]}
    files = {PLUGINS + name: digest for name, digest in (configs | MODULES).items()} | SCRIPTS
    files[SKELETON_PATH] = SKELETON_SHA
    with ZipFile(BytesIO(body)) as archive:
        for name in (BODY_PLUGIN, *(f"{BODY_DIR}/{sex.lower()}/{name}" for name in BODY_MEMBERS)):
            files[name] = sha256(archive.read(name)).hexdigest()
    return {path.casefold(): digest for path, digest in files.items()}, {name.casefold() for name in configs if name.endswith(".txt")}


def verify_vfs(state, association, files, inventory, pid):
    game, profile = state["game"], state["testProfileName"]
    bridge = association["observation"]
    proof = state["privateVrPoststageVfs"]
    context, batch = proof["context"], proof["batch"]
    require(game["pid"] == pid and positive_int(game["birth"]) and ntpath.basename(game["path"]).casefold() == "skyrimvr.exe" and
            state["gameEdition"] == "vr" and association["kind"] == "private-vr-bridge-observation" and
            association["location"] == "devbench-and-game-associated" and bridge["game"] == game and
            bridge["result"]["gameIdentityMatched"] is True and context["serverBootId"] == bridge["serverBootId"] and
            context["mo2Pid"] == bridge["mo2"]["pid"], "VFS profile is not linked to the recorded VR process")
    snapshot, batch_files = batch["snapshot"], batch["files"]
    before, after = (snapshot["observations"][name] for name in ("before", "after"))
    require(proof["observedBeforeStartup08FinalGate"] is True and context["batch"] is True and
            batch["complete"] is True and batch["count"] == len(batch_files) and
            batch["profile"] == profile == before["profile"] and snapshot["mappingRechecked"] is True and
            snapshot["state"] == "no-observed-divergence" and before == after and before["bridgeMutation"]["active"] is False and
            physical_path(before["profilePath"]) == physical_path(ntpath.join(context["profilesPath"], profile)) and
            all(before[name] == context[name] for name in ("serverBootId", "instanceId")), "No matching bracketed VFS snapshot")
    mapped = {row["path"].casefold(): row for row in batch_files}
    observed = {row["virtual"].casefold(): row for row in proof["resources"]}
    require(len(mapped) == len(batch_files) and len(observed) == len(proof["resources"]), "Duplicate VFS paths")
    for path in ISOLATED_ABSENCES:
        absent = mapped[path.casefold()]
        require(absent["status"] == "not-found" and not absent["origins"] and not absent.get("real"),
                f"Required absence is unproven: {path}")
    for path, digest in files.items():
        winner, pin = mapped[path], observed[path]["pin"]
        require(winner == observed[path]["actual"] and winner["status"] == "verified" and bool(winner["origins"]) and
                winner["winner"] == winner["origins"][0] and
                winner["archive"] is None and winner["sha256"] == pin["sha256"] == digest and
                physical_path(winner["real"]) == physical_path(pin["path"]) and positive_int(pin["bytes"]),
                f"Unexpected effective VFS winner: {path}")
    listed = proof["negatives"]["configInventory"]
    actual = [ntpath.basename(path).casefold() for path in listed["files"]]
    require(listed["path"] == "SKSE/Plugins" and listed["filter"] == "CBP*.txt" and set(actual) == inventory and
            len(actual) == len(inventory) and
            {physical_path(path) for path in listed["files"]} ==
            {physical_path(mapped[PLUGINS.casefold() + name]["real"]) for name in inventory},
            "Effective CBP configuration inventory differs from the isolated arm")
    return profile, game, observed


def verify_backing(backing, game, resources):
    require(backing["schema"] == "loaded-module-backing/2" and backing["status"] == "observed" and
            backing["qualified"] is True and backing["expectedProcess"] == backing["lastProcessIdentity"] == game and
            backing["inventoryBeforeComplete"] is backing["inventoryAfterComplete"] is True,
            "Missing same-process loaded module backing proof")
    selected = {row["name"]: row for row in backing["selected"]}
    require(len(selected) == len(backing["selected"]), "Duplicate mapped module receipt")
    for key in ("inventoryBefore", "inventoryAfter"):
        inventory = backing[key]
        require(not any(row["name"].casefold().startswith("hdtsmp") for row in inventory),
                "The isolated CBPC arm cannot share the reactive bones with FSMP")
        require(all(sum(row["name"].casefold() == name for row in inventory) == 1 for name in MODULES),
                "A required module was absent or duplicated in the mapped inventory")
    for name, digest in MODULES.items():
        row = selected[name]
        pin, module = row["pinFinal"], row["module"]
        mapped, path = row["mappedFinal"], row["finalBacking"]
        vfs = resources[PLUGINS.casefold() + name]["pin"]
        require(module["pid"] == game["pid"] and module["name"].casefold() == name and
                module in backing["inventoryBefore"] and module in backing["inventoryAfter"] and
                row["pinBefore"] == pin and pin["sha256"] == digest and pin["bytes"] == vfs["bytes"] and
                row["mappedBefore"] == row["mappedAfterRead"] == mapped and
                mapped["allocationBase"] == mapped["baseAddress"] == module["base"] == module["hModule"] and
                mapped["state"] == 0x1000 and mapped["type"] == 0x1000000 and
                row["openedBacking"] == path and path["ntPath"] == mapped["ntPath"] and
                physical_path(path["physicalPath"]) == physical_path(vfs["path"]),
                f"Mapped module or physical backing changed: {name}")


def verify_custody(state, association, backing, config, body, manifest):
    files, inventory = resources(config, body, manifest["arm"], manifest["sex"])
    profile, game, observed = verify_vfs(state, association, files, inventory, manifest["pid"])
    verify_backing(backing, game, observed)
    return {"profile": profile, "process": game, "requiredWinners": len(files), "mappedModules": sorted(MODULES)}
