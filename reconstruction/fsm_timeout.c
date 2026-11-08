#include "fsm_timeout.h"

/* Independently reconstructed from original V3.6/V3.8 MeasurementFSM.
 * The original caches start/timeout on entry. This pure component has no
 * concurrent mutation; original-code cache-intervention tests are separate.
 */
uint32_t ys4470_fsm_timed_step(ys4470_fsm_timed_state *s,
                             const ys4470_fsm_observation *e)
{
    uint32_t effects = 0;
    const uint32_t expired = (uint32_t)(e->now - s->start) >= s->timeout;
    if (s->state == 2u) {
        if (e->rx_count > 0 && e->first_byte == s->expected_header) {
            if (s->command >= 9u && s->command <= 15u) {
                s->start = e->now;
                s->timeout = (s->command == 13u || s->command == 14u) ? 100u : 50u;
                s->state = 4u;
                return YS4470_FSM_READ_TICK;
            }
            s->index++;
            s->retry = 0;
            s->state = 1u;
            return YS4470_FSM_CLEAR_GPIO_2_3;
        }
        effects = YS4470_FSM_READ_TICK;
        if (expired) s->state = 6u;
    } else if (s->state == 3u) {
        if ((int32_t)s->required > e->rx_count) {
            effects = YS4470_FSM_READ_TICK;
            if (expired) s->state = 6u;
        } else {
            s->state = ((s->command == 0x1bu && e->first_byte != 0x5eu) ||
                        (s->command == 0x1du && e->first_byte != 0x60u)) ? 6u : 5u;
        }
    } else if (s->state == 4u) {
        effects = YS4470_FSM_READ_TICK;
        if (expired) {
            s->index++;
            s->retry = 0;
            s->state = 1u;
            effects |= YS4470_FSM_CLEAR_GPIO_2_3;
        }
    }
    return effects;
}
