# Dióda fix-méréshatár jelölt — emulátoros ellenőrzés eredménye (2026-11-20, helyi Claude)

## Röviden
- Az **eredeti 5 helyes jelölt (c5544d36…) NEM biztonságos**, ezért elvetendő.
  A 0x80044ec0 `mov r8,#0x19` a 0x80044e54 módválasztóban függvényszintű regiszter.
  Az r8 értéke öt ágban kerül a UI+8 (0x805abf04) bájtba: Voltage (cfg 0x09), cfg 0x0c, cfg 0x0f, Dióda és nem-Fast Buzzer.
  A jelöltben ezért V/Ω/C módban is UI+8 = 0x13 lenne, miközben a chip továbbra is 0x19-et (`5a`) kap.
  A UI+8 értékét a kijelző-cache (0x800032b8/0x800032dc) és a skálaválasztó (0x800452d4) olvassa.
  A CODEX-TASK szabálya szerint („ha más mód rekordja, ki kell hagyni”) ezt a helyet ki kellett venni.
- **Új, 4 helyes jelölt:** `ys4470-ownprotocol-diodefixed13-4site-CANDIDATE.bin`
  SHA256 `934a2557f7b069645ca3484a70e64e4e33844bf0b0892d2f3583078cadae9417`
  Helyek: 0x8000d000, 0x8000d0bc, 0x80045044, 0x800450c4 (`#0x19` → `#0x13`). Alap: ownprotocol b081860a.
  **Minden ellenőrzés zöld.**

## Mit igazol a futás (adapter/runs/20261120T182228Z-4site, summary.json: all_pass=true)
Eredeti regressziók, változatlanul, friss scratch másolaton, mind PASS:
- trace_control_gui_cfd0 (24 eset)
- trace_dynamic_type2 (36 + 20 + 512 eset)
- trace_deferred_measurement (20 eset)
- trace_native_fast_cont
- trace_control_producer_suffixes (66 küldés)
- trace_measurement_event_sources (V3.6 és V3.8)
- test_ownprotocol (baseline)

Jelöltadapter (`adapter/candidate_adapter.py`), VERDICT PASS:
- **integrity:** b081860a-hoz képest pontosan a 4 bájt tér el. A méret és az első 32 bájt azonos.
  A cfd0, a selector és a producer ablak bájtra egyezik a V3.8 factory képpel.
- **register_uses:** a 0x8000d000 r8 egyetlen tárolója a 0x8000d0d4 (a dióda/nem-Fast Buzzer UI+8).
  A 0x8000d0bc, 0x80045044 és 0x800450c4 r2 értékét közvetlenül a producer `bl 0x80006778` használja.
- **selector_all_modes** (új, 7 index × 3 beállítás):
  - V, cfg 0x0c és cfg 0x0f módban bájtra azonos a baseline-nal.
  - Csak a dióda és a nem-Fast Buzzer producer byte5 értéke változik (0x19 → 0x13).
  - Fast CONT=1 változatlan.
- **cfd0_callback:** a rekord `020000000e13`, a Fast CONT=1 rekord `050000002213` változatlan.
  A diff kizárólag a type-2 esetek record/producer_args/UI+8 mezőiben és a 2 utasításszóban van.
- **deferred_measurement** (V3.6+V3.8 + ugyanazok a helyek):
  - Dióda vezetéken: `58 0a 62 | 59 00 59 | 60 60`.
  - Fast CONT=1: `58 07 5f 68 07 6f 59 00 59 60 60`, változatlan.
  - CTRL+8 = 0x0e, discard 2 → 1.
- **native_fast_cont:** a Fast CONT=1 esetek azonosak, a hang-visszaszámláló esetek is azonosak.
- **dynamic_type2:** teljesen azonos a baseline-nal; a 0x0c utak és a clamp nem változtak.
- **producer_suffixes:** csak a 0x8000d0c8, 0x80045050 és 0x800450d0 rekordja lett `…0e13`.
  A többi 28 hely, köztük a 0x80044f2c/f80/fdc 0x19 helyek, változatlan.
- **event_sources:** a dispatch parancslista `[0x0e,0x13,0x1d]`.
  A 3 parser-belépés (5001 = 0x1389 gate, discard életciklus) azonos a baseline-nal.
- **ownprotocol_integrated_dispatch** (új, a valódi ownprotocol képen, ProfileMachine):
  - A beinjektált (2,0x0e,0x13) rekord után a payloadok `580a`, `5900`, majd `60` lekérdezések.
  - CTRL+8 = 0x0e, a parser discard sorrendje 2, 1, 0.
  - A Base és az ownprotocol profil teljes idővonala azonos a baseline-nal; csak a `5a` → `5900` payload különbözik.
- **test_ownprotocol_on_candidate:** a teljes test_ownprotocol készlet a jelöltképpel PASS.

Kontroll: ugyanez az adapter az 5 helyes c5544d36 jelöltre **FAIL** (`selector_all_modes`, V/0x0c/0x0f UI+8 változás).
Az adapter tehát érzékeli a hibát. A többi teszt az 5 helyes jelöltön is zöld volt, ezt a hibát csak az új selector-teszt fogta meg.

## Megjegyzések, nyitott kérdések
- A 4 helyes jelöltben a módválasztón keresztül belépve a dióda UI+8 értéke 0x19 marad.
  A cfd0 gombon keresztül 0x13 lesz, ami ugyanaz a minta, mint a gyári Fast CONT (UI+8 = 0x13 + `59 00`).
  A 0x80063817 skálatábla config 0x0e esetén minden szelektorra 03, ezért a kijelzés statikusan nem függ ettől. Élőben ellenőrizendő.
- Az emulált modellben a `58 0a` után kb. 100 tick telik el a következő parancsig, és módváltás után 2 mérés eldobódik (discard = 2).
  Ez baseline-ban és jelöltben azonos. A tick fizikai egysége nem ismert.
- **Nem bizonyított:** hogy a `59 00` dióda módban elektromosan helyes (nem OL vagy rossz érték), és hogy fizikailag gyorsabb.
  Ezt csak a felhasználó tudja élőben megmérni (1N4148 ~0,6 V, LED, rövidzár, szakadás).
- Készülékre semmi nem került. Nincs publikálás.

## Újrafuttatás
`python -I work/claude-diode-fixedrange-20261120/adapter/run_all.py --candidate 4site` (vagy `5site` a kontrollhoz).
Új `adapter/runs/<időbélyeg>-<jelölt>/` mappát hoz létre. A bundle-t és a korábbi futásokat nem írja felül.
