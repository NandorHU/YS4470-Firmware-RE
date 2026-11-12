#include "display_copy.h"

static bool rectangle_inside(const struct ys4470_display_rectangle *rectangle,
                             int width, int height)
{
    return rectangle->left >= 0 && rectangle->top >= 0 &&
           rectangle->right >= rectangle->left &&
           rectangle->bottom >= rectangle->top &&
           rectangle->right < width && rectangle->bottom < height;
}

bool ys4470_panel_copy(const struct ys4470_display_rectangle *rectangle,
                      const uint16_t *source, uint16_t *panel)
{
    if (!rectangle_inside(rectangle, YS4470_PANEL_WIDTH, YS4470_PANEL_HEIGHT)) {
        return false;
    }

    for (int y = rectangle->top; y <= rectangle->bottom; ++y) {
        for (int x = rectangle->left; x <= rectangle->right; ++x) {
            panel[y * YS4470_PANEL_WIDTH + x] = *source++;
        }
    }
    return true;
}

bool ys4470_panel_copy_rotated(const struct ys4470_display_rectangle *rectangle,
                              const uint16_t *source, uint16_t *panel)
{
    if (!rectangle_inside(rectangle, YS4470_PANEL_HEIGHT, YS4470_PANEL_WIDTH)) {
        return false;
    }

    for (int y = rectangle->top; y <= rectangle->bottom; ++y) {
        int panel_x = YS4470_PANEL_WIDTH - 1 - y;
        for (int x = rectangle->left; x <= rectangle->right; ++x) {
            panel[x * YS4470_PANEL_WIDTH + panel_x] = *source++;
        }
    }
    return true;
}
