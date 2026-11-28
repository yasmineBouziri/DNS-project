#!/usr/bin/env bash
# bench.sh - temps de résolution : DNS classique vs DoT vs DoH
# Usage : ./bench.sh [nom] [nb_requetes]     ex : ./bench.sh example.com 50
set -u
DIR="$(cd "$(dirname "$0")" && pwd)"
SRV="${SRV:-127.0.0.1}"
TLS_NAME="${TLS_NAME:-resolver.lab.test}"
NAME="${1:-example.com}"
N="${2:-50}"
CA="$DIR/pki/ca.crt"
OUT="$DIR/mesures"
CSV="$OUT/temps.csv"
RES="$OUT/resume.md"

command -v kdig >/dev/null || { echo "kdig manquant : sudo apt install knot-dnsutils"; exit 1; }
[ -r "$CA" ] || { echo "CA introuvable : $CA"; exit 1; }
mkdir -p "$OUT"

q_classique() { kdig @"$SRV" +time=5 +retry=0 "$NAME" >/dev/null 2>&1; }
q_dot()       { kdig @"$SRV" +tls +tls-ca="$CA" +tls-hostname="$TLS_NAME" +time=5 +retry=0 "$NAME" >/dev/null 2>&1; }
q_doh()       { kdig @"$SRV" +https=/dns-query +tls-ca="$CA" +tls-hostname="$TLS_NAME" +time=5 +retry=0 "$NAME" >/dev/null 2>&1; }

echo "protocole,essai,ms" > "$CSV"

for p in classique dot doh; do
  # requête de chauffe : remplit le cache, vérifie que le protocole répond
  if ! q_$p; then
    echo "[!] $p : pas de réponse, protocole ignoré"
    continue
  fi
  echo "[*] $p : $N requêtes..."
  for i in $(seq 1 "$N"); do
    t0=${EPOCHREALTIME/[.,]/}
    if q_$p; then
      t1=${EPOCHREALTIME/[.,]/}
      echo "$p,$i,$(awk -v a="$t0" -v b="$t1" 'BEGIN{printf "%.2f",(b-a)/1000}')" >> "$CSV"
    fi
  done
done

{
  echo "Résolution de \`$NAME\` via $SRV ($N requêtes par protocole, réponse en cache)."
  echo
  echo "| Protocole | Réussies | Min (ms) | Moyenne (ms) | Médiane (ms) | Max (ms) |"
  echo "|---|---|---|---|---|---|"
  for p in classique dot doh; do
    grep "^$p," "$CSV" | sort -t, -k3 -n | awk -F, -v p="$p" '
      {v[NR]=$3; s+=$3}
      END{ if(NR){ m=(NR%2)?v[(NR+1)/2]:(v[NR/2]+v[NR/2+1])/2;
           printf "| %s | %d | %.2f | %.2f | %.2f | %.2f |\n", p, NR, v[1], s/NR, m, v[NR] } }'
  done
} | tee "$RES"
