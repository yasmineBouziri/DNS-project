"""
Harder synthetic attacks for development, plus a sealed final test set.

generate_data.py and simulated_dns_data.csv are left unchanged.
The severity ranges below are ASSUMPTIONS chosen for this exercise, not
measurements. "strong" in the original CSV is far outside normal traffic;
"mild" and "moderate" sit much closer to it.
Assumption: error_rate includes SERVFAIL, so error_rate >= servfail_rate.
"""

import numpy as np
import pandas as pd

from common import DATA_DIR
from generate_data import CSV_COLUMNS, normal_row

TRANSPORTS = ("classic", "dot", "doh")
SCENARIOS = ("dns_flood", "dns_tunneling", "authoritative_down", "dnssec_failure",
             "high_latency", "resource_overload", "traffic_spike")
DEV_SEED, FINAL_SEED = 101, 2027

# ("x", lo, hi) multiplies the normal value; ("set", lo, hi) replaces it.
SEVERITY = {
    "dns_flood": {
        "query_rate": [("x", 2, 3), ("x", 3, 7)],
        "nxdomain_rate": [("set", 8, 15), ("set", 15, 35)],
        "unique_domain_ratio": [("set", .25, .40), ("set", .40, .55)],
        "cpu_usage": [("x", 1.3, 1.8), ("x", 1.8, 3)],
        "avg_latency": [("x", 1.1, 1.5), ("x", 1.5, 2)],
    },
    "dns_tunneling": {
        "avg_response_size": [("x", 1.4, 2), ("x", 2, 4)],
        "unique_domain_ratio": [("set", .28, .45), ("set", .45, .80)],
        "query_rate": [("x", 1.0, 1.2), ("x", 1.1, 1.4)],
    },
    "authoritative_down": {
        "servfail_rate": [("set", 2, 8), ("set", 8, 35)],
        "avg_latency": [("x", 1.5, 2.5), ("x", 2.5, 5)],
    },
    "dnssec_failure": {"servfail_rate": [("set", 2, 8), ("set", 8, 45)]},
    "high_latency": {"avg_latency": [("x", 1.5, 2.2), ("x", 2.2, 6)]},
    "resource_overload": {
        "cpu_usage": [("set", 40, 60), ("set", 60, 90)],
        "memory_usage": [("set", 48, 65), ("set", 65, 88)],
        "avg_latency": [("x", 1.1, 1.5), ("x", 1.5, 3)],
    },
    "traffic_spike": {"query_rate": [("x", 1.5, 2), ("x", 2, 3)]},
}
LEVELS = ("mild", "moderate")


def attack_row(rng, scenario, transport, dnssec, level):
    row = normal_row(rng, transport, dnssec)
    for metric, ranges in SEVERITY[scenario].items():
        kind, lo, hi = ranges[level]
        value = rng.uniform(lo, hi)
        row[metric] = row[metric] * value if kind == "x" else value
    if scenario in ("authoritative_down", "dnssec_failure"):
        row["error_rate"] = row["servfail_rate"] + rng.uniform(0.5, 2.0)
    row.update(label=1, scenario=scenario, severity=LEVELS[level])
    return row


def attacks(rng, per_cell):
    rows = []
    for scenario in SCENARIOS:
        for transport in TRANSPORTS:
            for dnssec in ((1,) if scenario == "dnssec_failure" else (0, 1)):
                for level in range(len(LEVELS)):
                    rows += [attack_row(rng, scenario, transport, dnssec, level)
                             for _ in range(per_cell)]
    return rows


def frame(rows, start):
    data = pd.DataFrame(rows)
    data["timestamp"] = pd.date_range(start, periods=len(data), freq="10s").astype(str)
    return data[CSV_COLUMNS + ["severity"]]


def main():
    dev = frame(attacks(np.random.default_rng(DEV_SEED), 10), "2026-02-01T00:00:00Z")
    dev.to_csv(DATA_DIR / "dev_attacks.csv", index=False)

    rng = np.random.default_rng(FINAL_SEED)
    rows = [dict(normal_row(rng, t, d), severity="none")
            for t in TRANSPORTS for d in (0, 1) for _ in range(100)]
    rows += attacks(rng, 8)
    final = frame(rows, "2026-03-01T00:00:00Z")
    final.to_csv(DATA_DIR / "final_test_data.csv", index=False)

    print(f"dev attacks: {len(dev)}")
    print(f"sealed final test: {(final.label == 0).sum()} normal, "
          f"{int(final.label.sum())} attacks (do not use until the end)")


if __name__ == "__main__":
    main()
