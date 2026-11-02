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

kernel.krell: kernel_t1.krell kernel_t2.krell kernel_t3.krell kernel_t4.krell kernel_t5.krell kernel_t6.krell kernel_t7.krell kernel_t8.krell gen_kernel.py
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

MODULES = modules/hello.krel modules/fib.krel modules/mem.krel

modules/%.krel: modules/%.krell
	KRELL_TARGETS=$(dir $(KRELLC))targets $(KRELLC) parse $< -o $@

modules: $(MODULES)

NATMODS = modules/hello.nat modules/fib.nat modules/mem.nat

modules/%.nat: modules/%.krell natlink.py nat.ld k0.elf
	python3 natlink.py $< $@

nat: $(NATMODS)

# ---- aarch64 (QEMU virt): same kernel module, ARM machine layer

AAS   = aarch64-linux-gnu-as
ALD   = aarch64-linux-gnu-ld

kernel_arm.s: kernel.krel
	$(KRELLC) build kernel.krel --target aarch64 -o kernel_arm.s

kernel_arm.o: kernel_arm.s
	$(AAS) kernel_arm.s -o kernel_arm.o

boot_arm.inc scmap.inc scshift.inc: mkarm.py $(MODULES)
	python3 mkarm.py

boot_arm.o: boot_arm.s boot_arm.inc scmap.inc scshift.inc
	$(AAS) boot_arm.s -o boot_arm.o

k0arm.elf: boot_arm.o kernel_arm.o kernel_arm.ld
	$(ALD) -nostdlib -T kernel_arm.ld -o k0arm.elf boot_arm.o kernel_arm.o

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

disk.img: mkdisk.py
	python3 mkdisk.py disk.img

drive: k0.32.elf
	python3 drive.py

boot.img: mkboot.py stage1.s stage2.s k0.elf $(MODULES)
	python3 mkboot.py

clean:
	rm -f kernel.krell kernel.krel kernel.s kernel.o boot.o k0.elf k0.32.elf kernel.bin stage1.o stage1.bin stage2.o stage2.bin bootlayout.inc fs.tmp boot.img $(NATMODS) kernel_arm.s kernel_arm.o boot_arm.o boot_arm.inc scmap.inc scshift.inc k0arm.elf
	rm -rf natbuild

.PHONY: all run drive clean
