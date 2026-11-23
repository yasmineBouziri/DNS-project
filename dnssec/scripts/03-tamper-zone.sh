#!/usr/bin/env bash
# Scénario d'échec : modifie un enregistrement de la zone signée SANS la re-signer.
# La RRSIG ne correspond plus aux données -> Unbound doit répondre SERVFAIL.
# Usage (PRIMARY) : sudo ./03-tamper-zone.sh break   puis   sudo ./03-tamper-zone.sh restore
set -euo pipefail
ZONE="${ZONE:-lab.test}"
SIGNED="${SIGNED:-/etc/bind/zones/db.$ZONE.signed}"
NAME="${NAME:-www}"
FAKE_IP="${FAKE_IP:-10.10.10.40}"   # IP de la machine Attacker

case "${1:-}" in
  break)
    [[ -e "$SIGNED.orig" ]] || cp -p "$SIGNED" "$SIGNED.orig"
    # Le fichier signé est normalisé par dnssec-signzone : "www.lab.test. TTL IN A IP"
    sed -i -E "s/^($NAME\.$ZONE\.[[:space:]]+[0-9]+[[:space:]]+IN[[:space:]]+A[[:space:]]+).*/\1$FAKE_IP/" "$SIGNED"
    grep -E "^$NAME\.$ZONE\..*IN[[:space:]]+A[[:space:]]" "$SIGNED"
    rndc reload "$ZONE"
    echo "Zone falsifiée ($NAME.$ZONE -> $FAKE_IP). Sur le Resolver : sudo unbound-control flush_zone $ZONE"
    echo "Note : le serial n'a pas changé, le Secondary garde la version valide ;"
    echo "pour un test déterministe, interroger un Resolver dont le stub-addr pointe sur 10.10.10.30."
    ;;
  restore)
    mv "$SIGNED.orig" "$SIGNED"
    touch "$SIGNED"   # sinon BIND voit un mtime plus ancien et ignore le reload
    rndc reload "$ZONE"
    echo "Zone restaurée. Sur le Resolver : sudo unbound-control flush_zone $ZONE"
    ;;
  *) echo "Usage : $0 break|restore" ; exit 2 ;;
esac
