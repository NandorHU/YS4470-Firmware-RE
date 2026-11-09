"""Trace original calibration buttons, timer registration and status rendering."""

import argparse
import json
import struct
import sys
from pathlib import Path

from trace_deferred_producers import CTRL, PRODUCER, QUEUE, RET, SELECTION
from trace_extended_status import FLAG, PRODUCERS, STATUS, STATUS_CHECK, ExtendedReplay, SCENARIOS
from trace_uart_correlation import COUNTER, NEST, RESULT, OriginalUART, sha
from unicorn import UC_MEM_WRITE
from unicorn.arm_const import (
    UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2,
    UC_ARM_REG_R3, UC_ARM_REG_R4,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from trace_profiles import restore_globals

TIMER = 0x10016000
LABEL = 0x10016100
TEXT = 0x10016200
DRAIN = 0x10016300
PANEL = 0x10017000
BUTTONS = (0x10017500, 0x10017600)
EXTENSIONS = (0x10017700, 0x10017800)
EVENTS = (0x10017900, 0x10017A00)
HANDLE = 0x805ABEB8
TIMER_STATE = 0x805ABDAC
WIDGET_POINTER = 0x805AC540
INIT = 0x8004C4E0
RUN = 0x8004092C
UI = 0x8005DA88
STATUS_TEXT = (
    "", "Power On OK01", "Cal circuit 1 OK02", "Cal circuit 2 OK03",
    "EEPROM error01", "EEPROM initail error02", "EEPROM write error03", "Cal over range04",
)
CODE_WINDOWS = (
    (0x80000000, 0x80002900),  # Original ARM/Thumb C library, including formatter.
    (0x80003D74, 0x80003DB8),
    (0x8000E4C8, 0x8000E534 + 4),
    (0x8000E55C, 0x8000E5C8 + 4),
    (0x80006778, 0x800067C4),
    (0x80008F70, 0x80008F7E),  # Thumb digit classifier called by the formatter.
    (0x80032038, 0x800320E4),
    (0x800338DC, 0x800339B8),
    (0x8004078C, 0x800407A4),
    (0x80040894, 0x800408F0),
    (0x8004092C, 0x80040B8C),
    (0x80041E68, 0x80041E6C),
    (0x80046CA8, 0x80046CBC),
    (0x8004C454, 0x8004C47C),
    (0x8004C4E0, 0x8004C4F8),
    (0x8005DA88, 0x8005DE44),
)


class OriginalStatusUI(OriginalUART):
    def return_value(self, u, value):
        u.reg_write(UC_ARM_REG_R0, value)
        u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))

    def code(self, u, pc, size, data):
        r0, r1, lr = (u.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_LR))
        if pc == self.stop:
            u.reg_write(UC_ARM_REG_PC, RET)
            return
        if pc == 0x8000A9D8:
            assert r0 == 0x807B531C
            self.return_value(u, TIMER)
            return
        if pc == 0x8000A954:
            assert r0 == 0x807B531C
            self.return_value(u, TIMER)
            return
        if pc == 0x8000A994:
            assert (r0, r1) == (0x807B531C, TIMER)
            self.return_value(u, 0)
            return
        if pc in (0x80034380, 0x80037F3C, 0x800316FC):
            assert r0 in (*BUTTONS, LABEL)
            self.return_value(u, 0)
            return
        if pc in (0x80032800, 0x80032AE4):
            if lr == 0x8003392C:
                assert (r0, r1) == (0, 12)
                dst = EVENTS[self.registrations]
                self.registrations += 1
            else:
                assert (pc == 0x80032800 and 0 < r0 <= 64) or (r0 == TEXT and 0 < r1 <= 64)
                dst = TEXT
            self.return_value(u, dst)
            return
        if pc == 0x80032A80:
            assert r0 == TEXT and lr == 0x800320A0
            self.return_value(u, 0)
            return
        if pc in (0x80042AA0, 0x80060F5C):
            assert r0 == (68 if pc == 0x80042AA0 else DRAIN)
            self.return_value(u, DRAIN if pc == 0x80042AA0 else 0)
            return
        if pc == 0x800618DC:
            assert (r0, r1) == (QUEUE, DRAIN)
            self.drains += 1
            self.return_value(u, 0)
            return
        if pc == 0x80061ACC:
            assert r0 == QUEUE
            record = bytes(u.mem_read(r1, 68))
            kind = struct.unpack_from("<I", record)[0]
            assert kind in (1, 3)
            assert u.reg_read(UC_ARM_REG_R2) == (10 if kind == 1 else 0)
            assert u.reg_read(UC_ARM_REG_R3) == 0
            self.records.append(record[:6].hex())
            self.return_value(u, 1)
            return
        if pc == UI:
            assert r0 == TIMER
            self.callbacks += 1
        if pc == 0x80032038:
            assert r0 == LABEL
            self.label_inputs.append(self.cstring(r1))
        if any(lo <= pc < hi for lo, hi in CODE_WINDOWS):
            assert size in (2, 4)
            self.coverage[pc] = bytes(u.mem_read(pc, size)).hex()
            self.instruction_count += 1
            return
        super().code(u, pc, size, data)

    def memory(self, u, access, address, size, value, data):
        pc = u.reg_read(UC_ARM_REG_PC)
        if access != UC_MEM_WRITE and address in (STATUS, FLAG) and pc in (0x8005DAC4, 0x8005DBFC):
            self.status_reads.append((hex(pc), self.rd(address)))
        if access == UC_MEM_WRITE and (
            address in (HANDLE, 0x805ABD80, SELECTION, SELECTION + 1)
            or TIMER_STATE <= address and address + size <= TIMER_STATE + 0x14
        ):
            return
        if access == UC_MEM_WRITE and pc in (0x80046CB0, 0x80046CB8):
            assert (address, size, value) == (FLAG if pc == 0x80046CB0 else STATUS, 4, 0)
            self.reset_writes.append((hex(pc), hex(address), value))
            return
        super().memory(u, access, address, size, value, data)

    def cstring(self, address):
        data = bytes(self.u.mem_read(address, 64))
        assert b"\0" in data
        return data.split(b"\0", 1)[0].decode("ascii")

    def bind(self, init_globals, start):
        self.reset()
        self.u.mem_write(0x805AAAB4, init_globals)
        self.u.mem_write(0x10010000, bytes(0x10000))
        self.put(NEST, 0)
        self.put(CTRL + 4, QUEUE)
        self.put(RESULT + 0x1C, 0x7FFFFF)
        self.put(RESULT + 0x20, 0)
        self.put(WIDGET_POINTER, LABEL)
        self.put(COUNTER, start)
        self.u.mem_write(TIMER_STATE, b"\1" + bytes(0x13))
        self.stop = 0x8004C4F8
        self.callbacks = self.registrations = self.drains = 0
        self.label_inputs, self.records, self.status_reads, self.reset_writes = [], [], [], []
        self.invoke(INIT)
        self.stop = 0
        assert self.rd(HANDLE) == TIMER
        assert struct.unpack("<6I", self.u.mem_read(TIMER, 24)) == (2000, start, UI, 0, 0xFFFFFFFF, 0)

    def bind_buttons(self):
        for offset, button, ext in zip((0x434, 0x43C), BUTTONS, EXTENSIONS):
            self.put(PANEL + offset, button)
            self.put(button + 8, ext)
        self.u.reg_write(UC_ARM_REG_R4, PANEL)
        self.stop = 0x8004C47C
        self.invoke(0x8004C454)
        self.stop = 0
        callbacks = tuple(self.rd(event) for event in EVENTS)
        assert self.registrations == 2 and callbacks == (0x8000E55C, 0x8000E4C8)
        assert all(self.rd(event + 4) == 0 and self.byte(event + 8) == 1 for event in EVENTS)
        return callbacks[::-1]

    def fire_button(self, command, callback):
        self.invoke(callback)
        expected = "Cal Circuit 1 mode" if command == 0x28 else "Cal Circuit 2 mode"
        assert self.label_inputs == [expected] and self.cstring(TEXT) == expected
        assert self.rd(LABEL + 0x24) == TEXT and self.rd(TIMER) == 2000
        assert self.drains == 1 and self.records == [struct.pack("<IBB", 1, command, 0).hex()]
        assert self.byte(SELECTION) == command and self.byte(SELECTION + 1) == 0

    def schedule(self, start, elapsed):
        self.put(COUNTER, start + elapsed)
        self.invoke(RUN)

    def check_timer_edge(self, start, elapsed):
        calls = self.callbacks
        self.schedule(start, elapsed - 1)
        assert self.callbacks == calls
        self.schedule(start, elapsed)
        assert self.callbacks == calls + 1
        assert self.rd(TIMER + 4) == (start + elapsed) & 0xFFFFFFFF

    def ui_case(self, globals_data, start, status, flag):
        self.bind(globals_data, start)
        self.u.mem_write(SELECTION, b"\x28\x00")
        self.put(STATUS, status)
        self.put(FLAG, flag)
        self.check_timer_edge(start, 2000)
        assert self.rd(STATUS) == status and self.rd(FLAG) == flag
        reads = [("0x8005dac4", status)]
        if status == 0:
            reads.append(("0x8005dbfc", flag))
        assert self.status_reads == reads
        if 1 <= status <= 7:
            expected_label = STATUS_TEXT[status]
        elif status == 0:
            expected_label = "Calibration ..." if flag else ".OL"
        else:
            expected_label = None
        assert self.label_inputs == ([expected_label] if expected_label else [])
        if expected_label:
            assert self.cstring(TEXT) == expected_label and self.rd(LABEL + 0x24) == TEXT
        assert self.records == (["030000000000"] if status == flag == 0 else [])
        assert self.rd(TIMER) == (2000 if status == 0 and flag else 200)
        return dict(status=status, flag=flag, reader_sites=self.status_reads, widget_text=expected_label,
                    period_after=self.rd(TIMER), timer_initial_tick=hex(start), fire_elapsed=2000,
                    followup_records=self.records)

    def ui_sequence(self, globals_data, start, command, waiting, finished, writer_case):
        self.bind(globals_data, start)
        callback = self.bind_buttons()[command - 0x28]
        self.fire_button(command, callback)
        button_message = self.cstring(TEXT)
        record = self.records.pop()
        rows = []
        for elapsed, (status, flag) in ((2000, waiting), (4000, finished), (4200, finished), (4400, (0, 0))):
            if elapsed == 4400:
                self.stop = 0x80046CBC
                self.invoke(0x80046CA8)
                self.stop = 0
                assert self.reset_writes == [("0x80046cb0", hex(FLAG), 0), ("0x80046cb8", hex(STATUS), 0)]
            else:
                self.put(STATUS, status)
                self.put(FLAG, flag)
            assert (self.rd(STATUS), self.rd(FLAG)) == (status, flag)
            previous = len(self.records)
            self.check_timer_edge(start, elapsed)
            expected = STATUS_TEXT[status] if status else "Calibration ..." if flag else ".OL"
            assert self.cstring(TEXT) == self.label_inputs[-1] == expected
            records = self.records[previous:]
            assert records == (["030000000000"] if status == flag == 0 else [])
            period = 2000 if flag else 200
            assert self.rd(TIMER) == period
            rows.append(dict(elapsed=elapsed, status=status, flag=flag, text=expected,
                             new_records=records, next_period=period))
        return dict(command=hex(command), callback=hex(callback), button_message=button_message,
                    record_prefix_hex=record, writer_case=writer_case, timer_initial_tick=hex(start),
                    updates=rows, reset_writes=self.reset_writes)


class StatusSnapshots(ExtendedReplay):
    def code(self, u, pc, size, data):
        if pc == STATUS_CHECK and self.waiting is None:
            self.waiting = (self.rd(STATUS), self.rd(FLAG))
        super().code(u, pc, size, data)


def run_image(raw, globals_data):
    ui = OriginalStatusUI(raw)
    cases = [ui.ui_case(globals_data, 0x100, status, flag)
             for status in (0, *range(1, 8), 8, 0xFFFFFFFF) for flag in (0, 1)]
    writer = StatusSnapshots(raw)
    linked = []
    for producer, names in zip(PRODUCERS, (("a0-02", "ack-only"), ("a0-03", "a1-04-last-poll"))):
        for name in names:
            writer.waiting = None
            scenario = next(item for item in SCENARIOS if item.name == name)
            writer.run_case(producer, scenario)
            assert writer.waiting == (0, 1)
            linked.append(ui.ui_sequence(globals_data, 0xFFFFFF00, producer[0], writer.waiting,
                                         (writer.rd(STATUS), writer.rd(FLAG)), name))
    return cases, linked, {hex(pc): value for pc, value in sorted(ui.coverage.items())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[3]
    manifest = json.loads((root / "original-firmware/manifest.json").read_text())
    inputs = [(item, (root / item["path"]).read_bytes()) for item in manifest["images"]]
    assert all(sha(raw) == item["sha256"] for item, raw in inputs)
    globals_data = restore_globals(next(raw for item, raw in inputs if item["version"] == "V3.8"))
    results = [run_image(raw, globals_data) for _, raw in inputs]
    assert results[0] == results[1]
    cases, linked, instructions = results[0]
    report = dict(
        schema="ys4470.calibration-ui.v1", source_sha256=sha(Path(__file__).read_bytes()),
        init_globals_sha256=sha(globals_data),
        versions=[dict(version=item["version"], input_sha256=item["sha256"], status_cases=len(cases),
                       linked_sequences=len(linked))
                  for item, _ in inputs],
        cases_identical_across_versions=cases, instruction_bytes=instructions,
        linked_sequences_identical_across_versions=linked,
        reused_sources_sha256={name: sha((Path(__file__).parent / name).read_bytes())
                               for name in ("trace_extended_status.py", "trace_deferred_producers.py",
                                            "../uart/trace_uart_correlation.py", "../trace_profiles.py")},
        models=[
            "Fixture UI objects, timer allocation and single-item timer list.",
            "GUI invalidation leaves and fixed allocations for label/event data; original format and copy execute.",
            "Queue leaves and drain allocation/free are controlled. Status snapshots cross a modeled task boundary.",
            "Tick values and UART arrival are fixtures. No physical timing, pixels, or peer internals are established.",
        ],
    )
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("PASS", len(cases) * len(inputs), "status cases and",
          len(linked) * len(inputs), "linked calibration UI sequences")


if __name__ == "__main__":
    main()
