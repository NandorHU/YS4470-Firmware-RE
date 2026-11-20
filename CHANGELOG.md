# 2.0.0-beta.6-v2v4 — November 20, 2026

- Standalone Windows installer with embedded firmware; no separate factory-image download or personal firmware input required.
- Beta Diode switches between v2 and v4; v2 is the power-on default.
- Faster polling, a fixed-range request and additional measuring-chip configuration; v4 adds early contact-tone logic. No system-CPU overclock.
- Owner hardware feedback: substantially faster than earlier builds, with near-instant audible feedback — a practical responsiveness breakthrough.
- Quantitative latency, accuracy and full mode regression remain outstanding; early tone is not a stable measurement indication.

# 1.0 - November 2, 2026

First numbered build based on the tested Beta3 firmware.

- English switch label changed to highspeedv2.
- Retains the diode-response and display-update improvements.
- Adds continuous diode sound with a finite, measurement-refreshed watchdog; the timed-tone fallback remains available.
- Reproducible hash-verified build and Windows FEL installer preparation, complete readback verification, percentage progress, and Beta3 rollback.

This build was installed and tested on a device. The full flash readback matched the intended image, and version 1.0 works well. Quantitative latency measurements and complete regression testing remain outstanding. The build version identifies this package; the manufacturer's displayed version string is unchanged.
