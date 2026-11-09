#ifndef YS4470_MEASUREMENT_PLAN_H
#define YS4470_MEASUREMENT_PLAN_H

#include <stdint.h>

struct ys4470_measurement_plan {
    uint32_t mode;
    uint32_t count;
    uint32_t commands[4];
    uint32_t update_control;
    uint32_t configured;
    uint32_t discard;
};

/* Return 1 for handled record types 2–5. For other types, leave out untouched. */
uint32_t ys4470_make_measurement_plan(uint32_t type, uint8_t primary, uint8_t secondary,
                                     struct ys4470_measurement_plan *out);

#endif
