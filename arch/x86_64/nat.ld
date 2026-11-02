/* Link script for native K0 modules (natlink.py). The image
   is loaded at NAT_BASE by the kernel's nrun command and its
   main is called as native code. Host service names are
   bound to kernel addresses with --defsym at link time. */
ENTRY(main)

SECTIONS
{
    . = 0x2000000;

    .text : { *(.text) }
    .rodata : { *(.rodata) }
    .data : { *(.data) }
    .bss : { *(.bss) *(COMMON) }

    _mem_end = .;
}
