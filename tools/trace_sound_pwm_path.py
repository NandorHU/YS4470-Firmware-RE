"""Execute original sound gate, arithmetic, pinmux and PWM code on ARM926.

PIO/PWM addresses are ordinary emulator RAM shadows. No physical device
access occurs. ResultDispatch qualification is tested as a separate slice.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import struct
from pathlib import Path

from capstone import CS_ARCH_ARM, CS_MODE_ARM, Cs
from unicorn import (Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_PROT_READ, UC_PROT_WRITE,
                     UC_PROT_EXEC, UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE)
from unicorn.arm_const import (UC_CPU_ARM_926, UC_ARM_REG_CPSR, UC_ARM_REG_R0,
                               UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3,
                               UC_ARM_REG_R4, UC_ARM_REG_R7, UC_ARM_REG_R11,
                               UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC)

from emulate_state5_parser import BASE, EXPECTED_INPUTS

GATE, LOWER, PWM_CONFIG = 0x80006E4C, 0x800060D0, 0x80042D40
SETTINGS, RESULT, UI, ACTIVE = 0x805AC770, 0x805AC714, 0x805ABEFC, 0x805AB924
PIO, PWM, STACK, TOP, RETURN = 0x01C20800, 0x01C21000, 0x10000000, 0x10000F00, 0x80006FF8
MMIO = {PIO, PIO + 0x1C, PWM, PWM + 4}
TONES = (2000, 2222, 2444, 2666, 2888, 3110, 3332, 3554, 3776, 4000)


def f32(value):
    return struct.unpack("<f", struct.pack("<f", value))[0]


def bits(value):
    return struct.unpack("<I", struct.pack("<f", value))[0]


def signed(value):
    return value if value < 0x80000000 else value - 0x100000000


class SoundMachine:
    def __init__(self, image):
        self.mu = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        self.mu.ctl_set_cpu_model(UC_CPU_ARM_926)
        self.code_pages = (0x80000000, 0x80003000, 0x80006000,
                           0x80042000, 0x80062000, 0x80063000)
        for page in self.code_pages:
            self.mu.mem_map(page, 0x1000, UC_PROT_READ | UC_PROT_EXEC)
            self.mu.mem_write(page, image[page - BASE:page - BASE + 0x1000])
        for page in (0x805AB000, 0x805AC000, STACK, 0x01C20000, PWM):
            self.mu.mem_map(page, 0x1000, UC_PROT_READ | UC_PROT_WRITE)
        self.trace, self.lower_calls, self.config_calls, self.pio_calls = [], [], [], []
        self.stops = {RETURN}
        self.mu.hook_add(UC_HOOK_CODE, self.on_code)
        self.mu.hook_add(UC_HOOK_MEM_READ | UC_HOOK_MEM_WRITE, self.on_memory)

    def args(self):
        return [self.mu.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)]

    def on_code(self, mu, address, size, user_data):
        if address in self.stops:
            mu.emu_stop()
            return
        if address & ~0xFFF not in self.code_pages:
            raise RuntimeError(f"execution left admitted code pages: {address:#x}")
        if address == LOWER:
            self.lower_calls.append(self.args())
        elif address == PWM_CONFIG:
            self.config_calls.append(self.args())
        elif address == 0x8000302C:
            self.pio_calls.append(self.args())

    def on_memory(self, mu, access, address, size, value, user_data):
        from unicorn import UC_MEM_WRITE
        if 0x01C20000 <= address < 0x01C22000:
            if address not in MMIO or size != 4:
                raise RuntimeError(f"unexpected shadow MMIO {address:#x}/{size}")
            self.trace.append({"operation": "write" if access == UC_MEM_WRITE else "read",
                               "address": hex(address), "value": value if access == UC_MEM_WRITE else self.word(address)})
        elif access == UC_MEM_WRITE:
            if not (STACK <= address and address + size <= STACK + 0x1000 or
                    (address, size) in ((ACTIVE, 4), (RESULT + 0x50, 4))):
                raise RuntimeError(f"unexpected RAM write {address:#x}/{size}")

    def word(self, address):
        return struct.unpack("<I", self.mu.mem_read(address, 4))[0]

    def reset(self, enabled=1, active=0, duty_setting=90, pwm_seed=0):
        mu = self.mu
        mu.mem_write(STACK, bytes(0x1000))
        for address, value in ((SETTINGS + 0x10, enabled), (SETTINGS + 0xC, duty_setting),
                               (ACTIVE, active), (RESULT + 0x50, 0x11223344),
                               (PIO, 0xA5A5A5A5), (PIO + 0x1C, 0xA5A5A5A5),
                               (PWM, pwm_seed), (PWM + 4, 0x55667788)):
            mu.mem_write(address, struct.pack("<I", value))
        mu.reg_write(UC_ARM_REG_CPSR, 0x13)
        mu.reg_write(UC_ARM_REG_SP, TOP)
        mu.reg_write(UC_ARM_REG_LR, RETURN)
        self.trace.clear(); self.lower_calls.clear(); self.config_calls.clear(); self.pio_calls.clear()

    def run(self, start=GATE, stops=(RETURN,)):
        self.stops = set(stops)
        self.mu.emu_start(start, 0x80006FFC, count=100000)
        if self.mu.reg_read(UC_ARM_REG_PC) not in self.stops:
            raise RuntimeError("sound experiment exceeded its instruction bound")

    def gate(self, selector, action, enabled, active, duty_setting=90, seed=0):
        self.reset(enabled, active, duty_setting, seed)
        self.mu.reg_write(UC_ARM_REG_R0, selector & 0xFFFFFFFF)
        self.mu.reg_write(UC_ARM_REG_R1, action)
        self.run()
        if self.mu.reg_read(UC_ARM_REG_SP) != TOP:
            raise AssertionError("gate stack not restored")
        return {"active": self.word(ACTIVE), "result_control": self.word(RESULT + 0x50),
                "pio_cfg": self.word(PIO), "pio_pull": self.word(PIO + 0x1C),
                "pwm_ctrl": self.word(PWM), "pwm_period": self.word(PWM + 4),
                "lower_calls": list(self.lower_calls), "pwm_config_calls": list(self.config_calls),
                "pio_calls": list(self.pio_calls), "shadow_mmio_trace": list(self.trace)}

    def qualifier(self, mode, fast, command):
        self.reset()
        self.mu.mem_write(UI, bytes([mode]))
        self.mu.mem_write(UI + 7, bytes([command]))
        self.mu.mem_write(SETTINGS + 0x18, struct.pack("<I", fast))
        self.mu.reg_write(UC_ARM_REG_R11, UI)
        self.run(0x8000386C, (0x80003910, 0x8000388C))
        if self.trace:
            raise AssertionError("result qualifier unexpectedly accessed MMIO")
        return self.mu.reg_read(UC_ARM_REG_PC) == 0x80003910


def oracle(selector, action, enabled, active, duty_setting, seed):
    selector = max(1, min(10, signed(selector & 0xFFFFFFFF)))
    called = enabled == 1 and (action == 1 or active != 0)
    if not called:
        return {"active": active, "result_control": 0x11223344,
                "pwm_ctrl": seed, "pwm_period": 0x55667788,
                "pio_cfg": 0xA5A5A5A5, "pio_pull": 0xA5A5A5A5,
                "lower_calls": [], "pwm_config_calls": [], "pio_calls": []}
    frequency = TONES[selector - 1]
    period = 1000000000 // frequency
    half = duty_setting // 2 if action == 1 else 0
    duty = int(f32(f32(f32(period) * f32(f32(half) * 10.0)) / 1000.0))
    cycles = (24000000 * period + 500000000) // 1000000000
    active_cycles = cycles * duty // period
    return {"active": 1 if action == 1 else 0, "result_control": 3 if action == 1 else 0,
            "pwm_ctrl": (seed & ~0x3FFF) | 0x7F,
            "pwm_period": ((cycles - 1) << 16) | (active_cycles & 0xFFFF),
            "pio_cfg": (0xA5A5A5A5 & ~(15 << 8)) | (3 << 8),
            "pio_pull": 0xA5A5A5A5 & ~(3 << 4),
            "lower_calls": [[0, frequency, bits(float(half)), 1]],
            "pwm_config_calls": [[0, duty, period, 1]],
            "pio_calls": [[PIO, 2, 3, 0]]}


def collect(label, path):
    image = path.read_bytes()
    if hashlib.sha256(image).hexdigest() != EXPECTED_INPUTS.get(label):
        raise ValueError("only pinned originals accepted")
    if struct.unpack_from("<10H", image, 0x80063968 - BASE) != TONES:
        raise AssertionError("tone table mismatch")
    prescalers = struct.unpack_from("<16I", image, 0x80063ACC - BASE)
    if prescalers != (120, 180, 240, 360, 480, 0, 0, 0, 12000, 24000, 36000, 48000, 72000, 0, 0, 0):
        raise AssertionError("PWM prescaler table mismatch")
    machine = SoundMachine(image)
    selectors = (0, 1, 5, 10, 11, 0xFFFFFFFF, 0x80000000, 0x7FFFFFFF)
    vectors = [(*case, 90, seed) for case in itertools.product(selectors, (0, 1, 2), (0, 1, 2), (0, 1, 2))
               for seed in (0,)]
    vectors += [(selector, 1, 1, 0, level, seed) for selector, level, seed in
                itertools.product(range(1, 11), (0, 1, 2, 49, 50, 89, 90, 99, 100), (0, 0xABCDEF00))]
    fingerprint = hashlib.sha256()
    for case in vectors:
        actual = machine.gate(*case)
        expected = oracle(*case)
        if {k: actual[k] for k in expected} != expected:
            raise AssertionError((case, actual, expected))
        called = bool(expected["lower_calls"])
        if called:
            writes = [r for r in actual["shadow_mmio_trace"] if r["operation"] == "write"]
            if not writes or writes[0]["address"] != hex(PIO) or writes[-1]["address"] != hex(PWM):
                raise AssertionError("unexpected first/last MMIO write")
        elif actual["shadow_mmio_trace"]:
            raise AssertionError("disabled/no-op gate accessed MMIO")
        fingerprint.update(json.dumps([case, actual], sort_keys=True).encode())
    qualifier_cases = list(itertools.product((0, 3, 4, 5, 255), (0, 1, 2, 0xFFFFFFFF), (13, 14, 34, 255)))
    for mode, fast, command in qualifier_cases:
        actual = machine.qualifier(mode, fast, command)
        if actual != (mode == 4 and fast == 1 and command == 34):
            raise AssertionError("Fast CONT branch qualifier mismatch")
    # Execute original sentinel-off argument setup into the complete gate path.
    machine.reset(enabled=1, active=1)
    machine.run(0x8000384C, (0x80003858,))
    if machine.lower_calls != [[0, 2000, 0, 1]] or machine.word(ACTIVE) != 0:
        raise AssertionError("sentinel off call failed")
    examples = []
    for case in ((5, 1, 1, 0, 90, 0), (0, 0, 1, 1, 90, 0), (5, 1, 0, 1, 90, 0)):
        examples.append({"arguments": list(case), "observed": machine.gate(*case)})
    md = Cs(CS_ARCH_ARM, CS_MODE_ARM)
    windows = {}
    for name, start, end in (("gate", GATE, 0x80006F04), ("lower", LOWER, 0x8000618C),
                             ("pinmux", 0x8000302C, 0x800030B4),
                             ("pwm_config", PWM_CONFIG, 0x80042F2C),
                             ("result_qualifier", 0x8000386C, 0x8000388C)):
        blob = image[start - BASE:end - BASE]
        windows[name] = {"start": hex(start), "end_exclusive": hex(end), "sha256": hashlib.sha256(blob).hexdigest(),
                         "listing_scope": "per-word decode includes literals; actual execution is separately bounded",
                         "assembly": [{"address": hex(i.address), "assembly": f"{i.mnemonic} {i.op_str}"}
                                      for a in range(start, end, 4) for i in md.disasm(image[a - BASE:a - BASE + 4], a)]}
    return {"version": label, "input_sha256": hashlib.sha256(image).hexdigest(),
            "gate_cases_passed": len(vectors), "qualifier_cases_passed": len(qualifier_cases),
            "sentinel_off_calls_passed": 1, "failed": 0,
            "results_sha256": fingerprint.hexdigest(), "examples": examples, "windows": windows,
            "unchanged_pwm_prescaler_table": {"address": "0x80063acc", "values": list(prescalers)},
            "unclassified_version_delta_words": [{"linked_address": hex(0x80063AA8 + 4 * i),
                                                    "file_offset": hex(0x63AC8 + 4 * i), "value": value}
                                                   for i, value in enumerate(struct.unpack_from("<9I", image, 0x80063AA8 - BASE))]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", action="append", required=True, metavar="VERSION=PATH")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    results = [collect(label, Path(path)) for label, path in (s.split("=", 1) for s in args.input)]
    shared = results[0]["windows"]
    for result in results:
        if {k: v["sha256"] for k, v in result["windows"].items()} != {k: v["sha256"] for k, v in shared.items()}:
            raise AssertionError("sound code windows differ across originals")
        result["windows"] = {k: {"start": v["start"], "end_exclusive": v["end_exclusive"], "sha256": v["sha256"]} for k, v in result["windows"].items()}
    report = {"schema": "ys4470.sound-pwm-path.v1", "date": "2026-11-07", "cpu_model": "UC_CPU_ARM_926",
              "tone_frequencies_requested": list(TONES), "pwm_shadow": hex(PWM), "pio_shadow": hex(PIO),
              "shared_assembly_windows": shared, "versions": results,
              "version_delta_address_correction": {"link_base": hex(BASE),
                                                    "changed_file_word_range": "0x63ac8..0x63ae8",
                                                    "changed_linked_word_range": "0x80063aa8..0x80063ac8",
                                                    "prescaler_table": "0x80063acc (outside changed words)",
                                                    "note": "Earlier prose confused file offsets with linked addresses by 0x20; raw diff evidence already had correct mappings."},
              "external_reference_urls": ["https://github.com/torvalds/linux/blob/master/drivers/pinctrl/sunxi/pinctrl-suniv-f1c100s.c",
                                          "https://github.com/torvalds/linux/blob/master/drivers/pwm/pwm-sun4i.c"],
              "limits": ["MMIO uses plain emulator RAM shadows, not physical device access or a dynamic peripheral model.",
                         "Nominal PWM frequency assumes the firmware's literal 24 MHz source; no live clock or acoustic measurement.",
                         "ResultDispatch tests only the Fast CONT qualifier and sentinel-off call setup, excluding formatting and threshold paths.",
                         "The Fast CONT helper at 0x80007c88 (three-sample history) is identified statically but not executed here."]}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"versions": len(results), "gate_cases_passed": sum(r["gate_cases_passed"] for r in results),
                      "qualifier_cases_passed": sum(r["qualifier_cases_passed"] for r in results),
                      "sentinel_off_calls_passed": sum(r["sentinel_off_calls_passed"] for r in results),
                      "version_results_equal": len({r["results_sha256"] for r in results}) == 1}))


if __name__ == "__main__":
    main()
