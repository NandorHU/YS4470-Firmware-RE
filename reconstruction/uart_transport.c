#include "uart_transport.h"

/* Original 0x80005e84 framing, independent specification of the bounded data
 * transformation. This returns wire length; the original returns success1.
 * Blocking UART-ready polling and peripheral writes are caller responsibilities.
 */
uint32_t ys4470_uart_frame(const uint8_t *source, uint32_t count, uint8_t *wire)
{
    uint32_t i, sum = 0;
    if (count > 199u) return 0;
    for (i = 0; i < count; ++i) {
        wire[i] = source[i];
        sum += source[i];
    }
    wire[count] = (uint8_t)sum;
    return count + 1u;
}

/* Original RX ISR 0x800073bc append rule for valid nonnegative counts.
 * No framing, checksum or transaction identifier is added by this component.
 * These observations alone do not define the external peer's protocol.
 */
uint32_t ys4470_uart_rx_push(uint8_t *buffer, uint32_t *count,
                            uint32_t interrupt_status, uint32_t received_word)
{
    uint32_t n = *count;
    if (!(interrupt_status & 4u) || n >= 200u) return 0;
    buffer[n] = (uint8_t)received_word;
    *count = n + 1u;
    return 1;
}
