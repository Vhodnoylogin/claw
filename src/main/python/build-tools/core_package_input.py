"""Read a serialized CLAW core package with its reviewed archive or build receipt."""
from __future__ import annotations

import re
from xml.etree import ElementTree as ET


def core_version(files):
    versions = ET.fromstring(files['fomod/info.xml']).findall('Version')
    version = (versions[0].text or '').strip() if len(versions) == 1 else ''
    if not version:
        raise ValueError('Expected one version in the core installer info')
    return version


def read_core_package(pack, raw, *, receipt=None, known_digest=None):
    digest = pack.sha(raw)
    if receipt is None:
        if digest != known_digest:
            raise ValueError('Expected the reviewed core archive or its clean-source build receipt')
    else:
        commit = receipt.get('sourceCommit') if isinstance(receipt, dict) else None
        if (not isinstance(commit, str) or re.fullmatch(r'[0-9a-f]{40}', commit) is None or
                type(receipt.get('schemaVersion')) is not int or receipt['schemaVersion'] != 1 or
                receipt.get('sourceCheckoutHead') != commit or receipt.get('sourceWorktreeHasTrackedChanges') is not False or
                receipt.get('sha256') != digest or type(receipt.get('bytes')) is not int or receipt['bytes'] != len(raw)):
            raise ValueError('Core archive does not match its clean-source build receipt')

    files = pack.read_zip(raw)
    plans = pack.selection_audit(files)
    if receipt is not None:
        actual = {name: {'bytes': len(payload), 'sha256': pack.sha(payload)} for name, payload in files.items()}
        if receipt.get('payloads') != actual or receipt.get('selections') != plans:
            raise ValueError('Core build receipt file inventory or installer selections differ')
    return files, plans
