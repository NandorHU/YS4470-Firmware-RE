"""Follow the second actual STATE selector into metric14 and tags10/11."""
import argparse
import hashlib
import itertools
import json
from pathlib import Path
import struct
from unicorn.arm_const import UC_ARM_REG_PC, UC_ARM_REG_LR, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R4, UC_ARM_REG_R8, UC_ARM_REG_R9, UC_ARM_REG_SP, UC_ARM_REG_CPSR
from validate_native_cold_state_metric24_pair import StateMetric24PairReplay, RETURN as START, HEAP, HEAP_BYTES, STATE, BASE, REALLOC, vector_bytes, DISPLAY, PRIOR

RETURN = 0x800590E4


class StateMetric14PairReplay(StateMetric24PairReplay):
    def __init__(self, raw):
        self.state_metric14_phase = False
        self.state_metric14_buffers = {}
        self.state_metric14_calls, self.state_metric14_results = [], []
        self.state_metric14_branch, self.state_metric14_wrapper = [], []
        super().__init__(raw)

    def code(self, u, pc, size, data):
        if self.state_metric14_phase:
            if pc == self.stop:
                u.emu_stop()
                return
            if pc in (0x800590AC, 0x800590B0, 0x80059C60, 0x80059C6C):
                self.state_metric14_branch.append(pc)
                if pc == 0x800590B0:
                    assert u.reg_read(UC_ARM_REG_CPSR) & (1 << 30)
            if pc == 0x80025958:
                self.state_metric14_calls.append([u.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1)])
            if pc == 0x800259AC:
                self.state_metric14_results.append(u.reg_read(UC_ARM_REG_R0))
            if pc in (0x8003DDD8, 0x8003DD9C):
                self.state_metric14_wrapper.append([pc, u.reg_read(UC_ARM_REG_R0), u.reg_read(UC_ARM_REG_R1)])
            if any(lo <= pc < hi for lo, hi in ((START, RETURN), (0x80059C60, 0x80059C70),
                    (0x80025958, 0x800259B0), (0x80025CA4, 0x80025CD4), (0x8003DD9C, 0x8003DDA8), (0x8003DDD8, 0x8003DFAC))):
                assert size == 4
                self.coverage[pc] = bytes(u.mem_read(pc, size)).hex()
                return
        super().code(u, pc, size, data)

    def write(self, u, access, address, size, value, data):
        if self.state_metric14_phase:
            pc = u.reg_read(UC_ARM_REG_PC)
            if HEAP + 0x20 <= address and address + size <= HEAP + 0x28:
                assert pc in (0x8003DE98, 0x8003DED0, 0x8003DF98)
                return
            if any(a <= address and address + size <= a + len(raw) for a, raw in self.state_metric14_buffers.items()):
                assert pc in (0x8003DEB8, 0x8003DDF0, 0x8003DDF4)
                return
        super().write(u, access, address, size, value, data)

    def run_state_metric14_pair(self, schedule):
        assert len(schedule) == 2 and all(type(s) is bool for s in schedule)
        self.run_state_metric24_pair((True, True))
        self.state_metric24_phase = False
        self.state_metric14_phase = True
        u = self.u
        # The previous arena is occupied through1201f000; map a separate new arena.
        u.mem_map(0x12020000, 0x10000)
        assert u.reg_read(UC_ARM_REG_R4) == STATE and bytes(u.mem_read(STATE + 1, 1)) == b'\x01'
        sp = u.reg_read(UC_ARM_REG_SP)
        snapshots = self.snapshots()
        for buffers in (self.tail_buffers, self.state_metric24_buffers):
            for address, raw in buffers.items():
                snapshots[address - 16] = bytes(u.mem_read(address - 16, len(raw) + 32))
        snapshots[PRIOR - 16] = bytes(u.mem_read(PRIOR - 16, 80))
        snapshots[sp] = bytes(u.mem_read(sp, 0x1100F000 - sp))
        heap = bytearray(u.mem_read(HEAP, HEAP_BYTES))
        assert heap[0x20:0x28].hex() == '00f001120b00370a'
        values = [13, 0xFF, 0x1201E71C, 0x12019CF3, 2, 0x7F, 2, 0x12012104, 20, 20]
        tags = [0x0B, 0x21, 0x20, 0x44, 0x40, 0x45, 0x42, 0x55, 0x12, 0x13]
        pointer, start, steps = 0x1201F000, START, []
        for index, (success, tag, after) in enumerate(zip(schedule, (0x10, 0x11), (0x800590D8, RETURN))):
            count = len(values)
            size = 6 * (count + 1)
            self.stop = REALLOC
            u.emu_start(start, 0, count=10000)
            assert u.reg_read(UC_ARM_REG_PC) == REALLOC
            args = [u.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_LR)]
            assert args == [pointer, size, 0x8003DE90]
            assert u.reg_read(UC_ARM_REG_SP) == sp - 32
            assert u.reg_read(UC_ARM_REG_R8) == tag and u.reg_read(UC_ARM_REG_R9) == 11
            assert u.mem_read(pointer, count * 6) == vector_bytes(values, tags)
            assert u.mem_read(HEAP, HEAP_BYTES) == heap
            target = 0x12021000 + index * 0x1000
            initial = vector_bytes(values, tags) + b'\xA5' * 6 if success else b'\xA5' * size
            u.mem_write(target - 16, b'\x95' * 16)
            u.mem_write(target, initial)
            u.mem_write(target + size, b'\x59' * 16)
            self.state_metric14_buffers[target] = initial
            if success:
                values.append(11)
                tags.append(tag)
                pointer = target
                self.state_metric14_buffers[target] = vector_bytes(values, tags)
                # Nibble1 is already represented by the prior tags12/13.
                struct.pack_into('<IHBB', heap, 0x20, pointer, 0x0B, 0x37, len(values))
            u.reg_write(UC_ARM_REG_R0, target if success else 0)
            self.stop = after
            u.emu_start(0x8003DE90, 0, count=10000)
            assert u.reg_read(UC_ARM_REG_PC) == after and u.reg_read(UC_ARM_REG_SP) == sp
            assert u.mem_read(HEAP, HEAP_BYTES) == heap
            for a, raw in snapshots.items():
                assert u.mem_read(a, len(raw)) == raw
            for a, raw in self.state_metric14_buffers.items():
                assert u.mem_read(a, len(raw)) == raw
                assert u.mem_read(a - 16, 16) == b'\x95' * 16 and u.mem_read(a + len(raw), 16) == b'\x59' * 16
            assert u.mem_read(HEAP - 16, 16) == b'\x6E' * 16 and u.mem_read(HEAP + HEAP_BYTES, 16) == b'\xE6' * 16
            steps.append(dict(tag=hex(tag), raw_value=11, actual_realloc_arguments=[hex(args[0]), args[1], hex(args[2])],
                              success_fixture=success, style_hex=heap[0x20:0x28].hex(), vector_hex=vector_bytes(values, tags).hex()))
            start = after
        assert self.state_metric14_branch == [0x800590AC, 0x800590B0, 0x80059C60, 0x80059C6C]
        assert self.state_metric14_calls == [[DISPLAY, 14]] and self.state_metric14_results == [11]
        assert self.state_metric14_wrapper == [[0x8003DDD8, HEAP + 0x20, 11], [0x8003DD9C, HEAP + 0x20, 11]]
        return dict(allocation_success_fixtures=list(schedule), selector_state_address=hex(STATE + 1), selector_value=1,
                    actual_branch=[hex(a) for a in self.state_metric14_branch], metric_inputs=self.state_metric14_calls,
                    metric_results=self.state_metric14_results, wrapper_inputs=self.state_metric14_wrapper,
                    steps=steps, final_values=values, final_tags=tags, final_style_hex=heap[0x20:0x28].hex(),
                    all_heap_vectors_guards_globals_sp_and_caller_frame_checked=True, stop_pc=hex(RETURN), initializer_returned=False)


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
        for schedule in itertools.product((False, True), repeat=2):
            replay = StateMetric14PairReplay(raw)
            rows.append(replay.run_state_metric14_pair(schedule))
            words.update(replay.coverage)
        observations.append((rows, words))
    assert observations[0] == observations[1]
    rows, words = observations[0]
    assert all(all(raw[pc - BASE:pc - BASE + 4] == bytes.fromhex(word) for raw in originals) for pc, word in words.items())
    report = dict(schema='ys4470.native-cold-state-metric14-pair.v1', images=images, total_cases=8, cases=rows,
                  instruction_bytes={hex(pc): word for pc, word in sorted(words.items())},
                  source_sha256={f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in (Path(__file__), Path(__file__).with_name('validate_native_cold_state_metric24_pair.py'))},
                  limits=['Actual second STATE byte1=1 selector branches590b0->59c60, original25958(DISPLAY,14)->11 and wrappers3ddd8/tag10,3dd9c/tag11 through590e4. Alternate selector values remain untested.',
                          'Four explicit NULL/moving-success schedules per original. Exact realloc pointer/size checked before outcome fixtures. Fresh12020000 arena, all-success66/72-byte vectors.',
                          'Entire504-byte heap, all prior/new vectors/guards, BSS/DATA/display/timer, SP and saved caller frame checked. Prefix/allocator/free/reuse/hardware models remain explicit.',
                          'Stop590e4 before metric5 and next tag15. No complete configuration/initializer return, roots/callbacks, physical units or LCD/timing claim.'])
    a.out.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(passed_cases=8, actual_metric=rows[-1]['metric_results'], final_style=rows[-1]['final_style_hex'], sizes=[s['actual_realloc_arguments'][1] for s in rows[-1]['steps']])))


if __name__ == '__main__':
    main()
