#ifndef YS4470_USB_MEASUREMENT_EXPORT_H
#define YS4470_USB_MEASUREMENT_EXPORT_H

#include <stdbool.h>
#include <stdint.h>

enum { YS4470_EXPORT_TEXT_SIZE = 20, YS4470_EXPORT_REPORT_SIZE = 64 };

/* Logical caller state. This type is independent of the factory RAM layout. */
struct ys4470_export_state {
    int32_t stored_raw;
    uint8_t ui_mode;
    uint8_t configuration;
    uint8_t secondary;
    uint8_t selector;
    uint32_t fast_cont;
};

struct ys4470_export_mirror {
    uint8_t category;
    char text[YS4470_EXPORT_TEXT_SIZE];
};

/*
 * Reconstruct the report mirror for a NUL-terminated ASCII input. The
 * verified normal suffix table covers configurations 9, 10, 12, 13, 14, 15
 * and 34, along with the empty-suffix path for configurations 48 and above.
 * The mode-4, status-text and whitespace paths bypass normal unit selection.
 * The mirror is unchanged when the input is empty or no verified suffix
 * exists for the requested path. Input and output storage must be separate.
 */
bool ys4470_export_update(const struct ys4470_export_state *state,
                          const char *text, bool strip_whitespace,
                          struct ys4470_export_mirror *mirror);

/* Build the 64-byte report from a populated mirror. This performs no I/O. */
void ys4470_export_report(const struct ys4470_export_mirror *mirror,
                          uint8_t report[YS4470_EXPORT_REPORT_SIZE]);

#endif
