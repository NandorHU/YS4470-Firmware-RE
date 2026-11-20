"""Execute the next four cold style properties with independent guarded references."""
import argparse
import hashlib
import inspect
import itertools
import json
from pathlib import Path
import struct

from unicorn.arm_const import UC_ARM_REG_PC, UC_ARM_REG_LR, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R8, UC_ARM_REG_R9, UC_ARM_REG_SP, UC_ARM_REG_CPSR
from validate_native_cold_metric16_style import Metric16StyleReplay, METRIC16_RETURN, HEAP, HEAP_BYTES, DISPLAY, TIMER, BASE, vector_bytes, REALLOC, BSS, LENGTH, DATA, STATE

AFTER_TAIL = 0x8005904C
TARGETS = tuple(0x12019000 + i * 0x1000 for i in range(4))
TAGS = (0x44, 0x40, 0x45, 0x42)
RETURNS = (0x80058F98, 0x80058FE8, 0x80058FF8, AFTER_TAIL)
WRAPPERS = (0x8003DFAC, 0x8003DFEC, 0x8003DFD4, 0x8003DFC8)


class PaletteTailReplay(Metric16StyleReplay):
    def __init__(self, raw):
        self.palette_tail_phase = False
        self.tail_buffers = {}
        self.tail_wrapper_inputs = []
        self.tail_getter_inputs = []
        self.tail_getter_results = []
        self.tail_metric_calls = []
        self.tail_metric_results = []
        self.tail_branch = []
        super().__init__(raw)

    def code(self, u, pc, size, data):
        if self.palette_tail_phase:
            if pc == self.stop:
                u.emu_stop()
                return
            if pc in WRAPPERS:
                self.tail_wrapper_inputs.append([pc] + [u.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2)])
            if pc == 0x80025CA4:
                self.tail_getter_inputs.append([u.reg_read(UC_ARM_REG_R0), u.reg_read(UC_ARM_REG_LR)])
            # Unicorn emits a code hook even for a condition-false ARM instruction.
            if pc == 0x80025CD0 or (pc == 0x80025CBC and u.reg_read(UC_ARM_REG_CPSR) & (1 << 30)):
                self.tail_getter_results.append([pc, u.reg_read(UC_ARM_REG_R0)])
            if pc == 0x80025958:
                self.tail_metric_calls.append([u.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1)])
            if pc == 0x800259AC:
                self.tail_metric_results.append(u.reg_read(UC_ARM_REG_R0))
            if pc in (0x80058F10, 0x80058F14, 0x80058F18, 0x80058F1C, 0x80058F80):
                self.tail_branch.append(pc)
            if any(lo <= pc < hi for lo, hi in ((METRIC16_RETURN, AFTER_TAIL), (0x8003DFAC, 0x8003DFF8),
                    (0x8003DDE4, 0x8003DFAC), (0x8003AE20, 0x8003AE58),
                    (0x80025958, 0x800259B0), (0x80025CA4, 0x80025CD4))):
                assert size == 4
                self.coverage[pc] = bytes(u.mem_read(pc, size)).hex()
                return
        super().code(u, pc, size, data)

    def write(self, u, access, address, size, value, data):
        if self.palette_tail_phase:
            pc = u.reg_read(UC_ARM_REG_PC)
            if HEAP + 0x20 <= address and address + size <= HEAP + 0x28:
                assert pc in (0x8003DE98, 0x8003DED0, 0x8003DF98)
                return
            if any(a <= address and address + size <= a + len(raw) for a, raw in self.tail_buffers.items()):
                assert pc in (0x8003DEB8, 0x8003DDF0, 0x8003DDF4)
                return
        super().write(u, access, address, size, value, data)

    def snapshots(self):
        # Whole BSS/DATA include OBJECT, STATE, defaults and all other cold globals.
        regions = [(BSS, LENGTH), (DATA, 0x15E4), (DISPLAY, 0x15C), (TIMER, 32)]
        for name in ('compound_buffers', 'record_buffers', 'metric14_buffers', 'color_pair_buffers',
                     'metric2_buffers', 'metric24_buffers', 'padding14_buffers', 'palette_metric_buffers',
                     'a0_buffers', 'a8_buffers', 'metric16_buffers'):
            for a, raw in getattr(self, name).items():
                regions.append((a - 16, len(raw) + 32))
        # The prefix has some earlier singleton allocations not held in those dictionaries.
        from validate_native_cold_metric16_style import GROWTH, MOVED, NEW, BASE_VECTOR, SECONDARY_VECTOR, METRIC12_VECTOR
        regions.extend([(GROWTH - 16, 44), (MOVED - 16, 50), (NEW - 16, 74),
                        (BASE_VECTOR - 16, 44), (SECONDARY_VECTOR - 16, 50), (METRIC12_VECTOR - 16, 44)])
        return {a: bytes(self.u.mem_read(a, n)) for a, n in regions}

    def run_tail(self, schedule):
        assert len(schedule) == 4 and all(type(x) is bool for x in schedule)
        self.run_metric16_style((True, True))
        assert self.u.reg_read(UC_ARM_REG_PC) == METRIC16_RETURN
        self.metric16_style_phase = False  # Its getter hook is specific to metric16.
        before = self.snapshots()
        expected_heap = bytearray(self.u.mem_read(HEAP, HEAP_BYTES))
        assert expected_heap[0x20:0x28].hex() == '008001120b000503'
        sp = self.u.reg_read(UC_ARM_REG_SP)
        before[sp] = bytes(self.u.mem_read(sp, 0x1100F000 - sp))
        values, tags, pointer = [13, 0xFF, 0x1201E71C], [0x0B, 0x21, 0x20], 0x12018000
        assert self.u.mem_read(pointer, 18) == vector_bytes(values, tags)
        default_base = self.word(0x80025CD4)
        default_pointer = self.word(default_base + 12)
        assert default_base == 0x805ABD54 and default_pointer == DISPLAY
        driver = self.word(default_pointer)
        flags = self.word(driver + 0x10)
        getter_reference = ((flags << 15) & 0xFFFFFFFF) >> 22
        assert flags == 0x413C and getter_reference == 130
        expected_raw = (0x12019CF3, 2, 0x7F, 2)
        self.palette_tail_phase = True
        start, steps = METRIC16_RETURN, []
        for index, (tag, success, return_pc, target, value) in enumerate(zip(TAGS, schedule, RETURNS, TARGETS, expected_raw)):
            count = len(values)
            size = 6 * (count + 1)
            self.stop = REALLOC
            self.u.emu_start(start, 0, count=10000)
            assert self.u.reg_read(UC_ARM_REG_PC) == REALLOC
            actual = [self.u.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_LR)]
            assert actual == [pointer, size, 0x8003DE90]
            assert self.u.reg_read(UC_ARM_REG_SP) == sp - 32
            assert self.u.reg_read(UC_ARM_REG_R8) == tag and self.u.reg_read(UC_ARM_REG_R9) == value
            assert self.u.mem_read(pointer, count * 6) == vector_bytes(values, tags)
            assert self.u.mem_read(HEAP, HEAP_BYTES) == expected_heap
            wrapper, style, incoming, retained = self.tail_wrapper_inputs[-1]
            assert wrapper == WRAPPERS[index] and style == HEAP + 0x20
            if index == 0:
                assert incoming == 0x9CF3 and retained >> 16 == 0x1201
            else:
                assert incoming == value
            initial = vector_bytes(values, tags) + b'\xA5' * 6 if success else b'\xA5' * size
            self.u.mem_write(target - 16, b'\x92' * 16)
            self.u.mem_write(target, initial)
            self.u.mem_write(target + size, b'\x29' * 16)
            self.tail_buffers[target] = initial
            if success:
                values.append(value)
                tags.append(tag)
                pointer = target
                self.tail_buffers[target] = vector_bytes(values, tags)
                summary = 0
                for t in tags:
                    summary |= 1 << min((t >> 4) & 0x1F, 7)
                struct.pack_into('<IHBB', expected_heap, 0x20, pointer, 0x0B, summary, len(values))
            self.u.reg_write(UC_ARM_REG_R0, target if success else 0)
            self.stop = return_pc
            self.u.emu_start(0x8003DE90, 0, count=10000)
            assert self.u.reg_read(UC_ARM_REG_PC) == return_pc
            assert self.u.reg_read(UC_ARM_REG_SP) == sp
            assert self.u.mem_read(HEAP, HEAP_BYTES) == expected_heap
            for address, expected in before.items():
                assert self.u.mem_read(address, len(expected)) == expected
            for address, expected in self.tail_buffers.items():
                assert self.u.mem_read(address, len(expected)) == expected
                assert self.u.mem_read(address - 16, 16) == b'\x92' * 16
                assert self.u.mem_read(address + len(expected), 16) == b'\x29' * 16
            assert self.u.mem_read(HEAP - 16, 16) == b'\x6E' * 16
            assert self.u.mem_read(HEAP + HEAP_BYTES, 16) == b'\xE6' * 16
            steps.append(dict(tag=hex(tag), raw_value=hex(value), wrapper_input=[hex(x) for x in self.tail_wrapper_inputs[-1]],
                              actual_realloc_arguments=[hex(actual[0]), actual[1], hex(actual[2])],
                              outcome_fixture='guarded_success' if success else 'null',
                              style_hex=expected_heap[0x20:0x28].hex(), vector_hex=vector_bytes(values, tags).hex()))
            start = return_pc
        assert self.tail_branch == [0x80058F10, 0x80058F14, 0x80058F18, 0x80058F80]
        assert [x[0] for x in self.tail_getter_inputs] == [0, 0, 0, 0, DISPLAY, DISPLAY]
        assert self.tail_getter_results == [[0x80025CD0, 130]] * 6
        assert self.tail_metric_calls == [[DISPLAY, 3]] and self.tail_metric_results == [2]
        return dict(allocation_success_fixtures=list(schedule), default_display_pointer=hex(default_pointer),
                    default_driver=hex(driver), default_flags=hex(flags), getter_inputs=self.tail_getter_inputs,
                    getter_returns=self.tail_getter_results, metric_calls=self.tail_metric_calls,
                    metric_returns=self.tail_metric_results, steps=steps, final_values=values, final_tags=tags,
                    final_style_hex=expected_heap[0x20:0x28].hex(), final_vector_hex=vector_bytes(values, tags).hex(),
                    complete_heap_vectors_guards_checked=True, prior_vectors_bss_data_display_timer_unchanged=True,
                    caller_sp_preserved=True, saved_caller_frame_preserved=True, stop_pc=hex(AFTER_TAIL), initializer_returned=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--probe', action='store_true', help='One all-success case, retained separately from final campaign')
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[3]
    manifest = json.loads((repo / 'original-firmware/manifest.json').read_bytes())
    images, originals, observations = {}, [], []
    for item in manifest['images'][:1] if args.probe else manifest['images']:
        raw = (repo / item['path']).read_bytes()
        assert len(raw) == item['size_bytes'] and hashlib.sha256(raw).hexdigest() == item['sha256']
        images[item['version']] = item['sha256']
        originals.append(raw)
        rows, words = [], {}
        for schedule in [(True,) * 4] if args.probe else itertools.product((False, True), repeat=4):
            replay = PaletteTailReplay(raw)
            rows.append(replay.run_tail(schedule))
            words.update(replay.coverage)
        observations.append((rows, words))
    if not args.probe:
        assert observations[0] == observations[1]
    rows, words = observations[0]
    assert all(all(raw[pc - BASE:pc - BASE + 4] == bytes.fromhex(word) for raw in originals) for pc, word in words.items())
    sources = {Path(__file__).resolve()}
    for klass in PaletteTailReplay.__mro__:
        try:
            source = Path(inspect.getsourcefile(klass)).resolve()
            if source.parent == Path(__file__).resolve().parent:
                sources.add(source)
        except TypeError:
            pass
    report = dict(schema='ys4470.native-cold-palette-tail.v1', images=images,
                  total_cases=len(images) * len(rows), probe_only=args.probe, cases=rows,
                  instruction_bytes={hex(pc): word for pc, word in sorted(words.items())},
                  source_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(sources)},
                  limits=['Original continuation58f10..5904c and style-property bodies execute; allocator outcomes alone are injected at captured native realloc return3de90 after exact argument checks.',
                          'Four properties tags44/40/45/42 append raw values12019cf3/2/7f/2 under sixteen schedules per original. Opaque highhalf1201 is retained, not assigned a physical color meaning.',
                          'The zero-input default getter dereferences native restored805abd54+0xc=DISPLAY, then flags413c; it does not use its NULL fallback. All six actual getter returns130 and final active-display metric call(DISPLAY,3)->2 are checked.',
                          'Whole504-byte heap, all old/new vectors and guards, BSS/DATA/display/timer and caller stack pointer checked after each insertion. Prefix cold environment/raw clocks/list manager remain fixtures.',
                          'Native allocator implementation/free/reuse, later configuration suffix, initializer return, roots/callbacks and physical LCD/timing remain open. Probe is preparation, not an additional campaign case.'])
    args.out.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(passed_cases=report['total_cases'], final_all_success_style=rows[-1]['final_style_hex'],
                          success_sizes=[s['actual_realloc_arguments'][1] for s in rows[-1]['steps']],
                          native_default_display=rows[-1]['default_display_pointer'], stop=hex(AFTER_TAIL))))


if __name__ == '__main__':
    main()
