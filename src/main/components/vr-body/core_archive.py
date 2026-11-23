"""Read VR body inputs from the actual serialized CLAW core installer."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import re

from body_resource import parse_json

ROOT = Path(__file__).resolve().parents[4]
PACKAGER = ROOT / 'src/main/python/build-tools/package-source-build.py'


def open_tools(path):
    spec = importlib.util.spec_from_file_location('claw_vr_archive_tool', path)
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    return tool


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
        commit = receipt.get('sourceCommit') if isinstance(receipt, dict) else None
        if (not isinstance(commit, str) or re.fullmatch(r'[0-9a-f]{40}', commit) is None or
                receipt.get('schemaVersion') != 1 or receipt.get('sourceCheckoutHead') != commit or
                receipt.get('sourceWorktreeHasTrackedChanges') is not False or receipt.get('sha256') != digest or
                receipt.get('bytes') != len(raw)):
            raise ValueError('Core archive does not match its clean-source build receipt')
        provenance[str(receipt_path)] = pack.sha(receipt_raw)
    elif digest != known_digest:
        raise ValueError('Expected the reviewed core archive or its clean-source build receipt')

    files = pack.read_zip(raw)
    plans = pack.selection_audit(files)
    if receipt is not None:
        actual = {name: {'bytes': len(payload), 'sha256': pack.sha(payload)} for name, payload in files.items()}
        if receipt.get('payloads') != actual or receipt.get('selections') != plans:
            raise ValueError('Core build receipt file inventory or installer selections differ')
    return files, plans, provenance


def static_routes(plans, destinations):
    selected = [{row['path']: row['source'] for row in plan['files'] if row['path'] in destinations}
                for plan in plans if plan.get('physics') in {None, 'none'}]
    if not selected or set(selected[0]) != destinations or any(row != selected[0] for row in selected):
        raise ValueError('Core physics-off selections must share the requested body model and TRI routes')
    return selected[0]


def require_reviewed_body(pack, files, plans, profile):
    expected = {pack.MESH + '/' + name: digest for name, digest in profile['inputSha256'].items()}
    routes = static_routes(plans, expected.keys())
    if any(pack.sha(files[source]) != expected[name] for name, source in routes.items()):
        raise ValueError('Core archive body and TRI bytes differ from the reviewed VR resource profile')
