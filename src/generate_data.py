"""
Generate a chronological synthetic DNS metrics dataset.

Each row represents one 10-second observation window.
The synthetic labels are for evaluation only; they must never be model features.
"""

from pathlib import Path

import numpy as np
import pandas as pd


WINDOW_SECONDS = 10
START_TIMESTAMP = "2026-01-01T00:00:00Z"
NORMAL_ROWS_PER_MODE = 150

# Illustrative simulation baselines, NOT measurements from the actual lab.
# Percentages use the 0-100 scale; unique_domain_ratio uses the 0-1 scale.
BASELINES = {
    "classic": {
        "query_rate": 80.0,
        "avg_latency": 25.0,
        "error_rate": 1.0,
        "servfail_rate": 0.3,
        "nxdomain_rate": 5.0,
        "avg_response_size": 300.0,
        "unique_domain_ratio": 0.18,
        "cpu_usage": 15.0,
        "memory_usage": 35.0,
    },
    "dot": {
        "query_rate": 75.0,
        "avg_latency": 40.0,
        "error_rate": 1.0,
        "servfail_rate": 0.3,
        "nxdomain_rate": 5.0,
        "avg_response_size": 320.0,
        "unique_domain_ratio": 0.18,
        "cpu_usage": 22.0,
        "memory_usage": 38.0,
    },
    "doh": {
        "query_rate": 70.0,
        "avg_latency": 45.0,
        "error_rate": 1.0,
        "servfail_rate": 0.3,
        "nxdomain_rate": 5.0,
        "avg_response_size": 330.0,
        "unique_domain_ratio": 0.18,
        "cpu_usage": 25.0,
        "memory_usage": 40.0,
    },
}

# Relative standard deviations used to make normal observations vary naturally.
NOISE_SCALE = {
    "query_rate": 0.12,
    "avg_latency": 0.12,
    "error_rate": 0.25,
    "servfail_rate": 0.30,
    "nxdomain_rate": 0.20,
    "avg_response_size": 0.12,
    "unique_domain_ratio": 0.18,
    "cpu_usage": 0.12,
    "memory_usage": 0.05,
}

NUMERIC_COLUMNS = list(BASELINES["classic"].keys())
CSV_COLUMNS = [
    "timestamp",
    "transport",
    "dnssec",
    *NUMERIC_COLUMNS,
    "label",
    "scenario",
]


def normal_row(rng: np.random.Generator, transport: str, dnssec: int) -> dict:
    """Create one normal observation for a transport/DNSSEC mode."""
    baseline = BASELINES[transport]
    row = {}

    for metric in NUMERIC_COLUMNS:
        mean = baseline[metric]

        # DNSSEC adds modest normal overhead to response size and latency.
        if dnssec == 1 and metric == "avg_latency":
            mean *= 1.08
        elif dnssec == 1 and metric == "avg_response_size":
            mean *= 1.15

        std = max(mean * NOISE_SCALE[metric], 0.01)
        value = rng.normal(mean, std)
        row[metric] = max(0.0, float(value))

    row["unique_domain_ratio"] = min(row["unique_domain_ratio"], 1.0)
    row["error_rate"] = min(row["error_rate"], 100.0)
    row["servfail_rate"] = min(row["servfail_rate"], 100.0)
    row["nxdomain_rate"] = min(row["nxdomain_rate"], 100.0)
    row["cpu_usage"] = min(row["cpu_usage"], 100.0)
    row["memory_usage"] = min(row["memory_usage"], 100.0)

    row.update(
        {
            "transport": transport,
            "dnssec": int(dnssec),
            "label": 0,
            "scenario": "normal",
        }
    )
    return row


def anomaly_burst(
    rng: np.random.Generator,
    scenario: str,
    transport: str,
    dnssec: int,
    length: int,
) -> list[dict]:
    """Create consecutive observations for one simulated anomaly scenario."""
    rows = []

    for _ in range(length):
        row = normal_row(rng, transport, dnssec)

        if scenario == "dns_flood":
            row["query_rate"] *= rng.uniform(7.0, 12.0)
            row["nxdomain_rate"] = rng.uniform(35.0, 75.0)
            row["unique_domain_ratio"] = rng.uniform(0.55, 0.95)
            row["cpu_usage"] = rng.uniform(75.0, 98.0)
            row["avg_latency"] *= rng.uniform(2.0, 4.0)

        elif scenario == "dns_tunneling":
            row["query_rate"] *= rng.uniform(1.1, 1.5)
            row["avg_response_size"] *= rng.uniform(4.0, 8.0)
            row["unique_domain_ratio"] = rng.uniform(0.80, 1.0)

        elif scenario == "authoritative_down":
            row["servfail_rate"] = rng.uniform(35.0, 75.0)
            row["error_rate"] = rng.uniform(40.0, 80.0)
            row["avg_latency"] *= rng.uniform(5.0, 12.0)

        elif scenario == "dnssec_failure":
            # DNSSEC validation failure is only simulated with DNSSEC enabled.
            dnssec = 1
            row["dnssec"] = 1
            row["servfail_rate"] = rng.uniform(45.0, 85.0)
            row["error_rate"] = rng.uniform(45.0, 85.0)

        elif scenario == "high_latency":
            row["avg_latency"] *= rng.uniform(6.0, 12.0)

        elif scenario == "resource_overload":
            row["cpu_usage"] = rng.uniform(90.0, 100.0)
            row["memory_usage"] = rng.uniform(88.0, 100.0)
            row["avg_latency"] *= rng.uniform(3.0, 7.0)

        elif scenario == "traffic_spike":
            row["query_rate"] *= rng.uniform(3.0, 5.0)

        else:
            raise ValueError(f"Unknown scenario: {scenario}")

        # Keep percentages and ratios within their valid ranges.
        for metric in ("error_rate", "servfail_rate", "nxdomain_rate",
                       "cpu_usage", "memory_usage"):
            row[metric] = float(np.clip(row[metric], 0.0, 100.0))
        row["unique_domain_ratio"] = float(
            np.clip(row["unique_domain_ratio"], 0.0, 1.0)
        )

        row["label"] = 1
        row["scenario"] = scenario
        rows.append(row)

    return rows


def generate_dataset(seed: int = 42) -> pd.DataFrame:
    """Build normal observations and short, consecutive anomaly bursts."""
    rng = np.random.default_rng(seed)
    rows = []

    # Cover all six normal operating modes.
    modes = [
        (transport, dnssec)
        for transport in ("classic", "dot", "doh")
        for dnssec in (0, 1)
    ]

    for transport, dnssec in modes:
        rows.extend(
            normal_row(rng, transport, dnssec)
            for _ in range(NORMAL_ROWS_PER_MODE)
        )

    # Insert bursts of 10-25 consecutive rows.
    scenarios = [
        ("dns_flood", "classic", 0),
        ("dns_tunneling", "dot", 0),
        ("authoritative_down", "classic", 0),
        ("dnssec_failure", "classic", 1),
        ("high_latency", "doh", 1),
        ("resource_overload", "dot", 1),
        ("traffic_spike", "doh", 0),
    ]

    for scenario, transport, dnssec in scenarios:
        burst_length = int(rng.integers(10, 26))
        rows.extend(
            anomaly_burst(
                rng=rng,
                scenario=scenario,
                transport=transport,
                dnssec=dnssec,
                length=burst_length,
            )
        )

    data = pd.DataFrame(rows)

    timestamps = pd.date_range(
        start=START_TIMESTAMP,
        periods=len(data),
        freq=f"{WINDOW_SECONDS}s",
    )
    data.insert(0, "timestamp", timestamps.astype(str))
    data = data[CSV_COLUMNS]

    return data


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    output_dir = project_root / "data"
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / "simulated_dns_data.csv"
    data = generate_dataset()
    data.to_csv(output_path, index=False)

    print("Synthetic DNS dataset generated.")
    print(f"Output: {output_path}")
    print(f"Rows: {len(data)}")
    print(f"Normal rows: {(data['label'] == 0).sum()}")
    print(f"Anomaly rows: {(data['label'] == 1).sum()}")
    print("\nScenario distribution:")
    print(data["scenario"].value_counts())
    print("\nTransport/DNSSEC distribution:")
    print(data.groupby(["transport", "dnssec"]).size())


if __name__ == "__main__":
    main()
