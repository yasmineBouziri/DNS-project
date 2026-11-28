
#!/usr/bin/env bash
# Tests BIND9 installation, configuration, DNS resolution and replication.
# Usage: bash scripts/test-bind9.sh

cd "$(dirname "$0")/.." || exit 1

pass=0
fail=0

# check <vm> <command> <expected-output> <description>
check() {
  vm="$1"
  command="$2"
  expected="$3"
  label="$4"

  out=$(vagrant ssh "$vm" -c "$command" 2>/dev/null | tr -d '\r')

  if echo "$out" | grep -Fq "$expected"; then
    echo "PASS  $label"
    pass=$((pass+1))
  else
    echo "FAIL  $label"
    echo "      Expected: $expected"
    echo "      Received: $out"
    fail=$((fail+1))
  fi
}

echo "== BIND9 services =="

check primary "systemctl is-active named" \
  "active" "Primary BIND9 service"

check secondary "systemctl is-active named" \
  "active" "Secondary BIND9 service"

echo "== DNS configuration =="

check primary "sudo named-checkconf && echo CONFIG_OK" \
  "CONFIG_OK" "Primary configuration"

check primary "sudo named-checkzone lab.test /etc/bind/zones/db.lab.test" \
  "OK" "Primary zone configuration"

echo "== DNS resolution =="

check primary "dig @127.0.0.1 www.lab.test A +short" \
  "10.10.20.30" "Primary resolves www.lab.test"

check secondary "dig @127.0.0.1 www.lab.test A +short" \
  "10.10.20.30" "Secondary resolves www.lab.test"

echo "== Client DNS connectivity =="

check client "dig @10.10.20.30 www.lab.test A +short" \
  "10.10.20.30" "Client -> primary DNS"

check client "dig @10.10.20.31 www.lab.test A +short" \
  "10.10.20.30" "Client -> secondary DNS"

echo "== Primary / Secondary replication =="

primary_serial=$(vagrant ssh primary -c \
  "dig @127.0.0.1 lab.test SOA +short" 2>/dev/null | awk 'NR==1 {print $3}')

secondary_serial=$(vagrant ssh secondary -c \
  "dig @127.0.0.1 lab.test SOA +short" 2>/dev/null | awk 'NR==1 {print $3}')

if [[ -n "$primary_serial" && "$primary_serial" == "$secondary_serial" ]]; then
  echo "PASS  Primary and secondary serials match ($primary_serial)"
  pass=$((pass+1))
else
  echo "FAIL  Primary and secondary serials do not match"
  echo "      Primary:   ${primary_serial:-unavailable}"
  echo "      Secondary: ${secondary_serial:-unavailable}"
  fail=$((fail+1))
fi

echo
echo "================================"
echo "Result: $pass passed, $fail failed"
echo "================================"

[ "$fail" -eq 0 ]
