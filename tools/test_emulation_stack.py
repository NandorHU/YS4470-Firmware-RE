"""Smoke-test the isolated Capstone/Unicorn ARM analysis stack."""
from __future__ import annotations

import json
from importlib.metadata import version

from capstone import CS_ARCH_ARM, CS_MODE_ARM, Cs
from unicorn import UC_ARCH_ARM, UC_MODE_ARM, UC_PROT_ALL, Uc
from unicorn.arm_const import UC_ARM_REG_R0, UC_CPU_ARM_926


def main() -> None:
    code = bytes.fromhex("0100a0e3")  # mov r0, #1 (ARM state)
    instructions = list(Cs(CS_ARCH_ARM, CS_MODE_ARM).disasm(code, 0x80000000))
    if not instructions or instructions[0].mnemonic != "mov":
        raise SystemExit("Capstone ARM decode failed")

    emulator = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    emulator.ctl_set_cpu_model(UC_CPU_ARM_926)
    emulator.mem_map(0x80000000, 0x1000, UC_PROT_ALL)
    emulator.mem_write(0x80000000, code)
    emulator.emu_start(0x80000000, 0x80000004)
    result = emulator.reg_read(UC_ARM_REG_R0)
    if result != 1:
        raise SystemExit(f"Unicorn ARM execution failed: r0={result}")

    print(json.dumps({
        "schema": "ys4470.arm-analysis-stack-smoke.v1",
        "capstone_distribution_version": version("capstone"),
        "capstone_runtime_version": getattr(__import__("capstone"), "__version__", "unknown"),
        "unicorn_version": getattr(__import__("unicorn"), "__version__", "unknown"),
        "architecture": "Unicorn ARM926 CPU model, ARM state smoke case",
        "decoded": f"{instructions[0].mnemonic} {instructions[0].op_str}",
        "unicorn_r0": result,
        "passed": True,
    }, indent=2))


if __name__ == "__main__":
    main()
