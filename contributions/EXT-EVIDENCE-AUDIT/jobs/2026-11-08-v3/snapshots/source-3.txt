#ifndef YS4470_FSM_TIMEOUT_H
#define YS4470_FSM_TIMEOUT_H
#include <stdint.h>

/* Semantic interface, not the original in-RAM struct layout.
 * Valid state values: 2, 3 or 4. Call once per FSM observation.
 * now/start/timeout are raw modulo-2^32 RTOS counter values, not milliseconds.
 */
typedef struct {
    uint32_t state, command, start, timeout, index, retry, required, expected_header;
} ys4470_fsm_timed_state;
typedef struct {
    int32_t rx_count;
    uint32_t first_byte, now;
} ys4470_fsm_observation;
enum { YS4470_FSM_READ_TICK = 1u, YS4470_FSM_CLEAR_GPIO_2_3 = 2u };

/* Returns requested effects; does not perform MMIO, critical sections or I/O.
 * Caller supplies the tick snapshot when the returned path needs one.
 */
uint32_t ys4470_fsm_timed_step(ys4470_fsm_timed_state *s,
                             const ys4470_fsm_observation *e);
#endif
