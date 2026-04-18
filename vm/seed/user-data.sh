#!/usr/bin/env bash
set -euo pipefail

SSH_KEY="$HOME/.ssh/tractor.pub"
SEED_DIR="./vm/seed"

cat > "$SEED_DIR/user-data" <<EOF
#cloud-config

users:
  - name: tractor
    groups: [sudo]
    shell: /bin/bash
    sudo: ALL=(ALL) NOPASSWD:ALL
    lock_passwd: true
    ssh_authorized_keys:
      - $(cat "$SSH_KEY")

ssh_pwauth: false
disable_root: true

package_update: true
package_upgrade: true

runcmd:
  - apt update
  - apt install -y ca-certificates curl
  - install -m 0755 -d /etc/apt/keyrings
  - curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
  - chmod a+r /etc/apt/keyrings/docker.asc
  - apt update
  - apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  - cd /tmp
  - wget -q https://go.dev/dl/go1.26.2.linux-amd64.tar.gz
  - tar -C /usr/local -xzf go1.26.2.linux-amd64.tar.gz
  - echo 'export PATH=\$PATH:/usr/local/go/bin' >> /etc/profile
  - rm -f /tmp/go1.26.2.linux-amd64.tar.gz
EOF