"""Contract and mutation tests; these do not count as original ARM executions."""
import itertools
import unittest
from style_reference import INITIAL_POINTER, INITIAL_STYLE, INITIAL_TAGS, INITIAL_VALUES, TARGETS, TAGS, simulate

RAW = (0x12019CF3, 2, 0x7F, 2)  # Explicit illustrative fixture, not a binary-derived finding.


def decode(raw):
    count, = (len(raw) // 6,)
    return ([int.from_bytes(raw[i * 4:i * 4 + 4], "little") for i in range(count)],
            [int.from_bytes(raw[count * 4 + i * 2:count * 4 + i * 2 + 2], "little") for i in range(count)])


class ReferenceTests(unittest.TestCase):
    def test_all_schedules_obey_independent_selection_oracle(self):
        for schedule in itertools.product((False, True), repeat=4):
            with self.subTest(schedule=schedule):
                result = simulate(schedule, RAW)
                selected = [i for i, yes in enumerate(schedule) if yes]
                self.assertEqual(result["final_values"], INITIAL_VALUES + tuple(RAW[i] for i in selected))
                self.assertEqual(result["final_tags"], INITIAL_TAGS + tuple(TAGS[i] for i in selected))
                expected_pointer = TARGETS[selected[-1]] if selected else INITIAL_POINTER
                self.assertEqual(result["final_pointer"], expected_pointer)
                expected_summary = 0x15 if selected else 0x05
                self.assertEqual(result["final_style"], expected_pointer.to_bytes(4, "little") + b"\x0B\x00" + bytes((expected_summary, 3 + len(selected))))

    def test_all_success_sizes_style_and_wire_layout(self):
        r = simulate((True,) * 4, RAW)
        self.assertEqual([s.requested_bytes for s in r["steps"]], [24, 30, 36, 42])
        self.assertEqual(r["final_style"].hex(), "00c001120b001507")
        self.assertEqual(decode(r["buffers"][TARGETS[-1]]), (list(INITIAL_VALUES + RAW), list(INITIAL_TAGS + TAGS)))

    def test_all_null_does_not_increment_or_move_style(self):
        r = simulate((False,) * 4, RAW)
        self.assertEqual(r["final_style"], INITIAL_STYLE)
        self.assertEqual([s.requested_bytes for s in r["steps"]], [24] * 4)
        for s in r["steps"]:
            self.assertEqual(s.style_before, s.style_after)
            self.assertEqual(s.target_before, b"\xA5" * 24)
            self.assertEqual(s.target_before, s.target_after)

    def test_each_move_preserves_old_buffer_and_old_tag_values(self):
        for schedule in itertools.product((False, True), repeat=4):
            r = simulate(schedule, RAW)
            for index, step in enumerate(r["steps"]):
                if step.success:
                    self.assertEqual(step.target_before[:-6], r["buffers"][step.input_pointer])
                    self.assertEqual(step.target_before[-6:], b"\xA5" * 6)
                values, tags = decode(r["buffers"][step.input_pointer])
                old_values = list(INITIAL_VALUES) + [RAW[i] for i in range(index) if schedule[i]]
                old_tags = list(INITIAL_TAGS) + [TAGS[i] for i in range(index) if schedule[i]]
                self.assertEqual((values, tags), (old_values, old_tags))

    def test_whole_heap_preserved_outside_target_header(self):
        heap = bytearray(bytes(range(252)) * 2)
        heap[0x20:0x28] = INITIAL_STYLE
        for schedule in itertools.product((False, True), repeat=4):
            result = simulate(schedule, RAW, heap)
            actual = result["final_heap"]
            self.assertEqual(actual[:0x20], heap[:0x20])
            self.assertEqual(actual[0x28:], heap[0x28:])
            self.assertEqual(actual[0x20:0x28], result["final_style"])

    def test_color_high_halfword_is_raw_input_not_invented_by_reference(self):
        a, b = simulate((True,) * 4, RAW), simulate((True,) * 4, (0x9CF3, 2, 0x7F, 2))
        self.assertEqual(a["final_values"][3], 0x12019CF3)
        self.assertEqual(b["final_values"][3], 0x9CF3)
        self.assertEqual(a["final_style"], b["final_style"])

    def test_malformed_schedule_values_or_snapshot_fail_closed(self):
        for schedule, raw, heap in [((True,), RAW, None), ((1,) * 4, RAW, None), ((True,) * 4, (-1, 2, 3, 4), None), ((True,) * 4, (1 << 32, 2, 3, 4), None), ((True,) * 4, RAW, bytes(504))]:
            with self.assertRaises(ValueError): simulate(schedule, raw, heap)


if __name__ == "__main__":
    unittest.main()
