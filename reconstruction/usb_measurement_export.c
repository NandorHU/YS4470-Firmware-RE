#include "usb_measurement_export.h"

static uint8_t category_for(const struct ys4470_export_state *state)
{
    if (state->ui_mode == 4) {
        return 4;
    }
    switch (state->configuration) {
    case 9:
    case 10:
    case 11:
        return 1;
    case 12:
    case 34:
        return 2;
    case 14:
        return 4;
    case 15:
        return 3;
    default:
        return 0;
    }
}

static const char *suffix_for(const struct ys4470_export_state *state)
{
    static const char *const resistance[] = {"R", "K", "K", "K", "M", "M", "M"};
    static const char *const capacitance[] = {"nF", "uF", "uF", "mF", "mF", "mF", "mF"};
    uint8_t selector = state->selector < 7 ? state->selector : 0;

    if (state->ui_mode == 4) {
        return state->configuration == 34 && state->fast_cont == 1 ? "R" : "V";
    }
    switch (state->configuration) {
    case 9:
    case 10:
    case 13:
    case 14:
        return "V";
    case 12:
    case 34:
        if (state->secondary == 0x15 && state->stored_raw < 100) {
            selector = 0;
        }
        return resistance[selector];
    case 15:
        return capacitance[selector];
    default:
        return state->configuration >= 48 ? "" : 0;
    }
}

static bool is_status_text(const char *text)
{
    for (; *text; ++text) {
        if ((text[0] == '.' && text[1] == 'O' && text[2] == 'L') ||
            (text[0] == 'O' && text[1] == 'P' && text[2] == 'E' && text[3] == 'N')) {
            return true;
        }
    }
    return false;
}

static bool is_stripped(char character)
{
    return character == ' ' || character == '\t' || character == '\r' || character == '\n';
}

bool ys4470_export_update(const struct ys4470_export_state *state,
                          const char *text, bool strip_whitespace,
                          struct ys4470_export_mirror *mirror)
{
    if (text == 0 || *text == '\0') {
        return false;
    }
    const bool status = is_status_text(text);
    const bool strip = strip_whitespace && !status;
    const char *suffix = "";
    if (!status && !strip) {
        suffix = suffix_for(state);
        if (suffix == 0) {
            return false;
        }
    }

    unsigned used = 0;
    for (; *text && used < YS4470_EXPORT_TEXT_SIZE - 1; ++text) {
        if (!strip || !is_stripped(*text)) {
            mirror->text[used++] = *text;
        }
    }
    while (*suffix && used < YS4470_EXPORT_TEXT_SIZE - 1) {
        mirror->text[used++] = *suffix++;
    }
    while (used < YS4470_EXPORT_TEXT_SIZE) {
        mirror->text[used++] = '\0';
    }
    mirror->category = category_for(state);
    return true;
}

void ys4470_export_report(const struct ys4470_export_mirror *mirror,
                          uint8_t report[YS4470_EXPORT_REPORT_SIZE])
{
    report[0] = 0;
    report[1] = 4;
    report[2] = 0x3f;
    report[3] = mirror->category;
    for (unsigned i = 0; i < YS4470_EXPORT_TEXT_SIZE; ++i) {
        report[4 + i] = (uint8_t)mirror->text[i];
    }
    for (unsigned i = 4 + YS4470_EXPORT_TEXT_SIZE; i < YS4470_EXPORT_REPORT_SIZE; ++i) {
        report[i] = 0;
    }
}
