#ifndef YS4470_FAST_CONT_H
#define YS4470_FAST_CONT_H
#include <stdint.h>

/* Independent reconstruction of the bounded original helper 0x80007c88.
 * This is one pure component, not a complete or deployable YS-4470 firmware.
 * Caller contract: next < 3 and count <= 3. Values are signed scalar codes;
 * their physical measurement unit is deliberately unassigned.
 */
typedef struct {
    int32_t history[3];
    uint32_t next;
    uint32_t count;
    int32_t last_median;
} ys_fast_cont_state;

/* Returns the original sound selector (2/4/6/8/10), or 0 for an off request.
 * The caller must still apply the separately reconstructed sound-enable gate.
 * No hardware access, delay, allocation, reference-project code or libc call.
 */
uint32_t ys_fast_cont_update(ys_fast_cont_state *state, int32_t value);
#endif
