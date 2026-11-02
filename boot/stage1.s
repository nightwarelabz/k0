# K0 stage 1: the MBR. The BIOS loads it at 0x7C00. It loads
# stage 2 (32 sectors from LBA 1) to 0x7E00 with an int 13h
# extended read and jumps to it. Assembled as a flat binary
# linked at 0x7C00; mkboot.py pads it to 512 bytes and adds
# the 0x55AA signature.
    .code16
    .section .text
    .globl _start
_start:
    cli
    xorw %ax, %ax
    movw %ax, %ds
    movw %ax, %es
    movw %ax, %ss
    movw $0x7C00, %sp
    sti
    movw $dap, %si
    movb $0x42, %ah
    movb $0x80, %dl
    int $0x13
    jc halt
    ljmp $0x0000, $0x7E00
halt:
    hlt
    jmp halt
dap:
    .byte 16
    .byte 0
    .word 32
    .word 0x7E00
    .word 0
    .quad 1
