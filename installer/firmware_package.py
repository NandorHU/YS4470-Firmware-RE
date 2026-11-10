"""Read and create a replaceable, application-only firmware package."""

from dataclasses import dataclass
import json
from pathlib import Path
import re
import struct
from zipfile import BadZipFile, ZIP_DEFLATED, ZIP_STORED, ZipFile

import ys4470_patch as patch

SCHEMA = "ys4470.firmware-package.v1"
APP_BYTES = 0x5AB000
MANIFEST = "manifest.json"
IMAGE = "firmware.bin"
MAX_MANIFEST = 4096
FAMILIES = {
    "V3.6": "7523b2e91dd8627ffebfc7ac0525c0607a56df4cece04028a9c3a8ee558f6eb9",
    "V3.8": "7e7d7230155fe0790eb48531de2ef463bb122c0ae1a820ab6d10cf2e60f50290",
}
EXPERIMENTAL_V38 = frozenset({
    "884c39524942cf42580b52c0ce3ed8b33dab8d8fc4d3addd6266d1c9831c551e",
    "9890a3c671987b0aa75a505e4f389532ca102f9dcf306394daa45a9328bc91e1",
    "b04fb5bca7a052abfc5b1621bf50e03fd4f8116bf5cef849f1994e44d4b603b1",
    "e8c00750df2fc465b182c60d2c32dd8cd87cafc4a5cbff4f7e6abbfaec48c76a",
})
FIELDS = {"schema", "device", "family", "factory_sha256", "label", "image_sha256", "image_bytes"}
HEX_SHA = re.compile(r"[0-9a-f]{64}")


class PackageError(ValueError):
    pass


@dataclass(frozen=True)
class FirmwarePackage:
    label: str
    family: str
    factory_sha256: str
    image_sha256: str
    image: bytes

    def validate(self):
        if not isinstance(self.label, str) or not 1 <= len(self.label) <= 80 or not self.label.isprintable():
            raise PackageError("Invalid firmware package name.")
        if self.family not in FAMILIES or FAMILIES[self.family] != self.factory_sha256:
            raise PackageError("Unsupported factory firmware family.")
        if (not isinstance(self.image, bytes) or len(self.image) != APP_BYTES
                or self.image[4:12] != b"eGON.EXE"
                or struct.unpack_from("<I", self.image, 16)[0] != APP_BYTES):
            raise PackageError("Expected a complete YS-4470 application image, not a full flash backup.")
        if not isinstance(self.image_sha256, str) or patch.sha(self.image) != self.image_sha256:
            raise PackageError("Firmware image SHA-256 does not match the package manifest.")

    def manifest(self):
        return dict(schema=SCHEMA, device="YS-4470", family=self.family, factory_sha256=self.factory_sha256,
                    label=self.label, image_sha256=self.image_sha256, image_bytes=len(self.image))


def unique_fields(pairs):
    result = dict(pairs)
    if len(result) != len(pairs):
        raise PackageError("The firmware manifest has duplicate fields.")
    return result


def read_package(path):
    path = Path(path)
    try:
        with path.open("rb") as stream:
            stream.seek(0, 2)
            if stream.tell() > APP_BYTES + 65536:
                raise PackageError("Firmware package is too large.")
            stream.seek(0)
            with ZipFile(stream) as archive:
                entries = archive.infolist()
                if len(entries) != 2 or {entry.filename for entry in entries} != {MANIFEST, IMAGE}:
                    raise PackageError("Expected exactly manifest.json and firmware.bin in the package.")
                for entry in entries:
                    if entry.flag_bits & 1 or entry.compress_type not in (ZIP_STORED, ZIP_DEFLATED):
                        raise PackageError("Unsupported package compression or encryption.")
                if archive.getinfo(MANIFEST).file_size > MAX_MANIFEST or archive.getinfo(IMAGE).file_size != APP_BYTES:
                    raise PackageError("Invalid firmware package member size.")
                meta = json.loads(archive.read(MANIFEST), object_pairs_hook=unique_fields)
                if (not isinstance(meta, dict) or set(meta) != FIELDS or meta["schema"] != SCHEMA
                        or meta["device"] != "YS-4470" or meta["image_bytes"] != APP_BYTES
                        or not all(isinstance(meta[key], str) for key in FIELDS - {"image_bytes"})):
                    raise PackageError("Unsupported YS-4470 firmware manifest.")
                package = FirmwarePackage(meta["label"], meta["family"], meta["factory_sha256"],
                                          meta["image_sha256"], archive.read(IMAGE))
    except (OSError, BadZipFile, RuntimeError, UnicodeError, json.JSONDecodeError, NotImplementedError) as exc:
        raise PackageError(f"Cannot read the firmware package: {exc}") from exc
    package.validate()
    return package


def create_package(image, family, label, output):
    if family not in FAMILIES:
        raise PackageError("Unsupported factory firmware family.")
    package = FirmwarePackage(label, family, FAMILIES[family], patch.sha(image), image)
    package.validate()
    known = known_family(package.image_sha256, patch.load_patch())
    if known and known != family:
        raise PackageError(f"This image belongs to {known}, not {family}.")
    with ZipFile(output, "x", ZIP_DEFLATED, compresslevel=9) as archive:
        archive.writestr(MANIFEST, json.dumps(package.manifest(), indent=2) + "\n")
        archive.writestr(IMAGE, image)
    return package


def known_family(app_sha256, patch_data):
    if app_sha256 in EXPERIMENTAL_V38:
        return "V3.8"
    for variant in patch_data["variants"].values():
        for original, row in variant["inputs"].items():
            if app_sha256 in (original, row["output_sha256"]):
                return row["version"]
    return None


def recorded_family(app_sha256, backups):
    families = set()
    for path in Path(backups).glob("*/result.json"):
        try:
            with path.open("rb") as stream:
                row = json.loads(stream.read(8192))
        except (OSError, UnicodeError, ValueError, RecursionError):
            continue
        if not isinstance(row, dict):
            continue
        family = row.get("firmware_family")
        if (row.get("success") is True and row.get("action") == "install"
                and isinstance(family, str) and family in FAMILIES
                and row.get("factory_sha256") == FAMILIES[family]
                and row.get("application_sha256") == app_sha256
                and isinstance(row.get("full_flash_sha256"), str)
                and HEX_SHA.fullmatch(row["full_flash_sha256"])):
            families.add(family)
    return next(iter(families)) if len(families) == 1 else None
