# K0 - a kernel in pure Krell.
#
# make            build kernel32.elf (the bootable image)
# make run        boot it in QEMU, shell on the terminal
# make drive      boot it and run the scripted shell session
#
# The Krell toolchain (krellc) comes from a Krell checkout;
# point KRELLC at it if the default path does not match.

KRELLC ?= ~/workspace/rung/krellc
CC     ?= cc
LD     ?= ld

all: k0.32.elf

kernel.krell: kernel_t1.krell kernel_t2.krell gen_kernel.py
	python3 gen_kernel.py

kernel.krel: kernel.krell
	$(KRELLC) parse kernel.krell -o kernel.krel

kernel.s: kernel.krel
	$(KRELLC) build kernel.krel --target x86_64 -o kernel.s

kernel.o: kernel.s
	$(CC) -c kernel.s -o kernel.o

boot.o: boot.s
	$(CC) -c boot.s -o boot.o

k0.elf: boot.o kernel.o kernel.ld
	$(LD) -nostdlib -T kernel.ld -o k0.elf boot.o kernel.o

# QEMU's Multiboot loader accepts ELF32 containers; the code
# inside is the 64-bit image, entered in 32-bit mode exactly
# as Multiboot specifies.
k0.32.elf: k0.elf
	objcopy -O elf32-i386 k0.elf k0.32.elf

run: k0.32.elf
	qemu-system-x86_64 -kernel k0.32.elf -m 128 -display none -serial stdio

drive: k0.32.elf
	python3 drive.py

clean:
	rm -f kernel.krell kernel.krel kernel.s kernel.o boot.o k0.elf k0.32.elf

.PHONY: all run drive clean
