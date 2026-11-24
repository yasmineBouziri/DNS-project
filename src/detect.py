
"""
DNS Anomaly Detection

Run from project root:
    python src/detect.py

For another dataset:
    python src/detect.py --input data/real_dns_data.csv
"""

import argparse
import json
import math
from pathlib import Path

import joblib
import pandas as pd


ROOT = Path(__file__).resolve().parent.parent

MODEL_PATH = ROOT / "models" / "isolation_forest.joblib"
DEFAULT_INPUT = ROOT / "results" / "test_data.csv"

RESULTS_DIR = ROOT / "results"
DETECTIONS_PATH = RESULTS_DIR / "detections.csv"
ALERTS_PATH = RESULTS_DIR / "alerts.json"

FEATURES = [
    "transport",
    "dnssec",
    "query_rate",
    "avg_latency",
    "error_rate",
    "servfail_rate",
    "nxdomain_rate",
    "avg_response_size",
    "unique_domain_ratio",
    "cpu_usage",
    "memory_usage",
]

THRESHOLDS = {
    "query_rate": 180,
    "nxdomain_rate": 25,
    "unique_domain_ratio": 0.75,
    "response_size": 1200,
    "latency": 250,
    "error_rate": 20,
    "servfail_rate": 15,
    "cpu": 90,
    "memory": 90,
}


def load_data(input_path):
    if not input_path.exists():
        raise FileNotFoundError(f"Dataset not found: {input_path}")

    data = pd.read_csv(input_path)

    missing = [col for col in FEATURES if col not in data.columns]

    if missing:
        raise ValueError(f"Missing columns: {missing}")

    return data


def classify_anomaly(row):
    t = THRESHOLDS

    if (
        row["unique_domain_ratio"] >= t["unique_domain_ratio"]
        and row["avg_response_size"] >= t["response_size"]
    ):
        return "tunneling_suspected", "High unique-domain ratio and large DNS responses."

    elif (
        row["dnssec"] == 1
        and row["servfail_rate"] >= t["servfail_rate"]
        and row["avg_latency"] < t["latency"]
        and row["query_rate"] < t["query_rate"]
    ):
        return "dnssec_failure_suspected", "Elevated SERVFAIL while DNSSEC is enabled."

    elif (
        row["servfail_rate"] >= t["servfail_rate"]
        and row["avg_latency"] >= t["latency"]
    ):
        return "authoritative_or_upstream_failure_suspected", "SERVFAIL and latency are elevated."

    elif (
        row["query_rate"] >= t["query_rate"]
        and (
            row["nxdomain_rate"] >= t["nxdomain_rate"]
            or row["error_rate"] >= t["error_rate"]
        )
    ):
        return "dns_flood_suspected", "High query rate with elevated errors or NXDOMAIN."

    elif (
        row["cpu_usage"] >= t["cpu"]
        or row["memory_usage"] >= t["memory"]
    ):
        return "resource_overload", "CPU or memory usage is elevated."

    elif row["avg_latency"] >= t["latency"]:
        return "high_latency", "Average DNS response latency is elevated."

    elif row["query_rate"] >= t["query_rate"]:
        return "traffic_spike", "DNS query rate is elevated."

    elif (
        row["error_rate"] >= t["error_rate"]
        or row["servfail_rate"] >= t["servfail_rate"]
    ):
        return "high_failure", "DNS failure rates are elevated."

    return "unclassified_anomaly", "Unusual DNS behavior; no specific pattern matched."


def get_severity(row):
    if (
        row["query_rate"] >= THRESHOLDS["query_rate"] * 1.8
        or row["servfail_rate"] >= THRESHOLDS["servfail_rate"] * 2
        or row["error_rate"] >= THRESHOLDS["error_rate"] * 2
        or row["cpu_usage"] >= 97
        or row["memory_usage"] >= 97
    ):
        return "high"

    if (
        row["query_rate"] >= THRESHOLDS["query_rate"]
        or row["avg_latency"] >= THRESHOLDS["latency"]
        or row["error_rate"] >= THRESHOLDS["error_rate"]
        or row["servfail_rate"] >= THRESHOLDS["servfail_rate"]
        or row["cpu_usage"] >= THRESHOLDS["cpu"]
        or row["memory_usage"] >= THRESHOLDS["memory"]
    ):
        return "medium"

    return "low"


def normalize_score(raw_score):
    # Relative score for display, NOT a probability.
    raw_score = max(-50, min(50, raw_score * 10))
    return 1 / (1 + math.exp(-raw_score))


def map_anomaly_type(anomaly_type, row):
    if anomaly_type == "dns_flood_suspected":
        return "flood"

    if anomaly_type == "tunneling_suspected":
        return "tunneling"

    if row["nxdomain_rate"] >= THRESHOLDS["nxdomain_rate"]:
        return "nxdomain_burst"

    return "unknown"


def create_alert(row, alert_number):
    anomaly_type, explanation = classify_anomaly(row)
    task8_type = map_anomaly_type(anomaly_type, row)

    severity = get_severity(row)

    if (
        row["query_rate"] >= THRESHOLDS["query_rate"] * 3
        or row["cpu_usage"] >= 99
        or row["memory_usage"] >= 99
    ):
        severity = "critical"

    timestamp = pd.to_datetime(row["timestamp"], utc=True).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    features = {
        "qps": float(row["query_rate"]),
        "nxdomain_rate": float(row["nxdomain_rate"]),
    }

    if "avg_query_len" in row.index and pd.notna(row["avg_query_len"]):
        features["avg_query_len"] = float(row["avg_query_len"])

    if "txt_ratio" in row.index and pd.notna(row["txt_ratio"]):
        features["txt_ratio"] = float(row["txt_ratio"])

    if "unique_domains" in row.index and pd.notna(row["unique_domains"]):
        features["unique_domains"] = int(row["unique_domains"])

    source_ip = row.get("source_ip", "unknown")
    if pd.isna(source_ip):
        source_ip = "unknown"

    return {
        "alert_id": f"ALR-{timestamp[:10].replace('-', '')}-{alert_number:04d}",
        "timestamp": timestamp,
        "anomaly_type": task8_type,
        "severity": severity,
        "score": round(float(normalize_score(row["anomaly_score"])), 4),
        "source_ip": str(source_ip),
        "target": "resolver (10.10.10.20)",
        "transport": str(row["transport"]),
        "features": features,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    args = parser.parse_args()

    if not MODEL_PATH.exists():
        raise FileNotFoundError("Model not found. Run train_model.py first.")

    print("Loading dataset...")
    data = load_data(args.input)

    print("Loading calibrated model...")
    artifact = joblib.load(MODEL_PATH)

    model = artifact["pipeline"]
    threshold = artifact["threshold"]

    X = data[FEATURES]

    print("Detecting anomalies...")

    # Higher score means more anomalous.
    scores = -model.decision_function(X)

    # Use the threshold calibrated on held-out normal traffic.
    predictions = (scores >= threshold).astype(int)

    results = data.copy()
    results["anomaly_score"] = scores
    results["anomaly_threshold"] = threshold
    results["anomaly_detected"] = predictions.astype(bool)

    # Keep the familiar prediction convention: -1 = anomaly, 1 = normal.
    results["prediction"] = results["anomaly_detected"].map(
        {True: -1, False: 1}
    )

    alerts = []

    for alert_number, (index, row) in enumerate(
        results[results["anomaly_detected"]].iterrows(),
        start=1,
    ):
        alert = create_alert(row, alert_number)
        alerts.append(alert)

        results.loc[index, "anomaly_type"] = alert["anomaly_type"]
        results.loc[index, "severity"] = alert["severity"]

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    results.to_csv(DETECTIONS_PATH, index=False)

    with open(ALERTS_PATH, "w", encoding="utf-8") as file:
        json.dump(alerts, file, indent=4, ensure_ascii=False)

    total = len(results)
    detected = int(results["anomaly_detected"].sum())

    print("\n========== DETECTION RESULTS ==========")
    print(f"Input: {args.input}")
    print(f"Total observations: {total}")
    print(f"Anomalies detected: {detected}")
    print(f"Normal observations: {total - detected}")
    print(f"Calibrated threshold: {threshold:.6f}")
    print(f"\nDetection results: {DETECTIONS_PATH}")
    print(f"JSON alerts: {ALERTS_PATH}")

    if alerts:
        print("\nExample alert:")
        print(json.dumps(alerts[0], indent=4))


if __name__ == "__main__":
    main()
