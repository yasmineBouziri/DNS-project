
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
df = pd.read_csv(ROOT / "results" / "detections.csv")

# Actual attacks that the model missed
missed = df[
    (df["label"] == 1)
    & (~df["anomaly_detected"].astype(bool))
].copy()

columns = [
    "scenario",
    "transport",
    "dnssec",
    "query_rate",
    "avg_latency",
    "error_rate",
    "servfail_rate",
    "nxdomain_rate",
    "cpu_usage",
    "memory_usage",
    "anomaly_score",
]

print("\n========== MISSED ATTACKS ==========")
print(missed[columns].to_string(index=False))

print("\n========== MISSED ATTACKS BY SCENARIO ==========")
print(missed["scenario"].value_counts())
