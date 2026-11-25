#!/bin/bash
R=$HOME/DNS-project/dot-doh-certificats
CA=$R/pki/ca.crt
H=dns.lab.local
OUT=$R/mesures/cpu.txt
N=300

PID=$(pidof unbound)
if [ -z "$PID" ]; then echo "Unbound n'est pas lance"; exit 1; fi

# Temps CPU total d'Unbound en ticks (1 tick = 10 ms)
cpu() { awk '{print $14+$15}' /proc/$PID/stat; }

# Rechauffer le cache pour mesurer le cout du protocole seul
kdig @127.0.0.1 example.com >/dev/null 2>&1

echo "mode,ticks_cpu_pour_$N_requetes" > $OUT

A=$(cpu)
for i in $(seq $N); do kdig @127.0.0.1 example.com >/dev/null 2>&1; done
B=$(cpu)
echo "classique,$((B-A))" | tee -a $OUT

A=$(cpu)
for i in $(seq $N); do kdig @127.0.0.1 +tls +tls-ca=$CA +tls-hostname=$H example.com >/dev/null 2>&1; done
B=$(cpu)
echo "DoT,$((B-A))" | tee -a $OUT

A=$(cpu)
for i in $(seq $N); do kdig @127.0.0.1 +https=/dns-query +tls-ca=$CA +tls-hostname=$H example.com >/dev/null 2>&1; done
B=$(cpu)
echo "DoH,$((B-A))" | tee -a $OUT
