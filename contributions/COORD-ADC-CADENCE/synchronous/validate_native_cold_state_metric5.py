"""Verify the original metric5 scalar and guarded tag15 append."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
from unicorn.arm_const import UC_ARM_REG_PC, UC_ARM_REG_LR, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R8, UC_ARM_REG_R9, UC_ARM_REG_SP
from validate_native_cold_state_metric14_pair import StateMetric14PairReplay, RETURN as START, HEAP, HEAP_BYTES, STATE, BASE, REALLOC, vector_bytes, DISPLAY, PRIOR

RETURN = 0x80059100
TARGET = 0x12023000


class StateMetric5Replay(StateMetric14PairReplay):
    def __init__(self, raw):
        self.state_metric5_phase = False
        self.state_metric5_buffer = None
        self.state_metric5_calls, self.state_metric5_results = [], []
        self.state_metric5_wrapper = None
        super().__init__(raw)

    def code(self, u, pc, size, data):
        if self.state_metric5_phase:
            if pc == self.stop:
                u.emu_stop()
                return
            if pc == 0x80025958:
                self.state_metric5_calls.append([u.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1)])
            if pc == 0x800259AC:
                self.state_metric5_results.append(u.reg_read(UC_ARM_REG_R0))
            if pc == 0x8003DDA8:
                self.state_metric5_wrapper = [u.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1)]
            if any(lo <= pc < hi for lo, hi in ((START, RETURN), (0x80025958, 0x800259B0),
                    (0x80025CA4, 0x80025CD4), (0x8003DDA8, 0x8003DDB4), (0x8003DDE4, 0x8003DFAC))):
                assert size == 4
                self.coverage[pc] = bytes(u.mem_read(pc, size)).hex()
                return
        super().code(u, pc, size, data)

    def write(self, u, access, address, size, value, data):
        if self.state_metric5_phase:
            pc = u.reg_read(UC_ARM_REG_PC)
            if HEAP + 0x20 <= address and address + size <= HEAP + 0x28:
                assert pc in (0x8003DE98, 0x8003DED0, 0x8003DF98)
                return
            if self.state_metric5_buffer is not None and TARGET <= address and address + size <= TARGET + 78:
                assert pc in (0x8003DEB8, 0x8003DDF0, 0x8003DDF4)
                return
        super().write(u, access, address, size, value, data)

    def run_state_metric5(self, success):
        assert type(success) is bool
        self.run_state_metric14_pair((True, True))
        self.state_metric14_phase = False
        self.state_metric5_phase = True
        u = self.u
        sp = u.reg_read(UC_ARM_REG_SP)
        preserved_registers = {r: u.reg_read(r) for r in (UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R9)}
        snapshots = self.snapshots()
        for buffers in (self.tail_buffers, self.state_metric24_buffers, self.state_metric14_buffers):
            for address, raw in buffers.items():
                snapshots[address - 16] = bytes(u.mem_read(address - 16, len(raw) + 32))
        snapshots[PRIOR - 16] = bytes(u.mem_read(PRIOR - 16, 80))
        snapshots[sp] = bytes(u.mem_read(sp, 0x1100F000 - sp))
        heap = bytearray(u.mem_read(HEAP, HEAP_BYTES))
        assert heap[0x20:0x28].hex() == '002002120b00370c'
        values = [13, 0xFF, 0x1201E71C, 0x12019CF3, 2, 0x7F, 2, 0x12012104, 20, 20, 11, 11]
        tags = [0x0B, 0x21, 0x20, 0x44, 0x40, 0x45, 0x42, 0x55, 0x12, 0x13, 0x10, 0x11]
        pointer = 0x12022000
        assert u.mem_read(pointer, 72) == vector_bytes(values, tags)
        self.stop = REALLOC
        u.emu_start(START, 0, count=10000)
        assert u.reg_read(UC_ARM_REG_PC) == REALLOC
        args = [u.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_LR)]
        assert args == [pointer, 78, 0x8003DE90]
        assert u.reg_read(UC_ARM_REG_SP) == sp - 32
        assert u.reg_read(UC_ARM_REG_R8) == 0x15 and u.reg_read(UC_ARM_REG_R9) == 4
        assert self.state_metric5_calls == [[DISPLAY, 5]] and self.state_metric5_results == [4]
        assert self.state_metric5_wrapper == [HEAP + 0x20, 4]
        assert u.mem_read(HEAP, HEAP_BYTES) == heap
        initial = vector_bytes(values, tags) + b'\xA5' * 6 if success else b'\xA5' * 78
        u.mem_write(TARGET - 16, b'\x96' * 16)
        u.mem_write(TARGET, initial)
        u.mem_write(TARGET + 78, b'\x69' * 16)
        self.state_metric5_buffer = initial
        if success:
            values.append(4)
            tags.append(0x15)
            expected = vector_bytes(values, tags)
            struct.pack_into('<IHBB', heap, 0x20, TARGET, 0x0B, 0x37, 13)
        else:
            expected = initial
        u.reg_write(UC_ARM_REG_R0, TARGET if success else 0)
        self.stop = RETURN
        u.emu_start(0x8003DE90, 0, count=10000)
        assert u.reg_read(UC_ARM_REG_PC) == RETURN and u.reg_read(UC_ARM_REG_SP) == sp
        assert u.mem_read(HEAP, HEAP_BYTES) == heap and u.mem_read(TARGET, 78) == expected
        for r, value in preserved_registers.items():
            assert u.reg_read(r) == value
        for a, raw in snapshots.items():
            assert u.mem_read(a, len(raw)) == raw
        assert u.mem_read(TARGET - 16, 16) == b'\x96' * 16 and u.mem_read(TARGET + 78, 16) == b'\x69' * 16
        assert u.mem_read(HEAP - 16, 16) == b'\x6E' * 16 and u.mem_read(HEAP + HEAP_BYTES, 16) == b'\xE6'*16
        return dict(allocation_success_fixture=success, metric_inputs=self.state_metric5_calls,
                    metric_results=self.state_metric5_results, wrapper_input=self.state_metric5_wrapper,
                    tag='0x15', raw_value=4, actual_realloc_arguments=[hex(args[0]), args[1], hex(args[2])],
                    final_values=values, final_tags=tags, final_style_hex=heap[0x20:0x28].hex(), allocation_hex=expected.hex(),
                    all_heap_vectors_guards_globals_sp_frame_and_r4_r5_r9_checked=True,
                    stop_pc=hex(RETURN), initializer_returned=False)


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
            replay = StateMetric5Replay(raw)
            rows.append(replay.run_state_metric5(success))
            words.update(replay.coverage)
        observations.append((rows, words))
    assert observations[0] == observations[1]
    rows, words = observations[0]
    assert all(all(raw[pc - BASE:pc - BASE + 4] == bytes.fromhex(word) for raw in originals) for pc, word in words.items())
    report = dict(schema='ys4470.native-cold-state-metric5.v1', images=images, total_cases=4, cases=rows,
                  instruction_bytes={hex(pc): word for pc, word in sorted(words.items())},
                  source_sha256={f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in (Path(__file__), Path(__file__).with_name('validate_native_cold_state_metric14_pair.py'))},
                  limits=['Original25958(DISPLAY,5)->4 and3dda8/tag15 execute from590e4 through59100; exact realloc78 arguments precede NULL/moving-success outcome fixtures.',
                          'Full504-byte heap, every prior/new vector and guard, BSS/DATA/display/timer, SP/saved callerframe and caller R4/R5/R9 checked.',
                          'The raw scalar4 has no inferred physical unit. Original allocator/free/reuse, earlier hardware/environment models, later configuration/initializer/root/callback and physicalLCD/timing remain open.'])
    a.out.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(passed_cases=4, metric=rows[-1]['metric_results'], tag='0x15', success_style=rows[-1]['final_style_hex'])))


if __name__ == '__main__':
    main()
