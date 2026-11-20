"""Candidate-aware differential adapter for the diode fixed-range patch (2026-11-20).

Runs INSIDE a scratch copy of YS4470-EMULATOR-CLAUDE-20261120/source (cwd = that copy).
Original harness sources are imported unchanged; only expectations that depend on the
patched byte sites are parameterised here. Every harness runs on the pinned ownprotocol
baseline (original expectations) and on the candidate (derived expectations); results are
compared and only the differences implied by the patched site set are allowed.
No device I/O. Emulation does not establish physical timing or ADC behaviour.
"""
import argparse, copy, hashlib, json, struct, subprocess, sys, traceback
from itertools import product
from pathlib import Path

ROOT = Path.cwd()
for p in ("tools", "contributions/COORD-ADC-CADENCE", "contributions/COORD-ADC-CADENCE/synchronous",
          "contributions/COORD-ADC-CADENCE/uart", "contributions/COORD-ADC-CADENCE/ownprotocol"):
    sys.path.insert(0, str(ROOT / p))

BASE = 0x7FFFFFE0
SIZE = 5943296
V38_SHA = "7e7d7230155fe0790eb48531de2ef463bb122c0ae1a820ab6d10cf2e60f50290"
V36_SHA = "7523b2e91dd8627ffebfc7ac0525c0607a56df4cece04028a9c3a8ee558f6eb9"
OWN_SHA = "b081860a2383e5c1251ea80abf25cb4f39bdf74a340a376975acf2b0ff6f9c8e"
NEW = 0x13
# site -> (paired 'mov rY,#0xe' address, destination register use description)
SITES = {
    0x8000D000: 0x8000D004,  # cfd0 callback: r8, stored only to UI+8 at 0x8000d0d4
    0x8000D0BC: 0x8000D0C0,  # cfd0 callback: r2 -> producer bl 0x8000d0c8 (diode/non-fast buzzer)
    0x80044EC0: 0x80044EC4,  # selector: r8, function-wide, stored to UI+8 in FIVE branches
    0x80045044: 0x80045048,  # selector diode branch: r2 -> producer bl 0x80045050
    0x800450C4: 0x800450C8,  # selector buzzer non-fast: r2 -> producer bl 0x800450d0
}
CANDIDATES = {
    "5site": dict(sites=sorted(SITES),
                  sha="c5544d36f2069a8e7a503e0538abdeef732822a49cc2ad0524afaec4c653de0c"),
    "4site": dict(sites=sorted(set(SITES) - {0x80044EC0}),
                  sha="934a2557f7b069645ca3484a70e64e4e33844bf0b0892d2f3583078cadae9417"),
}


def sha(b): return hashlib.sha256(b).hexdigest()
def word(img, a): return struct.unpack_from("<I", img, a - BASE)[0]


def make(baseline, sites):
    """Same preimage contract as make_candidate.py; fail closed."""
    assert sha(baseline) == OWN_SHA and len(baseline) == SIZE
    return make_on(baseline, sites)


def make_on(baseline, sites):
    """Apply the same byte sites to a pinned factory image (for factory-only harness guards)."""
    assert sha(baseline) in (OWN_SHA, V38_SHA, V36_SHA) and len(baseline) == SIZE
    d = bytearray(baseline)
    for a in sites:
        w, wb = word(d, a), word(d, SITES[a])
        assert (w & 0xFFFF0FFF) == 0xE3A00019 and (wb & 0xFFFF0FFF) == 0xE3A0000E, hex(a)
        d[a - BASE] = NEW
    return bytes(d)


def load_images(kind):
    own_path = ROOT / "out/ownprotocol/ys4470-e2-ownprotocol-OFFLINE.bin"
    own = own_path.read_bytes()
    factory = (ROOT / "original-firmware/V3.8/f1c100s.bin").read_bytes()
    assert sha(factory) == V38_SHA and sha(own) == OWN_SHA
    spec = CANDIDATES[kind]
    cand = make(own, spec["sites"])
    assert spec["sha"] and sha(cand) == spec["sha"], (kind, sha(cand))
    return factory, own, cand, spec["sites"]


# ---------------------------------------------------------------- checks
def check_integrity(factory, own, cand, sites, kind):
    diff = [BASE + i for i in range(SIZE) if own[i] != cand[i]]
    assert diff == list(sites), [hex(x) for x in diff]
    assert len(cand) == len(own) == SIZE and cand[:32] == own[:32]
    for a in sites:
        assert own[a - BASE] == 0x19 and cand[a - BASE] == NEW
    # The ownprotocol patch does not touch the cfd0 callback or the mode selector.
    windows = ((0x8000CFD0, 0x8000D1C0), (0x80044E54, 0x80045180), (0x80006778, 0x800067C8))
    for lo, hi in windows:
        assert factory[lo - BASE:hi - BASE] == own[lo - BASE:hi - BASE], hex(lo)
    ref = Path(__file__).resolve().parents[1] / "ys4470-ownprotocol-diodefixed13-CANDIDATE.bin"
    if kind == "5site":
        assert ref.read_bytes() == cand, "regenerated 5-site candidate differs from cloud file"
    return dict(changed_sites=[hex(x) for x in diff], size=SIZE, first32_equal=True,
                factory_equal_windows=[[hex(a), hex(b)] for a, b in windows],
                cloud_file_identical=kind == "5site")


def register_uses(img):
    """Static: every instruction reading the patched destination register inside its function."""
    from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM
    md = Cs(CS_ARCH_ARM, CS_MODE_ARM)
    funcs = {0x8000D000: (0x8000CFD0, 0x8000D1A0), 0x8000D0BC: (0x8000CFD0, 0x8000D1A0),
             0x80044EC0: (0x80044E54, 0x80045160), 0x80045044: (0x80044E54, 0x80045160),
             0x800450C4: (0x80044E54, 0x80045160)}
    out = {}
    for site, (lo, hi) in funcs.items():
        ins = list(md.disasm(img[lo - BASE:hi - BASE], lo))
        reg = next(i for i in ins if i.address == site).op_str.split(",")[0]
        if reg == "r2":  # consumed by the immediately following producer call
            nxt = [i for i in ins if site < i.address <= site + 12]
            assert nxt[-1].mnemonic == "bl" and nxt[-1].op_str == "#0x80006778", hex(site)
            out[hex(site)] = dict(register=reg, consumer="producer bl " + hex(nxt[-1].address))
        else:
            uses = [hex(i.address) for i in ins if i.address != site and i.address < 0x80045160
                    and i.mnemonic.startswith("str") and i.op_str.startswith(reg + ",")]
            out[hex(site)] = dict(register=reg, stores=uses)
    assert out["0x8000d000"]["stores"] == ["0x8000d0d4"]
    assert out["0x80044ec0"]["stores"] == ["0x80044f3c", "0x80044f94", "0x80044fec", "0x8004505c", "0x800450dc"]
    return out


class Swap:
    """Temporarily replace entries of an imported module-level dict, restoring afterwards."""
    def __init__(self, d, updates): self.d, self.u, self.old = d, updates, {}
    def __enter__(self):
        for k, v in self.u.items(): self.old[k] = self.d[k]; self.d[k] = v
    def __exit__(self, *a):
        for k, v in self.old.items(): self.d[k] = v


def j(x): return json.loads(json.dumps(x, default=lambda o: o.hex() if isinstance(o, bytes) else str(o)))


def diff_paths(a, b, path=""):
    if type(a) != type(b): return [path]
    if isinstance(a, dict):
        out = []
        for k in sorted(set(a) | set(b), key=str):
            out += diff_paths(a.get(k), b.get(k), f"{path}/{k}") if k in a and k in b else [f"{path}/{k}"]
        return out
    if isinstance(a, list):
        if len(a) != len(b): return [path]
        return [p for i, (x, y) in enumerate(zip(a, b)) for p in diff_paths(x, y, f"{path}[{i}]")]
    return [] if a == b else [path]


def check_cfd0(own, cand, sites):
    import trace_control_gui_events as ev
    from trace_control_gui_cfd0 import CallbackReplay, CALLBACK
    r2 = NEW if 0x8000D0BC in sites else 0x19
    ui8 = NEW if 0x8000D000 in sites else 0x19

    class Cand(CallbackReplay):
        def run_callback(self, mode, setting, event):
            # Copy of the original method; only the type-2 record byte5 and UI+8 are parameters.
            use_type5 = mode != 4 and setting == 1
            producer_return = 0x8000D0A4 if use_type5 else 0x8000D0CC
            queue_before = self.prepare_dispatch(8, event, CALLBACK, producer_return)
            self.secondary, self.secondary_returns = [], []
            u = self.u
            u.mem_write(ev.MODE, bytes((mode,)) + b"\xA5" * 10)
            self.prepare_setting(setting)
            self.put(ev.SOUND_ENABLE, 0)
            self.prepare_secondary()
            from trace_control_gui_cfd0 import WIDGETS
            for offset, widget in WIDGETS.items():
                self.put(ev.UI + offset, widget)
            self.dispatch()
            after = bytes(u.mem_read(ev.MODE, 11))
            prefix = None
            if event == 1:
                assert self.calls == [["0x8001b030", hex(CALLBACK)]]
                expected = bytes.fromhex("050000002213") if use_type5 else bytes((2, 0, 0, 0, 0x0E, r2))
                self.check_send(expected, 100)
                tail = (0x22, 0x13) if use_type5 else (0x0E, ui8)
                next_mode = 3 if mode == 4 else 4
                assert after == bytes((next_mode, 0)) + b"\xA5" * 4 + bytes((2, *tail, 1, 0))
                assert self.secondary == [["0x8000d198", 4, 3, 255] if mode == 4 else ["0x8000d080", 4, 4, 255]]
                self.check_secondary()
                prefix = expected.hex()
            else:
                assert not any((self.calls, self.producer_args, self.copies, self.drained,
                                self.secondary, self.secondary_returns, self.timer_stores, self.ui_leaves))
                assert bytes(u.mem_read(ev.QUEUE, 760)) == queue_before and self.read(ev.TIMER) == 77
                assert after == bytes((mode,)) + b"\xA5" * 10
            return dict(mode=mode, setting=setting, event=event, mode_bytes_after=after.hex(),
                        record_prefix=prefix, producer_args=self.producer_args, drained=self.drained,
                        queue_count=self.read(ev.QUEUE + 0x38), timer_stores=self.timer_stores,
                        secondary_args=self.secondary, secondary_returns=self.secondary_returns,
                        modeled_ui_calls=self.ui_leaves)

    def run(cls, raw):
        rp = cls(raw)
        binding = rp.register(ev.SECOND_REGISTER, ev.SECOND_STOP, ev.SECOND_LITERALS, ev.SECOND_BINDINGS)[8]
        cases = [rp.run_callback(*i) for i in product((3, 4), (0, 1, 2), (1, 2))]
        return j(dict(binding=binding, cases=cases, ib={hex(k): v for k, v in sorted(rp.coverage.items())}))

    base, cnd = run(CallbackReplay, own), run(Cand, cand)
    # Original class output has extra keys; reduce to the shared key set for comparison.
    for c in base["cases"]:
        for k in ("callback", "indirect_calls", "producer_return"): c.pop(k, None)
    expected = copy.deepcopy(base)
    for c in expected["cases"]:
        if c["record_prefix"] == "020000000e19":
            c["record_prefix"] = f"020000000e{r2:02x}"
            c["producer_args"] = [[2, 0x0E, r2]]
            m = bytearray.fromhex(c["mode_bytes_after"]); m[8] = ui8; c["mode_bytes_after"] = m.hex()
    for a in sites:
        if hex(a) in expected["ib"]:
            w = bytearray.fromhex(expected["ib"][hex(a)]); w[0] = NEW; expected["ib"][hex(a)] = w.hex()
    d = diff_paths(expected, cnd)
    assert not d, d[:20]
    changed = diff_paths(base, cnd)
    return dict(cases=len(cnd["cases"]), type2_records=sorted({c["record_prefix"] for c in cnd["cases"] if c["record_prefix"]}),
                differences_vs_baseline=changed, unexpected_differences=[])


def check_deferred(own, cand, sites):
    import trace_deferred_measurement as dm
    r2 = NEW if 0x8000D0BC in sites else 0x19
    settings_list = ((0,), (1,), (2,), (0, 1), (1, 0))

    def run(raw, cand_mode):
        upd = {} if not cand_mode else None
        calls = {2: (0x8000D0CC, 0x0E, r2)} if cand_mode else {}
        lists = {2: (0x0E, r2, 0x1D)} if cand_mode else {}
        with Swap(dm.CALLS, calls), Swap(dm.LISTS, lists):
            m = dm.DispatcherReplay(raw)
            cases = [m.run_dispatch(s, r) for s in settings_list for r in (False, True)]
            # The harness itself asserts CTRL+8 == 0x0e, discard 2->1, builder list and wire bytes.
            return j(dict(cases=cases, ib={hex(k): v for k, v in sorted(m.coverage.items())}))

    base, cnd = run(own, False), run(cand, True)
    for b, c in zip(base["cases"], cnd["cases"]):
        if b["record_types"][-1] == 5:
            assert b == c, "type-5 (Fast CONT=1) path changed"
        else:
            for k in ("idle_model_tick", "discard_after", "parser_frames", "producer_returns", "record_types", "settings"):
                assert b[k] == c[k], k
            assert c["builder_calls"][0][1] == [0x0E, r2, 0x1D]
    for k in base["ib"]:
        exp = base["ib"][k]
        if int(k, 16) in sites: exp = f"{NEW:02x}" + exp[2:]
        assert cnd["ib"][k] == exp, k
    wires = sorted({c["wire_hex"] for c in cnd["cases"] if c["reply_fixtures"]})
    return dict(cases=len(cnd["cases"]), wire_with_replies=wires)


def check_fast_cont(own, cand, sites):
    import trace_deferred_measurement as dm
    import trace_native_fast_cont as fc
    r2 = NEW if 0x8000D0BC in sites else 0x19
    ui8 = NEW if 0x8000D000 in sites else 0x19

    def make_cls(rec2):
        class M(fc.ModeReplay):
            def run_case(self, old_mode, fast, discard):
                # Copy of original run_case; type-2 record is a parameter, UI+7/8 also reported.
                self.prepare()
                self.ui_models, self.measurement_starts = [], []
                self.u.mem_write(fc.TIMER_STATE, b"\1" + bytes(0x13))
                self.u.reg_write(fc.UC_ARM_REG_R6, fc.UI)
                self.u.reg_write(fc.UC_ARM_REG_R7, fc.HANDLE)
                self.invoke(0x800518BC)
                self.u.mem_write(fc.UI, bytes((old_mode, 1, 1, 0, 0, 0, 0, 9, 0x19, 9, 1)))
                self.put(fc.SETTING, fast)
                self.put(fc.RESULT + 0x1C, fc.STORED[0]); self.put(fc.RESULT + 0x20, fc.STORED[1])
                self.u.mem_write(fc.CTRL + 1, bytes((discard,)))
                self.u.mem_write(fc.HISTORY, fc.HISTORY_BYTES)
                self.u.mem_write(fc.ACTIVE + 4, fc.FILTER_BYTES)
                before = self.snapshot()
                self.invoke(fc.ENTRY)
                mode = 3 if old_mode == 4 else 4
                kind = 5 if mode == 4 and fast == 1 else 2
                record = (5, 0x22, 0x13) if kind == 5 else rec2
                assert self.byte(fc.UI) == mode and self.byte(fc.UI + 9) == 1
                assert self.byte(fc.UI + 1) == self.byte(fc.UI + 10) == 0
                assert self.rd(fc.TIMER) == 100 and self.enqueued[0][:6] == struct.pack("<IBB", *record)
                assert self.snapshot() == before and self.byte(fc.CTRL + 1) == discard
                ui78 = bytes(self.u.mem_read(fc.UI + 7, 2)).hex()
                self.invoke(fc.SERVICE)
                sequence = dm.LISTS[kind]
                assert self.builder_calls == [(3, sequence, 0x80004414 if kind == 5 else 0x80004480)]
                assert self.snapshot() == before and self.byte(fc.CTRL + 1) == 2
                assert self.rd(fc.CTRL + 8) == (0x22 if kind == 5 else 0x0E)
                delivered = 0
                for tick in range(1, 180):
                    self.set_tick(tick)
                    if delivered < len(self.sent):
                        command = self.sent[-1]
                        packet = b"\x60\x32\x00\x00\x03" if command == 0x1D else dm.FRAMES[command][:1]
                        for value in packet: self.receive(value)
                        delivered += 1
                    self.step(tick)
                    if self.byte(fc.FSM + 0x34) == 0: break
                assert self.byte(fc.FSM + 0x34) == 0 and tuple(self.sent) == sequence
                assert bytes(self.wire) == b"".join(dm.FRAMES[c] for c in sequence)
                assert self.snapshot() == before and self.byte(fc.CTRL + 1) == 1
                assert [e["frame"] for e in self.events if e["kind"] == "parse"] == ["6032000003"]
                assert not any(e["kind"] == "publish" for e in self.events)
                return dict(old_mode=old_mode, new_mode=mode, fast_cont=fast, record_prefix=self.enqueued[0][:6].hex(),
                            ui7_8=ui78, commands=[hex(c) for c in sequence], wire_hex=bytes(self.wire).hex(),
                            discard=[discard, discard, 2, 1], final_tick=tick)
        return M

    def run(raw, rec2, lists):
        with Swap(dm.LISTS, lists):
            m = make_cls(rec2)(raw)
            cases = [m.run_case(*a) for a in product((1, 4), (0, 1), (0, 1))]
            cd = fc.SoundCountdown(raw)
            exp = [cd.run_suffix(*a) for a in product((0, 1, 2), (0, 1))]
            return j(dict(cases=cases, countdown=exp, literals=fc.index(raw),
                          ib={hex(k): v for k, v in sorted(m.coverage.items())}))

    base = run(own, (2, 0x0E, 0x19), {})
    cnd = run(cand, (2, 0x0E, r2), {2: (0x0E, r2, 0x1D)})
    assert base["countdown"] == cnd["countdown"] and base["literals"] == cnd["literals"]
    for b, c in zip(base["cases"], cnd["cases"]):
        if b["record_prefix"].startswith("05"):
            assert b == c, "Fast CONT=1 path changed"
        else:
            assert c["ui7_8"] == f"0e{ui8:02x}" and c["record_prefix"] == f"020000000e{r2:02x}"
            assert c["final_tick"] == b["final_tick"] and c["discard"] == b["discard"]
    for k in base["ib"]:
        exp = base["ib"][k]
        if int(k, 16) in sites: exp = f"{NEW:02x}" + exp[2:]
        assert cnd["ib"][k] == exp, k
    return dict(cases=len(cnd["cases"]), countdown_cases=len(cnd["countdown"]),
                fast1_cases_identical=sum(c["record_prefix"].startswith("05") for c in cnd["cases"]),
                type2_wire=sorted({c["wire_hex"] for c in cnd["cases"] if c["record_prefix"].startswith("02")}))


def check_dynamic(own, cand, sites):
    import trace_dynamic_type2 as dt
    def run(raw):
        m = dt.DynamicReplay(raw)
        native = [m.native_case(*v) for v in product((0, 1, 2), (0, 1, 2), (0, 1))]
        clamp = [m.clamp_case(v) for v in range(256)]
        adj = [m.adjacent_case(p, c) for p, c in product((9, 0x0A, 0x0C, 0x22, 0x0E), (False, True))]
        return j(dict(native=native, clamp=clamp, adjacent=adj, bindings=dt.bindings(raw),
                      ib={hex(k): v for k, v in sorted(m.coverage.items())}))
    base, cnd = run(own), run(cand)
    d = diff_paths(base, cnd)
    assert not d, d[:20]
    return dict(native=len(cnd["native"]), clamp=len(cnd["clamp"]), adjacent=len(cnd["adjacent"]),
                identical_to_baseline=True,
                clamp_0x13_row=cnd["clamp"][0x13], clamp_0x19_row=cnd["clamp"][0x19])


def check_producer_suffixes(own, cand, sites):
    import trace_control_producer_suffixes as ps
    index = json.loads((ROOT / "contributions/COORD-ADC-CADENCE/synchronous/control-producer-index.json").read_bytes())
    rows = index["identical_observations"]["calls"]
    callsite = {0x8000D0C8: 0x8000D0BC, 0x80045050: 0x80045044, 0x800450D0: 0x800450C4}

    def run(raw, patched):
        rws = copy.deepcopy(rows)
        upd = {}
        for r in rws:
            s = int(r["address"], 16)
            if s in callsite and callsite[s] in patched:
                upd[s] = (0xE, NEW)
                for i in r["instructions"]:
                    if int(i["pc"], 16) == callsite[s]:
                        assert i["bytes"][:2] == "19"; i["bytes"] = f"{NEW:02x}" + i["bytes"][2:]
        with Swap(ps.ARGS, upd):
            rp = ps.CallerReplay(raw)
            cases = [rp.run(r, *sc) for r in rws for sc in ps.scenarios(r)]
        return j(dict(cases=cases, ib={hex(k): v for k, v in sorted(rp.coverage.items())})), upd

    base, _ = run(own, ())
    cnd, upd = run(cand, sites)
    for b, c in zip(base["cases"], cnd["cases"]):
        s = int(b["site"], 16)
        if s in upd:
            assert c["record_prefix"] == f"020000000e{NEW:02x}" and b["record_prefix"] == "020000000e19"
            assert {k: v for k, v in b.items() if k not in ("record_prefix", "producer_r0_r1_r2")} == \
                   {k: v for k, v in c.items() if k not in ("record_prefix", "producer_r0_r1_r2")}
        else:
            assert b == c, b["site"]
    for k in base["ib"]:
        exp = base["ib"][k]
        if int(k, 16) in sites: exp = f"{NEW:02x}" + exp[2:]
        assert cnd["ib"][k] == exp, k
    return dict(direct_sites=len(rows), cases=len(cnd["cases"]),
                changed_sites=[hex(s) for s in sorted(upd)],
                unchanged_0x19_sites_still_0x19=[c["site"] for c in cnd["cases"] if c["record_prefix"].endswith("19")])


def check_event_sources(own, cand, sites):
    from trace_measurement_event_sources import EventMachine, QUEUE_HANDLE
    from trace_state5_discard_lifecycle import LifecycleMachine, expected_producer
    from emulate_state5_parser import reference, CONTROL
    site_of = {"buzzer_callback": 0x8000D0BC, "diode_callback_tail": 0x8000D0BC,
               "diode_selector": 0x80045044, "buzzer_selector": 0x800450C4}
    rows = []
    for raw, patched in ((own, ()), (cand, sites)):
        em, pipe = EventMachine(raw), LifecycleMachine(raw)
        out = []
        for branch, setting, enabled in product(site_of, (0, 1, 2, 0xFFFFFFFF), (False, True)):
            actual = em.gui_branch(branch, setting, enabled)
            special = branch.startswith("buzzer") and setting == 1
            b5 = 19 if special else (NEW if site_of[branch] in patched else 25)
            exp = {"case": 5 if special else 2, "byte4": 34 if special else 14, "byte5": b5,
                   "queue_r0": QUEUE_HANDLE, "queue_r2": 10, "queue_r3": 0} if enabled else None
            assert actual == exp, (branch, setting, enabled, actual)
            row = dict(branch=branch, setting=setting, enabled=enabled, event=actual)
            if actual:
                dec = actual["case"], actual["byte4"], actual["byte5"]
                setup = pipe.produce(*dec)
                assert setup == expected_producer(*dec)
                steps = []
                for _ in range(3):  # 5001 = 0x1389 saturation gate, discard lifecycle
                    count = pipe.mu.mem_read(CONTROL + 1, 1)[0]
                    obs = pipe.execute(5001, 0x1D, 7, setup["control"], count, preserve_state=True)
                    assert obs == reference(5001, 0x1D, 7, setup["control"], count)
                    steps.append(obs)
                row.update(dispatch=setup, parser=steps)
            out.append(j(row))
        rows.append(out)
    for b, c in zip(*rows):
        if b["event"] and b["event"]["byte5"] == 25 and c["event"]["byte5"] == NEW:
            assert c["dispatch"]["commands"] == [14, NEW, 29] and c["dispatch"]["control"] == 14
            assert b["parser"] == c["parser"], "parser/0x1389 gate/discard changed"
            assert b["dispatch"]["control_writes"] == c["dispatch"]["control_writes"]
        else:
            assert b == c
    return dict(gui_branch_cases=len(rows[1]),
                candidate_commands=sorted({tuple(r["dispatch"]["commands"]) for r in rows[1] if r.get("dispatch")}))


def check_selector(own, cand, sites):
    """Execute the original mode selector 0x80044ea8..0x800450e8 for every index and setting.
    Leaves are stubbed; the producer 0x80006778 is captured. Records UI+0..10."""
    from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
    from unicorn.arm_const import (UC_CPU_ARM_926, UC_ARM_REG_PC, UC_ARM_REG_LR, UC_ARM_REG_R0,
                                   UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R4, UC_ARM_REG_R6,
                                   UC_ARM_REG_SP, UC_ARM_REG_CPSR)
    UI, GUI, SETTING = 0x805ABEFC, 0x805AC098, 0x805AC788
    LO, HI, STOPS = 0x80044EA8, 0x80045160, (0x800450E8, 0x80045158)

    def run(raw, index, setting):
        u = Uc(UC_ARCH_ARM, UC_MODE_ARM); u.ctl_set_cpu_model(UC_CPU_ARM_926)
        u.mem_map(0x7FFF0000, 0x2100000); u.mem_write(BASE, raw)
        u.mem_map(0x10000000, 0x10000)
        u.mem_write(UI, b"\xA5" * 0x20); u.mem_write(SETTING, struct.pack("<I", setting))
        log = dict(producer=[], leaves=[])
        def code(uc, pc, size, _):
            if pc in STOPS: uc.emu_stop(); return
            if LO <= pc < HI: return
            lr = uc.reg_read(UC_ARM_REG_LR)
            assert LO <= lr < HI, hex(pc)
            if pc == 0x80006778:
                log["producer"].append([hex(lr)] + [uc.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2)])
                uc.reg_write(UC_ARM_REG_R0, 1)
            else:
                log["leaves"].append(hex(pc)); uc.reg_write(UC_ARM_REG_R0, 0)
            uc.reg_write(UC_ARM_REG_PC, lr)
        u.hook_add(UC_HOOK_CODE, code)
        u.reg_write(UC_ARM_REG_CPSR, 0x13); u.reg_write(UC_ARM_REG_SP, 0x1000FF00)
        u.reg_write(UC_ARM_REG_R4, GUI); u.reg_write(UC_ARM_REG_R6, index)
        u.emu_start(LO, 0, count=5000)
        pc = u.reg_read(UC_ARM_REG_PC)
        assert pc in STOPS, hex(pc)
        return dict(index=index, setting=setting, stop=hex(pc), ui=bytes(u.mem_read(UI, 11)).hex(), **log)

    grid = list(product(range(7), (0, 1, 2)))
    base = [run(own, *g) for g in grid]
    cnd = [run(cand, *g) for g in grid]
    names = {0x09: "voltage?", 0x0C: "cfg0c", 0x0F: "cfg0f", 0x0E: "diode", 0x22: "fast-buzzer"}
    report, violations = [], []
    for b, c in zip(base, cnd):
        exp = copy.deepcopy(b)
        for p in exp["producer"]:
            if p[0] == "0x80045054" and 0x80045044 in sites: p[3] = NEW
            if p[0] == "0x800450d4" and 0x800450C4 in sites: p[3] = NEW
        prim = b["producer"][0][2] if b["producer"] else None
        diode_like = prim == 0x0E
        if 0x80044EC0 in sites and b["stop"] == "0x800450e8" and b["ui"][16:18] == "19":
            ui = bytearray.fromhex(exp["ui"]); ui[8] = NEW; exp["ui"] = ui.hex()
        assert c == exp, (b, c)
        if not diode_like and c != b:
            violations.append(dict(index=b["index"], setting=b["setting"], producer_primary=prim,
                                   baseline_ui=b["ui"], candidate_ui=c["ui"],
                                   producer_byte5_baseline=b["producer"][0][3], producer_byte5_candidate=c["producer"][0][3]))
        report.append(dict(index=b["index"], setting=b["setting"], primary=prim,
                           byte5=[b["producer"][0][3], c["producer"][0][3]] if b["producer"] else None,
                           ui8=[b["ui"][16:18], c["ui"][16:18]], changed=c != b))
    result = dict(cases=len(grid), rows=report, non_diode_mode_changes=violations)
    assert not violations, ("candidate changes UI state of non-diode modes", violations)
    return result


def check_ownprotocol_dispatch(own, cand, sites):
    """On the real ownprotocol image: inject the type-2 diode record into ProfileMachine's queue
    (CTRL+8 starts at 0x0c), run the E2/ownprotocol service loop, and record every UART payload."""
    import trace_profiles as trace
    factory = (ROOT / "original-firmware/V3.8/f1c100s.bin").read_bytes()
    init = trace.restore_globals(factory)
    trace.NAMES = ['Base', 'Direct', 'Auto', 'Ready', 'ownprotocol']
    r2 = NEW if 0x8000D0BC in sites else 0x19

    class Inj(trace.ProfileMachine):
        def code(self, u, a, size, _):
            if a == 0x80005E84:
                msg = bytes(u.mem_read(u.reg_read(trace.UC_ARM_REG_R0), u.reg_read(trace.UC_ARM_REG_R1)))
                self.wire.append((self.now, msg.hex()))
                if msg != b"`":
                    self.tx.append(self.now); self.event("request", request=len(self.tx), payload=msg.hex())
                    self.pending.append((self.now + self.reply_delay, self.sequence, msg[0], len(self.tx)))
                    self.sequence += 1; self.pending.sort(); self.ret(); return
            super().code(u, a, size, _)

    def run(img, byte5, profile):
        trace.E2_SHA = sha(img)
        m = Inj(img, profile, 1, "stable-low", init=init)
        m.wire = []
        m.wr(trace.CTRL + 8, 0x0C)
        m.u.mem_write(trace.UI + 8, bytes((byte5,)))
        m.queue.append(struct.pack("<IBB", 2, 0x0E, byte5) + bytes(62))
        row = m.run(200)
        ev = [e for e in row["events"] if e["kind"] in ("request", "accepted", "sound_control", "renderer")]
        setup = [w for t, w in m.wire if w not in ("60",)]
        outstanding = False
        for e in row["events"]:
            if e["kind"] == "request" and e["payload"] == "60":
                assert not outstanding, e; outstanding = True
            # A reply consumed by the parser (including the discard=2 slot) or a timeout closes it.
            if e["kind"] in ("accepted", "parser") or (e["kind"] == "state_write" and e["new"] == 6): outstanding = False
        discarded = [e["discard_counter"] for e in row["events"] if e["kind"] == "parser"][:3]
        first_poll = next(t for t, w in m.wire if w == "60")
        return dict(setup=setup, setup_times=[t for t, w in m.wire if w != "60"], first_poll=first_poll, parser_discard_counters=discarded, ctrl8=m.rd(trace.CTRL + 8), discard=m.byte(trace.CTRL + 1),
                    polls=sum(w == "60" for _, w in m.wire), accepted=row["counts"]["accepted"],
                    queue_max=row["queue_max"], timeline=[(e["t"], e["kind"]) for e in ev])

    out = {}
    for profile in (0, 4):
        b, c = run(own, 0x19, profile), run(cand, r2, profile)
        # 0x80005e84 receives the payload without the trailing 8-bit checksum byte.
        assert b["setup"] == ["580a", "5a"], b["setup"]
        assert c["setup"] == ["580a", "5900" if r2 == NEW else "5a"], c["setup"]
        assert c["ctrl8"] == b["ctrl8"] == 0x0E and c["discard"] == b["discard"]
        # queue_max includes the injected record plus GUI traffic (fixture); compared only differentially.
        assert c["accepted"] > 0 and c["polls"] > 0 and c["parser_discard_counters"] == [2, 1, 0]
        assert {k: v for k, v in b.items() if k != "setup"} == {k: v for k, v in c.items() if k != "setup"}
        out[trace.NAMES[profile]] = dict(baseline_setup=b["setup"], candidate_setup=c["setup"], ctrl8=hex(c["ctrl8"]),
                                         discard_after=c["discard"], polls=c["polls"], accepted=c["accepted"],
                                         setup_times=c["setup_times"], first_poll_tick=c["first_poll"],
                                         timeline_identical=True)
    return out


CHECKS = [("integrity", None), ("register_uses", None), ("selector_all_modes", check_selector),
          ("cfd0_callback", check_cfd0), ("deferred_measurement", check_deferred),
          ("native_fast_cont", check_fast_cont), ("dynamic_type2", check_dynamic),
          ("producer_suffixes", check_producer_suffixes), ("event_sources", check_event_sources),
          ("ownprotocol_integrated_dispatch", check_ownprotocol_dispatch)]
# Harnesses whose original UART/dispatcher guards only admit factory code paths: they run on the
# pinned factory images with the identical byte sites applied (windows proven identical in 'integrity').
FACTORY_ONLY = {"deferred_measurement", "native_fast_cont", "dynamic_type2", "event_sources"}


def ownprotocol_subtask(kind):
    """test_ownprotocol.py's complete suite with the built image replaced by the candidate."""
    import test_ownprotocol as t
    orig_build = t.build
    spec = CANDIDATES[kind]
    def build(e2):
        image, receipt = orig_build(e2)  # corrupt input still raises here
        assert sha(image) == OWN_SHA
        cand = make(image, spec["sites"])
        assert sha(cand) == spec["sha"]
        return cand, receipt
    t.build = build
    t.main()
    out = (t.ROOT / "out/ownprotocol/ys4470-e2-ownprotocol-OFFLINE.bin").read_bytes()
    assert sha(out) == spec["sha"]
    print("OWNPROTOCOL-CANDIDATE-PASS", sha(out))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate", choices=sorted(CANDIDATES), required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--subtask", choices=["ownprotocol"])
    ap.add_argument("--generate", type=Path, help="write the candidate image to this NEW path and exit")
    a = ap.parse_args()
    if a.subtask:
        return ownprotocol_subtask(a.candidate)
    if a.generate:
        own = (ROOT / "out/ownprotocol/ys4470-e2-ownprotocol-OFFLINE.bin").read_bytes()
        img = make(own, CANDIDATES[a.candidate]["sites"])
        assert not a.generate.exists(), "refusing to overwrite"
        a.generate.write_bytes(img); print(sha(img)); return
    factory, own, cand, sites = load_images(a.candidate)
    report = dict(schema="ys4470.diodefixed-candidate-adapter.v1", candidate=a.candidate,
                  baseline_sha256=OWN_SHA, candidate_sha256=sha(cand), factory_v38_sha256=V38_SHA,
                  sites=[hex(s) for s in sites], physical_device_operations=0,
                  physical_timing_established=False, checks={})
    failed = []
    for name, fn in CHECKS:
        try:
            if name == "integrity": res = check_integrity(factory, own, cand, sites, a.candidate)
            elif name == "register_uses": res = register_uses(cand)
            elif name in FACTORY_ONLY:
                res = {}
                for label, path, digest in (("V3.8", "original-firmware/V3.8/f1c100s.bin", V38_SHA),
                                            ("V3.6", "original-firmware/V3.6/f1c100s.bin", V36_SHA)):
                    raw = (ROOT / path).read_bytes(); assert sha(raw) == digest
                    patched = make_on(raw, sites)
                    assert [BASE + i for i in range(SIZE) if raw[i] != patched[i]] == list(sites)
                    res[label] = dict(base_sha256=digest, patched_sha256=sha(patched), result=fn(raw, patched, sites))
                assert json.dumps(res["V3.8"]["result"]) == json.dumps(res["V3.6"]["result"]), "V3.6/V3.8 disagree"
            else: res = fn(own, cand, sites)
            report["checks"][name] = dict(result="PASS", detail=res)
        except Exception as e:
            failed.append(name)
            report["checks"][name] = dict(result="FAIL", error=repr(e)[:4000], trace=traceback.format_exc()[-3000:])
        print(name, report["checks"][name]["result"], flush=True)
    # Full ownprotocol suite with the candidate image, isolated in a subprocess.
    p = subprocess.run([sys.executable, __file__, "--candidate", a.candidate, "--out", str(a.out), "--subtask", "ownprotocol"],
                       capture_output=True, text=True)
    ok = p.returncode == 0 and "OWNPROTOCOL-CANDIDATE-PASS" in p.stdout
    report["checks"]["test_ownprotocol_on_candidate"] = dict(result="PASS" if ok else "FAIL",
                                                             stdout=p.stdout[-4000:], stderr=p.stderr[-4000:])
    if not ok: failed.append("test_ownprotocol_on_candidate")
    print("test_ownprotocol_on_candidate", "PASS" if ok else "FAIL", flush=True)
    report["verdict"] = "PASS" if not failed else "FAIL"
    report["failed"] = failed
    report["limits"] = [
        "Bounded ARM926 replays of original code with modelled leaves, queue fixtures and synthetic replies.",
        "Proves which command bytes the firmware emits and which RAM state it writes; it does NOT prove the meter chip's "
        "electrical behaviour for 59 00 in diode mode, conversion latency, or physical speed-up.",
    ]
    a.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("VERDICT", report["verdict"], failed)
    sys.exit(0 if not failed else 1)


if __name__ == "__main__":
    main()
