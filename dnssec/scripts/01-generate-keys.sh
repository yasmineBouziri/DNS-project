#!/usr/bin/env bash
# Génère la ZSK et la KSK de lab.test (à lancer sur le PRIMARY, 10.10.10.30).
# Algorithme 13 = ECDSAP256SHA256 (recommandé, signatures courtes).
set -euo pipefail
ZONE="${ZONE:-lab.test}"
KEYDIR="${KEYDIR:-/etc/bind/keys}"
ALG="${ALG:-ECDSAP256SHA256}"

sudo mkdir -p "$KEYDIR"
cd "$KEYDIR"
if ls K"$ZONE".+*.key >/dev/null 2>&1; then
    echo "Des clés existent déjà dans $KEYDIR pour $ZONE :" ; ls K"$ZONE".+*
    echo "Supprimez-les volontairement avant d'en régénérer." ; exit 1
fi

ZSK=$(sudo dnssec-keygen -a "$ALG" -n ZONE "$ZONE")          # flags 256
KSK=$(sudo dnssec-keygen -a "$ALG" -n ZONE -f KSK "$ZONE")   # flags 257
sudo chown -R bind:bind "$KEYDIR"
sudo chmod 600 "$KEYDIR"/*.private

echo "ZSK : $KEYDIR/$ZSK"
echo "KSK : $KEYDIR/$KSK"
echo "Les fichiers .private ne doivent JAMAIS être commités."
