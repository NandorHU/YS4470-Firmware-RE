"""Verify the local transfer kit using only Python stdlib. No extraction/execution.

Run: python verify_handoff.py --package PATH_TO_EXTRACTED_PACKAGE
Hashes detect corruption, not authenticity of a replacement manifest. Compare
the outer ZIP SHA-256 supplied by the coordinator separately.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile

ORIGINALS = {
    'original-firmware/V3.6/f1c100s.bin': '7523b2e91dd8627ffebfc7ac0525c0607a56df4cece04028a9c3a8ee558f6eb9',
    'original-firmware/V3.8/f1c100s.bin': '7e7d7230155fe0790eb48531de2ef463bb122c0ae1a820ab6d10cf2e60f50290',
}

def safe_name(value: str) -> str:
    p = PurePosixPath(value)
    if not value or '\\' in value or ':' in value or p.is_absolute() or '..' in p.parts:
        raise ValueError(f'Unsafe archive/manifest path: {value!r}')
    return value

def local_file(root: Path, name: str) -> Path:
    path = root.joinpath(*PurePosixPath(safe_name(name)).parts)
    if not path.resolve().is_relative_to(root.resolve()) or path.is_symlink():
        raise ValueError(f'Path escapes package: {name}')
    return path

def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def verify(root: Path) -> dict:
    manifest = json.loads((root/'TRANSFER_MANIFEST.json').read_text(encoding='utf-8'))
    checked = set()
    for row in manifest['files']:
        name = safe_name(row['path'])
        if name in checked:
            raise ValueError(f'Duplicate package entry: {name}')
        checked.add(name)
        raw = local_file(root,name).read_bytes()
        if len(raw) != row['size_bytes'] or sha256(raw) != row['sha256']:
            raise ValueError(f'Package hash/size mismatch: {name}')
    checksum_names = set()
    for line in (root/'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
        digest,name = line.split('  ',1)
        if name in checksum_names or sha256(local_file(root,name).read_bytes()) != digest:
            raise ValueError(f'Checksum mismatch/duplicate: {name}')
        checksum_names.add(name)
    if checksum_names != checked | {'TRANSFER_MANIFEST.json'}:
        raise ValueError('Checksum coverage does not match manifest')
    actual_files = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
    if actual_files != checked | {'TRANSFER_MANIFEST.json','SHA256SUMS.txt'}:
        raise ValueError('Unexpected or missing files in package')
    snapshot = manifest['source_snapshot']
    rows = json.loads(local_file(root,snapshot['manifest']).read_text(encoding='utf-8'))['files']
    prefix = snapshot['prefix']
    expected_names = {prefix+row['path'] for row in rows}
    with zipfile.ZipFile(local_file(root,snapshot['path'])) as archive:
        members = [item.filename for item in archive.infolist() if not item.is_dir()]
        if len(members) != len(set(members)) or set(members) != expected_names:
            raise ValueError('Source ZIP inventory mismatch')
        for row in rows:
            name = safe_name(prefix+safe_name(row['path']))
            raw = archive.read(name)
            git_blob = hashlib.sha1(b'blob '+str(len(raw)).encode('ascii')+b'\0'+raw).hexdigest()
            if len(raw)!=row['size_bytes'] or sha256(raw)!=row['sha256'] or git_blob!=row['git_blob_sha1']:
                raise ValueError(f'Source blob mismatch: {name}')
        for path,digest in ORIGINALS.items():
            raw = archive.read(prefix+path)
            if len(raw)!=5943296 or sha256(raw)!=digest:
                raise ValueError(f'Pinned original mismatch: {path}')
    return dict(status='PASS',package_files=len(checked),source_files=len(rows),
                originals_verified=len(ORIGINALS),handoff_commit=manifest['handoff_commit'],
                device_operations=0,model_calls=0)

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package',type=Path,default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    print(json.dumps(verify(args.package.resolve()),indent=2))

if __name__ == '__main__':
    main()
