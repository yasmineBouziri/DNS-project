#!/usr/bin/env bash
# cpu.sh - temps CPU consommé par Unbound pour N requêtes, par protocole
# Usage : ./cpu.sh [nom] [nb_requetes]       ex : ./cpu.sh example.com 200
set -u
DIR="$(cd "$(dirname "$0")" && pwd)"
SRV="${SRV:-127.0.0.1}"
TLS_NAME="${TLS_NAME:-resolver.lab.test}"
NAME="${1:-example.com}"
N="${2:-200}"
CA="$DIR/pki/ca.crt"
OUT="$DIR/mesures"
TXT="$OUT/cpu.txt"
CSV="$OUT/cpu_ms.csv"

command -v kdig >/dev/null || { echo "kdig manquant : sudo apt install knot-dnsutils"; exit 1; }
[ -r "$CA" ] || { echo "CA introuvable : $CA"; exit 1; }
PID=$(systemctl show -p MainPID --value unbound)
[ "${PID:-0}" -gt 0 ] || { echo "Unbound ne tourne pas"; exit 1; }
TICK=$(getconf CLK_TCK)
mkdir -p "$OUT"

# temps CPU (utime + stime) du processus Unbound, en ms
cpu_ms() { awk -v t="$TICK" '{printf "%d", ($14+$15)*1000/t}' /proc/"$PID"/stat; }

q_classique() { kdig @"$SRV" +time=5 +retry=0 "$NAME" >/dev/null 2>&1; }
q_dot()       { kdig @"$SRV" +tls +tls-ca="$CA" +tls-hostname="$TLS_NAME" +time=5 +retry=0 "$NAME" >/dev/null 2>&1; }
q_doh()       { kdig @"$SRV" +https=/dns-query +tls-ca="$CA" +tls-hostname="$TLS_NAME" +time=5 +retry=0 "$NAME" >/dev/null 2>&1; }

echo "protocole,requetes,cpu_ms_total,cpu_ms_par_requete" > "$CSV"
{
  echo "CPU d'Unbound (PID $PID) pour $N requêtes de $NAME, via $SRV"
  echo "Résolution du compteur : $((1000/TICK)) ms (d'où un N assez grand)"
  echo
} > "$TXT"

for p in classique dot doh; do
  q_$p || { echo "[!] $p : pas de réponse, ignoré"; continue; }   # chauffe + test
  a=$(cpu_ms)
  for i in $(seq 1 "$N"); do q_$p; done
  b=$(cpu_ms)
  d=$((b-a))
  per=$(awk -v d="$d" -v n="$N" 'BEGIN{printf "%.3f", d/n}')
  echo "$p,$N,$d,$per" >> "$CSV"
  printf "%-10s %6d ms CPU au total, %s ms par requête\n" "$p" "$d" "$per" | tee -a "$TXT"
done
