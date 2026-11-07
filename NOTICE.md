# Provenance and scope

This project contains device-specific binary patches, build and installation scripts, tests, and supporting assets. The manufacturer's complete firmware source code is not available.

The public source package excludes complete firmware backups read from the device, the sunxi-fel executable, and external Python packages. Rights and licenses for third-party materials remain with their respective rights holders. This notice does not grant a blanket license for third-party materials.

The native installer pins the previously used sunxi-fel.exe to SHA-256 da14ffa7243767d9c8c5579618171fde2956c4b37b82139bb519932aba6e9375. This verifies the expected tool build; it does not constitute an independent security audit.

The owner requested publication of the two unmodified factory application images
V3.6 and V3.8 on 2026-11-07 for reproducible research. Their exact identities and
package names are recorded in original-firmware/manifest.json. They are not
personal 16 MiB flash backups; such backups and device/calibration dumps remain
excluded. This publication does not grant a blanket license to third-party code.
