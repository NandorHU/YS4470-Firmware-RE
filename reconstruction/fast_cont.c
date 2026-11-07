#include "fast_cont.h"

uint32_t ys_fast_cont_update(ys_fast_cont_state *s, int32_t value)
{
    if (value > 1000) {
        s->history[0] = s->history[1] = s->history[2] = 1000;
        s->count = 0;
        s->last_median = -1;
        /* The original helper does not reset the ring index here. */
    }
    s->history[s->next] = value;
    s->next = s->next == 2 ? 0 : s->next + 1;
    if (s->count < 3) ++s->count;
    if (s->count == 3) {
        int32_t lo = s->history[0], hi = lo;
        for (uint32_t i = 1; i != 3; ++i) {
            if (s->history[i] < lo) lo = s->history[i];
            if (s->history[i] > hi) hi = s->history[i];
        }
        /* Preserve the original SMULL + SUBS/SBCS + unsigned carry test.
         * A signed comparison would differ for mixed-sign histories.
         */
        uint64_t left = (uint64_t)((int64_t)lo * 120);
        uint64_t right = (uint64_t)((int64_t)hi * 100);
        if (left >= right) {
            /* Median-of-three avoids signed-overflow assumptions. */
            int32_t a = s->history[0], b = s->history[1], c = s->history[2];
            s->last_median = a < b ? (b < c ? b : (a < c ? c : a))
                                 : (a < c ? a : (b < c ? c : b));
        }
    }
    /* The original 11 rows implement these five nonzero selector bands;
     * all remaining rows/ranges request off. Stored median is retained
     * when the new three-value history fails the stability condition.
     */
    if (s->last_median < 0 || s->last_median >= 100) return 0;
    return 10u - 2u * ((uint32_t)s->last_median / 20u);
}
