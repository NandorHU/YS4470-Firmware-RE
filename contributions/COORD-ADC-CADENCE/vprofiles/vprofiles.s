@ Beta Diode profiles: 0 Base (factory E2 path), 1..4 = v1..v4, all with ownprotocol polling.
@ beta.6: only v2 and v4 are reachable (cycle, toggle and boot default); 0/1/3 remain as tested code paths.
@   v1 = beta.4 behaviour          v2 = A: diode config adds 68 0a (descriptor 0x1e)
@   v3 = B: early short tone       v4 = A + B
@ Every numeric external branch stays before the first literal pool (Keystone 0.9.2 relocation bug).

own_auto:
    push {r4, lr}
    bl own_reconfig
    cmp r0, #0
    popne {r4, pc}
    ldr r4, =0x80060a90
    ldrb r0, [r4]
    sub r1, r0, #1
    cmp r1, #3
    bhi 0x80011110
    ldrb r1, [r4, #1]
    cmp r1, r0
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
    bl 0x80004490
    add sp, sp, #8
    pop {r4, pc}

@ Re-send the diode configuration when the chip's 68-state does not match the active profile.
@ Same idle/diode guards as own_auto. Returns r0=1 if a record was queued.
own_reconfig:
    push {r4, lr}
    ldr r4, =own_state
    ldrb r0, [r4, #1]
    cmp r0, #0
    bne own_reconfig_no
    ldr r3, =0x80060a90
    ldrb r0, [r3]
    ldrb r1, [r3, #1]
    cmp r0, r1
    bne own_reconfig_no
    ldr ip, =0x805abefc
    ldrb r1, [ip]
    cmp r1, #3
    ldrbeq r1, [ip, #7]
    cmpeq r1, #14
    bne own_reconfig_no
    ldr ip, =0x805aae8c
    ldrb r1, [ip]
    cmp r1, #0
    ldrbeq r1, [ip, #1]
    cmpeq r1, #0
    ldreq r1, [ip, #8]
    cmpeq r1, #14
    bne own_reconfig_no
    ldr ip, =0x805ac694
    ldrb r1, [ip, #0x34]
    cmp r1, #0
    bne own_reconfig_no
    mov r2, #0
    cmp r0, #2
    cmpne r0, #4
    moveq r2, #1
    ldrb r1, [r4]
    cmp r1, r2
    beq own_reconfig_no
    mov r0, #1
    strb r0, [r4, #1]
    mov r0, #2
    mov r1, #14
    mov r2, #0x13
    bl 0x80006778
    mov r0, #1
    pop {r4, pc}
own_reconfig_no:
    mov r0, #0
    pop {r4, pc}

@ Hook at 0x8000446c (case-2 list build). r1=config r2=secondary r3=CTRL r4=0x1d, sp=16-byte list.
own_case2:
    ldr ip, =own_state
    mov r0, #0
    cmp r1, #14
    bne own_case2_store
    ldr r0, =0x80060a90
    ldrb r0, [r0]
    cmp r0, #2
    cmpne r0, #4
    moveq r0, #1
    movne r0, #0
own_case2_store:
    strb r0, [ip]
    mov r0, #0
    strb r0, [ip, #1]
    ldrb r0, [ip]
    cmp r0, #0
    beq own_case2_plain
    str r1, [sp]
    mov r0, #0x1e
    str r0, [sp, #4]
    str r2, [sp, #8]
    str r4, [sp, #12]
    mov r2, #4
    mov r1, sp
    mov r0, #3
    bl 0x8000489c
    b 0x80004480
own_case2_plain:
    stm sp, {r1, r2, r4}
    b 0x80004470

@ Replaces 'bl 0x80010754' at 0x80060c94. r0 = raw (mV). Returns r5 class (0.0 / 0.5 / 1.0 float bits).
@ v3/v4 "tone first": the first valid reading after OL (contact) reports short at once. While distinct
@ readings keep falling the flag is kept; with three valid readings the decay is extrapolated
@ (geometric if decelerating, otherwise one linear step) and the flag stays only if it points below 100 mV.
@ A rise, a plateau value or OL clears it, so the factory policy then switches a mistaken tone off.
own_classify:
    push {r0-r4, lr}
    bl 0x80010754
    ldr r4, =0x80060a90
    ldrb r1, [r4]
    cmp r1, #3
    cmpne r1, #4
    bne own_classify_done
    ldr r4, =own_hist
    ldr r1, [r4]
    cmp r0, r1
    beq own_classify_reuse
    ldr r2, [r4, #4]
    str r1, [r4, #4]
    str r0, [r4]
    ldr r3, [r4, #8]
    ldr ip, =5000
    cmp r0, ip
    bhi own_classify_clear
    cmp r1, ip
    bhi own_classify_set
    cmp r0, r1
    bhs own_classify_clear
    cmp r2, ip
    bhi own_classify_store
    sub r2, r2, r1
    sub r1, r1, r0
    cmp r2, #0
    ble own_classify_clear
    cmp r1, r2
    bge own_classify_linear
    sub r2, r2, r1
    mul ip, r1, r1
    rsb lr, r0, #100
    mul lr, r2, lr
    adds ip, ip, lr
    movgt r3, #1
    movle r3, #0
    b own_classify_store
own_classify_linear:
    @ Linear (or accelerating) fall: the end point is unknown, keep the previous flag.
    b own_classify_store
own_classify_set:
    mov r3, #1
    b own_classify_store
own_classify_clear:
    mov r3, #0
own_classify_store:
    str r3, [r4, #8]
    ldr r1, =0x805abbc8
    ldr r1, [r1]
    str r1, [r4, #12]
    b own_classify_apply
own_classify_reuse:
    @ Unchanged reading: a flag older than PLATEAU ticks (1 tick = 1 ms) is dropped.
    ldr r3, [r4, #8]
    cmp r3, #0
    beq own_classify_apply
    ldr r1, =0x805abbc8
    ldr r1, [r1]
    ldr r2, [r4, #12]
    sub r1, r1, r2
    cmp r1, #200
    movhi r3, #0
    strhi r3, [r4, #8]
own_classify_apply:
    cmp r3, #0
    movne r5, #0
own_classify_done:
    pop {r0-r4, pc}

@ Replaces 'bleq 0x8001110c' at 0x8005fb84 (after profile apply + reply-owner gate). Flags of the gate are
@ live on entry. The 68-state check runs for every profile, Base included; then the original conditional call.
own_post_apply:
    push {r4, lr}
    moveq r4, #1
    movne r4, #0
    bl own_reconfig
    cmp r0, #0
    popne {r4, pc}
    cmp r4, #1
    pop {r4, lr}
    beq 0x8001110c
    bx lr

@ Only v2 and v4 are selectable (beta.6): r0 = requested + 1 -> 2 <-> 4.
own_cycle:
    cmp r0, #3
    moveq r0, #4
    movne r0, #2
    b 0x8005f8b4

own_label:
    push {r0-r3, ip, lr}
    ldr r0, [r4, #12]
    cmp r0, #0
    beq own_label_size_done
    mov r1, #112
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
.word BASE_LABEL, name_v1, name_v2, name_v3, name_v4
own_hist:
.word 0, 0, 0, 0
own_state:
.byte 0, 0, 0, 0
own_cmd68:
.byte 0x68, 0x0a, 0, 0
name_v1:
.asciz "v1"
name_v2:
.asciz "v2"
name_v3:
.asciz "v3"
name_v4:
.asciz "v4"
.align 2
