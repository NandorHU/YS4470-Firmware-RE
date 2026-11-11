"""Replay the original USB TX-interrupt busy clear and gadget-mode setter."""

import argparse
import hashlib
import json
from itertools import product
from pathlib import Path

from trace_secondary_channel1 import BASE, INITIAL_INDEX, LOG, PAYLOAD, RETURN, STACK, USB, INDEX, TXCSR
from unicorn import UC_ARCH_ARM, UC_HOOK_CODE, UC_HOOK_MEM_WRITE, UC_MODE_ARM, Uc
from unicorn.arm_const import (
    UC_ARM_REG_CPSR, UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0,
    UC_ARM_REG_SP, UC_CPU_ARM_926,
)

IRQ, MODE_ENABLE, MODE_INIT = 0x800606EC, 0x80060664, 0x8005FA04
MODE, BUSY = 0x805AAC40, 0x805AAC70
TX_STATUS, RX_STATUS, BUS_STATUS = USB + 0x44, USB + 0x46, USB + 0x4C
LOG_MODE = 0x8005A8A8
STOP_BEFORE_INIT = 0x8005FA2C
WINDOWS = (
    (IRQ, 0x80060774), (0x800607BC, 0x80060830), (0x80060890, 0x80060928),
    (0x80060A58, 0x80060A90), (0x800606CC, 0x800606DC), (0x800079D0, 0x800079DC),
    (0x80007AF4, 0x80007B18), (0x80007B1C, 0x80007B28), (0x80007A54, 0x80007A60),
    (0x80007A0C, 0x80007A3C), (0x80007BE0, 0x80007BEC), (0x80007740, 0x8000776C),
    (0x800077A8, 0x800077D0), (MODE_ENABLE, MODE_ENABLE + 8),
    (MODE_INIT, STOP_BEFORE_INIT), (0x8005FAF0, 0x8005FB00),
)
IRQ_LOG_RETURNS = (0x80060748, 0x80060760, 0x800608E0, 0x80060A64)
MODE_LOG_RETURNS = (0x8005FA18, 0x8005FAF8)


class Replay:
    def __init__(self, raw):
        self.u = u = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        u.ctl_set_cpu_model(UC_CPU_ARM_926)
        low, high = BASE & ~0xFFF, (BASE + len(raw) + 0xFFF) & ~0xFFF
        u.mem_map(low, high - low)
        u.mem_write(BASE, raw)
        u.mem_map(PAYLOAD, 0x4000)
        u.mem_map(USB, 0x1000)
        self.coverage, self.mmio, self.stores, self.logs, self.clear_callers = {}, [], [], [], []
        u.hook_add(UC_HOOK_CODE, self.code)
        u.hook_add(UC_HOOK_MEM_WRITE, self.write)

    def code(self, u, pc, size, _data):
        lr = u.reg_read(UC_ARM_REG_LR)
        if pc in (LOG, LOG_MODE):
            assert lr in (IRQ_LOG_RETURNS if pc == LOG else MODE_LOG_RETURNS), hex(lr)
            self.logs.append(hex(lr))
            u.reg_write(UC_ARM_REG_PC, lr)
            return
        assert size == 4 and any(lo <= pc < hi for lo, hi in WINDOWS), hex(pc)
        self.coverage[pc] = bytes(u.mem_read(pc, size)).hex()
        if pc == 0x800606CC:
            self.clear_callers.append(hex(lr))

    def write(self, u, _access, address, size, value, _data):
        pc = u.reg_read(UC_ARM_REG_PC)
        if STACK - 0x100 <= address and address + size <= STACK:
            return
        if address in (MODE, BUSY):
            assert size == 1 and (pc, address) in ((0x8005FA28, MODE), (0x800606D4, BUSY))
            self.stores.append([hex(pc), hex(address), value])
            return
        assert (pc, address, size) in (
            (0x80007A58, BUS_STATUS, 1), (0x80007A28, TX_STATUS, 2), (0x80007BE4, INDEX, 1),
        ), (hex(pc), hex(address), size, value)
        self.mmio.append([hex(address), value])

    def put(self, address, value, size=1):
        self.u.mem_write(address, value.to_bytes(size, "little"))

    def get(self, address):
        return self.u.mem_read(address, 1)[0]

    def invoke(self, entry, stop=RETURN):
        u = self.u
        for reg, value in ((UC_ARM_REG_CPSR, 0x13), (UC_ARM_REG_SP, STACK), (UC_ARM_REG_LR, RETURN)):
            u.reg_write(reg, value)
        u.emu_start(entry, stop, count=1200)
        assert u.reg_read(UC_ARM_REG_PC) == stop
        assert u.reg_read(UC_ARM_REG_SP) == STACK - (16 if stop == STOP_BEFORE_INIT else 0)
        return u.reg_read(UC_ARM_REG_R0)

    def report(self):
        return dict(mmio=self.mmio, state_stores=self.stores, log_return_sites=self.logs,
                    busy_clear_return_sites=self.clear_callers,
                    instruction_bytes={hex(pc): self.coverage[pc] for pc in sorted(self.coverage)})


def run_irq(raw, mode, endpoint, tx_ready):
    replay = Replay(raw)
    replay.put(MODE, mode)
    replay.put(BUSY, 1)
    replay.put(INDEX, INITIAL_INDEX)
    replay.put(TX_STATUS, 1 << endpoint if endpoint else 0, 2)
    replay.put(RX_STATUS, 0, 2)
    replay.put(BUS_STATUS, 0)
    replay.put(TXCSR, int(not tx_ready), 2)
    replay.invoke(IRQ)
    clear = endpoint != 0 and tx_ready and mode == 1
    assert replay.get(BUSY) == int(not clear)
    assert replay.get(INDEX) == INITIAL_INDEX and replay.get(MODE) == mode
    assert replay.clear_callers == (["0x80060a70"] if clear else [])
    assert replay.stores == ([["0x800606d4", hex(BUSY), 0]] if clear else [])
    expected = [[hex(BUS_STATUS), v] for v in (0x80, 0x40, 0x10, 8)]
    if endpoint:
        expected.extend([[hex(TX_STATUS), 1 << endpoint], [hex(INDEX), endpoint], [hex(INDEX), INITIAL_INDEX]])
    expected.append([hex(INDEX), INITIAL_INDEX])
    assert replay.mmio == expected
    return dict(mode=mode, endpoint=endpoint, tx_ready=tx_ready, busy_after=replay.get(BUSY), **replay.report())


def run_mode_enable(raw, prior_mode):
    replay = Replay(raw)
    replay.put(MODE, prior_mode)
    stop = RETURN if prior_mode == 1 else STOP_BEFORE_INIT
    result = replay.invoke(MODE_ENABLE, stop)
    assert replay.get(MODE) == 1 and not replay.mmio
    assert replay.stores == ([] if prior_mode == 1 else [["0x8005fa28", hex(MODE), 1]])
    assert replay.logs == (["0x8005fa18", "0x8005faf8"] if prior_mode == 1 else ["0x8005fa18"])
    if prior_mode == 1:
        assert result == 0xFFFFFFFF
    return dict(prior_mode=prior_mode, mode_after=replay.get(MODE), stop=hex(stop),
                return_value=result if stop == RETURN else None, **replay.report())


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
        # Use all ready/mode combinations for the channel-1 TX bit, then two
        # controls for no TX interrupt and a distinct indexed TX interrupt.
        irq = [run_irq(raw, mode, 1, ready) for mode, ready in product((0, 1, 2), (False, True))]
        irq.extend(run_irq(raw, 1, endpoint, True) for endpoint in (0, 2))
        setup = [run_mode_enable(raw, mode) for mode in (0, 1, 2)]
        observations.append(dict(irq=irq, mode_enable=setup))
        images[item["version"]] = digest
    assert images.keys() == {"V3.6", "V3.8"} and observations[0] == observations[1]
    report = dict(schema="ys4470.secondary-usb-irq.v1", images=images, **observations[0], limits=[
        "Original ARM926 handler is entered directly with modeled interrupt status registers. It reads the selected endpoint status and performs original acknowledgement, conditional busy clear, and index restoration.",
        "Only TX endpoints 1 and 2 and an empty TX-status case are exercised, with RX and bus status zero. Acknowledgement writes are recorded, with no physical interrupt delivery or timing.",
        "The mode-1 wrapper runs only to the first hardware initialization call for changed modes. Log calls are modeled. This is not a device enumeration or USB transaction test.",
    ])
    args.out.write_bytes((json.dumps(report, indent=2) + "\n").encode())
    print("PASS 8 USB IRQ cases and 3 mode-entry cases per factory image, 22 total")


if __name__ == "__main__":
    main()
