# COORD-FSM-TIMEOUT — completed 2026-11-08

Owner: current Codex coordinator.
Baseline: ddcb3f1c55acb0bb2df98c88e24450d2066bb35a; branch: re/2026-11-04-pyghidra-fel.
Result: the development-branch commit containing this handoff and its evidence.
No external branch or main update is involved.

Last proven result: original V3.6/V3.8 cached deadline transitions, critical tick
snapshot, setup durations, unsigned wrap and complete-frame precedence.
13,302 checks pass;12,914 compare original/Python/compiled C.
Fingerprint: 22212642cf8e42e7be6b1829508a6dc593a116be5f6298b63707f4911f5accfe.
Four actual Ghidra exports and nine provenance tests pass.

Evidence: fsm-timeout.json / fsm-timeout-ghidra.json.
Reproduction and models: README.md / trace_fsm_timeout.py.
Independent sources: reconstruction/fsm_timeout.c / fsm_timeout.h.

Remaining limits: UART-send leaf model, partial tick prefix, other FSM states,
actual Beta3 image and physical frequency/cadence/acoustic behavior.
Initial Ghidra launch-directory error was corrected; no research blocker remains.

Next reserved task: COORD-ADC-CADENCE. Validate the MainADCTask candidate 0x80005a78 and actual callers of FSM 0x80004490; bound one task-loop iteration and the delay candidate 0x80060fbc before assigning a polling cadence. Keep GUI callback periods, live clock frequency and acoustic latency separate.
