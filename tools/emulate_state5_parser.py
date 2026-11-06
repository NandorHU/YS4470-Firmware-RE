"""Run original YS-4470 state-5 ARM bytes on Unicorn's ARM926 model.

The harness enters 0x80004738 after state-3 admission and stops BEFORE the
shared state-7 epilogue at 0x80004518. It maps only code/literals and three
RAM pages. MMIO and all other memory are unmapped. No physical I/O occurs.

Example (install analysis-requirements.txt in an isolated Python environment):
  python emulate_state5_parser.py --input V3.6=path/to/f1c100s.bin \
      --input V3.8=other/path/f1c100s.bin --out state5.json
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import random
import struct
from importlib.metadata import version
from pathlib import Path

import capstone
import unicorn
from capstone import CS_ARCH_ARM, CS_MODE_ARM, Cs
from unicorn import (UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE,
                     UC_HOOK_MEM_WRITE, UC_PROT_READ, UC_PROT_WRITE,
                     UC_PROT_EXEC, Uc)
from unicorn.arm_const import (UC_ARM_REG_CPSR, UC_ARM_REG_PC,
                               UC_ARM_REG_R1, UC_ARM_REG_R7,
                               UC_ARM_REG_R12, UC_CPU_ARM_926)

BASE = 0x7FFFFFE0
ENTRY, END, LAST = 0x80004738, 0x80004518, 0x800047BC
CONTROL, RESULT, RX = 0x805AAE8C, 0x805AC714, 0x805B408C
CODE_PAGE = 0x80004000
INITIAL_VALUE, INITIAL_SELECTOR = 0xA1B2C3D4, 0x55667788
EXPECTED_INPUTS = {
    "V3.6": "7523b2e91dd8627ffebfc7ac0525c0607a56df4cece04028a9c3a8ee558f6eb9",
    "V3.8": "7e7d7230155fe0790eb48531de2ef463bb122c0ae1a820ab6d10cf2e60f50290",
}


def reference(raw24: int, command: int, selector: int,
              control: int, holdoff: int) -> dict:
    """Independent functional reconstruction of this bounded code slice."""
    if holdoff:
        return {"value_u32": INITIAL_VALUE, "selector": INITIAL_SELECTOR,
                "holdoff": holdoff - 1, "published": False}
    signed = raw24 if raw24 < 0x800000 else raw24 - 0x1000000
    saturated = control in (13, 14) and (signed & 0xFFFFFFFF) >= 5001
    return {"value_u32": 0x7FFFFF if saturated else signed & 0xFFFFFFFF,
            "selector": 0 if saturated or command == 0x1B else min(selector, 6),
            "holdoff": 0, "published": True}


def vectors(seed: int, random_cases: int) -> list[tuple[int, ...]]:
    boundaries = (0, 1, 5000, 5001, 5002, 0x7FFFFE,
                  0x7FFFFF, 0x800000, 0xFFFFFE, 0xFFFFFF)
    cases = list(itertools.product(boundaries, (0x1B, 0x1D),
                                  (0, 1, 5, 6, 7, 255), (0, 13, 14, 34),
                                  (0, 1, 255)))
    # Exhaust each byte-domain once in addition to the boundary cross product.
    cases += [(0x123456, cmd, scale, 34, 0)
              for cmd in (0x1B, 0x1D) for scale in range(256)]
    cases += [(0xFFFFFF, 0x1D, 255, mode, 0) for mode in range(256)]
    cases += [(1, 0x1D, 1, 0, count) for count in range(256)]
    rng = random.Random(seed)
    cases += [(rng.randrange(1 << 24), rng.choice((0x1B, 0x1D)),
               rng.randrange(256), rng.choice((0, 13, 14, 34)),
               rng.choice((0, 0, 0, 1, 2, 255))) for _ in range(random_cases)]
    return cases


class ParserMachine:
    def __init__(self, image: bytes):
        self.mu = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        self.mu.ctl_set_cpu_model(UC_CPU_ARM_926)
        self.mu.mem_map(CODE_PAGE, 0x1000, UC_PROT_READ | UC_PROT_EXEC)
        self.mu.mem_write(CODE_PAGE, image[CODE_PAGE - BASE:CODE_PAGE - BASE + 0x1000])
        for address in (CONTROL, RESULT, RX):
            self.mu.mem_map(address & ~0xFFF, 0x1000, UC_PROT_READ | UC_PROT_WRITE)
        self.mu.mem_protect(RX & ~0xFFF, 0x1000, UC_PROT_READ)
        self.covered: set[int] = set()
        self.writes: list[tuple[int, int]] = []
        self.mu.hook_add(UC_HOOK_CODE, self.on_code)
        self.mu.hook_add(UC_HOOK_MEM_WRITE, self.on_write)

    def on_code(self, mu: Uc, address: int, size: int, _data) -> None:
        if address < ENTRY or address > LAST or size != 4:
            raise RuntimeError(f"execution left parser slice: 0x{address:08x}")
        self.covered.add(address)

    def on_write(self, mu: Uc, access: int, address: int, size: int,
                 value: int, _data) -> None:
        if (address, size) not in ((CONTROL + 1, 1), (RESULT + 0x1C, 4),
                                  (RESULT + 0x20, 4)):
            raise RuntimeError(f"unexpected parser write: 0x{address:08x}/{size}")
        self.writes.append((address, size))

    def execute(self, raw24: int, command: int, selector: int,
                control: int, holdoff: int, *, preserve_state: bool = False) -> dict:
        mu = self.mu
        if not preserve_state:
            mu.mem_write(CONTROL, b"\0" * 16)
            mu.mem_write(CONTROL + 1, bytes([holdoff]))
            mu.mem_write(CONTROL + 8, struct.pack("<I", control))
            mu.mem_write(RESULT + 0x1C, struct.pack("<II", INITIAL_VALUE, INITIAL_SELECTOR))
        elif (mu.mem_read(CONTROL + 1, 1)[0] != holdoff or
              struct.unpack("<I", mu.mem_read(CONTROL + 8, 4))[0] != control):
            raise ValueError("preserved control state does not match the supplied contract")
        header = 0x5E if command == 0x1B else 0x60
        mu.mem_write(RX, bytes([header]) + raw24.to_bytes(3, "little") + bytes([selector]))
        mu.reg_write(UC_ARM_REG_CPSR, 0x13)  # ARM state, supervisor mode.
        mu.reg_write(UC_ARM_REG_R1, command)
        mu.reg_write(UC_ARM_REG_R7, 0)  # Factory prologue MOV at 0x800044c0.
        mu.reg_write(UC_ARM_REG_R12, RX)
        self.writes.clear()
        # The instruction-count bound is sufficient for this straight-line
        # slice; a per-case wall timer would spawn thousands of timer threads.
        mu.emu_start(ENTRY, END, count=64)
        if mu.reg_read(UC_ARM_REG_PC) != END:
            raise RuntimeError("parser failed to reach the shared exit within 64 instructions")
        value, scale = struct.unpack("<II", mu.mem_read(RESULT + 0x1C, 8))
        expected_writes = [(CONTROL + 1, 1)] if holdoff else [(RESULT + 0x1C, 4), (RESULT + 0x20, 4)]
        if self.writes != expected_writes:
            raise RuntimeError(f"unexpected write set: {self.writes}")
        return {"value_u32": value, "selector": scale,
                "holdoff": mu.mem_read(CONTROL + 1, 1)[0], "published": not bool(holdoff)}


def analyze(label: str, path: Path, cases: list[tuple[int, ...]]) -> dict:
    image = path.read_bytes()
    digest = hashlib.sha256(image).hexdigest()
    if EXPECTED_INPUTS.get(label) != digest:
        raise ValueError(f"unrecognized original input {label}: {digest}")
    if struct.unpack_from("<I", image, 0x800044C0 - BASE)[0] != 0xE3A07000:
        raise ValueError("factory r7=0 prologue assumption not satisfied")
    for address, expected in ((0x8000481C, CONTROL), (0x80004820, RESULT),
                              (0x80004824, 5001), (0x80004828, 0x7FFFFF)):
        if struct.unpack_from("<I", image, address - BASE)[0] != expected:
            raise ValueError(f"literal mismatch at 0x{address:08x}")
    machine = ParserMachine(image)
    results_digest = hashlib.sha256()
    for index, case in enumerate(cases):
        actual, expected = machine.execute(*case), reference(*case)
        if actual != expected:
            raise AssertionError(f"case {index} {case}: actual {actual}, expected {expected}")
        results_digest.update(json.dumps([case, actual], sort_keys=True).encode())
    code = image[ENTRY - BASE:LAST - BASE + 4]
    disassembly = [{"address": f"0x{i.address:08x}", "assembly": f"{i.mnemonic} {i.op_str}"}
                   for i in Cs(CS_ARCH_ARM, CS_MODE_ARM).disasm(code, ENTRY)]
    decoded = {int(i["address"], 16) for i in disassembly}
    if len(decoded) != 34 or not decoded.issubset(machine.covered):
        raise AssertionError("test vectors did not visit all 34 instruction addresses")
    representative = [(5000, 0x1D, 7, 13, 0), (5001, 0x1D, 7, 13, 0),
                      (0xFFFFFF, 0x1D, 7, 13, 0), (0xFFFFFF, 0x1D, 255, 34, 0),
                      (1, 0x1B, 255, 0, 0), (1, 0x1D, 255, 0, 1)]
    return {"version": label, "input_sha256": digest,
            "parser_slice_sha256": hashlib.sha256(code).hexdigest(),
            "cases_passed": len(cases), "cases_failed": 0,
            "results_sha256": results_digest.hexdigest(),
            "instruction_addresses_visited": len(decoded), "assembly": disassembly,
            "examples": [{"input": dict(zip(("raw24", "command", "selector", "control", "holdoff"), c)),
                          "result": machine.execute(*c)} for c in representative]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", action="append", required=True, metavar="VERSION=PATH")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--random-cases", type=int, default=512)
    parser.add_argument("--seed", type=int, default=4470)
    args = parser.parse_args()
    if args.random_cases < 0:
        parser.error("--random-cases cannot be negative")
    cases = vectors(args.seed, args.random_cases)
    results = []
    for item in args.input:
        if "=" not in item:
            parser.error("--input requires VERSION=PATH")
        label, raw_path = item.split("=", 1)
        results.append(analyze(label, Path(raw_path), cases))
        print(f"{label}: {len(cases)} cases passed", flush=True)
    report = {
        "schema": "ys4470.state5-arm926-emulation.v1",
        "toolchain": {"unicorn": unicorn.__version__, "cpu_model": "UC_CPU_ARM_926",
                      "capstone_distribution": version("capstone"),
                      "capstone_runtime": capstone.__version__},
        "entry": hex(ENTRY), "stop_before": hex(END), "seed": args.seed,
        "cases_per_version": len(cases), "random_cases": args.random_cases,
        "contract": {"r12": hex(RX), "r1": "0x1b or 0x1d", "r7": 0,
                     "control_holdoff_byte": hex(CONTROL + 1),
                     "control_mode_word": hex(CONTROL + 8),
                     "result_value_word": hex(RESULT + 0x1C),
                     "result_selector_word": hex(RESULT + 0x20)},
        "limits": ["State-3 count/header admission and shared state-7 epilogue are excluded.",
                   "Synthetic RAM inputs; no ADC, UART, timing, interrupts, or MMIO modeled.",
                   "Instruction-address coverage is not full path or hardware coverage.",
                   "This bounded experiment does not identify physical measurement units or modes."],
        "versions": results,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"versions": len(results), "cases_passed": len(cases) * len(results),
                      "all_outputs_equal": len({r["results_sha256"] for r in results}) == 1,
                      "out": str(args.out)}))


if __name__ == "__main__":
    main()
