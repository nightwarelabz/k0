/* K0 aarch64 link layout.
 *
 * The entry stub (.bootarm) is linked at its physical address,
 * 0x40100000, so the ELF entry point is the physical address
 * QEMU jumps to. The page tables map virtual [0, 128 MiB) onto
 * RAM at 0x40000000, so the stub's bytes also sit at virtual
 * 0x100000, the first bytes of the kernel image. The kernel
 * proper (.text onward) is linked immediately after the stub
 * in virtual space, with load addresses in RAM at
 * 0x40000000 + virtual: every section's load address equals
 * its virtual address plus the RAM base, which is what the
 * mapping translates once the stub turns the MMU on. */
ENTRY(_arm_start)
SECTIONS {
    . = 0x40100000;
    .bootarm : { *(.bootarm) }

    . = 0x100000 + SIZEOF(.bootarm);
    .text : AT(LOADADDR(.bootarm) + SIZEOF(.bootarm)) {
        *(.text)
        *(.text.*)
    }
    .rodata : AT(LOADADDR(.text) + SIZEOF(.text)) {
        *(.rodata)
        *(.rodata.*)
    }
    .data : AT(LOADADDR(.rodata) + SIZEOF(.rodata)) {
        *(.data)
        *(.data.*)
    }
    .bss : {
        *(.bss)
        *(.bss.*)
        *(COMMON)
    }
}
