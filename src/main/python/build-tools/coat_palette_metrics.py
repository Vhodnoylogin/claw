# SPDX-FileCopyrightText: 2026 CLAW contributors
"""Read actual local DDS pixels; export sampled metadata, never texture pixels.

Pillow and NumPy are optional analysis prerequisites, not game dependencies.
No texture is edited and no colour value is invented when decoding fails.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, __version__ as pillow_version

import coat_library as library


def sample_rgba(rgba, maximum_samples=65536):
    library.require(isinstance(maximum_samples, int) and 16 <= maximum_samples <= 1048576, "Invalid sample limit")
    library.require(rgba.dtype == np.uint8 and len(rgba.shape) == 3 and rgba.shape[2] == 4, "Expected uint8 RGBA pixels")
    height, width = rgba.shape[:2]
    stride = max(1, math.ceil(math.sqrt(width * height / maximum_samples)))
    while math.ceil(width / stride) * math.ceil(height / stride) > maximum_samples:
        stride += 1
    samples = rgba[::stride, ::stride].reshape(-1, 4)
    alpha = samples[:, 3].astype(np.float64) / 255
    visible = alpha > 0
    result = {"available": bool(np.any(visible)), "imagePixels": width * height,
              "samplePixels": len(samples), "sampleStrideXY": [stride, stride],
              "visibleSamplePixels": int(np.count_nonzero(visible)),
              "sampleCoverageAlphaPositive": float(np.mean(visible)),
              "sampleCoverageAlpha90": float(np.mean(samples[:, 3] >= 90)),
              "sampleMeanAlpha": float(np.mean(alpha))}
    if not result["available"]:
        result["reason"] = "All sampled texels are fully transparent; no representative RGB was assigned."
        return result
    srgb = samples[visible, :3].astype(np.float64) / 255
    linear = np.where(srgb <= .04045, srgb / 12.92, ((srgb + .055) / 1.055) ** 2.4)
    weights = alpha[visible]
    mean = np.sum(linear * weights[:, None], axis=0) / np.sum(weights)
    display = np.where(mean <= .0031308, mean * 12.92, 1.055 * mean ** (1 / 2.4) - .055)
    luminance = linear @ np.array([.2126, .7152, .0722])
    order = np.argsort(luminance)
    cumulative = np.cumsum(weights[order])
    quantiles = {str(q): float(luminance[order[min(len(order) - 1, np.searchsorted(cumulative, q * cumulative[-1]))]])
                 for q in [.1, .5, .9]}
    result.update({"alphaWeightedLinearMeanRgb": mean.tolist(), "alphaWeightedSrgbMeanRgb": display.tolist(),
                   "alphaWeightedSrgbMeanRgb8": np.rint(display * 255).astype(int).tolist(),
                   "alphaWeightedLinearMeanLuminance": float(np.dot(mean, [.2126, .7152, .0722])),
                   "alphaWeightedLinearLuminanceQuantiles": quantiles})
    return result


def analyze(library_root, inventory, maximum_samples=65536):
    manifest = library.verify(library_root, inventory)
    patterns = []
    for pattern in manifest["patterns"]:
        files = []
        for entry in pattern["files"]:
            path = Path(library_root) / entry["gamePath"]
            try:
                with Image.open(path) as image:
                    with image.convert("RGBA") as rgba:
                        metrics = sample_rgba(np.asarray(rgba), maximum_samples)
            except (OSError, ValueError, NotImplementedError) as error:
                metrics = {"available": False, "reason": f"DDS decode unavailable: {type(error).__name__}: {error}"}
            files.append({"name": entry["name"], "group": entry["group"], "sha256": entry["sha256"], "metrics": metrics})
        groups = {}
        for group in ["undercoat", "fur"]:
            selected = [f["metrics"] for f in files if f["group"] == group]
            available = all(m["available"] for m in selected)
            groups[group] = {"available": available, "textureCount": len(selected),
                             "weighting": "Equal per-texture weight; not UV/surface-area weighting."}
            if available:
                groups[group]["meanLinearRgb"] = np.mean([m["alphaWeightedLinearMeanRgb"] for m in selected], axis=0).tolist()
                groups[group]["meanLinearLuminance"] = float(np.mean([m["alphaWeightedLinearMeanLuminance"] for m in selected]))
        patterns.append({"id": pattern["id"], "label": pattern["label"], "groups": groups, "files": files})
    return {"schemaVersion": 1, "kind": "claw-local-coat-palette-metrics", "libraryId": manifest["libraryId"],
            "sourceArchiveSha256": manifest["source"]["archiveSha256"],
            "pillowVersion": pillow_version, "numpyVersion": np.__version__, "maximumSamplesPerTexture": maximum_samples,
            "method": "Deterministic texel grid from decoded DDS. Fully transparent samples are excluded; remaining samples are weighted by their actual alpha. RGB bytes are interpreted as sRGB for this comparison metric and converted to linear RGB before averaging. Alpha>=90 coverage is diagnostic, not a replacement for per-shape alpha blend/test state.",
            "limits": "Metadata is sampled from real diffuse pixels, not rendered game colour. No lighting, normal/specular response, UV surface-area weighting or coat-direction model is included. Undercoat textures also paint fur and are not a biological skin mask. No runtime palette selector or colour calibration is implemented.",
            "patterns": patterns}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library", required=True, type=Path)
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--runtime-xml", type=Path, help="Also write a NEW runtime XML sidecar from these actual measurements")
    parser.add_argument("--maximum-samples", type=int, default=65536)
    args = parser.parse_args()
    args.output = library.new_destination(args.output, [Path(__file__).resolve().parent])
    if args.runtime_xml is not None:
        args.runtime_xml = library.new_destination(args.runtime_xml, [Path(__file__).resolve().parent])
    result = analyze(args.library, library.validate_inventory(library.read_json(args.inventory)), args.maximum_samples)
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(result, output, indent=2); output.write("\n")
    if args.runtime_xml is not None:
        inventory = library.validate_inventory(library.read_json(args.inventory))
        manifest = library.validate_manifest(library.read_json(args.library / library.MANIFEST_PATH), inventory)
        text = library.runtime_xml(manifest, inventory, result)
        with args.runtime_xml.open("x", encoding="utf-8") as output:
            output.write(text)
    print(json.dumps({"patterns": len(result["patterns"]),
                      "decodedTextures": sum(f["metrics"]["available"] for p in result["patterns"] for f in p["files"]),
                      "totalTextures": sum(len(p["files"]) for p in result["patterns"]), "output": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
