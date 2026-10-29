"""Apply a reviewed coefficient-only proportions policy to a pinned family XML.

No mesh, source-preset, runtime contract or installed mod is changed. The policy
is an authored finite trial; its scores and owner visual acceptance are separate.
"""
import argparse,hashlib,json,math
from pathlib import Path
import xml.etree.ElementTree as ET


def refine(source, policy):
    if policy.get("schemaVersion") != 1 or hashlib.sha256(source).hexdigest() != policy.get("baseSourceSha256"):
        raise ValueError("Exact reviewed coefficient baseline required")
    root=ET.fromstring(source)
    if root.tag != "MorphLinkProfiles" or root.attrib != {"schemaVersion":"1"}:
        raise ValueError("Expected family schema1")
    seen=set()
    for profile in root.findall("Profile"):
        family=profile.attrib["family"]
        if family not in policy["families"]:continue
        seen.add(family);change=policy["families"][family]
        for row in profile.findall("Rule"):
            target=row.attrib["target"]
            scale=change["targetMultipliers"].get(target,1)
            if not math.isfinite(scale) or scale <= 0:raise ValueError("Positive finite trial multiplier required")
            old_cap=float(row.attrib["cap"])
            cap=change.get("targetCaps",{}).get(target,old_cap)
            if not math.isfinite(cap) or not 0 < cap <= 1:raise ValueError("Native target cap must be in (0,1]")
            if target in change["targetMultipliers"] or target in change.get("targetCaps",{}):
                # Native output is cap*clamp(sum(gain*source),0,1).
                # Normalize gains so the multiplier means the same sub-cap
                # linear response while cap places a hard geometry bound.
                row.attrib["gain"]=str(round(float(row.attrib["gain"])*scale*old_cap/cap,7))
                row.attrib["cap"]=str(cap)
        for row in change["addRules"]:
            ET.SubElement(profile,"Rule",{k:str(v) for k,v in row.items()})
        pairs=set();caps={}
        if len(profile.findall("Rule")) > 128:raise ValueError("Native rule budget exceeded")
        for row in profile.findall("Rule"):
            pair=(row.attrib["source"],row.attrib["target"]);gain=float(row.attrib["gain"]);cap=float(row.attrib["cap"])
            if pair in pairs or not math.isfinite(gain) or not 0 < cap <= 1 or caps.get(pair[1],cap)!=cap:
                raise ValueError("Invalid native coefficient rule")
            pairs.add(pair);caps[pair[1]]=cap
        profile.attrib["calibration"]=policy.get("calibration","regional-primary-proportions-trial1")
    if seen != set(policy["families"]):raise ValueError("Reviewed family missing")
    return root


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source",required=True,type=Path);ap.add_argument("--policy",required=True,type=Path)
    ap.add_argument("--output",required=True,type=Path);ap.add_argument("--default-male");ap.add_argument("--default-female")
    args=ap.parse_args();output=args.output.resolve()
    source_root=Path(__file__).resolve().parents[1]
    if output.exists() or source_root==output or source_root in output.parents or any((p/".git").exists() for p in [output,*output.parents]) or any(p.lower() in ("mods","data","overwrite","downloads") for p in output.parts):
        raise ValueError("New external candidate output required")
    root=refine(args.source.read_bytes(),json.loads(args.policy.read_text(encoding="utf-8")))
    if args.default_male or args.default_female:
        if root.find("Defaults") is not None:raise ValueError("Defaults already declared")
        ET.SubElement(root,"Defaults",{k:v for k,v in [("male",args.default_male),("female",args.default_female)] if v})
    ET.indent(root);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(ET.tostring(root,encoding="unicode")+"\n",encoding="ascii",newline="\n")
    print(json.dumps({"path":str(output),"sha256":hashlib.sha256(output.read_bytes()).hexdigest()}))


if __name__=="__main__":main()
