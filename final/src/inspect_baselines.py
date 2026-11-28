
from pathlib import Path
import joblib
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent

DATA_PATH = ROOT / "data" / "simulated_dns_data.csv"
MODEL_PATH = ROOT / "models" / "dns_detector.joblib"
DETECTIONS_PATH = ROOT / "results" / "detections.csv"

data = pd.read_csv(DATA_PATH)
detections = pd.read_csv(DETECTIONS_PATH)

artifact = joblib.load(MODEL_PATH)
threshold = artifact["threshold"]

print(f"\nCurrent anomaly threshold: {threshold:.6f}")

# Compare normal traffic for each transport.
normal = data[data["label"] == 0]

metrics = [
    "query_rate",
    "avg_latency",
    "error_rate",
    "servfail_rate",
    "cpu_usage",
]

print("\n========== NORMAL BASELINES BY TRANSPORT ==========")

for transport, group in normal.groupby("transport"):
    print(f"\n--- {transport.upper()} ---")
    print(
        group[metrics].quantile(
            [0.50, 0.90, 0.95, 0.99]
        ).round(2)
    )

# Compare missed attacks with correctly detected attacks.
missed = detections[
    (detections["label"] == 1)
    & (~detections["anomaly_detected"].astype(bool))
]

detected = detections[
    (detections["label"] == 1)
    & (detections["anomaly_detected"].astype(bool))
]

print("\n========== ATTACK COMPARISON ==========")

for name, group in [
    ("MISSED", missed),
    ("DETECTED", detected),
]:
    print(f"\n--- {name} ATTACKS ---")

    print(
        group.groupby("scenario")[
            ["query_rate", "avg_latency", "servfail_rate"]
        ].mean().round(2)
    )

print("\n========== FALSE POSITIVES ==========")

false_positives = detections[
    (detections["label"] == 0)
    & (detections["anomaly_detected"].astype(bool))
]

print(
    false_positives.groupby("transport").size()
)
