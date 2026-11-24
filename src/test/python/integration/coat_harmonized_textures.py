"""Build local-only diffuse maps for the regional coat comparisons."""
from __future__ import annotations

import struct
from pathlib import Path

import numpy as np
from PIL import Image


SIZE = 1024
# Hair contributes most around the head and progressively less on the body.
# These are material-wide blend weights, not a model-space seam mask.
HAIR_WEIGHT = {
    "body.dds": .10,
    "head.dds": .86,
    "furarms.dds": .25,
    "furback.dds": .50,
    "furbelly.dds": .23,
    "furchest.dds": .55,
    "furface.dds": .89,
    "furshoulders.dds": .53,
    "furtail.dds": .39,
}
SKIN_DONORS = {(185, 179, 170): "Timber", (221, 221, 221): "White"}
HAIR_DONORS = {
    (20, 20, 24): "ValleyBlack",
    (48, 35, 33): "Brown",
    (81, 77, 57): "Timber",
    (90, 95, 105): "Grey",
    (92, 88, 80): "ValleyWhite",
}

LINEAR_TO_LMS = np.array([
    [.4122214708, .5363325363, .0514459929],
    [.2119034982, .6806995451, .1073969566],
    [.0883024619, .2817188376, .6299787005],
], dtype=np.float32)
LMS_TO_LAB = np.array([
    [.2104542553, .7936177850, -.0040720468],
    [1.9779984951, -2.4285922050, .4505937099],
    [.0259040371, .7827717662, -.8086757660],
], dtype=np.float32)
LAB_TO_LMS = np.linalg.inv(LMS_TO_LAB)
LMS_TO_LINEAR = np.linalg.inv(LINEAR_TO_LMS)


def _decode(rgb8):
    srgb = np.asarray(rgb8, dtype=np.float32) / 255
    return np.where(srgb <= .04045, srgb / 12.92, ((srgb + .055) / 1.055) ** 2.4)


def _encode(linear):
    linear = np.clip(linear, 0, 1)
    srgb = np.where(linear <= .0031308, linear * 12.92, 1.055 * linear ** (1 / 2.4) - .055)
    return np.rint(srgb * 255).astype(np.uint8)


def _lab(rgb8):
    return np.cbrt(_decode(rgb8) @ LINEAR_TO_LMS.T) @ LMS_TO_LAB.T


def _donor(path):
    with Image.open(path) as image:
        pixels = np.asarray(image.convert("RGBA").resize((SIZE, SIZE), Image.Resampling.BOX))
    lab = _lab(pixels[..., :3])
    alpha = pixels[..., 3].copy()
    sample_lab, sample_alpha = lab[::4, ::4], alpha[::4, ::4]
    opaque = sample_lab[sample_alpha >= 128]
    if not len(opaque):
        raise ValueError(f"No opaque diffuse samples in {path}")
    center = np.median(opaque, axis=0)
    return lab, alpha, center


def _target(skin_input, hair_input, skin_center, hair_center, hair_weight):
    # The fixture uses input lightness continuously within its calibrated range.
    # The donor controls local features. The minimum lightness lifts near-black
    # donors and the soft limit avoids the original black/white discontinuity.
    body = .51 + .55 * (skin_input[0] - .77)
    wanted_hair = .34 + 1.3 * (hair_input[0] - .19)
    hair = body + .24 * np.tanh((wanted_hair - body) / .24)
    body_chroma = skin_center[1:] * .50 + skin_input[1:] * .35
    hair_chroma = hair_center[1:] * .60 + hair_input[1:] * .68
    return np.array([
        body + hair_weight * (hair - body),
        *(body_chroma + hair_weight * (hair_chroma - body_chroma)),
    ], dtype=np.float32)


def _compose(skin, hair, skin_input, hair_input, name, hair_weight):
    skin_lab, skin_alpha, skin_center = skin
    hair_lab, hair_alpha, hair_center = hair
    target = _target(skin_input, hair_input, skin_center, hair_center, hair_weight)
    # Blend centered detail from the two UV-compatible diffuse maps. Preserve
    # the original material's alpha exactly at the preview resolution.
    detail = skin_lab - skin_center
    detail += hair_weight * ((hair_lab - hair_center) - detail)
    detail[..., 0] = .22 * np.tanh(detail[..., 0] / .22)
    adjusted = detail + target
    adjusted[..., 0] = np.clip(adjusted[..., 0], .015, .83)
    rgba = np.empty((SIZE, SIZE, 4), dtype=np.uint8)
    rgba[..., :3] = _encode((adjusted @ LAB_TO_LMS.T) ** 3 @ LMS_TO_LINEAR.T)
    rgba[..., 3] = skin_alpha if name == "body.dds" else hair_alpha
    return rgba, float(target[0])


def _mip(rgba):
    """Two-by-two premultiplied linear average, then straight-alpha sRGB."""
    shape = (rgba.shape[0] // 2, 2, rgba.shape[1] // 2, 2)
    alpha = rgba[..., 3].astype(np.float32) / 255
    linear = _decode(rgba[..., :3])
    weighted = (linear * alpha[..., None]).reshape(*shape, 3).sum(axis=(1, 3))
    alpha_sum = alpha.reshape(shape).sum(axis=(1, 3))
    contributing = alpha_sum > 0
    weighted[contributing] /= alpha_sum[contributing, None]
    unweighted = linear.reshape(*shape, 3).mean(axis=(1, 3))
    weighted[~contributing] = unweighted[~contributing]
    result = np.empty((*alpha_sum.shape, 4), dtype=np.uint8)
    result[..., :3] = _encode(weighted)
    result[..., 3] = np.rint(alpha_sum * 63.75).astype(np.uint8)
    return result


def _save_dds(path, top):
    # DDS_HEADER with pitch, mip count, DX10 pixel format, and texture/mipmap
    # caps, followed by a single 2D DXGI_FORMAT_R8G8B8A8_UNORM_SRGB resource.
    levels = SIZE.bit_length()
    dx10 = int.from_bytes(b"DX10", "little")
    header = struct.pack("<31I", 124, 0x2100F, SIZE, SIZE, SIZE * 4, 0, levels,
                         *([0] * 11), 32, 4, dx10, 0, 0, 0, 0, 0,
                         0x401008, 0, 0, 0, 0)
    with path.open("xb") as stream:
        stream.write(b"DDS " + header + struct.pack("<5I", 29, 3, 0, 1, 1))
        level = top
        for index in range(levels):
            stream.write(level.tobytes())
            if index + 1 < levels:
                level = _mip(level)
        expected_bytes = 148 + 4 * sum((SIZE >> index) ** 2 for index in range(levels))
        if stream.tell() != expected_bytes:
            raise ValueError(f"Incomplete mip chain: {path}")
    with Image.open(path) as saved:
        if not np.array_equal(np.asarray(saved.convert("RGBA"))[..., 3], top[..., 3]):
            raise ValueError(f"DDS alpha readback mismatch: {path}")


def generate(installed: Path, output: Path, pairs: list[dict], *, skin_donor=None, hair_donor=None) -> dict:
    """Generate the exact disposable comparison for locally installed assets."""
    installed, output = Path(installed).resolve(), Path(output).resolve()
    repository = Path(__file__).resolve().parents[4]
    if output.is_relative_to(repository) or output.is_relative_to(installed):
        raise ValueError("Use a separate external directory for the generated textures")
    if skin_donor is not None and skin_donor not in {"Grey", *SKIN_DONORS.values()}:
        raise ValueError(f"Unknown fixture skin donor: {skin_donor}")
    if hair_donor is not None and hair_donor not in set(HAIR_DONORS.values()):
        raise ValueError(f"Unknown fixture hair donor: {hair_donor}")
    if not (installed / "Timber").is_dir():
        installed /= "textures/DiverseElegantWerewolves"
    entries = {}
    for pair in pairs:
        base = pair["base"]
        skin, hair = tuple(pair["skinRecordRGB8"]), tuple(pair["hair"])
        pattern = f"harmonized-{int(base, 16):08x}"
        if base in entries or any(item["pattern"] == pattern for item in entries.values()):
            raise ValueError(f"Duplicate fixture actor base: {base}")
        entries[base] = {
            "pattern": pattern, "textures": list(HAIR_WEIGHT),
            "skinDonor": skin_donor or SKIN_DONORS[skin], "hairDonor": hair_donor or HAIR_DONORS[hair],
            "skinRGB8": list(skin), "hairRGB8": list(hair), "materials": {},
        }
    if not entries or any(not (installed / donor / name).is_file()
                          for donor in {entry[key] for entry in entries.values() for key in ("skinDonor", "hairDonor")}
                          for name in HAIR_WEIGHT):
        raise ValueError(f"Missing fixture donor maps in {installed}")
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"Generated texture directory is not empty: {output}")
    for entry in entries.values():
        (output / entry["pattern"]).mkdir(parents=True, exist_ok=True)
    for name, hair_weight in HAIR_WEIGHT.items():
        donors = {donor: _donor(installed / donor / name)
                  for donor in {entry[key] for entry in entries.values() for key in ("skinDonor", "hairDonor")}}
        for entry in entries.values():
            rgba, lightness = _compose(donors[entry["skinDonor"]], donors[entry["hairDonor"]],
                                       _lab(entry["skinRGB8"]), _lab(entry["hairRGB8"]), name, hair_weight)
            _save_dds(output / entry["pattern"] / name, rgba)
            sample = rgba[::4, ::4]
            rgb = sample[sample[..., 3] >= 128, :3]
            entry["materials"][name] = {
                "hairWeight": hair_weight, "targetLightness": round(lightness, 4),
                "medianLuma8": round(float(np.median(rgb @ np.array([.2126, .7152, .0722]))), 1),
            }
    return entries
