# K0 stage 2. Stage 1 loads it at 0x7E00. The real-mode part
# builds a Multiboot information block in low memory: the
# memory map comes from int 15h E820, memory sizes from int
# 12h and int 15h E801, and the module table describes the
# three modules the 32-bit part is about to load. It then
# enables A20, loads a flat GDT and switches to 32-bit
# protected mode. The 32-bit part reads the kernel and the
# modules off the disk with ATA PIO and enters the kernel
# exactly as a Multiboot loader would: EAX = 0x2BADB002,
# EBX = address of the information block, jump to the entry
# point. Layout constants come from bootlayout.inc, which
# mkboot.py generates from the actual file sizes.
    .include "bootlayout.inc"
    .code16
    .section .text
    .globl _start2
_start2:
    cli
    xorw %ax, %ax
    movw %ax, %ds
    movw %ax, %es
    movw %ax, %ss
    movw $0x7C00, %sp
    sti
    # ---- memory map (int 15h E820) into 0x5000 ----
    # Multiboot entry format: size u32 (=20), base u64,
    # length u64, type u32; stride 24. The E820 result
    # lands at entry+4, which is exactly that layout.
    movw $0x5000, %di
    xorl %ebx, %ebx
    xorw %bp, %bp
e820_loop:
    movw $20, (%di)
    movw $0, 2(%di)
    pushw %di
    addw $4, %di
    movl $0xE820, %eax
    movl $0x534D4150, %edx
    movl $24, %ecx
    int $0x15
    popw %di
    jc e820_done
    cmpl $0x534D4150, %eax
    jne e820_done
    addw $24, %di
    incw %bp
    cmpw $40, %bp
    jae e820_done
    testl %ebx, %ebx
    jnz e820_loop
e820_done:
    # ---- memory sizes ----
    int $0x12
    movzwl %ax, %eax
    movl %eax, lowkb
    movw $0xE801, %ax
    int $0x15
    movzwl %ax, %ecx
    movzwl %bx, %eax
    shll $6, %eax
    addl %ecx, %eax
    movl %eax, upkb
    # ---- the Multiboot information block at 0x6000 ----
    movw $0x6000, %di
    xorw %ax, %ax
    movw $128, %cx
    rep stosw
    movl $0x49, 0x6000
    movl lowkb, %eax
    movl %eax, 0x6004
    movl upkb, %eax
    movl %eax, 0x6008
    movl $3, 0x6014
    movl $0x6100, 0x6018
    movzwl %bp, %eax
    movl $24, %ecx
    mull %ecx
    movl %eax, 0x602C
    movl $0x5000, 0x6030
    # ---- module table at 0x6100, name strings at 0x6200 ----
    movl $MOD0_ADDR, 0x6100
    movl $(MOD0_ADDR + MOD0_BYTES), 0x6104
    movl $0x6200, 0x6108
    movl $0, 0x610C
    movl $MOD1_ADDR, 0x6110
    movl $(MOD1_ADDR + MOD1_BYTES), 0x6114
    movl $0x6220, 0x6118
    movl $0, 0x611C
    movl $MOD2_ADDR, 0x6120
    movl $(MOD2_ADDR + MOD2_BYTES), 0x6124
    movl $0x6240, 0x6128
    movl $0, 0x612C
    movw $name0, %si
    movw $0x6200, %di
    call copyz
    movw $name1, %si
    movw $0x6220, %di
    call copyz
    movw $name2, %si
    movw $0x6240, %di
    call copyz
    # ---- A20, GDT, protected mode ----
    inb $0x92, %al
    orb $2, %al
    outb %al, $0x92
    cli
    lgdt gdt_desc
    movl %cr0, %eax
    orl $1, %eax
    movl %eax, %cr0
    ljmp $0x08, $pm32
copyz:
    lodsb
    stosb
    testb %al, %al
    jnz copyz
    ret
lowkb:
    .long 0
upkb:
    .long 0
name0:
    .asciz "modules/hello.krel"
name1:
    .asciz "modules/fib.krel"
name2:
    .asciz "modules/mem.krel"
gdt:
    .quad 0
    .quad 0x00CF9A000000FFFF
    .quad 0x00CF92000000FFFF
gdt_desc:
    .word gdt_desc - gdt - 1
    .long gdt
    .code32
pm32:
    movw $0x10, %ax
    movw %ax, %ds
    movw %ax, %es
    movw %ax, %ss
    movw %ax, %fs
    movw %ax, %gs
    movl $0x90000, %esp
    movl $KERN_LBA, %eax
    movl $KERN_SECS, %ecx
    movl $0x100000, %edi
    call ata_read
    movl $MOD0_LBA, %eax
    movl $MOD0_SECS, %ecx
    movl $MOD0_ADDR, %edi
    call ata_read
    movl $MOD1_LBA, %eax
    movl $MOD1_SECS, %ecx
    movl $MOD1_ADDR, %edi
    call ata_read
    movl $MOD2_LBA, %eax
    movl $MOD2_SECS, %ecx
    movl $MOD2_ADDR, %edi
    call ata_read
    movl $0x2BADB002, %eax
    movl $0x6000, %ebx
    movl $KERN_ENTRY, %ecx
    jmp *%ecx
# ata_read: EAX = LBA, ECX = sector count, EDI = destination.
# One sector at a time through the primary-bus PIO ports.
ata_read:
    pushl %ebx
    pushl %esi
    movl %eax, %ebx
    movl %ecx, %esi
ata_sector:
    movl $0x1F7, %edx
ata_bsy:
    inb %dx, %al
    testb $0x80, %al
    jnz ata_bsy
    movl %ebx, %eax
    shrl $24, %eax
    andl $0x0F, %eax
    orl $0xE0, %eax
    movl $0x1F6, %edx
    outb %al, %dx
    movl $1, %eax
    movl $0x1F2, %edx
    outb %al, %dx
    movl %ebx, %eax
    movl $0x1F3, %edx
    outb %al, %dx
    movl %ebx, %eax
    shrl $8, %eax
    movl $0x1F4, %edx
    outb %al, %dx
    movl %ebx, %eax
    shrl $16, %eax
    movl $0x1F5, %edx
    outb %al, %dx
    movl $0x20, %eax
    movl $0x1F7, %edx
    outb %al, %dx
    movl $0x1F7, %edx
ata_drq:
    inb %dx, %al
    testb $0x80, %al
    jnz ata_drq
    testb $0x08, %al
    jz ata_drq
    movl $0x1F0, %edx
    movl $256, %ecx
    rep insw
    incl %ebx
    decl %esi
    jnz ata_sector
    popl %esi
    popl %ebx
    ret
