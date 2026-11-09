#include "measurement_plan.h"

uint32_t ys4470_make_measurement_plan(uint32_t type, uint8_t primary, uint8_t secondary,
                                     struct ys4470_measurement_plan *out)
{
    if (type < 2 || type > 5)
        return 0;

    out->commands[1] = 0;
    out->commands[2] = 0;
    out->commands[3] = 0;
    if (type == 3 || type == 4) {
        out->mode = type - 2;
        out->count = 1;
        out->commands[0] = type == 3 ? 0x1d : 0x1b;
        out->update_control = 0;
        out->configured = 0;
        out->discard = 0;
        return 1;
    }

    out->mode = 3;
    out->update_control = 1;
    out->discard = 2;
    if (type == 2) {
        out->count = 3;
        out->commands[0] = primary;
        out->commands[1] = secondary >= 0x13 && secondary <= 0x18 ? secondary : 0x19;
        out->commands[2] = 0x1d;
        out->configured = primary;
    } else {
        out->count = 4;
        out->commands[0] = 0x0c;
        out->commands[1] = 0x22;
        out->commands[2] = 0x13;
        out->commands[3] = 0x1d;
        out->configured = 0x22;
    }
    return 1;
}
