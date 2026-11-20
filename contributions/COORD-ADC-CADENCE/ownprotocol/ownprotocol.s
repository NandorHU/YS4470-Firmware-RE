@ Hooks for profile 4. Other profiles execute their original paths.
own_auto:
    push {r4, lr}
    ldr r4, =0x80060a90
    ldrb r0, [r4]
    cmp r0, #4
    bne 0x80011110
    ldrb r0, [r4, #1]
    cmp r0, #4
    popne {r4, pc}
    ldr r4, =0x805abefc
    ldrb r0, [r4]
    cmp r0, #3
    ldrbeq r0, [r4, #7]
    cmpeq r0, #14
    popne {r4, pc}
    ldr r4, =0x805aae8c
    ldrb r0, [r4]
    cmp r0, #0
    ldrbeq r0, [r4, #1]
    cmpeq r0, #0
    ldreq r0, [r4, #8]
    cmpeq r0, #14
    popne {r4, pc}
    ldr r4, =0x805ac694
    ldrb r0, [r4, #0x34]
    cmp r0, #0
    popne {r4, pc}
    sub sp, sp, #8
    mov r0, #0x1d
    str r0, [sp]
    mov r0, #1
    mov r1, sp
    mov r2, #1
    bl 0x8000489c
    @ Start exactly one factory transaction now, without a synthetic queue item.
    bl 0x80004490
    add sp, sp, #8
    pop {r4, pc}

own_cycle:
    cmp r0, #5
    movhs r0, #0
    b 0x8005f8b4

own_label:
    push {r0-r3, ip, lr}
    ldr r0, [r4, #12]
    cmp r0, #0
    beq own_label_size_done
    mov r1, #112
    cmp r6, #4
    moveq r1, #180
    mov r2, #30
    bl 0x8003a2c8
own_label_size_done:
    pop {r0-r3, ip, lr}
    cmp r0, #4
    movhi r0, #0
    ldr r1, =own_names
    ldr r1, [r1, r0, lsl #2]
    b 0x800609c8

.ltorg
.align 2
own_names:
.word BASE_LABEL, DIRECT_LABEL, AUTO_LABEL, READY_LABEL, own_name
own_name:
.asciz "ownprotocol"
.align 2
