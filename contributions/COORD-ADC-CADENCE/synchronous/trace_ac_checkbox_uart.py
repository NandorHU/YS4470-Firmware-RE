"""Follow a native AC checkbox release from the real queue into the original UART FSM."""

import argparse
import hashlib
import json
import struct
from itertools import product
from pathlib import Path

from trace_ac_checkbox_release import RELEASED, ReleaseReplay
from trace_control_gui_events import QUEUE, RECORD_SIZE, SECOND_BINDINGS, SECOND_LITERALS, SECOND_REGISTER, SECOND_STOP
from trace_dynamic_type2 import FRAMES
from trace_gauge_scheduled_service import DEFERRED, SERVICE, GaugeReplay
from trace_scheduler_delay_wake import BASE, SCHED, TICK
from trace_timer0_uart2_irq import CTRL, FSM, RESULT, RX_COUNT, STORED, TIMER_SLOT, TX_READY, UART, UART_ISR, UART_SLOT
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2

DISPATCH_RECORD, BUILDER, FSM_STEP, WIRE_SEND = 0x80004390, 0x8000489C, 0x80004490, 0x80005E84
MEASUREMENT_REPLY = bytes.fromhex("6032000003")


class CheckboxUartReplay(ReleaseReplay):
    def code(self, u, pc, size, data):
        if self.phase == "consume":
            if pc == DISPATCH_RECORD:
                start = u.reg_read(UC_ARM_REG_R0)
                record = bytes(u.mem_read(start, RECORD_SIZE))
                assert record == self.queued_record == bytes(u.mem_read(DEFERRED, RECORD_SIZE))
                self.dispatch_records.append(record[:6].hex())
            elif pc == BUILDER:
                mode, words, count, lr = (u.reg_read(reg) for reg in (
                    UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_LR,
                ))
                assert count == 3
                self.builder_calls.append([mode, list(struct.unpack("<3I", u.mem_read(words, 12))), hex(lr)])
            elif pc == WIRE_SEND:
                self.commands.append(self.read(FSM + 0x20))
        super().code(u, pc, size, data)

    def write(self, u, access, address, size, value, data):
        if self.phase == "consume" and address == CTRL + 8:
            assert size == 4 and u.reg_read(UC_ARM_REG_PC) == 0x80004464
            return
        super().write(u, access, address, size, value, data)

    def interrupt(self, u, number, data):
        if self.phase == "consume":
            self.svc_calls.append([number, hex(u.reg_read(UC_ARM_REG_PC)), hex(u.reg_read(UC_ARM_REG_LR))])
            return GaugeReplay.interrupt(self, u, number, data)
        super().interrupt(u, number, data)

    def deliver(self, value):
        before = self.read(SCHED + 0xC)
        self.put(UART + 8, 4)
        self.put(UART, value)
        irq = self.transport_irq(1 << 3, UART_SLOT)
        assert ["pc", hex(UART_ISR)] in irq and self.read(SCHED + 0xC) == before

    def tick(self):
        before = self.read(SCHED + 0xC)
        irq = self.transport_irq(1 << 13, TIMER_SLOT)
        assert ["pc", hex(TICK)] in irq and self.read(SCHED + 0xC) == before + 1

    def consume(self, initial, reply):
        self.install_vectors(False)
        self.register(SECOND_REGISTER, SECOND_STOP, SECOND_LITERALS, SECOND_BINDINGS)
        event = self.release(initial, True, RELEASED)
        selector = 9 if initial & 1 else 10
        sequence = [selector, 0x19, 0x1D]
        self.queued_record, = self.copies
        assert self.read(QUEUE + 0x38) == 1
        assert self.queued_record[:6] == bytes((2, 0, 0, 0, selector, 0x19))
        self.configure()
        self.u.mem_write(FSM, bytes(0x3C))
        self.put(RESULT + 0x1C, STORED[0])
        self.put(RESULT + 0x20, STORED[1])
        self.put(RX_COUNT, 0)
        self.put(TX_READY, 2)
        self.transport_events, self.dispatch_records, self.builder_calls, self.commands = [], [], [], []
        self.svc_calls = []
        delivery = []
        self.phase = "consume"
        try:
            self.invoke_transport(SERVICE)
            assert self.dispatch_records == [event["record_prefix"]]
            assert self.builder_calls == [[3, sequence, "0x80004480"]]
            assert self.read(QUEUE + 0x38) == 0 and self.read(CTRL + 8) == selector
            assert self.commands == [selector] and self.u.mem_read(CTRL + 1, 1)[0] == 2
            for _ in range(420):
                if reply and len(delivery) < len(self.commands):
                    cmd = self.commands[-1]
                    packet = MEASUREMENT_REPLY if cmd == 0x1D else FRAMES[cmd][:1]
                    delivery.append([hex(cmd), packet.hex()])
                    for value in packet:
                        self.deliver(value)
                self.tick()
                self.invoke_transport(FSM_STEP)
                if self.u.mem_read(FSM + 0x34, 1)[0] == 0:
                    break
        finally:
            self.phase = None
        assert self.u.mem_read(FSM + 0x34, 1)[0] == 0
        expected_commands = sequence if reply else [selector, selector]
        assert self.commands == expected_commands
        tx = bytes(row[1] for row in self.transport_events if row[0] == "tx")
        assert tx == b"".join(FRAMES[cmd] for cmd in expected_commands)
        parse = [row for row in self.transport_events if row[0] == "parse"]
        assert parse == ([["parse", 5, MEASUREMENT_REPLY.hex()]] if reply else [])
        assert self.u.mem_read(CTRL + 1, 1)[0] == (1 if reply else 2)
        assert (self.read(RESULT + 0x1C), self.read(RESULT + 0x20)) == STORED
        return dict(initial_checkbox_state=initial, reply=reply, event=event, uart_wire=tx.hex(),
                    commands=expected_commands, original_builder=self.builder_calls,
                    injected_replies=delivery, parser_records=parse,
                    discard_after=self.u.mem_read(CTRL + 1, 1)[0], retained_result=STORED,
                    timer_irq_steps=self.read(SCHED + 0xC) - 100, modeled_svc_yields=self.svc_calls,
                    instruction_bytes={hex(pc): self.coverage[pc] for pc in sorted(self.coverage)})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    manifest = json.loads(Path("original-firmware/manifest.json").read_bytes())
    assert manifest["linked_base"] == hex(BASE)
    images, results = {}, []
    for item in manifest["images"]:
        raw = Path(item["path"]).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        assert digest == item["sha256"] and len(raw) == item["size_bytes"]
        images[item["version"]] = digest
        results.append([CheckboxUartReplay(raw).consume(*case) for case in product((0, 1), (False, True))])
    assert images.keys() == {"V3.6", "V3.8"} and results[0] == results[1]
    report = dict(schema="ys4470.ac-checkbox-uart.v1", images=images, cases=results[0], limits=[
        "Original checkbox event, queue, measurement dispatcher, transaction builder, FSM and Timer0/UART2 interrupts execute. The queue record flows from the GUI to the original service without host re-enqueue.",
        "The harness supplies the outer release event and selected GUI leaves, seeds idle scheduler and FSM state, steps service and supplies modeled timer and UART interrupt inputs. SVC yields are recorded without switching tasks.",
        "UART bytes describe writes to the model, and measured results remain unchanged under the tested discard path. Hardware conversion, elapsed time and physical touch are outside the test.",
    ])
    args.out.write_bytes((json.dumps(report, indent=2) + "\n").encode())
    print("PASS 4 AC checkbox-to-UART cases per factory image, 8 total")


if __name__ == "__main__":
    main()
