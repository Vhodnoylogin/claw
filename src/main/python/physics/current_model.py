"""Shared schema-3 evaluator settings; geometry remains in the hashed regions.

The historical identity already includes every region. Top-level convenience
settings may select those pinned values, but must never override them.
"""
from __future__ import annotations
import math
from pathlib import Path
import sys

SOURCE_BYTES = Path(__file__).read_bytes()
if compile(SOURCE_BYTES, sys._getframe().f_code.co_filename, "exec", dont_inherit=True,
           optimize=sys.flags.optimize) != sys._getframe().f_code:
    raise ValueError("Evaluator-settings source bytes do not match the loaded code")


PCA_EVALUATOR = "deform-actual-normalized-rest-LBS-support-then-PCA-refit-v1"
CONTACT_EVALUATOR = "deform-rest-LBS-support-then-symmetric-triangle-contact-minimax-RMS-v3"
DEFAULT_PADDING = 1e-4


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
