"""Shared schema-3 evaluator settings; geometry remains in the hashed regions.

The historical identity already includes every region. Top-level convenience
settings may select those pinned values, but must never override them.
"""
from __future__ import annotations
import math
import re
from pathlib import Path
import sys

SOURCE_BYTES = Path(__file__).read_bytes()
if compile(SOURCE_BYTES, sys._getframe().f_code.co_filename, "exec", dont_inherit=True,
           optimize=sys.flags.optimize) != sys._getframe().f_code:
    raise ValueError("Evaluator-settings source bytes do not match the loaded code")


PCA_EVALUATOR = "deform-actual-normalized-rest-LBS-support-then-PCA-refit-v1"
CONTACT_EVALUATOR = "deform-rest-LBS-support-then-symmetric-triangle-contact-minimax-RMS-v3"
DEFAULT_PADDING = 1e-4

COARSE_PROFILE = "coarse-whole-body-v1"


def identity_fields(model):
    """Preserve historical identities; include any new support declaration."""
    return (("evaluator", "morphs", "regions", "slots")
            + (("weightDependent",) if "weightDependent" in model else ())
            + (("supportProfile", "supportDeclaration") if "supportProfile" in model else ()))


def support_regions(value, *, measured=False):
    """Validate explicit attachment data, never infer a second bone whitelist."""
    if not isinstance(value, list) or not value:
        raise ValueError("Explicit support requires nonempty declared regions")
    seen=set(); total=0
    for row in value:
        keys={"node", "count", "sexMask"} | ({"ancestry"} if measured else set())
        if not isinstance(row, dict) or set(row) != keys:
            raise ValueError("Invalid declared support region fields")
        node=row["node"]
        if not isinstance(node,str) or not re.fullmatch(r"[A-Za-z0-9_ \[\].-]{1,128}",node) or node in seen:
            raise ValueError("Invalid or duplicate declared support node")
        seen.add(node)
        if type(row["count"]) is not int or not 1 <= row["count"] <= 128 or row["sexMask"] not in ("both","female"):
            raise ValueError("Invalid declared support count/sex mask")
        total+=row["count"]
        if measured:
            ancestry=row["ancestry"]
            if (not isinstance(ancestry,list) or not ancestry or ancestry[0]!=node
                    or not all(isinstance(name,str) and name for name in ancestry)
                    or len(ancestry)!=len(set(ancestry))):
                raise ValueError("Invalid measured XP32 support ancestry")
    if total>128:raise ValueError("Declared support exceeds 128 host slots")
    return value


def support_declaration(model):
    """Check a self-pinned measured declaration consumed by the generic host."""
    if "supportProfile" not in model:return None
    if model["supportProfile"]!=COARSE_PROFILE:raise ValueError("Unknown fitted support profile")
    value=model.get("supportDeclaration")
    if not isinstance(value,dict) or set(value)!={"regions","skinShapes","skeletonSha256"}:
        raise ValueError("Missing explicit fitted support declaration")
    regions=support_regions(value["regions"],measured=True)
    shapes=value["skinShapes"]
    if (not isinstance(shapes,list) or not shapes
            or not all(isinstance(name,str) and re.fullmatch(r"[A-Za-z0-9_.-]{1,128}",name) for name in shapes)
            or len(shapes)!=len(set(shapes))
            or model.get("coveredShapes")!=shapes):
        raise ValueError("Declared skin shapes differ from fitted support")
    digest=value["skeletonSha256"]
    if (not isinstance(digest,str) or not re.fullmatch(r"[0-9a-f]{64}",digest)
            or not any(row.get("sha256")==digest for row in model.get("sourceInputs",[]) if isinstance(row,dict))):
        raise ValueError("Measured skeleton is not pinned as a source input")
    if model.get("contactPasses",0)!=0:
        raise ValueError("Coarse support requires its enclosing evaluator")
    return {row["node"]:row for row in regions}


def evaluator_settings(model):
    """Return the one native pass/padding pair, refusing divergent Python fits."""
    passes = model.get("contactPasses", 0)
    if type(passes) is not int or not 0 <= passes <= 8:
        raise ValueError("Current-vector contact passes must be an integer in 0..8")
    expected = CONTACT_EVALUATOR if passes else PCA_EVALUATOR
    if model.get("evaluator") != expected:
        raise ValueError("Current-vector evaluator does not match its contact passes")
    regions = model.get("regions")
    if not isinstance(regions, dict) or not regions:
        raise ValueError("Current-vector evaluator requires pinned support regions")
    padding = None
    for region in regions.values():
        if not isinstance(region, dict):
            raise ValueError("Invalid current-vector support region")
        region_passes = region.get("contactPasses", 0)
        if type(region_passes) is not int or region_passes != passes:
            raise ValueError("Top-level contact passes differ from pinned support regions")
        value = region.get("padding", DEFAULT_PADDING)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 < value <= .01:
            raise ValueError("Current-vector padding must be finite and in (0, .01]")
        if padding is not None and value != padding:
            raise ValueError("Native model requires one common pinned region padding")
        padding = value
        if passes and "axisHints" in region:
            raise ValueError("Prescribed-axis contact optimization is not a supported family")
    return passes, padding
