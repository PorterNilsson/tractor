VM_DIR=./vm
BASE_IMAGE=$(VM_DIR)/base/debian-base.qcow2
VM_DISK=$(VM_DIR)/disks/debian.qcow2
SEED_DIR := $(VM_DIR)/seed
SEED_ISO=$(SEED_DIR)/seed.iso
SSH_KEY := $(HOME)/.ssh/tractor
SSH_PUB_KEY := $(SSH_KEY).pub

$(BASE_IMAGE):
	mkdir -p $(VM_DIR)/base
	curl -L -o $(BASE_IMAGE) \
		https://cloud.debian.org/images/cloud/trixie/latest/debian-13-genericcloud-arm64.qcow2

$(VM_DISK): $(BASE_IMAGE)
	mkdir -p $(VM_DIR)/disks
	qemu-img create -f qcow2 \
		-b "$(abspath $(BASE_IMAGE))" \
		-F qcow2 \
		$(VM_DISK)

$(SSH_PUB_KEY):
	ssh-keygen -t ed25519 -f $(SSH_KEY) -N ""

$(SEED_DIR)/user-data: $(SSH_PUB_KEY)
	./vm/seed/user-data.sh

$(SEED_ISO): $(SEED_DIR)/user-data $(SEED_DIR)/meta-data
	hdiutil makehybrid \
		-o $(SEED_ISO) \
		-iso \
		-joliet \
		-default-volume-name cidata \
		$(SEED_DIR)

build:
	go build -o ./bin/tractor ./cmd/tractor

run:
	go run ./cmd/tractor

dev-up: $(VM_DISK) $(SEED_ISO)
	qemu-system-aarch64 \
		-machine virt,accel=hvf \
		-cpu host \
		-smp 4 \
		-m 4096 \
		-drive if=virtio,file=$(VM_DISK),format=qcow2 \
		-drive if=virtio,file=$(SEED_ISO),format=raw \
		-netdev user,id=net0,hostfwd=tcp::2222-:22 \
		-device virtio-net-pci,netdev=net0 \
		-nographic \
		-serial mon:stdio

dev-down:
