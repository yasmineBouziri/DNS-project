#!/usr/bin/env bash
# Signe la zone lab.test et produit l'ancre de confiance pour Unbound.
# Usage : sudo ./02-sign-zone.sh [/etc/bind/zones/db.lab.test]
set -euo pipefail
ZONE="${ZONE:-lab.test}"
KEYDIR="${KEYDIR:-/etc/bind/keys}"
ZONEFILE="${1:-/etc/bind/zones/db.$ZONE}"
ZONEDIR="$(dirname "$ZONEFILE")"
VALIDITY="${VALIDITY:-+2592000}"   # signatures valables 30 jours

named-checkzone "$ZONE" "$ZONEFILE"

# -S : smart signing (ajoute automatiquement les DNSKEY trouvées dans -K)
# -N INCREMENT : incrémente le serial pour que le Secondary se mette à jour
dnssec-signzone -S -K "$KEYDIR" -o "$ZONE" -N INCREMENT -e "$VALIDITY" \
    -d "$ZONEDIR" -f "$ZONEFILE.signed" "$ZONEFILE"

# Vérification indépendante de toute la chaîne de signatures
dnssec-verify -o "$ZONE" "$ZONEFILE.signed"

# Ancre de confiance = enregistrement DS de la KSK (fichier dsset-lab.test.)
cp "$ZONEDIR/dsset-$ZONE." "$ZONEDIR/$ZONE.ds"
chown bind:bind "$ZONEFILE.signed"
echo
echo "Zone signée : $ZONEFILE.signed"
echo "Ancre de confiance (à copier sur le Resolver dans /etc/unbound/$ZONE.ds) :"
cat "$ZONEDIR/$ZONE.ds"
echo
echo "Puis : sudo named-checkconf && sudo rndc reload $ZONE"
