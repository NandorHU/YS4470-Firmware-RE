"""Independent byte reference for the next four HEAP+20 insertions.

No Unicorn, replay-source imports or binary execution.  The coordinator must
bind this reference to captured original wrapper inputs before treating a
comparison as firmware evidence.  Allocation results and prefix preservation
remain explicit fixtures, not an allocator implementation model.
"""
from dataclasses import dataclass
from itertools import product


INITIAL_VALUES = (13, 0xFF, 0x1201E71C)
INITIAL_TAGS = (0x0B, 0x21, 0x20)
INITIAL_POINTER = 0x12018000
TARGETS = (0x12019000, 0x1201A000, 0x1201B000, 0x1201C000)
TAGS = (0x44, 0x40, 0x45, 0x42)
INITIAL_STYLE = bytes.fromhex("008001120b000503")


def checked(value, bits):
    if type(value) is not int or not 0 <= value < 1 << bits:
        raise ValueError(f"Expected unsigned {bits}-bit integer")
    return value


def vector_bytes(values, tags):
    """Values are contiguous u32s, THEN tags are contiguous u16s, little-endian."""
    if len(values) != len(tags):
        raise ValueError("Unequal value/tag counts")
    return b"".join(checked(v, 32).to_bytes(4, "little") for v in values) + b"".join(
        checked(t, 16).to_bytes(2, "little") for t in tags)


def style_bytes(pointer, tags):
    if not 2 <= len(tags) <= 255:
        raise ValueError("This reference covers array-backed styles only")
    summary = 0
    for tag in tags:
        summary |= 1 << min((checked(tag, 16) >> 4) & 31, 7)
    return (checked(pointer, 32).to_bytes(4, "little")
            + checked(tags[0], 16).to_bytes(2, "little")
            + bytes((summary, len(tags))))


@dataclass(frozen=True)
class Step:
    tag: int
    value: int
    success: bool
    input_pointer: int
    input_count: int
    requested_bytes: int
    target: int
    target_before: bytes
    target_after: bytes
    style_before: bytes
    style_after: bytes
    values_after: tuple
    tags_after: tuple


def simulate(schedule, captured_values, heap_before=None):
    """Return independent expected steps for exactly four new distinct tags.

    captured_values is mandatory: e.g. color44 retains the opaque HIGH16 of
    captured incoming R2.  This module cannot independently establish those
    raw inputs, or the scalar metric meanings, from the original firmware.
    """
    schedule = tuple(schedule)
    if len(schedule) != 4 or any(type(s) is not bool for s in schedule):
        raise ValueError("Exactly four explicit Boolean allocation outcomes required")
    captured_values = tuple(captured_values)
    if len(captured_values) != 4:
        raise ValueError("Exactly four independently captured raw values required")
    for v in captured_values:
        checked(v, 32)
    if heap_before is not None:
        heap_before = bytes(heap_before)
        if len(heap_before) != 504 or heap_before[0x20:0x28] != INITIAL_STYLE:
            raise ValueError("Expected the exact initial 504-byte heap/style snapshot")
    values, tags = list(INITIAL_VALUES), list(INITIAL_TAGS)
    pointer = INITIAL_POINTER
    buffers = {pointer: vector_bytes(values, tags)}
    steps = []
    for tag, value, success, target in zip(TAGS, captured_values, schedule, TARGETS):
        count = len(values)
        requested = (count + 1) * 6
        old_pointer, old_style = pointer, style_bytes(pointer, tags)
        before = buffers[pointer] + b"\xA5" * 6 if success else b"\xA5" * requested
        assert len(before) == requested
        after = before
        if success:
            values.append(value)
            tags.append(tag)
            pointer = target
            after = vector_bytes(values, tags)
        buffers[target] = after
        steps.append(Step(tag, value, success, old_pointer, count, requested, target,
                          before, after, old_style, style_bytes(pointer, tags),
                          tuple(values), tuple(tags)))
    final_heap = None
    if heap_before is not None:
        final_heap = bytearray(heap_before)
        final_heap[0x20:0x28] = style_bytes(pointer, tags)
        final_heap = bytes(final_heap)
    return {"steps": steps, "final_pointer": pointer, "final_values": tuple(values),
            "final_tags": tuple(tags), "final_style": style_bytes(pointer, tags),
            "buffers": buffers, "final_heap": final_heap}


def schedules():
    return product((False, True), repeat=4)
