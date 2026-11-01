# boot.s - the machine layer for K0, a kernel written in Krell.
#
# This file is deliberately tiny. It is the power button and
# the interrupt trampoline, nothing more: a Multiboot header,
# the 32-to-64 bit transition, and eight one-or-two-instruction
# services that the Krell kernel calls as externs. Every line
# of kernel logic - console, serial, memory, interrupt
# dispatch, drivers, scheduler, shell - is Krell.
#
# Machine services offered to Krell:
#   k_out8(port, val)      byte port write
#   k_in8(port) -> val     byte port read
#   k_lidt(ptr)            load the interrupt table register
#   k_sti() / k_cli()      interrupt enable / disable
#   k_hlt()                halt until the next interrupt
#   k_stub_base() -> i64   address of the interrupt stub table
#   k_arena_base() -> i64  address of the 1 MiB kernel arena

.intel_syntax noprefix

# ---- Multiboot 1 header -------------------------------------
.section .multiboot, "a"
.align 4
.long 0x1BADB002
.long 0x00000003
.long -(0x1BADB002 + 3)

# ---- 64-bit GDT ----------------------------------------------
.section .rodata
.align 16
gdt64:
    .quad 0
    .quad 0x00209A0000000000
    .quad 0x0000920000000000
gdt64_ptr:
    .word 23
    .quad gdt64

# ---- boot state -----------------------------------------------
.section .bss
.align 16
stack_bottom:
    .skip 65536
stack_top:
.align 4096
pml4:
    .skip 4096
pdpt:
    .skip 4096
pd_tables:
    .skip 4096 * 4
k_arena:
    .skip 1048576

# ---- 32-bit entry ----------------------------------------------
.section .text
.global _start
.code32
_start:
    cli
    mov esp, offset stack_top
    # Keep the Multiboot handshake in edi/esi: they become the
    # SysV arguments of the Krell entry, main(magic, mbi).
    # The trampoline below uses only eax, ecx, edx, ebp.
    mov edi, eax
    mov esi, ebx

    # Zero the page tables (6 pages).
    mov eax, offset pml4
    mov ecx, 6144
    xor edx, edx
zero_tables:
    mov [eax], edx
    add eax, 4
    dec ecx
    jnz zero_tables

    # Identity map the first 4 GiB with 2 MiB pages.
    mov eax, offset pdpt
    or eax, 0x3
    mov [pml4], eax
    mov ecx, 0
pdpt_loop:
    mov eax, offset pd_tables
    mov edx, ecx
    shl edx, 12
    add eax, edx
    or eax, 0x3
    mov edx, offset pdpt
    mov [edx + ecx * 8], eax
    inc ecx
    cmp ecx, 4
    jne pdpt_loop
    mov ebp, 0
pd_loop:
    mov ecx, 0
pd_inner:
    mov eax, ebp
    shl eax, 21
    mov edx, ecx
    shl edx, 21
    add eax, edx
    or eax, 0x83
    mov edx, ebp
    shl edx, 12
    add edx, offset pd_tables
    mov [edx + ecx * 8], eax
    inc ecx
    cmp ecx, 512
    jne pd_inner
    inc ebp
    cmp ebp, 4
    jne pd_loop

    # Enter long mode: PAE, cr3, EFER.LME, then paging.
    mov eax, cr4
    or eax, 0x20
    mov cr4, eax
    mov eax, offset pml4
    mov cr3, eax
    mov ecx, 0xC0000080
    rdmsr
    or eax, 0x100
    wrmsr
    mov eax, cr0
    or eax, 0x80000001
    mov cr0, eax
    lgdt [gdt64_ptr]
    push 0x08
    push offset code64
    retf

.code64
code64:
    mov ax, 0x10
    mov ds, ax
    mov es, ax
    mov ss, ax
    mov fs, ax
    mov gs, ax
    mov rsp, offset stack_top
    call main
hang:
    cli
    hlt
    jmp hang

# ---- machine services -----------------------------------------
.global k_out8
k_out8:
    mov edx, edi
    mov eax, esi
    out dx, al
    ret

.global k_in8
k_in8:
    mov edx, edi
    xor eax, eax
    in al, dx
    ret

.global k_lidt
k_lidt:
    lidt [rdi]
    ret

.global k_sti
k_sti:
    sti
    ret

.global k_cli
k_cli:
    cli
    ret

.global k_hlt
k_hlt:
    hlt
    ret

.global k_stub_base
k_stub_base:
    mov rax, offset k_intr_stubs
    ret

.global k_arena_base
k_arena_base:
    mov rax, offset k_arena
    ret

# ---- interrupt stubs --------------------------------------------
# Fixed 16-byte stubs, one per vector 0..47, then a catch-all at
# slot 48. Error-code vectors (8, 10-14, 17) get no dummy push.
.altmacro
.macro STUB vec, haserr
    .balign 16
    .if \haserr == 0
    push 0
    .endif
    push \vec
    jmp k_intr_common
.endm

.balign 16
.global k_intr_stubs
k_intr_stubs:
.set v, 0
.rept 48
    .if v == 8 || v == 10 || v == 11 || v == 12 || v == 13 || v == 14 || v == 17
        STUB %v, 1
    .else
        STUB %v, 0
    .endif
    .set v, v + 1
.endr
    # slot 48: the catch-all for vectors 48..255
    .balign 16
    push 0
    push 255
    jmp k_intr_common

k_intr_common:
    push rax
    push rcx
    push rdx
    push rbx
    push rbp
    push rsi
    push rdi
    push r8
    push r9
    push r10
    push r11
    push r12
    push r13
    push r14
    push r15
    mov rdi, [rsp + 120]
    call k_dispatch
    pop r15
    pop r14
    pop r13
    pop r12
    pop r11
    pop r10
    pop r9
    pop r8
    pop rdi
    pop rsi
    pop rbp
    pop rbx
    pop rdx
    pop rcx
    pop rax
    add rsp, 16
    iretq

.section .note.GNU-stack, "", @progbits
