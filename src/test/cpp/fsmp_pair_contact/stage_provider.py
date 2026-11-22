"""Stage an opt-in FSMP derivative in a new external directory."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import shutil


HERE = Path(__file__).resolve().parent
BASE = "2215ec3ba09adf0843a3291ed0437a6ca6d385e2"
PINNED = {
    "CMakeLists.txt": "8f8b68b13c19a7f0dd59aaed4599569c9a4d03203b165333db9f06f9083f9542",
    "src/CMakeLists.txt": "69bbbd92f944c3e1f3f3d81e706147a41cce10e7f401e361d365d267a4938184",
    "src/dhdtPapyrusFunctions.cpp": "64ab570ab40b81d8583a78b6df12a4078bb501dd66d1b284a0690cd180e344d5",
    "src/hdtSkyrimPhysicsWorld.cpp": "b20c3c582a35cf4cf50939e9ec532f5f0dd81060ca3481fb1fa61ed027bfea19",
    "src/hdtSkinnedMesh/hdtSkinnedMeshAlgorithm.cpp": "e2e5da1b2f82482c8d26fb54381bfb71f179e1f161ba4aabc1d970e144a6f5a5",
}
OPTION = "CLAW_FSMP_PAIR_CONTACT_TEST"


def digest(data):
    return sha256(data).hexdigest()


def insert(source, before, replacement):
    if source.count(before) != 1:
        raise ValueError("Expected exactly one pinned insertion anchor: " + before)
    return source.replace(before, replacement)


def gate(code):
    return f"#if defined({OPTION})\n{code}\n#endif\n"


def patch(name, raw):
    with_crlf = b"\r\n" in raw
    source = raw.decode("utf-8").replace("\r\n", "\n")
    if name == "CMakeLists.txt":
        anchor = "add_subdirectory(src)"
        source = insert(source, anchor, f'option({OPTION} "CLAW owned-pair contact test only" OFF)\n{anchor}')
    elif name == "src/CMakeLists.txt":
        anchor = 'target_compile_features("${PROJECT_NAME}" PRIVATE cxx_std_20)'
        source = insert(source, anchor, f"""if({OPTION})
  target_sources("${{PROJECT_NAME}}" PRIVATE "${{SOURCE_DIR}}/claw_pair_contact/PairProvider.cpp")
  target_compile_definitions("${{PROJECT_NAME}}" PRIVATE {OPTION}=1)
endif()

{anchor}""")
    elif name == "src/dhdtPapyrusFunctions.cpp":
        anchor = '#include "hdtSkyrimPhysicsWorld.h"\n'
        source = insert(source, anchor, anchor + gate('#include "claw_pair_contact/PairProvider.h"'))
        anchor = '\tregistry->RegisterFunction("ResetPhysics", "DynamicHDT", hdt::papyrus::ResetPhysics);\n'
        source = insert(source, anchor, anchor + gate("\tclaw::contact::provider::registerFunctions(registry);"))
    elif name == "src/hdtSkyrimPhysicsWorld.cpp":
        anchor = '#include "hdtSkyrimPhysicsWorld.h"\n'
        source = insert(source, anchor, anchor + gate('#include "claw_pair_contact/PairProvider.h"'))
        anchor = "\t\t\tstepSimulation(remainingTimeStep, 0, tick);\n"
        source = insert(source, anchor, gate("\t\t\tclaw::contact::provider::begin(getCollisionObjectArray());")
                        + anchor + gate("\t\t\tclaw::contact::provider::end();"))
    else:
        anchor = '#include "hdtSkinnedMeshAlgorithm.h"\n'
        source = insert(source, anchor, anchor + gate('#include "../claw_pair_contact/PairProvider.h"'))
        anchor = "\t\t\tmaniford->addManifoldPoint(newPt);\n"
        source = insert(source, anchor, anchor + gate("\t\t\tclaw::contact::provider::note(body0, body1, rb0, rb1, newPt);"))
    if with_crlf:
        source = source.replace("\n", "\r\n")
    return source.encode("utf-8")


def stage(provider, out):
    provider, out = provider.resolve(strict=True), out.resolve()
    if out.exists() or out.is_relative_to(provider) or out.is_relative_to(HERE.parents[3]):
        raise ValueError("Select a new external staging directory")
    inputs = {name: (provider / name).read_bytes() for name in PINNED}
    for name, data in inputs.items():
        if digest(data) != PINNED[name]:
            raise ValueError("Pinned upstream file differs: " + name)
    patches = {name: patch(name, data) for name, data in inputs.items()}
    addition = {name: (HERE / name).read_bytes() for name in ("PairWindow.h", "PairProvider.h", "PairProvider.cpp")}
    out.mkdir()
    derivative = out / "source"
    shutil.copytree(provider, derivative)
    for name, data in patches.items():
        if (derivative / name).read_bytes() != inputs[name]:
            raise ValueError("Input changed during staging: " + name)
        (derivative / name).write_bytes(data)
    destination = derivative / "src/claw_pair_contact"
    destination.mkdir()
    for name, data in addition.items():
        (destination / name).write_bytes(data)
    record = {
        "upstream": str(provider), "upstreamCommit": BASE, "pinnedModifiedInputHashes": PINNED,
        "derivative": str(derivative), "patchOutputHashes": {name: digest(data) for name, data in patches.items()},
        "addedSourceHashes": {name: digest(data) for name, data in addition.items()}, "testOption": OPTION,
        "optionDefault": "OFF", "compiled": False, "installed": False, "gameStarted": False,
    }
    (out / "stage-report.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(stage(args.provider, args.out)["derivative"])
