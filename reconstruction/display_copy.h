#ifndef YS4470_DISPLAY_COPY_H
#define YS4470_DISPLAY_COPY_H

#include <stdbool.h>
#include <stdint.h>

enum {
    YS4470_PANEL_WIDTH = 480,
    YS4470_PANEL_HEIGHT = 854
};

struct ys4470_display_rectangle {
    int16_t left;
    int16_t top;
    int16_t right;
    int16_t bottom;
};

/*
 * Source pixels are packed row-major RGB565 and occupy the complete rectangle.
 * The panel holds 480 * 854 pixels. Source and panel storage must be separate.
 * Invalid or inverted rectangles return false before copying any pixels.
 */
bool ys4470_panel_copy(const struct ys4470_display_rectangle *rectangle,
                      const uint16_t *source, uint16_t *panel);

/* Map the native 854 * 480 logical orientation into the 480 * 854 panel. */
bool ys4470_panel_copy_rotated(const struct ys4470_display_rectangle *rectangle,
                              const uint16_t *source, uint16_t *panel);

#endif
