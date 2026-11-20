"""Run original regressions + candidate adapter in a NEW scratch copy of the emulator bundle source.
Usage: python run_all.py --candidate 4site|5site   (Windows x64 or Linux x86-64). No device I/O."""
import argparse, importlib.util, json, os, shutil, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUNDLE = HERE.parents[2] / "YS4470-EMULATOR-CLAUDE-20261120"

spec = importlib.util.spec_from_file_location("run_emulator", BUNDLE / "run_emulator.py")
emu = importlib.util.module_from_spec(spec); spec.loader.exec_module(emu)

REGRESSIONS = [  # original harnesses, unchanged, on the pinned factory images
    ("trace_control_gui_cfd0", "contributions/COORD-ADC-CADENCE/synchronous/trace_control_gui_cfd0.py", ["--out", "R/cfd0.json"]),
    ("trace_dynamic_type2", "contributions/COORD-ADC-CADENCE/synchronous/trace_dynamic_type2.py", ["--out", "R/dynamic.json"]),
    ("trace_deferred_measurement", "contributions/COORD-ADC-CADENCE/synchronous/trace_deferred_measurement.py", ["--out", "R/deferred.json"]),
    ("trace_native_fast_cont", "contributions/COORD-ADC-CADENCE/synchronous/trace_native_fast_cont.py", ["--out", "R/fastcont.json"]),
    ("trace_control_producer_suffixes", "contributions/COORD-ADC-CADENCE/synchronous/trace_control_producer_suffixes.py", ["--out", "R/suffixes.json"]),
    ("trace_measurement_event_sources", "tools/trace_measurement_event_sources.py",
     ["--input", "V3.6=original-firmware/V3.6/f1c100s.bin", "--input", "V3.8=original-firmware/V3.8/f1c100s.bin", "--out", "R/event_sources.json"]),
    ("test_ownprotocol_baseline", "contributions/COORD-ADC-CADENCE/ownprotocol/test_ownprotocol.py", []),
]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--candidate", required=True); a = ap.parse_args()
    emu.verify(); deps = emu.dependencies()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run = HERE / "runs" / f"{stamp}-{a.candidate}"; src = run / "source"
    shutil.copytree(BUNDLE / "source", src); (run / "R").mkdir()
    env = os.environ.copy(); env["PYTHONNOUSERSITE"] = "1"
    env["PYTHONPATH"] = os.pathsep.join(map(str, [deps, src / "tools", src / "contributions/COORD-ADC-CADENCE",
                                                   src / "contributions/COORD-ADC-CADENCE/synchronous",
                                                   src / "contributions/COORD-ADC-CADENCE/uart"]))
    summary = dict(run=str(run), candidate=a.candidate, regressions={})
    def go(name, cmd):
        p = subprocess.run(cmd, cwd=src, env=env, capture_output=True, text=True)
        (run / f"{name}.log").write_text(p.stdout + "\n--- stderr ---\n" + p.stderr, encoding="utf-8")
        print(f"{name}: {'PASS' if p.returncode == 0 else 'FAIL'}  {p.stdout.strip().splitlines()[-1][:160] if p.stdout.strip() else ''}", flush=True)
        return p.returncode == 0
    ok = go("build_ownprotocol", [sys.executable, "contributions/COORD-ADC-CADENCE/ownprotocol/build_ownprotocol.py", "--out", "out/ownprotocol"])
    for name, script, args in REGRESSIONS:
        summary["regressions"][name] = go(name, [sys.executable, script, *[x.replace("R/", str(run / "R") + "/") for x in args]])
    summary["adapter"] = go("candidate_adapter", [sys.executable, str(HERE / "candidate_adapter.py"),
                                                  "--candidate", a.candidate, "--out", str(run / "adapter-report.json")])
    summary["all_pass"] = ok and all(summary["regressions"].values()) and summary["adapter"]
    (run / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    sys.exit(0 if summary["all_pass"] else 1)


if __name__ == "__main__":
    main()
