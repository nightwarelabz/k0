# K0 - a kernel in pure Krell.
#
# make            build kernel32.elf (the bootable image)
# make run        boot it in QEMU, shell on the terminal
# make drive      boot it and run the scripted shell session
#
# The Krell toolchain (krellc) comes from a Krell checkout;
# point KRELLC at it if the default path does not match.
#
# Layout: kernel/ holds the Krell kernel sources and their
# assembler; arch/x86_64 and arch/aarch64 hold the machine
# layers; boot/ builds the self-booting disk image; tools/
# holds the image/module/include builders; tests/ holds the
# QEMU session drivers; modules/ holds the sample modules.
# Build outputs stay at the root.

KRELLC ?= $(shell test -f ~/krell/krellc && echo ~/krell/krellc || echo ~/workspace/rung/krellc)
CC     ?= cc
LD     ?= ld

all: k0.32.elf

kernel/kernel.krell: kernel/kernel_t1.krell kernel/kernel_t2.krell kernel/kernel_t3.krell kernel/kernel_t4.krell kernel/kernel_t5.krell kernel/kernel_t6.krell kernel/kernel_t7.krell kernel/kernel_t8.krell kernel/gen_kernel.py
	python3 kernel/gen_kernel.py

kernel.krel: kernel/kernel.krell
	$(KRELLC) parse kernel/kernel.krell -o kernel.krel

kernel.s: kernel.krel
	$(KRELLC) build kernel.krel --target x86_64 -o kernel.s

kernel.o: kernel.s
	$(CC) -c kernel.s -o kernel.o

boot.o: arch/x86_64/boot.s
	$(CC) -c arch/x86_64/boot.s -o boot.o

k0.elf: boot.o kernel.o arch/x86_64/kernel.ld
	$(LD) -nostdlib -T arch/x86_64/kernel.ld -o k0.elf boot.o kernel.o

# QEMU's Multiboot loader accepts ELF32 containers; the code
# inside is the 64-bit image, entered in 32-bit mode exactly
# as Multiboot specifies.
k0.32.elf: k0.elf
	objcopy -O elf32-i386 k0.elf k0.32.elf

MODULES = modules/hello.krel modules/fib.krel modules/mem.krel

modules/%.krel: modules/%.krell
	KRELL_TARGETS=$(dir $(KRELLC))targets $(KRELLC) parse $< -o $@

modules: $(MODULES)

NATMODS = modules/hello.nat modules/fib.nat modules/mem.nat

modules/%.nat: modules/%.krell tools/natlink.py arch/x86_64/nat.ld k0.elf
	KRELLC=$(KRELLC) python3 tools/natlink.py $< $@

nat: $(NATMODS)

# ---- aarch64 (QEMU virt): same kernel module, ARM machine layer

AAS   ?= $(shell which aarch64-linux-gnu-as 2>/dev/null || which aarch64-elf-as 2>/dev/null || echo aarch64-linux-gnu-as)
ALD   ?= $(shell which aarch64-linux-gnu-ld 2>/dev/null || which aarch64-elf-ld 2>/dev/null || echo aarch64-linux-gnu-ld)

kernel_arm.s: kernel.krel
	$(KRELLC) build kernel.krel --target aarch64 -o kernel_arm.s

kernel_arm.o: kernel_arm.s
	$(AAS) kernel_arm.s -o kernel_arm.o

arch/aarch64/boot_arm.inc arch/aarch64/scmap.inc arch/aarch64/scshift.inc: tools/mkarm.py $(MODULES)
	python3 tools/mkarm.py

boot_arm.o: arch/aarch64/boot_arm.s arch/aarch64/boot_arm.inc arch/aarch64/scmap.inc arch/aarch64/scshift.inc
	$(AAS) -Iarch/aarch64 arch/aarch64/boot_arm.s -o boot_arm.o

k0arm.elf: boot_arm.o kernel_arm.o arch/aarch64/kernel_arm.ld
	$(ALD) -nostdlib -T arch/aarch64/kernel_arm.ld -o k0arm.elf boot_arm.o kernel_arm.o

arm: k0arm.elf

runarm: k0arm.elf $(MODULES)
	qemu-system-aarch64 -machine virt -cpu max -m 128 \
	    -kernel k0arm.elf \
	    -device loader,file=modules/hello.krel,addr=0x44000000 \
	    -device loader,file=modules/fib.krel,addr=0x44800000 \
	    -device loader,file=modules/mem.krel,addr=0x45000000 \
	    -display none -serial stdio

run: k0.32.elf modules disk.img
	qemu-system-x86_64 -kernel k0.32.elf -initrd modules/hello.krel,modules/fib.krel,modules/mem.krel -drive file=disk.img,format=raw,if=ide -m 128 -display none -serial stdio

disk.img: tools/mkdisk.py
	python3 tools/mkdisk.py disk.img

drive: k0.32.elf
	python3 tests/drive.py

boot.img: boot/mkboot.py boot/stage1.s boot/stage2.s k0.elf $(MODULES)
	python3 boot/mkboot.py

clean:
	rm -f kernel/kernel.krell kernel.krel kernel.s kernel.o boot.o k0.elf k0.32.elf boot/kernel.bin boot/stage1.o boot/stage1.bin boot/stage2.o boot/stage2.bin boot/bootlayout.inc boot/fs.tmp boot.img $(NATMODS) kernel_arm.s kernel_arm.o boot_arm.o arch/aarch64/boot_arm.inc arch/aarch64/scmap.inc arch/aarch64/scshift.inc k0arm.elf
	rm -rf natbuild

.PHONY: all run drive clean
