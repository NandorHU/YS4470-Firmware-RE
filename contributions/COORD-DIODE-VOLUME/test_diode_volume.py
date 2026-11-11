"""Check the offline E2 volume overlay through original ARM event and PWM paths."""

import argparse
import json
from pathlib import Path
import struct
import sys

from capstone import CS_ARCH_ARM, CS_MODE_ARM, Cs
from capstone.arm import ARM_INS_BL, ARM_OP_IMM
from unicorn import UC_ARCH_ARM, UC_HOOK_CODE, UC_HOOK_MEM_WRITE, UC_MODE_ARM, Uc
from unicorn.arm_const import (
    UC_ARM_REG_CPSR, UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_SP, UC_CPU_ARM_926,
    UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3,
)

from build_diode_volume import BASE, BITMAP, BITMAP_END, FONT, FORMAT, build, digest

CTX, MODE = 0x805AC098, 0x805ABEFC
SETTINGS, RESULT, ACTIVE = 0x805AC770, 0x805AC714, 0x805AB924
PROFILE, ALT = 0x80060A90, CTX + 0x2F0
PWM, STACK, STOP = 0x01C21000, 0x81FF0000, 0x81FFF000
GATE, LOWER, EVENT = 0x80006E4C, 0x800060D0, 0x8002C758
GUI_INIT, GUI_TICK = 0x8004ED34, 0x8005D048
OBJECT_ALLOC, ARRAY_ALLOC = 0x80032800, 0x80032AE4
EVENT_REGISTER, LABEL_SET = 0x800338DC, 0x80032038
CREATORS = {
    0x80034C10: "container", 0x80021F3C: "button", 0x80030AD0: "label",
    0x80033094: "widget", 0x8003E5E4: "widget", 0x8002DD80: "widget", 0x80024390: "widget",
}
PROPERTIES = {
    0x8003A160, 0x8003A2C8, 0x8003A718, 0x8003A778, 0x8003A788, 0x8003A7C8,
    0x8003A7B8, 0x8003AA38, 0x8003AA58, 0x80033B7C, 0x800339BC, 0x80034A50,
}
ARGS = (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)
GUI_TRACE_RANGE = (0x8004ED34, 0x80051C10)
GAIN = dict(zip(range(0, 101, 10), (0.0, 0.25, 0.5, 1.0, 2.0, 3.5, 5.5, 8.5, 12.5, 18.0, 25.0)))


class Replay:
    def __init__(self, image, overlay=None):
        self.u = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        self.u.ctl_set_cpu_model(UC_CPU_ARM_926)
        self.u.mem_map(0x7FFF0000, 0x2100000)
        self.u.mem_write(BASE, image)
        self.u.mem_map(0x01C20000, 0x10000)
        self.image = image
        self.overlay = overlay
        self.init = self.tick = False
        self.next_object, self.next_alloc = 0x81000000, 0x81200000
        self.objects, self.bindings = {}, {}
        self.pwm, self.dispatches, self.allocations = [], [], []
        self.registrations, self.flag_writes, self.mmio_writes = [], [], []
        self.bitmap_writes, self.frees = [], []
        self.stop = STOP
        arm = Cs(CS_ARCH_ARM, CS_MODE_ARM)
        arm.detail = True
        self.leaves = set(CREATORS) | PROPERTIES | {LABEL_SET, EVENT_REGISTER}
        for pc in range(*GUI_TRACE_RANGE, 4):
            for insn in arm.disasm(image[pc - BASE:pc - BASE + 4], pc):
                if insn.id == ARM_INS_BL and insn.operands[0].type == ARM_OP_IMM:
                    self.leaves.add(insn.operands[0].imm & 0xFFFFFFFF)
        self.u.hook_add(UC_HOOK_CODE, self.code)
        self.u.hook_add(UC_HOOK_MEM_WRITE, self.write)

    def get(self, address):
        return struct.unpack("<I", self.u.mem_read(address, 4))[0]

    def put(self, address, value):
        self.u.mem_write(address, struct.pack("<I", value & 0xFFFFFFFF))

    def byte(self, address, value):
        self.u.mem_write(address, bytes((value,)))

    def ret(self, value=0):
        self.u.reg_write(UC_ARM_REG_R0, value)
        self.u.reg_write(UC_ARM_REG_PC, self.u.reg_read(UC_ARM_REG_LR))

    def code(self, u, pc, size, _):
        if pc == self.stop:
            u.emu_stop()
            return
        regs = [u.reg_read(r) for r in ARGS]
        r0, r1, r2, r3 = regs
        lr = u.reg_read(UC_ARM_REG_LR)
        if pc in (OBJECT_ALLOC, ARRAY_ALLOC):
            length = r0 if pc == OBJECT_ALLOC else r1
            assert 0 < length <= BITMAP_END - BITMAP
            addr = self.next_alloc
            self.next_alloc += (length + 15) & ~15
            self.allocations.append((hex(lr), addr, length))
            self.ret(addr)
            return
        if pc == 0x80032A80 and self.overlay and BITMAP <= lr < BITMAP + self.overlay:
            self.frees.append(r0)
            self.ret()
            return
        if pc == LOWER:
            self.pwm.append(regs)
            return
        if pc == 0x8001B030:
            self.dispatches.append((self.get(r0), r1, self.get(r0 + 12)))
            return
        if pc == EVENT_REGISTER:
            self.bindings.setdefault(r0, []).append((r1, r2, r3))
            if self.overlay and BITMAP <= r1 < BITMAP + self.overlay:
                self.registrations.append(r0)
                return
        if self.tick and pc == 0x8001B5CC:
            self.ret()
            return
        if pc in CREATORS and self.init:
            address = self.next_object
            self.next_object += 0x100
            self.objects[address] = dict(kind=CREATORS[pc], parent=r0, pos=[0, 0], size=[0, 0])
            self.ret(address)
            return
        if pc not in self.leaves or not (self.init or pc in PROPERTIES or pc == LABEL_SET):
            return
        obj = self.objects.get(r0)
        if obj is not None:
            if pc == 0x8003A160:
                obj["pos"] = regs[1:3]
            elif pc == 0x8003A2C8:
                obj["size"] = regs[1:3]
            elif pc == 0x8003AA58:
                obj["font"] = r1
            elif pc == LABEL_SET:
                raw = bytes(u.mem_read(r1, 48)).split(b"\0", 1)[0]
                obj["text"] = raw.decode("utf-8", errors="replace")
            elif pc in (0x800339BC, 0x80034A50):
                flags = self.get(r0 + 28)
                self.put(r0 + 28, flags | r1 if pc == 0x800339BC else flags & ~r1)
                self.flag_writes.append((r0, pc))
        if pc == 0x80024CA4:
            self.ret(((r0 >> 8) & 0xF800) | ((r0 >> 5) & 0x7E0) | ((r0 >> 3) & 0x1F))
            return
        self.ret()

    def write(self, u, access, address, size, value, _):
        if 0x01C20000 <= address < 0x01C30000:
            assert address in (0x01C20800, 0x01C2081C, PWM, PWM + 4) and size == 4
            self.mmio_writes.append((hex(address), value))
        if address == FORMAT and size == 4:
            self.bitmap_writes.append(value)

    def call(self, entry, *args, stop=STOP):
        self.stop = stop
        self.u.reg_write(UC_ARM_REG_CPSR, 0x13)
        self.u.reg_write(UC_ARM_REG_SP, STACK)
        self.u.reg_write(UC_ARM_REG_LR, stop)
        for reg, value in zip(ARGS, (*args, 0, 0, 0, 0)):
            self.u.reg_write(reg, value)
        self.u.emu_start(entry, 0, count=260000)
        assert self.u.reg_read(UC_ARM_REG_PC) == stop, (hex(entry), hex(self.u.reg_read(UC_ARM_REG_PC)))
        assert self.u.reg_read(UC_ARM_REG_SP) == STACK and not self.u.reg_read(UC_ARM_REG_CPSR) & 0x80
        return self.u.reg_read(UC_ARM_REG_R0)

    def create(self):
        self.init = True
        self.call(GUI_INIT, CTX)
        self.init = False

    def update(self):
        self.tick = True
        self.call(GUI_TICK)
        self.tick = False

    def hidden(self, obj):
        return bool(self.get(obj + 28) & 1)

    def float_half(self, expected):
        return struct.unpack("<f", struct.pack("<I", self.pwm[-1][2]))[0] == expected


def check_controls(e2, image, receipt):
    baseline = Replay(e2)
    baseline.create()
    app = Replay(image, receipt["overlay_bytes"])
    app.byte(MODE, 3)
    app.byte(MODE + 7, 14)
    app.create()
    assert len(app.registrations) == 2
    down, up = app.registrations
    label, = [p for p, o in app.objects.items() if o.get("text") == "60%"]
    caption, = [p for p, o in app.objects.items() if o.get("text") == "Volume"]
    objects = (caption, down, label, up)
    assert [app.objects[p]["pos"] for p in objects] == [[226, 74], [288, 66], [333, 74], [383, 66]]
    assert [app.objects[p]["size"] for p in objects] == [[58, 24], [42, 38], [46, 24], [42, 38]]
    root = app.get(CTX + 0x268)
    assert app.objects[root]["size"] == [854, 480] and all(app.objects[p]["parent"] == root for p in objects)
    for off in (4, 12):
        obj = app.get(PROFILE + off)
        original = baseline.get(PROFILE + off)
        assert app.objects[obj] == baseline.objects[original] and app.bindings[obj] == baseline.bindings[original]
    beta = app.get(PROFILE + 4)
    assert app.objects[beta]["pos"][0] == 430
    assert all(app.objects[p]["pos"][0] + app.objects[p]["size"][0] < 430 for p in objects)

    for left, right in zip(objects, objects[1:]):
        assert app.objects[left]["pos"][0] + app.objects[left]["size"][0] < app.objects[right]["pos"][0]
    assert all(app.objects[p]["font"] == 0x8006EAF8 for p in (caption, label))
    assert all(app.objects[p]["font"] == app.objects[beta]["font"] == 0x80080888 for p in (down, up))
    for p, delta, text in ((down, 0xFFFFFFFF, "-"), (up, 1, "+")):
        assert any(o.get("text") == text and o["parent"] == p for o in app.objects.values())
        ext = app.get(p + 8)
        desc = app.get(ext + 12)
        assert bytes(app.u.mem_read(ext + 26, 1)) == b"\1"
        assert app.get(desc + 4) == delta and bytes(app.u.mem_read(desc + 8, 1)) == b"\x01"
        assert app.bindings[p] == [(app.get(desc), 1, delta)]

    assert all(app.hidden(p) for p in objects)
    app.byte(MODE, 3)
    app.byte(MODE + 7, 14)
    app.put(app.get(ALT) + 28, 1)
    app.update()
    assert not any(app.hidden(p) for p in objects)
    count = len(app.flag_writes)
    app.update()
    assert len(app.flag_writes) == count
    app.call(EVENT, up, 14, 0)
    assert not app.dispatches and app.objects[label]["text"] == "60%"

    # Idle clicks change only the next tone. A non-diode gate still reads the shared setting.
    app.put(SETTINGS + 12, 80)
    app.put(SETTINGS + 16, 1)
    app.call(EVENT, down, 1, 0)
    assert app.objects[label]["text"] == "50%" and not app.pwm
    for return_pc, half, pitch in ((0x80003A78, GAIN[50], 1321), (0x80060CB0, GAIN[50], 1321),
                                   (STOP, 40.0, 2888)):
        app.call(GATE, 5, 1, stop=return_pc)
        assert app.float_half(half) and app.pwm[-1][1] == pitch
    assert app.get(SETTINGS + 12) == 80

    # Continuous tone is active. Presses go through the original dispatch and write real PWM logic.
    app.byte(MODE + 10, 2)
    app.put(RESULT + 0x50, 13)
    app.put(ACTIVE, 1)
    levels = []
    steps = [(down, level) for level in range(40, -1, -10)] + [(down, 0)]
    steps += [(up, level) for level in range(10, 101, 10)]
    for button, expected in steps:
        prev = len(app.pwm)
        app.call(EVENT, button, 1, 0)
        assert app.objects[label]["text"] == f"{expected}%"
        period = app.get(PWM + 4)
        if levels and expected == levels[-1][0]:
            assert len(app.pwm) == prev
        else:
            assert len(app.pwm) == prev + 1 and app.float_half(GAIN[expected])
        assert (period >> 16) + 1 == 18168
        assert bool(period & 0xFFFF) == bool(expected)
        assert app.get(RESULT + 0x50) == 13 and app.get(ACTIVE) == 1 and app.get(SETTINGS + 12) == 80
        ticks = period & 0xFFFF
        assert abs(100 * ticks / 18168 - GAIN[expected]) < 0.01
        for return_pc in (0x80003A78, 0x80060CB0):
            app.call(GATE, 5, 1, stop=return_pc)
            assert app.float_half(GAIN[expected]) and app.get(PWM + 4) == period
        app.put(RESULT + 0x50, 13)
        levels.append([expected, ticks])

    # Key beep ownership, mode transition, and original alternate header.
    app.put(RESULT + 0x50, 3)
    pwm_count = len(app.pwm)
    app.call(EVENT, down, 1, 0)
    assert app.objects[label]["text"] == "90%" and len(app.pwm) == pwm_count
    app.byte(MODE, 4)
    app.update()
    assert all(app.hidden(p) for p in objects)
    app.call(EVENT, down, 1, 0)
    assert app.objects[label]["text"] == "90%" and len(app.pwm) == pwm_count
    app.byte(MODE, 3)
    app.update()
    assert not any(app.hidden(p) for p in objects)
    for _ in range(10):
        app.call(EVENT, up, 1, 0)
    assert app.objects[label]["text"] == "100%" and len(app.pwm) == pwm_count
    app.put(app.get(ALT) + 28, 0)
    app.update()
    assert all(app.hidden(p) for p in objects)
    return dict(positions=[app.objects[p]["pos"] for p in objects],
                sizes=[app.objects[p]["size"] for p in objects], levels=levels, requested_pwm_duty_percent=GAIN,
                original_beta_and_profile_geometry_preserved=True,
                original_indirect_dispatches=len(app.dispatches), real_pwm_updates=len(app.pwm))


def check_font(e2, image, receipt):
    old, new = Replay(e2), Replay(image, receipt["overlay_bytes"])
    original = e2[BITMAP - BASE:BITMAP_END - BASE]
    old_entry, new_entry = old.get(FONT + 4), new.get(FONT + 4)
    assert old_entry == 0x8002C844 and new_entry == BITMAP + 12
    for point in range(32, 127):
        expected = old.call(old_entry, FONT, point)
        got = new.call(new_entry, FONT, point)
        assert (expected == 0 and got == 0) or got == new.get(FORMAT) + expected - BITMAP
    bitmap, = new.bitmap_writes
    assert bytes(new.u.mem_read(bitmap, len(original))) == original
    assert len(new.allocations) == 1 and new.allocations[0][1:] == (bitmap, len(original))
    corrupt = Replay(image, receipt["overlay_bytes"])
    corrupt.byte(BITMAP + receipt["overlay_bytes"], 0)
    assert corrupt.call(new_entry, FONT, 65) == 0 and corrupt.get(FORMAT) == BITMAP
    assert corrupt.frees == [corrupt.allocations[0][1]] and not corrupt.bitmap_writes
    metrics = 0x81110000
    widths = {}
    for label, font, available in (("Volume", 0x8006EAF8, 58), ("100%", 0x8006EAF8, 46),
                                    ("-", 0x80080888, 42), ("+", 0x80080888, 42)):
        width = 0
        for idx, ch in enumerate(label):
            following = ord(label[idx + 1]) if idx + 1 < len(label) else 0
            assert new.call(0x8002C9C0, font, metrics, ord(ch), following) == 1
            width += struct.unpack("<H", new.u.mem_read(metrics + 4, 2))[0]
        assert width + 2 * (len(label) - 1) <= available
        widths[label] = width
    return dict(decoded_bitmap_sha256=digest(original), lookup_cases=95, allocation_bytes=len(original),
                truncated_bitmap_rejected=True, volume_label_glyph_advances_px=widths)


def check_profiles(e2, image, original, root):
    sys.path.insert(0, str(root / "contributions/COORD-ADC-CADENCE"))
    import trace_profiles as trace
    init = trace.restore_globals(original)
    rows = []
    for profile in range(4):
        for scenario in ("stable-low", "contact-open"):
            summaries = []
            for app in (e2, image):
                trace.E2_SHA = digest(app)
                machine = trace.ProfileMachine(app, profile, 1, scenario, init=init)
                summaries.append(machine.run(185))
            old, new = summaries
            kinds = {"request", "accepted", "renderer", "sound_control"}
            old_events = [e for e in old["events"] if e["kind"] in kinds]
            new_events = [e for e in new["events"] if e["kind"] in kinds]
            assert len(old_events) == len(new_events)
            for before, after in zip(old_events, new_events):
                if after["kind"] == "sound_control" and after["args"][1] == 1321 and after["args"][2]:
                    assert struct.unpack("<f", struct.pack("<I", after["args"][2]))[0] == GAIN[60]
                    after = after | {"args": [*after["args"][:2], before["args"][2], after["args"][3]]}
                assert before == after, (profile, scenario, before, after)
            assert new["counts"]["sound_control"] >= 1
            rows.append(dict(profile=profile, scenario=scenario, events=len(new_events)))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    root = args.repo.resolve()
    sys.path.insert(0, str(root / "contributions/COORD-ADC-CADENCE"))
    from reproduce_profiles import reproduce
    original = (root / "original-firmware/V3.8/f1c100s.bin").read_bytes()
    e2 = reproduce(original)[0]["profiles-E2"]
    image, receipt = build(e2)
    assert args.candidate.read_bytes() == image
    report = dict(application_sha256=digest(image), controls=check_controls(e2, image, receipt),
                  font=check_font(e2, image, receipt), profiles=check_profiles(e2, image, original, root),
                  models=["LVGL layout/text leaves", "allocation", "UART and RTOS schedule in the profile replay",
                          "PWM registers as RAM shadows"], physical_device_operations=0)
    args.out.write_bytes((json.dumps(report, indent=2) + "\n").encode())
    print("PASS: E2 GUI, original event dispatch and PWM, 95 font lookups, 8 profile regressions")


if __name__ == "__main__":
    main()
