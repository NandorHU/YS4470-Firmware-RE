"""Capture the actual R4 STATE halfword and append tag55 with guarded outcomes."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from unicorn.arm_const import UC_ARM_REG_PC, UC_ARM_REG_LR, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R8, UC_ARM_REG_R9, UC_ARM_REG_SP
from validate_native_cold_palette_tail import PaletteTailReplay, AFTER_TAIL, HEAP, HEAP_BYTES, BASE, STATE, REALLOC, vector_bytes

RETURN = 0x8005905C
TARGET = 0x1201D000


class StateHalfwordReplay(PaletteTailReplay):
    def __init__(self, raw):
        self.state_halfword_phase = False
        self.state_halfword_input = None
        self.state_halfword_buffer = None
        super().__init__(raw)

    def code(self, u, pc, size, data):
        if self.state_halfword_phase:
            if pc == self.stop:
                u.emu_stop()
                return
            if pc == 0x8003E004:
                self.state_halfword_input = [u.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2)]
            if any(lo <= pc < hi for lo, hi in ((AFTER_TAIL, RETURN), (0x8003E004, 0x8003E020), (0x8003DDE4, 0x8003DFAC))):
                assert size == 4
                self.coverage[pc] = bytes(u.mem_read(pc, size)).hex()
                return
        super().code(u, pc, size, data)

    def write(self, u, access, address, size, value, data):
        if self.state_halfword_phase:
            pc = u.reg_read(UC_ARM_REG_PC)
            if HEAP + 0x20 <= address and address + size <= HEAP + 0x28:
                assert pc in (0x8003DE98, 0x8003DED0, 0x8003DF98)
                return
            if self.state_halfword_buffer is not None and TARGET <= address and address + size <= TARGET + 48:
                assert pc in (0x8003DEB8, 0x8003DDF0, 0x8003DDF4)
                return
        super().write(u, access, address, size, value, data)

    def run_state_halfword(self, success):
        self.run_tail((True,) * 4)
        self.palette_tail_phase = False
        self.state_halfword_phase = True
        u = self.u
        sp = u.reg_read(UC_ARM_REG_SP)
        snapshots = self.snapshots()
        for a, raw in self.tail_buffers.items():
            snapshots[a - 16] = bytes(u.mem_read(a - 16, len(raw) + 32))
        snapshots[sp] = bytes(u.mem_read(sp, 0x1100F000 - sp))
        heap = bytearray(u.mem_read(HEAP, HEAP_BYTES))
        assert heap[0x20:0x28].hex() == '00c001120b001507'
        assert u.reg_read(UC_ARM_REG_R4) == STATE == 0x805ABC6C
        object_pointer = u.reg_read(UC_ARM_REG_R5)
        assert object_pointer == 0x807B52F8
        halfword = struct.unpack('<H', u.mem_read(STATE + 4, 2))[0]
        assert halfword == 0x2104
        values = [13, 0xFF, 0x1201E71C, 0x12019CF3, 2, 0x7F, 2]
        tags = [0x0B, 0x21, 0x20, 0x44, 0x40, 0x45, 0x42]
        pointer = 0x1201C000
        assert u.mem_read(pointer, 42) == vector_bytes(values, tags)
        self.stop = REALLOC
        u.emu_start(AFTER_TAIL, 0, count=10000)
        assert u.reg_read(UC_ARM_REG_PC) == REALLOC
        actual = [u.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_LR)]
        assert actual == [pointer, 48, 0x8003DE90]
        style, incoming, retained = self.state_halfword_input
        assert style == HEAP + 0x20 and incoming == halfword and retained >> 16 == 0x1201
        value = (retained & 0xFFFF0000) | halfword
        assert value == 0x12012104 and u.reg_read(UC_ARM_REG_R8) == 0x55 and u.reg_read(UC_ARM_REG_R9) == value
        assert u.reg_read(UC_ARM_REG_SP) == sp - 32
        assert u.mem_read(HEAP, HEAP_BYTES) == heap
        initial = vector_bytes(values, tags) + b'\xA5' * 6 if success else b'\xA5' * 48
        u.mem_write(TARGET - 16, b'\x93' * 16)
        u.mem_write(TARGET, initial)
        u.mem_write(TARGET + 48, b'\x39' * 16)
        self.state_halfword_buffer = initial
        if success:
            values.append(value)
            tags.append(0x55)
            expected = vector_bytes(values, tags)
            struct.pack_into('<IHBB', heap, 0x20, TARGET, 0x0B, 0x35, 8)
        else:
            expected = initial
        u.reg_write(UC_ARM_REG_R0, TARGET if success else 0)
        self.stop = RETURN
        u.emu_start(0x8003DE90, 0, count=10000)
        assert u.reg_read(UC_ARM_REG_PC) == RETURN and u.reg_read(UC_ARM_REG_SP) == sp
        assert u.mem_read(HEAP, HEAP_BYTES) == heap
        assert u.mem_read(TARGET, 48) == expected
        assert u.mem_read(TARGET - 16, 16) == b'\x93' * 16 and u.mem_read(TARGET + 48, 16) == b'\x39' * 16
        assert u.mem_read(HEAP - 16, 16) == b'\x6E' * 16 and u.mem_read(HEAP + HEAP_BYTES, 16) == b'\xE6' * 16
        for a, raw in snapshots.items():
            assert u.mem_read(a, len(raw)) == raw
        return dict(allocation_success_fixture=success, actual_r4_state=hex(STATE), actual_r5_object=hex(object_pointer),
                    source_halfword_address=hex(STATE + 4), source_halfword=hex(halfword),
                    wrapper_inputs=[hex(v) for v in self.state_halfword_input], tag='0x55', raw_payload=hex(value),
                    actual_realloc_arguments=[hex(actual[0]), actual[1], hex(actual[2])],
                    final_style_hex=heap[0x20:0x28].hex(), new_allocation_hex=expected.hex(),
                    next_selector_state_byte1=int(u.mem_read(STATE + 1, 1)[0]),
                    whole_heap_all_vectors_guards_globals_and_saved_frame_preserved=True,
                    caller_sp_preserved=True, stop_pc=hex(RETURN), initializer_returned=False)


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
        originals.append(raw)
        images[item['version']] = item['sha256']
        rows, words = [], {}
        for success in (False, True):
            r = StateHalfwordReplay(raw)
            rows.append(r.run_state_halfword(success))
            words.update(r.coverage)
        observations.append((rows, words))
    assert observations[0] == observations[1]
    rows, words = observations[0]
    assert all(all(raw[pc - BASE:pc - BASE + 4] == bytes.fromhex(word) for raw in originals) for pc, word in words.items())
    report = dict(schema='ys4470.native-cold-state-halfword.v1', images=images, total_cases=4, cases=rows,
                  instruction_bytes={hex(pc): word for pc, word in sorted(words.items())},
                  source_sha256={f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in (Path(__file__), Path(__file__).with_name('validate_native_cold_palette_tail.py'))},
                  limits=['Original caller5904c..5905c, wrapper3e004/tag55 and property engine execute after the all-success prefix; exact realloc48 arguments precede NULL/moving-success outcome fixtures.',
                          'Actual R4=STATE805abc6c, R5=OBJECT807b52f8; source halfword is STATE+4=2104, not OBJECT+4. Opaque incoming R2 HIGH16 is1201, payload12012104. No physical field/color/unit meaning inferred.',
                          'Complete504-byte heap, prior/new vectors/guards, BSS/DATA/display/timer, saved caller frame and SP checked. Native allocator/free/reuse and prior environment models persist.',
                          'Stop5905c before selector dispatch. STATE byte1 is observed as1; its actual branch59c50 has not been executed in these cases. Full initializer/root/callback/physical timing remain open.'])
    a.out.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(passed_cases=4, raw_halfword=rows[-1]['source_halfword'], payload=rows[-1]['raw_payload'], success_style=rows[-1]['final_style_hex'], next_selector=rows[-1]['next_selector_state_byte1'])))


if __name__ == '__main__':
    main()
