#!/usr/bin/env bash
# Tests every network path in the lab.
# Usage (from the repo folder):  bash scripts/test-network.sh

cd "$(dirname "$0")/.." || exit 1

pass=0
fail=0

# check <from-vm> <to-ip> <expected-ttl> <description>
check() {
  from="$1"; ip="$2"; ttl="$3"; label="$4"
  out=$(vagrant ssh "$from" -c "ping -c 2 -W 2 $ip" 2>/dev/null | tr -d '\r')
  if echo "$out" | grep -q "ttl=$ttl " && echo "$out" | grep -q " 0% packet loss"; then
    echo "PASS  $label"
    pass=$((pass+1))
  else
    echo "FAIL  $label   ($from -> $ip, expected ttl=$ttl)"
    fail=$((fail+1))
  fi
}

echo "== Same zone: packet goes direct, TTL stays 64 =="
check client      10.10.10.1  64 "client -> router (zone-clients)"
check client      10.10.10.20 64 "client -> resolver (zone-clients)"
check primary     10.10.20.1  64 "primary -> router (zone-dns)"
check secondary   10.10.20.30 64 "secondary -> primary (zone-dns)"
check supervision 10.10.30.1  64 "supervision -> router (zone-supervision)"

echo "== Across zones: packet crosses the router, TTL drops to 63 =="
check client      10.10.20.30 63 "client -> primary"
check client      10.10.30.50 63 "client -> supervision"
check resolver    10.10.20.31 63 "resolver -> secondary"
check primary     10.10.10.20 63 "primary -> resolver"
check supervision 10.10.20.30 63 "supervision -> primary"
check supervision 10.10.10.10 63 "supervision -> client"

echo
echo "Result: $pass passed, $fail failed"
[ "$fail" -eq 0 ]