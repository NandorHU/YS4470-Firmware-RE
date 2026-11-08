# YS-4470 local assistant lessons
These are coordinator-checked in-context instructions, not a weight update.

1. Use only the supplied, versioned source. Earlier model notes are unverified.
   A printed date, label or guessed role is not evidence.
2. Preserve a supplied ISA. PC-relative loads occur in ARM too; they do not prove Thumb.
3. Distinguish an instruction address, a literal-pool address, the pointer stored
   there, and the final effective address. Use tool-resolved numbers; request a
   calculation instead of guessing hexadecimal arithmetic.
4. Condition flags come from the last flag-writing instruction.
   CMP followed by BHS tests unsigned >=; BGT tests signed >.
   Worked example: CMP r7,r8; BLO A is unsigned < and does not branch at equality.
   Worked example: CMP r1,r2; BLE B is signed <= and does branch at equality.
5. SUB plus an unsigned deadline comparison gives a modulo counter test, not
   physical milliseconds. A completed-frame branch can bypass that comparison.
6. The original 0x80061f84 returns the RTOS counter snapshot at0x805abbc8
   under critical helpers; it is not an analog threshold.
7. Cite an exact quote. Let tooling locate its line. No invented line numbers,
   file versions, cache effects, physical speedups or chip identities.
8. Altering the test's assertions or expected values is not a counterexample.
   An example-output filter is not the loop that chooses which tests execute.
9. A response stopped by the token limit is incomplete even if done=true.
10. Report uncertainty and missing context briefly. Up to two useful claims per
    short task are enough. Never pad an answer with fabricated findings.

Scope limits: original/Python/C agreement applies only to documented paths.
Historical Beta3 labels are not new execution proof. UART send remains a leaf
model in the FSM setup test. Physical counter rate and acoustic delay are unproven.
