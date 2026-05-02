VM_CLOUD_IMAGE = vm/debian.qcow2
VM_COPY_ON_WRITE = vm/debian-cow.qcow2
CLOUD_INIT_META_DATA = vm/meta-data
CLOUD_INIT_USER_DATA = vm/user-data
SSH_KEY = ~/.ssh/tractor

build:
	go build -o bin/tractor cmd/tractor

run:
	go run cmd/tractor

clean:
	rm -f $(VM_COPY_ON_WRITE)
	rm -f $(CLOUD_INIT_META_DATA)
	rm -f $(CLOUD_INIT_USER_DATA)
	rm -f $(SSH_KEY).pub
	rm -f $(SSH_KEY)

dev-up: $(VM_COPY_ON_WRITE) $(CLOUD_INIT_META_DATA)
	qemu-system-aarch64 \
		-machine virt,accel=hvf \
		-cpu host \
		-smp 4 \
		-m 4096 \
		-bios /opt/homebrew/share/qemu/edk2-aarch64-code.fd \
		-drive if=virtio,file=$(VM_COPY_ON_WRITE),format=qcow2 \
		-netdev user,id=net0,hostfwd=tcp::2222-:22 \
		-device virtio-net-pci,netdev=net0 \
		-nographic \
		-serial stdio \
		-monitor none \
		-smbios type=1,serial=ds='nocloud;s=http://10.0.2.2:8000/'

dev-down:

$(VM_CLOUD_IMAGE):
	curl -L -o $(VM_CLOUD_IMAGE) https://cloud.debian.org/images/cloud/trixie/latest/debian-13-genericcloud-arm64.qcow2

$(VM_COPY_ON_WRITE): $(VM_CLOUD_IMAGE)
	qemu-img create -f qcow2 \
		-b '$(abspath $(VM_CLOUD_IMAGE))' \
		-F qcow2 \
		'$(abspath $(VM_COPY_ON_WRITE))'

$(CLOUD_INIT_META_DATA): $(CLOUD_INIT_USER_DATA)
	echo "instance-id: tractor-$(shell date +%s)" > $(CLOUD_INIT_META_DATA)
	echo "local-hostname: tractor" >> $(CLOUD_INIT_META_DATA)
	python3 vm/imds_server.py &

$(SSH_KEY).pub:
	ssh-keygen -t ed25519 -f $(SSH_KEY) -N ""

$(CLOUD_INIT_USER_DATA): $(SSH_KEY).pub
	@PUB_KEY=$$(cat $(SSH_KEY).pub); \
	printf "%s\n" \
"#cloud-config" \
"" \
"# ===== Users =====" \
"users:" \
"  - name: tractor" \
"    groups: [sudo]" \
"    shell: /bin/bash" \
"    sudo: ALL=(ALL) NOPASSWD:ALL" \
"    lock_passwd: true" \
"    ssh_authorized_keys:" \
"      - $$PUB_KEY" \
"" \
"# ===== SSH config =====" \
"ssh_pwauth: false" \
"disable_root: true" \
"" \
"# ===== System updates =====" \
"package_update: true" \
"package_upgrade: true" \
"" \
"# ===== Provisioning =====" \
"runcmd:" \
"  - apt update" \
"  - apt install -y ca-certificates curl" \
> $(CLOUD_INIT_USER_DATA)