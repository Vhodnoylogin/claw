"""Local-only Bijin1.2.1 skin test patch. No installation or game operations."""
from pathlib import Path
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
import struct
import subprocess
import zipfile
import zlib

HERE = Path(__file__).resolve().parent
HELPER = HERE.parents[1]/'inspection/lighting/build_lighting.py'
spec = importlib.util.spec_from_file_location('claw_inspection_binary', HELPER)
binary = importlib.util.module_from_spec(spec); spec.loader.exec_module(binary)
NAME = 'test_CLAW - Bijin NPCs Skin Werewolf.esp'


def sha(raw): return hashlib.sha256(raw).hexdigest()
def require(value, reason):
    if not value: raise ValueError(reason)


def make_override(row, addon):
    kind, form, flags, raw, original, ancestors = row
    fields = binary.subs(raw)
    # Refuse unsupported encodings instead of normalizing the author's bytes.
    rebuilt = b''.join(binary.sub(k.decode('ascii'), v) for k, v in fields)
    require(rebuilt == raw, 'Unsupported noncanonical/extended ARMO subrecord encoding')
    indexes = [i for i, (kind, value) in enumerate(fields) if kind == b'MODL']
    require(bool(indexes), 'Skin has no existing armature list')
    require(all(len(fields[i][1]) == 4 for i in indexes), 'Invalid ARMO MODL form reference')
    require(all(struct.unpack('<I', fields[i][1])[0] != addon for i in indexes), 'Wolf addon already present')
    offset = sum(6+len(value) for _, value in fields[:indexes[-1]+1])
    inserted = binary.sub('MODL', struct.pack('<I', addon))
    patched = raw[:offset]+inserted+raw[offset:]
    require(patched[:offset]+patched[offset+len(inserted):] == raw, 'Inverse payload comparison failed')
    payload = struct.pack('<I', len(patched))+zlib.compress(patched, 9) if flags & 0x40000 else patched
    header = original[:4]+struct.pack('<I', len(payload))+original[8:24]
    require(header[:4]+header[8:] == original[:4]+original[8:24], 'ARMO header changed beyond payload size')
    return header+payload, {'form': f'0x{form:08X}', 'originalPayloadSha256': sha(raw),
            'patchedPayloadSha256': sha(patched), 'insertOffset': offset,
            'inversePayloadByteExact': True, 'headerExactExceptDataSize': True,
            'originalSubrecordCount': len(fields), 'patchedSubrecordCount': len(fields)+1}


def validate(source_rows, output):
    rows = list(binary.records(output))
    require(Counter(r[0] for r in rows) == Counter({b'TES4': 1, b'ARMO': 14}), 'Unexpected record classes/counts')
    masters = [v.rstrip(b'\0').decode('ascii') for k, v in binary.subs(rows[0][3]) if k == b'MAST']
    require(masters == ['Skyrim.esm', 'Update.esm', 'Bijin NPCs.esp'], 'Master indexes changed')
    original = {r[1]: r for r in source_rows if r[0] == b'ARMO'}
    for row in rows[1:]:
        require(row[1] in original and row[1] >> 24 == 2, 'Override is not an original Bijin form')
        require(len(row[5]) == 1 and row[5][0][8:12] == b'ARMO', 'Unexpected record grouping')
        old = original[row[1]]
        fields = binary.subs(row[3]); old_fields = binary.subs(old[3])
        wolf = [i for i, (kind, value) in enumerate(fields) if kind == b'MODL' and value == struct.pack('<I', 0xCDD87)]
        require(len(wolf) == 1, 'Wolf addon not unique')
        index = wolf[0]
        require(index > 0 and fields[index-1][0] == b'MODL', 'New addon does not follow last original MODL')
        require(all(k != b'MODL' for k, _ in fields[index+1:]), 'New addon not last armature entry')
        restored = fields[:index]+fields[index+1:]
        require(restored == old_fields and b''.join(binary.sub(k.decode(), v) for k, v in restored) == old[3],
                'Original payload not byte-exact after inverse removal')
        require(row[4][:4]+row[4][8:24] == old[4][:4]+old[4][8:24], 'Original header flags/identity/version changed')
    return {'recordTypes': {'TES4': 1, 'ARMO': 14}, 'masters': masters,
            'all14InversePayloadsExact': True, 'all14HeadersExactExceptSize': True,
            'onlyOneArmoGroup': True, 'npcOverrides': 0, 'newArmorAddons': 0, 'artworkFiles': 0}


def independent_roundtrip(output, exe):
    original = output/'payload'/NAME
    rebuilt = output/'roundtrip'/NAME; rebuilt.parent.mkdir()
    calls = []
    for name, arguments in [
        ('serialize', ['serialize', '-i', str(original), '-o', str(output/'spriggit-source'),
                       '-g', 'SkyrimSE', '-p', 'Spriggit.Yaml', '-v', '0.41.0', '-t', '1']),
        ('deserialize', ['deserialize', '-i', str(output/'spriggit-source'), '-o', str(rebuilt), '-t', '1']),
        ('readback', ['serialize', '-i', str(rebuilt), '-o', str(output/'roundtrip-source'),
                      '-g', 'SkyrimSE', '-p', 'Spriggit.Yaml', '-v', '0.41.0', '-t', '1'])]:
        done = subprocess.run([str(exe), *arguments], capture_output=True, text=True,
                              encoding='utf-8', errors='replace', timeout=90)
        (output/(name+'.stdout.log')).write_text(done.stdout, encoding='utf-8')
        (output/(name+'.stderr.log')).write_text(done.stderr, encoding='utf-8')
        calls.append({'argv': [str(exe), *arguments], 'exitCode': done.returncode})
        require(done.returncode == 0, 'Spriggit failed: '+name+'; retain logs')
    def tree(root): return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob('*') if p.is_file()}
    require(tree(output/'spriggit-source') == tree(output/'roundtrip-source'), 'Spriggit text roundtrip differs')
    kinds = Counter(row[0].decode() for row in binary.records(rebuilt.read_bytes()))
    require(kinds == Counter({'TES4': 1, 'ARMO': 14}), 'Spriggit rebuilt record classes differ')
    return {'passed': True, 'textTreesByteEqual': True, 'textFileCount': len(tree(output/'spriggit-source')),
            'recordTypes': dict(kinds), 'calls': calls, 'tool': {'path': str(exe), 'sha256': sha(exe.read_bytes())}}


def build(source, output, spriggit):
    source, output, spriggit = source.resolve(), output.resolve(), spriggit.resolve()
    pin = json.loads((HERE/'pin.json').read_text(encoding='utf-8'))
    data = source.read_bytes()
    require(source.name == pin['plugin'] and sha(data) == pin['sha256'], 'Only exact original Bijin1.2.1 AIO is supported')
    require(not any((p/'.git').exists() for p in [output, *output.parents]), 'Generated vendor records must stay outside Git')
    rows = list(binary.records(data)); masters = [v.rstrip(b'\0').decode() for k, v in binary.subs(rows[0][3]) if k == b'MAST']
    require(masters == pin['sourceMasters'], 'Unexpected original master order')
    skins = [row for row in rows if row[0] == b'ARMO']
    npcs = [row for row in rows if row[0] == b'NPC_']
    referenced = {struct.unpack('<I', v)[0] for row in npcs for k, v in binary.subs(row[3]) if k == b'WNAM'}
    require(len(skins) == pin['skinCount'] and len(npcs) == pin['npcCount'] and referenced == {r[1] for r in skins},
            'ARMO set does not equal all original NPC skin records')
    overrides, proofs = [], []
    for row in skins:
        require(row[1] >> 24 == 2, 'Original skin is not self-index2')
        blob, proof = make_override(row, int(pin['werewolfAddon'], 16)); overrides.append(blob); proofs.append(proof)
    own_masters = [*masters, source.name]
    header = binary.rec('TES4', 0, binary.sub('HEDR', struct.pack('<fII', 1.7, 15, 0x800))+
        binary.sub('CNAM', b'CLAW private compatibility test\0')+
        binary.sub('SNAM', b'Local test: append werewolf addon to Bijin skin armor only.\0')+
        b''.join(binary.sub('MAST', name.encode()+b'\0')+binary.sub('DATA', b'\0'*8) for name in own_masters))
    plugin = header+binary.grp(b'ARMO', 0, b''.join(overrides))
    structural = validate(rows, plugin)
    output.mkdir(parents=True, exist_ok=False); payload = output/'payload'; payload.mkdir()
    (payload/NAME).write_bytes(plugin)
    independent = independent_roundtrip(output, spriggit)
    archive = output/(NAME[:-4]+'.zip')
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z: z.write(payload/NAME, NAME)
    require(source.read_bytes() == data, 'Original source changed during build')
    receipt = {'status': 'OFFLINE_PRIVATE_PATCH_NOT_INSTALLED_NOT_GAME_QUALIFIED',
        'source': {'path': str(source), 'sha256': sha(data)}, 'builderSha256': sha(Path(__file__).read_bytes()),
        'binaryHelperSha256': sha(HELPER.read_bytes()), 'structural': structural, 'records': proofs,
        'spriggit': independent, 'plugin': {'path': str(payload/NAME), 'bytes': len(plugin), 'sha256': sha(plugin)},
        'mo2Archive': {'path': str(archive), 'bytes': archive.stat().st_size, 'sha256': sha(archive.read_bytes())},
        'originalSourceUnchanged': True, 'gameLaunches': 0, 'installed': False,
        'scope': 'All14skin overrides structurally checked; no claim that all16NPCs or all skins work in game'}
    (output/'receipt.json').write_text(json.dumps(receipt, indent=2)+'\n', encoding='utf-8')
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--spriggit', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.output, args.spriggit), indent=2))
