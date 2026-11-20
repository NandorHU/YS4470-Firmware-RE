# Diode fixed range (beta.4)

`build_diodefixed.py --out out/diodefixed` rebuilds the ownprotocol image (b081860a) and changes
four `mov rX,#0x19` to `#0x13` (0x8000d000, 0x8000d0bc, 0x80045044, 0x800450c4). Output SHA-256
934a2557f7b069645ca3484a70e64e4e33844bf0b0892d2f3583078cadae9417. Needs keystone/capstone/unicorn.

`candidate_adapter.py` / `run_all.py` / `scan_ui8.py` are the hash-pinned differential adapter used
for validation. They are copied from `work/claude-diode-fixedrange-20261120/adapter/` and expect to
run from there (next to the YS4470-EMULATOR-CLAUDE-20261120 bundle). Results:
`VALIDATION-RESULT.md` (Hungarian), `adapter-report-4site.json` (PASS) and
`adapter-report-5site-REJECTED.json` (the earlier 5-site candidate, rejected because 0x80044ec0's
shared r8 also writes UI+8 for the voltage / cfg 0x0c / cfg 0x0f modes).
Emulation does not establish electrical correctness of range 0 in diode mode or physical speed.
