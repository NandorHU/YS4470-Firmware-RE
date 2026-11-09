#ifndef YS4470_UART_TRANSPORT_H
#define YS4470_UART_TRANSPORT_H
#include <stdint.h>

/* Pure bounded components, not UART drivers or a complete meter firmware.
 * Equivalence domain: count 0..201, separate source/destination buffers with
 * at least count/200 bytes respectively. Original count+1 overflow at UINT_MAX
 * and invalid/negative RX counts are outside the established contract.
 */
uint32_t ys4470_uart_frame(const uint8_t *source, uint32_t count, uint8_t *wire);
uint32_t ys4470_uart_rx_push(uint8_t *buffer, uint32_t *count,
                            uint32_t interrupt_status, uint32_t received_word);
#endif
