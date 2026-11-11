"""Build the YS-4470 E2 diode-volume application offline from public V3.8."""

import argparse
from hashlib import sha256
from itertools import groupby
import json
from pathlib import Path
import struct
import sys

from keystone import KS_ARCH_ARM, KS_MODE_ARM, Ks

HERE = Path(__file__).resolve().parent
BASE = 0x7FFFFFE0
BITMAP = 0x8006B688
BITMAP_END = 0x8006DC14
FORMAT = 0x8006EAE0
FONT = 0x8006EAF8
E2_SHA = "b04fb5bca7a052abfc5b1621bf50e03fd4f8116bf5cef849f1994e44d4b603b1"


def digest(data):
    return sha256(data).hexdigest()


def branch(src, dst, link=False):
    delta = dst - src - 8
    if delta % 4 or not -(1 << 25) <= delta < (1 << 25):
        raise ValueError("Unreachable ARM branch")
    return (0xEB000000 if link else 0xEA000000) | ((delta >> 2) & 0xFFFFFF)


def pack_bitmap(raw):
    out = bytearray()
    literal = bytearray()

    def flush():
        while literal:
            out.append(min(127, len(literal)))
            out.extend(literal[:127])
            del literal[:127]

    for value, run in groupby(raw):
        count = sum(1 for _ in run)
        while count >= 3:
            flush()
            take = min(count, 130)
            out.extend((0x80 | (take - 3), value))
            count -= take
        literal.extend(bytes((value,)) * count)
        if len(literal) >= 127:
            flush()
    flush()
    out.append(0)
    return bytes(out)


def build(image):
    if digest(image) != E2_SHA:
        raise ValueError("Expected the exact E2 application")
    if struct.unpack_from("<II", image, FORMAT - BASE) != (BITMAP, BITMAP_END):
        raise ValueError("Unexpected font descriptor")
    pointer = struct.pack("<I", BITMAP)
    if image.find(pointer) != FORMAT - BASE or image.find(pointer, FORMAT - BASE + 1) != -1:
        raise ValueError("Unexpected references to bitmap base")

    bitmap = image[BITMAP - BASE:BITMAP_END - BASE]
    packed = pack_bitmap(bitmap)
    source = (HERE / "volume_overlay.s").read_text(encoding="utf-8")
    program, _ = Ks(KS_ARCH_ARM, KS_MODE_ARM).asm(
        f".equ PACKED_SIZE, {len(packed)}\n{source}", BITMAP, as_bytes=True,
    )
    if len(program) + len(packed) > len(bitmap):
        raise ValueError(f"Overlay and lossless bitmap exceed the original resource ({len(program)} + {len(packed)})")

    output = bytearray(image)
    edits = []

    def replace(address, data, expected):
        offset = address - BASE
        if len(expected) != len(data) or output[offset:offset + len(data)] != expected:
            raise ValueError(f"Unexpected bytes at {address:#x}")
        output[offset:offset + len(data)] = data
        edits.append(dict(address=hex(address), bytes=len(data), before_sha256=digest(expected),
                          after_sha256=digest(data)))

    def word(address, value, expected):
        replace(address, struct.pack("<I", value), struct.pack("<I", expected))

    replace(BITMAP, (program + packed).ljust(len(bitmap), b"\0"), bitmap)
    word(0x80051C0C, branch(0x80051C0C, BITMAP), branch(0x80051C0C, 0x80060A08))
    word(0x8005D048, branch(0x8005D048, BITMAP + 4), branch(0x8005D048, 0x8001B5CC))
    word(0x80006ECC, branch(0x80006ECC, BITMAP + 8, link=True), branch(0x80006ECC, 0x800630A4, link=True))
    word(FONT + 4, BITMAP + 12, 0x8002C844)
    assert output[:32] == image[:32] and len(output) == len(image)
    return bytes(output), dict(
        schema="ys4470.diode-volume.e2.v1", base_application_sha256=E2_SHA,
        application_sha256=digest(output), image_bytes=len(output),
        bitmap_sha256=digest(bitmap), bitmap_bytes=len(bitmap), packed_bytes=len(packed),
        overlay_bytes=len(program), edits=edits, physical_device_operations=0,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    root = args.repo.resolve()
    sys.path.insert(0, str(root / "contributions/COORD-ADC-CADENCE"))
    from reproduce_profiles import reproduce

    manifest = json.loads((root / "original-firmware/manifest.json").read_bytes())
    entry, = (item for item in manifest["images"] if item["version"] == "V3.8")
    original = (root / entry["path"]).read_bytes()
    if len(original) != entry["size_bytes"] or digest(original) != entry["sha256"]:
        raise ValueError("Factory V3.8 failed manifest verification")
    outputs, _ = reproduce(original)
    result, receipt = build(outputs["profiles-E2"])
    receipt["factory_application_sha256"] = entry["sha256"]
    args.out.mkdir(parents=True, exist_ok=True)
    target = args.out / "ys4470-e2-diode-volume-OFFLINE.bin"
    report = args.out / "build-receipt.json"
    for file, data in ((target, result), (report, (json.dumps(receipt, indent=2) + "\n").encode())):
        if file.exists():
            if file.read_bytes() != data:
                raise ValueError(f"Existing output differs: {file}")
        else:
            with file.open("xb") as stream:
                stream.write(data)
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
