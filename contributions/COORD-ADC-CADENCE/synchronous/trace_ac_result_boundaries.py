"""Replay signed UART samples and AC result boundaries through the original display path."""

import argparse
import hashlib
import json
from itertools import product
from pathlib import Path

from trace_ac_checkbox_renderer import BASE, INIT_BASE, SETTINGS, TABLE_SIZE, UNIT_TABLE, NativeViewReplay, restore_globals

SELECTORS = (0, 1, 2, 3, 4, 5, 6, 7, 255)
EXPONENTS = (3, 2, 1, 0, 0, 0, 0)
SIGNED_MIN = -(1 << 23)
OVERLOAD = (1 << 23) - 1


def samples(selector):
    """Include the nearest representable samples on each side of the two cutoffs."""
    divisor = 10 ** EXPONENTS[min(selector, 6)]
    values = {SIGNED_MIN, -12345, -1, 0, 1, OVERLOAD - 1, OVERLOAD}
    for twice_cutoff in (5, 11):
        floor, remainder = divmod(twice_cutoff * divisor, 2)
        values.update((floor - 1, floor, floor + 1))
        if remainder:
            values.add(floor + 2)
    return sorted(values)


def replay_path(raw, table, initial_checkbox, cutoff_setting):
    replay = NativeViewReplay(raw, table)
    replay.prepare_refresh_state(initial_checkbox, 2)
    replay.put(SETTINGS + 0x14, cutoff_setting)
    replay.timer_refresh(2)
    assert not replay.measurement(100, 0, True)["published"]
    replay.timer_refresh(2)
    rows = []
    for selector in SELECTORS:
        for sample in samples(selector):
            packet = replay.measurement(sample & 0xFFFFFF, selector, True)
            assert packet["published"]
            row = replay.timer_refresh(2)
            record, = row["native_render_record"]
            assert record["configuration"] == (9 if initial_checkbox else 10)
            assert record["selector"] == min(selector, 6)
            assert record["raw"] == (sample & 0xFFFFFFFF)
            rows.append([sample, selector, packet["reply"], record["raw"], record["selector"],
                         record["scale_bits"], record["text"], record["unit"], record["flags"]])
    return dict(configuration=9 if initial_checkbox else 10, cutoff_setting=cutoff_setting,
                cases=rows), replay.coverage


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    manifest = json.loads(Path("original-firmware/manifest.json").read_bytes())
    assert int(manifest["linked_base"], 16) == BASE
    images, observations = {}, []
    for entry in manifest["images"]:
        raw = Path(entry["path"]).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        assert digest == entry["sha256"] and len(raw) == entry["size_bytes"]
        images[entry["version"]] = digest
        offset = UNIT_TABLE - INIT_BASE
        table = restore_globals(raw)[offset:offset + TABLE_SIZE]
        assert len(table) == TABLE_SIZE
        for configuration in (9, 10):
            start = 0x80063817 - BASE + 7 * configuration
            assert tuple(raw[start:start+7]) == EXPONENTS
        paths, coverage = [], {}
        for initial_checkbox, cutoff_setting in product((0, 1), repeat=2):
            path, instructions = replay_path(raw, table, initial_checkbox, cutoff_setting)
            paths.append(path)
            coverage.update(instructions)
        observations.append((paths, coverage))
    assert images.keys() == {"V3.6", "V3.8"} and observations[0] == observations[1]
    paths, coverage = observations[0]
    count = sum(len(path["cases"]) for path in paths)
    report = dict(
        schema="ys4470.ac-result-boundaries.v1", images=images, cases_per_image=count,
        case_columns=["signed_uart_sample", "uart_selector", "reply_hex", "stored_raw_word", "stored_selector",
                      "render_float_bits", "render_text", "render_unit", "render_flags"],
        paths=paths, scale_exponent_table="0x80063817", config_9_10_scale_exponents=EXPONENTS,
        instruction_bytes={hex(pc): code for pc, code in sorted(coverage.items())},
        limits=["Original checkbox, UART2 IRQ, parser, result dispatch and renderer execute.",
                "The cutoff setting is seeded independently. Timer-list, formatting and display sinks are modeled.",
                "The tested UART words are synthetic. ADC conversion, input voltage and pixel output remain outside the model."],
    )
    with args.out.open("w", encoding="utf-8", newline="\n") as output:
        output.write(json.dumps(report, separators=(",", ":")) + "\n")
    print(f"PASS {count} native AC result cases per factory image, {2*count} total")


if __name__ == "__main__":
    main()
