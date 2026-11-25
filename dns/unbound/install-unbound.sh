#!/bin/bash
set -e

echo "[Unbound] Installation..."

apt-get update
apt-get install -y unbound dnsutils

echo "[Unbound] Installation de la configuration..."

install -m 644 /vagrant/dns/unbound/lab.conf \
    /etc/unbound/unbound.conf.d/lab.conf

echo "[Unbound] Vérification de la configuration..."

unbound-checkconf

echo "[Unbound] Activation et redémarrage..."

systemctl enable unbound
systemctl restart unbound

echo "[Unbound] Installation terminée."
