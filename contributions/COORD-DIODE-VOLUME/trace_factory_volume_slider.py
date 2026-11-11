"""Follow the factory volume slider through preview sound and settings persistence."""

import argparse
import hashlib
import json
import struct
from itertools import product
from pathlib import Path

from trace_factory_settings_roundtrip import BASE, SETTING, SOUND_ENABLE, UI, SettingsReplay
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3

SLIDER, SLIDER_GET, SOUND, PWM = 0x80057D34, 0x80021C6C, 0x80006E4C, 0x800060D0
GLOBAL_VOLUME, ACTIVE, COUNTDOWN = SETTING + 0xC, 0x805AB924, 0x805AC764
WIDGET = 0x10017600
WINDOWS = ((SLIDER, 0x80057D6C), (SLIDER_GET, 0x80021C80),
           (SOUND, 0x80006EF4), (0x800630A4, 0x800630D4))


class VolumeReplay(SettingsReplay):
    def __init__(self, raw, slider, animating):
        super().__init__(raw)
        self.slider, self.animating = slider, animating
        self.preview, self.volume_writes = [], []
        self.frequency = int.from_bytes(raw[0x80063970 - BASE:0x80063972 - BASE], "little")

    def code(self, u, pc, size, data):
        if self.phase == "volume" and pc == PWM:
            r0, r1, r2, r3, lr = (u.reg_read(reg) for reg in (
                UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_LR,
            ))
            assert (r0, r1, r3, lr) == (0, self.frequency, 1, 0x80006EE4)
            amplitude = struct.unpack("<f", struct.pack("<I", r2))[0]
            self.preview.append([hex(lr), r1, amplitude])
            self.return_leaf(u, lr, 0)
            return
        if self.phase == "volume" and any(lo <= pc < hi for lo, hi in WINDOWS):
            assert size == 4
            self.coverage[pc] = bytes(u.mem_read(pc, 4)).hex()
            return
        super().code(u, pc, size, data)

    def write(self, u, access, address, size, value, data):
        if self.phase == "volume" and address in (GLOBAL_VOLUME, ACTIVE, COUNTDOWN):
            pc = u.reg_read(UC_ARM_REG_PC)
            assert size == 4 and (pc, address) in (
                (0x80057D58, GLOBAL_VOLUME), (0x80006EE8, ACTIVE), (0x80006EB8, COUNTDOWN),
            )
            self.volume_writes.append([hex(pc), hex(address), value])
            return
        super().write(u, access, address, size, value, data)

    def before_save_event(self):
        self.put(SOUND_ENABLE, 1)
        self.put(UI + 0x3A0, WIDGET)
        self.put(WIDGET + 0x48, 0 if self.animating else 0xFFFFFFFF)
        self.put(WIDGET + 0x24, 19 if self.animating else self.slider)
        self.put(WIDGET + 0x44, self.slider if self.animating else 19)
        self.phase = "volume"
        try:
            self.invoke(SLIDER)
        finally:
            self.phase = None
        gain = min(self.slider, 100) // 2
        assert self.read(GLOBAL_VOLUME) == gain
        assert self.preview == [["0x80006ee4", self.frequency, gain // 2]]
        assert self.read(ACTIVE) == 1 and self.read(COUNTDOWN) == 3
        assert not self.saved

    def run_volume(self):
        row = self.roundtrip(1, 1)
        assert self.read(GLOBAL_VOLUME) == min(self.slider, 100) // 2
        return dict(slider_value=self.slider, animating=self.animating, preview=self.preview[0],
                    ram_writes=self.volume_writes, saved_global_word=self.read(GLOBAL_VOLUME),
                    save_event=row["event"], record_crc32=row["crc32"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    manifest = json.loads(Path("original-firmware/manifest.json").read_bytes())
    assert manifest["linked_base"] == hex(BASE)
    images, observations = {}, []
    for item in manifest["images"]:
        raw = Path(item["path"]).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        assert digest == item["sha256"] and len(raw) == item["size_bytes"]
        assert int.from_bytes(raw[0x80054B28 - BASE:0x80054B2C - BASE], "little") == SLIDER
        coverage, cases = {}, []
        for slider, animating in product((0, 1, 2, 37, 99, 100, 101), (False, True)):
            replay = VolumeReplay(raw, slider, animating)
            cases.append(replay.run_volume())
            coverage.update(replay.coverage)
        images[item["version"]] = digest
        observations.append(dict(cases=cases, instruction_bytes={hex(pc): v for pc, v in sorted(coverage.items())}))
    assert images.keys() == {"V3.6", "V3.8"} and observations[0] == observations[1]
    report = dict(schema="ys4470.factory-volume-slider.v1", images=images, **observations[0], limits=[
        "The original slider handler is invoked with a seeded slider object. Native getter, integer scaling and sound control execute to the modeled PWM leaf.",
        "The separate original save event and valid-record loader round-trip the global field through a synthetic in-memory storage boundary.",
        "The observed numeric preview argument is a firmware value, not a measured acoustic amplitude. No independent persistent diode-volume field is established.",
    ])
    args.out.write_bytes((json.dumps(report, indent=2) + "\n").encode())
    print("PASS 14 original global-volume slider cases per image, 28 total")


if __name__ == "__main__":
    main()
