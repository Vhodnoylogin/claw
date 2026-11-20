"""Export only the exact two observed VR poses and their bound support."""
import argparse
from hashlib import sha256
import json
from pathlib import Path

import numpy as np

import posed_contact as replay


def load(path, expected):
    contents = path.read_bytes()
    assert sha256(contents).hexdigest() == expected
    return json.loads(contents)


def encode(values):
    if isinstance(values,(tuple,list,np.ndarray)):
        return "{" + ", ".join(encode(value) for value in values) + "}"
    if isinstance(values,(np.integer,int)): return str(int(values))
    assert np.isfinite(values)
    return repr(float(values))


def matrix(value):
    return value[:3,:].reshape(-1).tolist()


def prepare(raw, model, expected, pynifly):
    poses = [json.loads(s) for s in raw["scope"]["rawReadReplies"]]
    assert len(poses) == 2
    basis, _ = replay.pinned_asset(model,"malebodywerewolf_1.nif")
    _, raw_tri = replay.pinned_asset(model,"malebodywerewolf.tri")
    api, _, _ = replay.breast_rig.load_pynifly(pynifly)
    nif = api.NifFile(str(basis))
    names = [n["name"] for n in poses[0]["sample"]["nodes"]]
    assert names == [n["name"] for n in poses[1]["sample"]["nodes"]]
    assert len(names) == len(set(names)) == 15
    assert all(set(p["sample"]["effectiveMorphs"].values()) == {0} for p in poses)
    records = replay.offsets(raw_tri)
    skins = {r: replay.Skin(nif.shape_dict[r],records,poses[0]["sample"]["effectiveMorphs"]) for r in ("head","body")}
    projected = {shape:{name: skin.binds[name] @ skin.global_to_skin for name in skin.names} for shape,skin in skins.items()}

    point_keys, influences, clusters, slot_points, unique_vertices = {}, [], [], [], []
    slots=model["slots"]; indexes=list(range(88,120))
    for index in indexes:
        slot = slots[index]
        owner = slot["node"]
        region = model["regions"]["male/"+owner]
        source, = region["sources"]
        shape = source["shape"]
        skin=skins[shape]
        base=len(slot_points)
        for local in slot["male"]["partitionIndices"]:
            v=source["vertices"][local]
            if (shape,v) not in point_keys:
                point_keys[shape,v]=len(unique_vertices)
                start=len(influences)
                weights=skin.weights[v]
                assert np.isfinite(weights).all() and (weights >= 0).all() and (weights <= 1).all() and weights.sum() > 0
                for i, weight in enumerate(weights/weights.sum()):
                    if weight > 0:
                        name=skin.names[i]
                        source_local=(projected[shape][name] @ np.r_[skin.vertices[v],1.])[:3]
                        influences.append((names.index(name), weight, source_local.tolist()))
                unique_vertices.append((start,len(influences)-start))
            slot_points.append(point_keys[shape,v])
        clusters.append((names.index(owner),base,len(slot_points)-base,region["padding"]))

    frames=[]; reference=[]
    for k,p in enumerate(poses):
        state=p["sample"]
        assert state["weight"]==50 and state["actor"]==0xff0008be
        origin=np.array(state["rootWorld"]["translation"])
        world=[replay.world_matrix(row["world"]) for row in state["nodes"]]
        for t in world: t[:3,3]-=origin
        inverse=[np.linalg.inv(t) for t in world]
        frames.append((list(map(matrix,world)),list(map(matrix,inverse))))
        rows=expected["results"][k]["result"]["slots"]
        assert [r["slot"] for r in rows]==indexes
        reference.append([[r["refit"]["capsule"]["p1"],r["refit"]["capsule"]["p2"],r["refit"]["capsule"]["radius"]] for r in rows])

    return {"Influence influences": influences,"Vertex uniqueVertices":unique_vertices,
            "std::size_t slotPointIndices":slot_points,"Region regions":clusters,"Pose poses":frames,
            "Expected expected":reference}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("native", "geometry", "model", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--pynifly", type=Path)
    args = parser.parse_args()
    data = load(args.native, "4023ec337c2e07b4cd68e5e207ab1c48c7e1c35d3d44cc851cde40dffb77f14f")
    expected = load(args.geometry, "82f24894a151043156bba61ec7903850d535f071cfab9a4f2f817afa6010b8a5")
    model = load(args.model, "66f7522934d75573087842f55073a1299338a9dadd2215d813057ba2eeb25918")
    parts = prepare(data, model, expected, args.pynifly)
    with (args.out/"observations.h").open("x",encoding="utf-8") as out:
        out.write("// Exact VR65 replay inputs. Generated outside the product repository.\n")
        for declaration, rows in parts.items():
            extra="[32]" if declaration.startswith("Expected ") else ""
            out.write("constexpr " + declaration + "[]" + extra + " = {\n")
            out.writelines("    "+encode(row)+",\n" for row in rows)
            out.write("};\n")
    print({name:len(rows) for name,rows in parts.items()})


if __name__=="__main__":
    main()
