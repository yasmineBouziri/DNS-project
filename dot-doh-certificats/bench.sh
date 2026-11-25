#!/bin/bash
SRV=127.0.0.1
CA=$HOME/DNS-project/dot-doh-certificats/pki/ca.crt
H=dns.lab.local
N=30
OUT=$HOME/DNS-project/dot-doh-certificats/mesures/temps.csv

mesure() {   # $1 = options kdig
  for i in $(seq $N); do
    kdig @$SRV $1 example.com 2>/dev/null | grep -oP ' in \K[0-9.]+(?= ms)'
  done | awk '{s+=$1} END {printf "%.2f", s/NR}'
}

# Réchauffer le cache d'Unbound pour mesurer le coût du protocole seul
kdig @$SRV example.com >/dev/null 2>&1

echo "mode,temps_moyen_ms" | tee $OUT
echo "classique,$(mesure '')" | tee -a $OUT
echo "DoT,$(mesure "+tls +tls-ca=$CA +tls-hostname=$H")" | tee -a $OUT
echo "DoH,$(mesure "+https=/dns-query +tls-ca=$CA +tls-hostname=$H")" | tee -a $OUT

