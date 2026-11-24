"""Read VR body inputs from the actual serialized CLAW core installer."""
from __future__ import annotations

import importlib.util
from pathlib import Path

from body_resource import parse_json
import core_package_input

ROOT = Path(__file__).resolve().parents[4]
PACKAGER = ROOT / 'src/main/python/build-tools/package-source-build.py'
CORE_INPUT_SOURCE = Path(core_package_input.__file__)
ANATOMY_VISIBILITY_SOURCE = ROOT / 'src/main/components/adult-anatomy/python/visual_variants.py'
MALE_ENDPOINTS = frozenset(f'malebodywerewolf_{index}.nif' for index in (0, 1))


def open_tools(path):
    spec = importlib.util.spec_from_file_location('claw_vr_archive_tool', path)
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    return tool


anatomy_visibility = open_tools(ANATOMY_VISIBILITY_SOURCE)


def read_core_archive(pack, archive, *, receipt_path=None, known_digest=None):
    """A reviewed archive hash or a clean-source build receipt binds the actual bytes."""
    archive = Path(archive).resolve(strict=True)
    raw = archive.read_bytes()
    digest = pack.sha(raw)
    provenance = {str(archive): digest}
    receipt = None
    if receipt_path is not None:
        receipt_path = Path(receipt_path).resolve(strict=True)
        receipt_raw = receipt_path.read_bytes()
        receipt = parse_json(receipt_raw.decode('utf-8-sig'))
        if receipt is None:
            raise ValueError('Expected an object in the core build receipt')
        provenance[str(receipt_path)] = pack.sha(receipt_raw)
    files, plans = core_package_input.read_core_package(pack, raw, receipt=receipt, known_digest=known_digest)
    return files, plans, provenance


def static_routes(plans, destinations):
    selected = [{row['path']: row['source'] for row in plan['files'] if row['path'] in destinations}
                for plan in plans if plan.get('physics') in {None, 'none'}]
    if not selected or set(selected[0]) != destinations or any(row != selected[0] for row in selected):
        raise ValueError('Core physics-off selections must share the requested body model and TRI routes')
    return selected[0]


def require_reviewed_body(pack, files, plans, profile):
    expected = profile['inputSha256']
    paths = {name: f'{pack.MESH}/{name}' for name in expected}
    routes = static_routes(plans, set(paths.values()))
    payloads = {name: files[routes[path]] for name, path in paths.items()}
    digests = {name: pack.sha(data) for name, data in payloads.items()}
    changed = {name for name, digest in digests.items() if digest != expected[name]}
    if not changed:
        return digests, False
    if changed != MALE_ENDPOINTS:
        raise ValueError('Core archive body and TRI bytes differ from the reviewed VR resource profile')
    for name in sorted(MALE_ENDPOINTS):
        anatomy_visibility.reviewed_visible_anatomy(payloads[name], expected[name])
    return digests, True
