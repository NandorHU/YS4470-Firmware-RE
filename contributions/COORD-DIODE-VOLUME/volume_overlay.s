.equ MODE, 0x805abefc
.equ GUI, 0x805ac098
.equ SOUND, 0x805ac770
.equ RESULT, 0x805ac714
.equ PLAYING, 0x805ab924
.equ FONT_BITMAP, 0x8006b688
.equ FONT_SIZE, 9612

b create_hook
b tick_hook
b tone_volume
b get_bitmap

create_hook:
    push {r0-r12, lr}
    bl 0x80060a08
    bl create_volume
    pop {r0-r12, pc}

tick_hook:
    push {r0-r3, r12, lr}
    bl update_visibility
    pop {r0-r3, r12, lr}
    b 0x8001b5cc

tone_volume:
    ldr ip, [sp, #12]
    ldr r3, =0x80003a78
    cmp ip, r3
    ldrne r3, =0x80060cb0
    cmpne ip, r3
    bne 0x800630a4
    ldr r0, =volume_state
    ldr r0, [r0]
    b volume_gain

volume_gain:
    ldr ip, =gain_table
    ldr r0, [ip, r0, lsl #2]
    bx lr

create_volume:
    push {r4-r8, lr}
    ldr r4, =volume_state
    mov r0, #0
    str r0, [r4, #4]
    str r0, [r4, #8]
    str r0, [r4, #12]
    str r0, [r4, #16]
    mvn r0, #0
    str r0, [r4, #20]
    ldr r5, =GUI
    ldr r5, [r5, #0x268]
    cmp r5, #0
    popeq {r4-r8, pc}
    mov r0, r5
    mov r1, #288
    ldr r2, =minus_text
    mvn r3, #0
    bl make_button
    str r0, [r4, #4]
    mov r0, r5
    ldr r1, =383
    ldr r2, =plus_text
    mov r3, #1
    bl make_button
    str r0, [r4, #12]
    mov r0, r5
    ldr r1, =333
    mov r2, #46
    mov r3, #0
    bl make_text
    str r0, [r4, #8]
    mov r0, r5
    mov r1, #226
    mov r2, #58
    ldr r3, =caption_text
    bl make_text
    str r0, [r4, #16]
    bl refresh_label
    bl update_visibility
    pop {r4-r8, pc}

make_text:
    push {r4-r8, lr}
    mov r5, r1
    mov r6, r2
    mov r7, r3
    bl 0x80030ad0
    cmp r0, #0
    popeq {r4-r8, pc}
    mov r4, r0
    mov r1, r5
    mov r2, #74
    bl 0x8003a160
    mov r0, r4
    mov r1, r6
    mov r2, #24
    bl 0x8003a2c8
    mov r0, r4
    ldr r1, =0x8006eaf8
    mov r2, #0
    bl 0x8003aa58
    mov r0, r4
    ldr r1, =0xffff
    mov r2, #0
    bl 0x8003aa38
    mov r0, r4
    mov r1, r7
    cmp r1, #0
    blne 0x80032038
    mov r0, r4
    pop {r4-r8, pc}

make_button:
    push {r4-r8, lr}
    mov r5, r1
    mov r6, r2
    mov r7, r3
    bl 0x80021f3c
    cmp r0, #0
    popeq {r4-r8, pc}
    mov r4, r0
    mov r1, r5
    mov r2, #66
    bl 0x8003a160
    mov r0, r4
    mov r1, #42
    mov r2, #38
    bl 0x8003a2c8
    mov r0, r4
    ldr r1, =0x2945
    mov r2, #0
    bl 0x8003a718
    mov r0, r4
    mov r1, #6
    mov r2, #0
    bl 0x8003a7b8
    mov r0, r4
    ldr r1, =0x80080888
    mov r2, #0
    bl 0x8003aa58
    mov r0, r4
    bl 0x80030ad0
    cmp r0, #0
    beq hide_failed_button
    mov r5, r0
    mov r1, r6
    bl 0x80032038
    mov r0, r5
    mov r1, #9
    mov r2, #0
    mov r3, #0
    bl 0x80033b7c
    mov r0, r4
    ldr r1, =volume_click
    mov r2, #1
    mov r3, r7
    bl 0x800338dc
    mov r0, r4
    pop {r4-r8, pc}
hide_failed_button:
    mov r0, r4
    mov r1, #1
    bl 0x800339bc
    mov r0, #0
    pop {r4-r8, pc}

refresh_label:
    ldr r2, =volume_state
    ldr r0, [r2, #8]
    cmp r0, #0
    bxeq lr
    ldr r1, [r2]
    add r1, r1, r1, lsl #2
    ldr r2, =volume_text
    add r1, r2, r1
    b 0x80032038

diode_selected:
    ldr r0, =MODE
    ldrb r1, [r0]
    cmp r1, #3
    ldrbeq r1, [r0, #7]
    cmpeq r1, #14
    bx lr

update_visibility:
    push {r4-r8, lr}
    ldr r4, =volume_state
    ldr r0, [r4, #4]
    ldr r1, [r4, #8]
    orrs r0, r0, r1
    ldreq r0, [r4, #12]
    cmpeq r0, #0
    ldreq r0, [r4, #16]
    cmpeq r0, #0
    popeq {r4-r8, pc}
    mov r5, #1
    bl diode_selected
    bne apply_visibility
    ldr r0, =GUI
    ldr r0, [r0, #0x2f0]
    cmp r0, #0
    beq apply_visibility
    ldr r0, [r0, #28]
    tst r0, #1
    beq apply_visibility
    ldr r0, [r4, #4]
    cmp r0, #0
    ldrne r0, [r4, #8]
    cmpne r0, #0
    ldrne r0, [r4, #12]
    cmpne r0, #0
    ldrne r0, [r4, #16]
    cmpne r0, #0
    movne r5, #0
apply_visibility:
    ldr r0, [r4, #20]
    cmp r0, r5
    popeq {r4-r8, pc}
    str r5, [r4, #20]
    cmp r5, #1
    ldreq r6, =0x800339bc
    ldrne r6, =0x80034a50
    mov r7, #4
vis_loop:
    ldr r0, [r4, r7]
    mov r1, #1
    cmp r0, #0
    blxne r6
    add r7, r7, #4
    cmp r7, #20
    bne vis_loop
    pop {r4-r8, pc}

volume_click:
    push {r4-r8, lr}
    ldr r7, [r0, #12]
    ldr r4, =volume_state
    ldr r0, [r4, #20]
    cmp r0, #0
    popne {r4-r8, pc}
    bl 0x80060efc
    bl diode_selected
    bne release
    ldr r5, [r4]
    add r6, r5, r7
    cmp r6, #0
    movlt r6, #0
    cmp r6, #10
    movgt r6, #10
    cmp r5, r6
    beq release
    str r6, [r4]
    ldrb r0, [r0, #10]
    cmp r0, #2
    bne changed
    ldr r0, =SOUND
    ldr r0, [r0, #16]
    cmp r0, #1
    bne changed
    ldr r0, =PLAYING
    ldr r0, [r0]
    cmp r0, #1
    bne changed
    ldr r0, =RESULT
    ldr r0, [r0, #0x50]
    cmp r0, #3
    bls changed
    mov r0, r6
    bl volume_gain
    mov r2, r0
    mov r0, #0
    ldr r1, =1321
    mov r3, #1
    bl 0x800060d0
changed:
    bl 0x80060f20
    bl refresh_label
    pop {r4-r8, pc}
release:
    bl 0x80060f20
    pop {r4-r8, pc}

get_bitmap:
    push {r4-r8, lr}
    mov r4, r0
    mov r5, r1
    ldr r6, [r4, #16]
    ldr r0, [r6]
    ldr r8, =FONT_BITMAP
    cmp r0, r8
    bne bitmap_ready
    ldr r0, =FONT_SIZE
    bl 0x80032800
    cmp r0, #0
    popeq {r4-r8, pc}
    mov r7, r0
    ldr r8, =FONT_SIZE
    add r8, r0, r8
    ldr r1, =font_packed
    ldr ip, =PACKED_SIZE
    add ip, r1, ip
decode_next:
    cmp r1, ip
    bhs decode_failed
    ldrb r2, [r1], #1
    cmp r2, #0
    beq decode_done
    tst r2, #128
    bne decode_run
    sub r3, r8, r0
    cmp r2, r3
    bhi decode_failed
    sub r3, ip, r1
    cmp r2, r3
    bhi decode_failed
literal_loop:
    ldrb r3, [r1], #1
    strb r3, [r0], #1
    subs r2, r2, #1
    bne literal_loop
    b decode_next
decode_run:
    bic r2, r2, #128
    add r2, r2, #3
    sub r3, r8, r0
    cmp r2, r3
    bhi decode_failed
    cmp r1, ip
    bhs decode_failed
    ldrb r3, [r1], #1
run_loop:
    strb r3, [r0], #1
    subs r2, r2, #1
    bne run_loop
    b decode_next
decode_done:
    cmp r0, r8
    bne decode_failed
    str r7, [r6]
bitmap_ready:
    mov r0, r4
    mov r1, r5
    pop {r4-r8, lr}
    b 0x8002c844
decode_failed:
    mov r0, r7
    bl 0x80032a80
    mov r0, #0
    pop {r4-r8, pc}

.ltorg
.align 2
@ PWM duty in percent, passed as float32 to the factory routine.
gain_table:
.float 0.0, 0.25, 0.5, 1.0, 2.0, 3.5, 5.5, 8.5, 12.5, 18.0, 25.0
volume_state:
.word 6, 0, 0, 0, 0, 0xffffffff
minus_text:
.asciz "-"
plus_text:
.asciz "+"
caption_text:
.asciz "Volume"
volume_text:
.ascii "0%"
.byte 0, 0, 0
.ascii "10%"
.byte 0, 0
.ascii "20%"
.byte 0, 0
.ascii "30%"
.byte 0, 0
.ascii "40%"
.byte 0, 0
.ascii "50%"
.byte 0, 0
.ascii "60%"
.byte 0, 0
.ascii "70%"
.byte 0, 0
.ascii "80%"
.byte 0, 0
.ascii "90%"
.byte 0, 0
.asciz "100%"
.align 2
font_packed:
