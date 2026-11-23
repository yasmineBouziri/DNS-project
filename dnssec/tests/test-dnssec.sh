#!/usr/bin/env bash
# Tests de validation DNSSEC, à lancer depuis le CLIENT (10.10.10.10).
#   ./test-dnssec.sh valid    -> attend NOERROR + flag AD + RRSIG
#   ./test-dnssec.sh invalid  -> attend SERVFAIL (après 03-tamper-zone.sh break)
set -uo pipefail
RESOLVER="${RESOLVER:-10.10.10.20}"
PRIMARY="${PRIMARY:-10.10.10.30}"
PRIMARY_PORT="${PRIMARY_PORT:-53}"
NAME="${NAME:-www.lab.test}"
mode="${1:-valid}"
fail=0
check() { if eval "$2"; then echo "  [OK]    $1"; else echo "  [ECHEC] $1"; fail=1; fi; }

out=$(dig @"$RESOLVER" "$NAME" A +dnssec +multiline)
status=$(grep -oP 'status: \K[A-Z]+' <<<"$out")
echo "== $mode : $NAME via $RESOLVER (status=$status)"

if [[ $mode == valid ]]; then
    check "status NOERROR"              '[[ $status == NOERROR ]]'
    check "flag AD (donnée authentifiée)" 'grep -qE "flags:[^;]* ad" <<<"$out"'
    check "RRSIG présente"              'grep -q RRSIG <<<"$out"'
    check "DNSKEY publiée par le Primary" 'dig @"$PRIMARY" -p "$PRIMARY_PORT" lab.test DNSKEY +short | grep -q "^257 "'
elif [[ $mode == invalid ]]; then
    check "status SERVFAIL (réponse rejetée)" '[[ $status == SERVFAIL ]]'
    cd_out=$(dig @"$RESOLVER" "$NAME" A +cd +short)
    check "avec +cd (sans validation) la fausse IP apparaît" '[[ -n $cd_out ]]'
    echo "  Donnée falsifiée vue avec +cd : $cd_out"
    echo "  Raison côté Resolver : sudo journalctl -u unbound | grep -i 'validation failure'"
else
    echo "Usage : $0 valid|invalid"; exit 2
fi
exit $fail
