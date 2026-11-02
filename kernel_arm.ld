/* K0 aarch64 link layout.
 *
 * The entry stub (.bootarm) is linked at its physical address,
 * 0x40100000, so the ELF entry point is the physical address
 * QEMU jumps to. Everything else is linked at the virtual
 * addresses the kernel uses on x86_64 (.text at 0x100000), with
 * load addresses in RAM at 0x40000000 + virtual, which is where
 * the page tables map them once the stub turns the MMU on. */
ENTRY(_arm_start)
SECTIONS {
    . = 0x40100000;
    .bootarm : { *(.bootarm) }

    . = 0x100000;
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
