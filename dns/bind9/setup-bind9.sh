#!/usr/bin/env bash
set -e

ROLE="$1" # "primary" or "secondary"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

sudo apt update
sudo apt install -y bind9 bind9utils dnsutils

if [ "$ROLE" = "primary" ]; then
  sudo mkdir -p /etc/bind/zones
  sudo cp "$SCRIPT_DIR/primary/named.conf.local" /etc/bind/named.conf.local
  sudo cp "$SCRIPT_DIR/primary/db.lab.test" /etc/bind/zones/db.lab.test
  sudo named-checkzone lab.test /etc/bind/zones/db.lab.test
elif [ "$ROLE" = "secondary" ]; then
  sudo cp "$SCRIPT_DIR/secondary/named.conf.local" /etc/bind/named.conf.local
else
  echo "Usage: $0 [primary|secondary]"
  exit 1
fi

sudo named-checkconf
sudo systemctl enable named
sudo systemctl restart named
