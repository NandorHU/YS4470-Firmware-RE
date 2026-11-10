"""Create a replaceable YS-4470 package from a reviewed application image."""

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "patcher"))
from firmware_package import FAMILIES, create_package


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("--family", choices=FAMILIES, required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    package = create_package(args.image.read_bytes(), args.family, args.label, args.out)
    print(f"{package.label} ({package.family}): {package.image_sha256}")


if __name__ == "__main__":
    main()
