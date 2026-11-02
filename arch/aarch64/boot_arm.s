// SPDX-License-Identifier: Apache-2.0
//
// boot_arm.s - the aarch64 machine layer for K0 (QEMU virt).
//
// The kernel is a single Krell module (kernel.krell). Its logic
// is machine independent; this file provides the same thirteen
// services boot.s provides on x86_64, with the same semantics,
// over the ARM platform:
//
//   serial console   COM1 (polled)      -> PL011 UART0, MMIO
//   keyboard         PS/2 IRQ1          -> UART receive, polled
//                                         on each timer tick and
//                                         translated from ASCII
//                                         to PS/2 set-1 scancodes
//   timer            PIT at 100 Hz      -> ARM generic timer,
//                                         PPI 29, at 100 Hz
//   interrupt ctrl   PIC                -> GICv2 (distributor and
//                                         CPU interface)
//   port I/O         x86 ports          -> the COM1 register file
//                                         is mapped onto the
//                                         PL011; every other
//                                         device reads as absent
//   physical memory  addresses from 0   -> the MMU maps virtual
//                                         [0, 128 MiB) onto RAM
//                                         at 0x40000000, so the
//                                         kernel's address space
//                                         is identical to x86
//   VGA text memory  0xB8000            -> unmapped; data aborts
//                                         from that range are
//                                         emulated (stores
//                                         dropped, loads read 0)
//                                         so the console code
//                                         runs unchanged and all
//                                         output reaches serial
//
// Boot state is fabricated as a Multiboot information block, the
// same construction stage2.s uses on x86_64: flags, memory
// fields, a one-entry memory map covering the RAM window, and
// three module entries for the images QEMU loads at fixed
// addresses with -device loader.
//
// RAM size is fixed at 128 MiB (-m 128). The kernel is linked at
// virtual 0x100000 and loaded at physical 0x40100000.

    .include "boot_arm.inc"

    .equ RAM_PA,      0x40000000
    .equ RAM_MIB_KIB, 130048          // mem_upper for 128 MiB
    .equ UART_VA,     0x08000000      // PL011 at PA 0x09000000
    .equ GICD_VA,     0x08200000      // GICD at PA 0x08000000
    .equ GICC_VA,     0x08210000      // GICC at PA 0x08010000
    .equ VGA_LO,      0xB8000
    .equ VGA_HI,      0xC0000

// ----------------------------------------------------------------
// entry stub. Linked at its physical address; runs with the MMU
// off. Builds the page tables, switches the MMU on, and branches
// to the landing pad at its virtual address.
// ----------------------------------------------------------------

    .section .bootarm, "ax"
    .globl _arm_start
_arm_start:
    mrs     x1, CurrentEL
    ubfx    x1, x1, #2, #2
    cmp     x1, #2
    b.ne    el1_in
    // drop from EL2 to EL1
    mov     x1, #(1 << 31)            // HCR_EL2.RW: EL1 is AArch64
    msr     hcr_el2, x1
    mov     x1, #0x3c5                // SPSR_EL2: EL1h, DAIF masked
    msr     spsr_el2, x1
    adr     x1, el1_in
    msr     elr_el2, x1
    eret
el1_in:
    mov     x28, #0x40000000          // RAM physical base
    ldr     x1, =k_stack_top
    add     x1, x1, x28
    mov     sp, x1

    // zero the two page table pages (physical addresses)
    ldr     x0, =arm_l1
    add     x0, x0, x28
    mov     x2, #8192
1:  str     xzr, [x0], #8
    subs    x2, x2, #8
    b.ne    1b

    // L1[0] -> L2 table
    ldr     x0, =arm_l1
    add     x0, x0, x28
    ldr     x1, =arm_l2
    add     x1, x1, x28
    orr     x1, x1, #3                // valid table descriptor
    str     x1, [x0]
    str     x1, [x0, #8]

    // L2[0..63]: 2 MiB blocks, VA i*2MiB -> PA RAM + i*2MiB,
    // normal write-back, inner shareable, access flag set
    ldr     x0, =arm_l2
    add     x0, x0, x28
    mov     x1, x28                   // PA of first block
    mov     x2, #64
2:  orr     x3, x1, #0x700            // AF + inner shareable
    orr     x3, x3, #1                // + valid block
    str     x3, [x0], #8
    add     x1, x1, #0x200000
    subs    x2, x2, #1
    b.ne    2b

    // L2[64]: VA 0x08000000 -> PL011 PA 0x09000000, device
    ldr     x0, =arm_l2
    add     x0, x0, x28
    mov     x1, #0x09000000
    orr     x1, x1, #0x400            // AF
    orr     x1, x1, #0x4              // AttrIndx 1 (device)
    orr     x1, x1, #0x1              // valid block
    str     x1, [x0, #512]
    // L2[65]: VA 0x08200000 -> GIC PA 0x08000000, device
    mov     x1, #0x08000000
    orr     x1, x1, #0x400            // AF
    orr     x1, x1, #0x4              // AttrIndx 1 (device)
    orr     x1, x1, #0x1              // valid block
    str     x1, [x0, #520]

    // memory attributes: index 0 normal WB, index 1 device nGnRE
    mov     x1, #0x04ff
    msr     mair_el1, x1
    // translation control: 39-bit VA, 4 KiB granule, 40-bit PA
    ldr     x1, =0x200003519
    msr     tcr_el1, x1
    ldr     x1, =arm_l1
    add     x1, x1, x28
    msr     ttbr0_el1, x1
    dsb     ish
    tlbi    vmalle1
    dsb     ish
    isb
    // MMU on, caches on, no alignment check (total semantics)
    mrs     x1, sctlr_el1
    orr     x1, x1, #(1 << 0)         // M
    orr     x1, x1, #(1 << 2)         // C
    orr     x1, x1, #(1 << 12)        // I
    bic     x1, x1, #(1 << 1)         // A off
    bic     x1, x1, #(1 << 3)         // SA off
    msr     sctlr_el1, x1
    isb
    adr     x1, arm_land
    sub     x1, x1, x28               // physical -> virtual
    br      x1

// landing pad: first code at virtual addresses. Reached through
// the stub section, which the tables map at VA 0x100000.
arm_land:
    ldr     x1, =k_stack_top
    mov     sp, x1
    ldr     x1, =arm_vectors
    msr     vbar_el1, x1

    // GIC: distributor on, timer PPI 30 enabled, CPU interface on
    ldr     x0, =GICD_VA
    mov     w1, #1
    str     w1, [x0]                  // GICD_CTLR
    mov     w1, #((1 << 29) | (1 << 30))
    str     w1, [x0, #0x100]          // GICD_ISENABLER0
    strb    wzr, [x0, #0x400 + 29]    // GICD_IPRIORITYR29 = 0
    strb    wzr, [x0, #0x400 + 30]    // GICD_IPRIORITYR30 = 0
    ldr     x0, =GICC_VA
    mov     w1, #0xff
    str     w1, [x0, #0x4]            // GICC_PMR
    mov     w1, #1
    str     w1, [x0, #0x0]            // GICC_CTLR

    // PL011: 115200 8n1, FIFOs on, all interrupts masked (polled)
    ldr     x0, =UART_VA
    str     wzr, [x0, #0x30]          // CR off
    mov     w1, #13
    str     w1, [x0, #0x24]           // IBRD
    mov     w1, #1
    str     w1, [x0, #0x28]           // FBRD
    mov     w1, #0x70
    str     w1, [x0, #0x2c]           // LCR_H
    str     wzr, [x0, #0x38]          // IMSC = 0
    mov     w1, #0x301
    str     w1, [x0, #0x30]           // CR: UART + TX + RX on

    // generic timer at 100 Hz
    mrs     x1, cntfrq_el0
    mov     x2, #100
    udiv    x1, x1, x2
    ldr     x3, =arm_step
    str     x1, [x3]
    msr     cntp_tval_el0, x1
    mov     x1, #1
    msr     cntp_ctl_el0, x1

    // fabricate the Multiboot information block (bss is zeroed)
    ldr     x0, =arm_mbi
    mov     w1, #0x49                 // flags: mem, modules, mmap
    str     w1, [x0]
    mov     w1, #640
    str     w1, [x0, #4]              // mem_lower
    ldr     w1, =RAM_MIB_KIB
    str     w1, [x0, #8]              // mem_upper
    mov     w1, #3
    str     w1, [x0, #20]             // mods_count
    ldr     x1, =arm_mods
    str     w1, [x0, #24]             // mods_addr (low 32 used)
    mov     w1, #24
    str     w1, [x0, #44]             // mmap_length
    ldr     x1, =arm_mmap
    str     w1, [x0, #48]             // mmap_addr (low 32 used)

    ldr     x0, =arm_mmap
    mov     w1, #20
    str     w1, [x0]                  // entry size
    str     xzr, [x0, #4]             // base 0 (virtual window)
    mov     x1, #0x08000000
    str     x1, [x0, #12]             // length 128 MiB
    mov     w1, #1
    str     w1, [x0, #20]             // type: available

    ldr     x0, =arm_mods
    mov     x1, #0x4000000            // module 0 VA (PA 0x44000000)
    str     w1, [x0]
    add     w1, w1, #ARM_MOD0_LEN
    str     w1, [x0, #4]
    ldr     x1, =arm_mod0_name
    str     w1, [x0, #8]
    mov     x1, #0x4800000            // module 1 VA (PA 0x44800000)
    str     w1, [x0, #16]
    add     w1, w1, #ARM_MOD1_LEN
    str     w1, [x0, #20]
    ldr     x1, =arm_mod1_name
    str     w1, [x0, #24]
    mov     x1, #0x5000000            // module 2 VA (PA 0x45000000)
    str     w1, [x0, #32]
    add     w1, w1, #ARM_MOD2_LEN
    str     w1, [x0, #36]
    ldr     x1, =arm_mod2_name
    str     w1, [x0, #40]

    // main(magic, mbi)
    ldr     w0, =0x2BADB002
    ldr     x1, =arm_mbi
    ldr     x16, =main
    blr     x16
3:  wfi
    b       3b

// ----------------------------------------------------------------
// the thirteen services (AAPCS64, same signatures as boot.s)
// ----------------------------------------------------------------

    .text

    .globl k_out8
k_out8:                               // (port, value)
    ldr     x2, =1016                 // COM1 data / divisor low
    cmp     x0, x2
    b.eq    1f
    ldr     x2, =1019                 // COM1 line control
    cmp     x0, x2
    b.eq    2f
    ret
1:  ldr     x2, =arm_lcr              // divisor write while DLAB set
    ldrb    w3, [x2]
    tbnz    w3, #7, 3f
    ldr     x2, =UART_VA              // data: PL011 transmit
    str     w1, [x2]
3:  ret
2:  ldr     x2, =arm_lcr
    strb    w1, [x2]
    ret

    .globl k_in8
k_in8:                                // (port) -> byte
    cmp     x0, #96                   // PS/2 data: pop scancode
    b.eq    1f
    cmp     x0, #100                  // PS/2 status: queue nonempty
    b.eq    2f
    ldr     x2, =1021                 // COM1 line status
    cmp     x0, x2
    b.eq    3f
    cmp     x0, #503                  // ATA status: no disk
    b.eq    4f
    mov     w0, #0
    ret
1:  ldr     x1, =arm_q_head
    ldrb    w2, [x1]
    ldr     x3, =arm_q_tail
    ldrb    w4, [x3]
    cmp     w2, w4
    b.eq    5f                        // empty: read as 0
    ldr     x5, =arm_kbdq
    ldrb    w0, [x5, x2]
    add     w2, w2, #1
    and     w2, w2, #63
    strb    w2, [x1]
    ret
5:  mov     w0, #0
    ret
2:  ldr     x1, =arm_q_head
    ldrb    w2, [x1]
    ldr     x3, =arm_q_tail
    ldrb    w4, [x3]
    cmp     w2, w4
    cset    w0, ne                    // 1 when a scancode waits
    ret
3:  ldr     x2, =UART_VA              // THR empty unless TXFF
    ldr     w3, [x2, #0x18]
    tbnz    w3, #5, 6f
    mov     w0, #96
    ret
6:  mov     w0, #0
    ret
4:  mov     w0, #0xff
    ret

    .globl k_out16
k_out16:
    ret

    .globl k_in16
k_in16:
    mov     w0, #0
    ret

    .globl k_out32
k_out32:                              // PCI address port is kept
    ldr     x2, =3320                 // as a shadow; no PCI here
    cmp     x0, x2
    b.ne    1f
    ldr     x2, =arm_pci_addr
    str     w1, [x2]
1:  ret

    .globl k_in32
k_in32:                               // PCI data reads as absent
    ldr     x2, =3324
    cmp     x0, x2
    b.ne    1f
    mov     w0, #-1
    ret
1:  mov     w0, #0
    ret

    .globl k_lidt
k_lidt:                               // the ARM vector table is
    ret                               // fixed; nothing to load

    .globl k_sti
k_sti:
    msr     daifclr, #2
    ret

    .globl k_cli
k_cli:
    msr     daifset, #2
    ret

    .globl k_hlt
k_hlt:
    wfi
    ret

    .globl k_stub_base
k_stub_base:                          // inert on ARM: the kernel
    ldr     x0, =arm_vectors          // builds its IDT entries
    ret                               // from this, unused here

    .globl k_arena_base
k_arena_base:
    ldr     x0, =k_arena
    ret

    .globl k_exec
k_exec:                               // (entry) -> module result
    mov     x16, x0
    mov     w0, wzr                   // main(0, NULL)
    mov     x1, xzr
    blr     x16
    sxtw    x0, w0
    ret

// compiler runtime helpers (the Krell backend emits plain calls
// for its memory operations on some targets)
    .globl memcpy
memcpy:
    mov     x3, x0
1:  cbz     x2, 2f
    ldrb    w4, [x1], #1
    strb    w4, [x0], #1
    sub     x2, x2, #1
    b       1b
2:  mov     x0, x3
    ret

    .globl memset
memset:
    mov     x3, x0
1:  cbz     x2, 2f
    strb    w1, [x0], #1
    sub     x2, x2, #1
    b       1b
2:  mov     x0, x3
    ret

    .globl memmove
memmove:
    cmp     x0, x1
    b.hs    memcpy
    add     x3, x0, x2
    add     x1, x1, x2
1:  cbz     x2, 2f
    ldrb    w4, [x1, #-1]!
    strb    w4, [x3, #-1]!
    sub     x2, x2, #1
    b       1b
2:  ret

// ----------------------------------------------------------------
// exception vectors
// ----------------------------------------------------------------

    .section .rodata
    .balign 2048
    .globl arm_vectors
arm_vectors:
    .rept 4                       // current EL, SP0: unused
    b       .
    .balign 128
    .endr
    b       sync_entry            // current EL, SPx: sync
    .balign 128
    b       irq_entry             // current EL, SPx: IRQ
    .balign 128
    b       .                     // FIQ
    .balign 128
    b       .                     // SError
    .balign 128
    .rept 12                      // lower EL: unused
    b       .
    .balign 128
    .endr

// ----------------------------------------------------------------
// synchronous exception entry: an emulated VGA access, or a real
// fault routed to the kernel dispatcher (vector 13)
// ----------------------------------------------------------------

    .text
sync_entry:
    sub     sp, sp, #256
    stp     x0, x1, [sp, #0]
    stp     x2, x3, [sp, #16]
    stp     x4, x5, [sp, #32]
    stp     x6, x7, [sp, #48]
    stp     x8, x9, [sp, #64]
    stp     x10, x11, [sp, #80]
    stp     x12, x13, [sp, #96]
    stp     x14, x15, [sp, #112]
    stp     x16, x17, [sp, #128]
    stp     x18, x19, [sp, #144]
    stp     x20, x21, [sp, #160]
    stp     x22, x23, [sp, #176]
    stp     x24, x25, [sp, #192]
    stp     x26, x27, [sp, #208]
    stp     x28, x29, [sp, #224]
    str     x30, [sp, #240]
    mrs     x0, esr_el1
    ubfx    x1, x0, #26, #6           // exception class
    cmp     x1, #0x25                 // data abort, same EL
    b.ne    sync_fault
    mrs     x2, far_el1
    ldr     x3, =VGA_LO
    cmp     x2, x3
    b.lo    sync_fault
    ldr     x3, =VGA_HI
    cmp     x2, x3
    b.hs    sync_fault
    mrs     x4, elr_el1
    ldr     w5, [x4]                  // the faulting instruction
    // load/store family 1: unsigned immediate offset
    and     x6, x5, #0x3F000000
    ldr     x7, =0x39000000
    cmp     x6, x7
    b.eq    sync_emulate
    // load/store family 2: register offset / unscaled / pre-post
    and     x6, x5, #0x3F000000
    ldr     x7, =0x38000000
    cmp     x6, x7
    b.ne    sync_fault
sync_emulate:
    tbz     w5, #22, 1f               // store: drop the write
    and     x6, x5, #31               // load: Rt reads as zero
    cmp     x6, #31
    b.eq    1f
    str     xzr, [sp, x6, lsl #3]
1:  add     x4, x4, #4
    msr     elr_el1, x4
    b       sync_out
sync_fault:
    mov     x0, #13
    ldr     x16, =k_dispatch
    blr     x16                       // the panic path halts
1:  b       1b
sync_out:
    ldp     x0, x1, [sp, #0]
    ldp     x2, x3, [sp, #16]
    ldp     x4, x5, [sp, #32]
    ldp     x6, x7, [sp, #48]
    ldp     x8, x9, [sp, #64]
    ldp     x10, x11, [sp, #80]
    ldp     x12, x13, [sp, #96]
    ldp     x14, x15, [sp, #112]
    ldp     x16, x17, [sp, #128]
    ldp     x18, x19, [sp, #144]
    ldp     x20, x21, [sp, #160]
    ldp     x22, x23, [sp, #176]
    ldp     x24, x25, [sp, #192]
    ldp     x26, x27, [sp, #208]
    ldp     x28, x29, [sp, #224]
    ldr     x30, [sp, #240]
    add     sp, sp, #256
    eret

// ----------------------------------------------------------------
// IRQ entry: the generic timer (PPI 29). Re-arms the timer,
// drains the UART receive FIFO into the scancode queue
// (dispatching each scancode to the kernel), then dispatches
// the tick (vector 32).
// ----------------------------------------------------------------

irq_entry:
    sub     sp, sp, #256
    stp     x0, x1, [sp, #0]
    stp     x2, x3, [sp, #16]
    stp     x4, x5, [sp, #32]
    stp     x6, x7, [sp, #48]
    stp     x8, x9, [sp, #64]
    stp     x10, x11, [sp, #80]
    stp     x12, x13, [sp, #96]
    stp     x14, x15, [sp, #112]
    stp     x16, x17, [sp, #128]
    stp     x18, x19, [sp, #144]
    stp     x20, x21, [sp, #160]
    stp     x22, x23, [sp, #176]
    stp     x24, x25, [sp, #192]
    stp     x26, x27, [sp, #208]
    stp     x28, x29, [sp, #224]
    str     x30, [sp, #240]
    ldr     x19, =GICC_VA
    ldr     w20, [x19, #0xc]          // GICC_IAR
    and     w21, w20, #0x3ff          // interrupt id
    cmp     w21, #29
    b.eq    10f
    cmp     w21, #30
    b.ne    irq_eoi                   // spurious or unexpected
10: ldr     x0, =arm_step             // re-arm the timer
    ldr     x0, [x0]
    msr     cntp_tval_el0, x0
    // drain the UART receive FIFO
1:  ldr     x0, =UART_VA
    ldr     w1, [x0, #0x18]           // FR
    tbnz    w1, #4, 4f                // RXFE: FIFO empty, done
    ldr     w1, [x0]                  // DR: the received byte
    and     w1, w1, #0x7f
    ldr     x2, =arm_scmap
    ldrb    w3, [x2, x1]              // scancode, 0 = unmapped
    cbz     w3, 1b
    ldr     x2, =arm_scshift
    ldrb    w4, [x2, x1]
    cbz     w4, 2f
    mov     w5, #0x2a                 // shift make
    bl      q_push
    mov     w5, w3
    bl      q_push
    orr     w5, w3, #0x80             // break
    bl      q_push
    mov     w5, #0xaa                 // shift break
    bl      q_push
    b       3f
2:  mov     w5, w3
    bl      q_push
    orr     w5, w3, #0x80
    bl      q_push
3:  // dispatch every queued scancode (kernel vector 33)
    ldr     x0, =arm_q_head
    ldrb    w1, [x0]
    ldr     x2, =arm_q_tail
    ldrb    w3, [x2]
    cmp     w1, w3
    b.eq    1b
    mov     x0, #33
    ldr     x16, =k_dispatch
    blr     x16
    b       3b
4:  mov     x0, #32                   // the tick
    ldr     x16, =k_dispatch
    blr     x16
irq_eoi:
    str     w20, [x19, #0x10]         // GICC_EOIR
    ldp     x0, x1, [sp, #0]
    ldp     x2, x3, [sp, #16]
    ldp     x4, x5, [sp, #32]
    ldp     x6, x7, [sp, #48]
    ldp     x8, x9, [sp, #64]
    ldp     x10, x11, [sp, #80]
    ldp     x12, x13, [sp, #96]
    ldp     x14, x15, [sp, #112]
    ldp     x16, x17, [sp, #128]
    ldp     x18, x19, [sp, #144]
    ldp     x20, x21, [sp, #160]
    ldp     x22, x23, [sp, #176]
    ldp     x24, x25, [sp, #192]
    ldp     x26, x27, [sp, #208]
    ldp     x28, x29, [sp, #224]
    ldr     x30, [sp, #240]
    add     sp, sp, #256
    eret

// q_push: append w5 to the scancode queue (clobbers x0-x3)
q_push:
    ldr     x0, =arm_q_tail
    ldrb    w1, [x0]
    ldr     x2, =arm_kbdq
    strb    w5, [x2, x1]
    add     w1, w1, #1
    and     w1, w1, #63
    strb    w1, [x0]
    ret

// ----------------------------------------------------------------
// data
// ----------------------------------------------------------------

    .section .rodata
arm_mod0_name: .asciz "modules/hello.krel"
arm_mod1_name: .asciz "modules/fib.krel"
arm_mod2_name: .asciz "modules/mem.krel"

    .balign 8
arm_scmap:
    .include "scmap.inc"
arm_scshift:
    .include "scshift.inc"

    .section .bss
    .balign 4096
arm_l1:        .skip 4096
arm_l2:        .skip 4096
k_arena:       .skip 1048576
    .balign 16
k_stack:       .skip 65536
k_stack_top:
arm_step:      .skip 8
arm_mbi:       .skip 256
arm_mmap:      .skip 24
arm_mods:      .skip 48
arm_lcr:       .skip 1
arm_pci_addr:  .skip 4
arm_kbdq:      .skip 64
arm_q_head:    .skip 1
arm_q_tail:    .skip 1
