"""Verify the second native metric5 call and tag14 before global writes."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
from unicorn.arm_const import UC_ARM_REG_PC, UC_ARM_REG_LR, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R8, UC_ARM_REG_R9, UC_ARM_REG_SP
from validate_native_cold_state_metric5 import StateMetric5Replay, RETURN as START, TARGET as PRIOR_METRIC5, HEAP, HEAP_BYTES, BASE, REALLOC, vector_bytes, DISPLAY, PRIOR

RETURN, TARGET = 0x8005911C, 0x12024000


class SecondMetric5Replay(StateMetric5Replay):
    def __init__(self, raw):
        self.second_metric5_phase = False
        self.second_metric5_buffer = None
        self.second_metric5_calls, self.second_metric5_results = [], []
        self.second_metric5_wrapper = None
        super().__init__(raw)

    def code(self, u, pc, size, data):
        if self.second_metric5_phase:
            if pc == self.stop:
                u.emu_stop()
                return
            if pc == 0x80025958:
                self.second_metric5_calls.append([u.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1)])
            if pc == 0x800259AC:
                self.second_metric5_results.append(u.reg_read(UC_ARM_REG_R0))
            if pc == 0x8003DDCC:
                self.second_metric5_wrapper = [u.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1)]
            if any(lo <= pc < hi for lo, hi in ((START, RETURN), (0x80025958, 0x800259B0),
                    (0x80025CA4, 0x80025CD4), (0x8003DDCC, 0x8003DDD8), (0x8003DDE4, 0x8003DFAC))):
                assert size == 4
                self.coverage[pc] = bytes(u.mem_read(pc, size)).hex()
                return
        super().code(u, pc, size, data)

    def write(self, u, access, address, size, value, data):
        if self.second_metric5_phase:
            pc = u.reg_read(UC_ARM_REG_PC)
            if HEAP + 0x20 <= address and address + size <= HEAP + 0x28:
                assert pc in (0x8003DE98, 0x8003DED0, 0x8003DF98)
                return
            if self.second_metric5_buffer is not None and TARGET <= address and address + size <= TARGET + 84:
                assert pc in (0x8003DEB8, 0x8003DDF0, 0x8003DDF4)
                return
        super().write(u, access, address, size, value, data)

    def run_second_metric5(self, success):
        assert type(success) is bool
        self.run_state_metric5(True)
        self.state_metric5_phase = False
        self.second_metric5_phase = True
        u = self.u
        sp = u.reg_read(UC_ARM_REG_SP)
        preserved = {r: u.reg_read(r) for r in (UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R9)}
        snapshots = self.snapshots()
        for buffers in (self.tail_buffers, self.state_metric24_buffers, self.state_metric14_buffers):
            for address, raw in buffers.items():
                snapshots[address - 16] = bytes(u.mem_read(address - 16, len(raw) + 32))
        snapshots[PRIOR - 16] = bytes(u.mem_read(PRIOR - 16, 80))
        snapshots[PRIOR_METRIC5 - 16] = bytes(u.mem_read(PRIOR_METRIC5 - 16, 110))
        snapshots[sp] = bytes(u.mem_read(sp, 0x1100F000 - sp))
        heap = bytearray(u.mem_read(HEAP, HEAP_BYTES))
        assert heap[0x20:0x28].hex() == '003002120b00370d'
        values = [13, 0xFF, 0x1201E71C, 0x12019CF3, 2, 0x7F, 2, 0x12012104, 20, 20, 11, 11, 4]
        tags = [0x0B, 0x21, 0x20, 0x44, 0x40, 0x45, 0x42, 0x55, 0x12, 0x13, 0x10, 0x11, 0x15]
        assert u.mem_read(PRIOR_METRIC5, 78) == vector_bytes(values, tags)
        self.stop = REALLOC
        u.emu_start(START, 0, count=10000)
        assert u.reg_read(UC_ARM_REG_PC) == REALLOC
        args = [u.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_LR)]
        assert args == [PRIOR_METRIC5, 84, 0x8003DE90]
        assert u.reg_read(UC_ARM_REG_SP) == sp - 32
        assert u.reg_read(UC_ARM_REG_R8) == 0x14 and u.reg_read(UC_ARM_REG_R9) == 4
        assert self.second_metric5_calls == [[DISPLAY, 5]] and self.second_metric5_results == [4]
        assert self.second_metric5_wrapper == [HEAP + 0x20, 4]
        assert u.mem_read(HEAP, HEAP_BYTES) == heap
        initial = vector_bytes(values, tags) + b'\xA5'*6 if success else b'\xA5'*84
        u.mem_write(TARGET - 16, b'\x97'*16)
        u.mem_write(TARGET, initial)
        u.mem_write(TARGET + 84, b'\x79'*16)
        self.second_metric5_buffer = initial
        if success:
            values.append(4)
            tags.append(0x14)
            expected = vector_bytes(values, tags)
            struct.pack_into('<IHBB', heap, 0x20, TARGET, 0x0B, 0x37, 14)
        else:
            expected = initial
        u.reg_write(UC_ARM_REG_R0, TARGET if success else 0)
        self.stop = RETURN
        u.emu_start(0x8003DE90, 0, count=10000)
        assert u.reg_read(UC_ARM_REG_PC) == RETURN and u.reg_read(UC_ARM_REG_SP) == sp
        assert u.mem_read(HEAP, HEAP_BYTES) == heap and u.mem_read(TARGET, 84) == expected
        for register, value in preserved.items():
            assert u.reg_read(register) == value
        for address, raw in snapshots.items():
            assert u.mem_read(address, len(raw)) == raw
        assert u.mem_read(TARGET - 16, 16) == b'\x97'*16 and u.mem_read(TARGET + 84, 16) == b'\x79'*16
        assert u.mem_read(HEAP - 16, 16) == b'\x6E'*16 and u.mem_read(HEAP + HEAP_BYTES, 16) == b'\xE6'*16
        return dict(allocation_success_fixture=success, metric_inputs=self.second_metric5_calls,
                    metric_results=self.second_metric5_results, wrapper_input=self.second_metric5_wrapper,
                    tag='0x14', raw_value=4, actual_realloc_arguments=[hex(args[0]), args[1], hex(args[2])],
                    final_values=values, final_tags=tags, final_style_hex=heap[0x20:0x28].hex(), allocation_hex=expected.hex(),
                    all_heap_vectors_guards_globals_sp_frame_and_r4_r5_r9_checked=True,
                    global_stores_executed=False, stop_pc=hex(RETURN), initializer_returned=False)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', required=True, type=Path)
    a = p.parse_args()
    repo = Path(__file__).resolve().parents[3]
    manifest = json.loads((repo / 'original-firmware/manifest.json').read_bytes())
    observations, images, originals = [], {}, []
    for item in manifest['images']:
        raw = (repo / item['path']).read_bytes()
        assert len(raw) == item['size_bytes'] and hashlib.sha256(raw).hexdigest() == item['sha256']
        images[item['version']] = item['sha256']
        originals.append(raw)
        rows, words = [], {}
        for success in (False, True):
            replay = SecondMetric5Replay(raw)
            rows.append(replay.run_second_metric5(success))
            words.update(replay.coverage)
        observations.append((rows, words))
    assert observations[0] == observations[1]
    rows, words = observations[0]
    assert all(all(raw[pc - BASE:pc - BASE + 4] == bytes.fromhex(word) for raw in originals) for pc, word in words.items())
    report = dict(schema='ys4470.native-cold-state-metric5-second.v1', images=images, total_cases=4, cases=rows,
                  instruction_bytes={hex(pc): word for pc, word in sorted(words.items())},
                  source_sha256={f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in (Path(__file__), Path(__file__).with_name('validate_native_cold_state_metric5.py'))},
                  limits=['Second original25958(DISPLAY,5)->4 and3ddcc/tag14 execute59100..5911c; exact realloc84 arguments precede NULL/moving-success fixtures.',
                          'Whole504-byte heap, all prior/new vectors/guards, BSS/DATA/display/timer, SP/saved callerframe and callerR4/R5/R9 checked.',
                          'Stop5911c before literal-fed global stores59124/59130. No meaning assigned to scalar4 or later globals; native allocator/free/reuse, full configuration/initializer/root/callback/physicaltiming remain open.'])
    a.out.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(passed_cases=4, tag='0x14', metric=rows[-1]['metric_results'], success_style=rows[-1]['final_style_hex'])))


if __name__ == '__main__':
    main()
