
"""
Evaluate DNS anomaly detection performance.

Run from project root:
    python src/evaluate_model.py
"""

from pathlib import Path

import pandas as pd
from sklearn.metrics import (
    confusion_matrix,
    classification_report,
    precision_score,
    recall_score,
    f1_score,
    accuracy_score,
    roc_auc_score,
    average_precision_score
)

ROOT = Path(__file__).resolve().parent.parent

RESULTS_PATH = ROOT / "results" / "detections.csv"
REPORT_PATH = ROOT / "results" / "evaluation.csv"


def main():

    if not RESULTS_PATH.exists():
        raise FileNotFoundError(
            "Detection results not found. Run detect.py first."
        )

    data = pd.read_csv(RESULTS_PATH)

    if "label" not in data.columns:
        raise ValueError(
            "The dataset needs a label column for evaluation."
        )

    # Actual labels: 0 = normal, 1 = anomaly
    y_true = data["label"].astype(int)

    # Model predictions: False = normal, True = anomaly
    y_pred = data["anomaly_detected"].astype(int)

    print("\n========== MODEL EVALUATION ==========")

    print(f"Total observations: {len(data)}")

    print("\nClassification report:")

    print(
        classification_report(
            y_true,
            y_pred,
            target_names=["Normal", "Anomaly"],
            zero_division=0
        )
    )

    print("\nConfusion matrix:")
    print(confusion_matrix(y_true, y_pred))

    print("\nOverall metrics:")

    print(f"Accuracy:  {accuracy_score(y_true, y_pred):.4f}")
    print(f"Precision: {precision_score(y_true, y_pred, zero_division=0):.4f}")
    print(f"Recall:    {recall_score(y_true, y_pred, zero_division=0):.4f}")
    print(f"F1-score:  {f1_score(y_true, y_pred, zero_division=0):.4f}")

    normal_count = int((y_true == 0).sum())
    if normal_count:
        false_positives = int(((y_true == 0) & (y_pred == 1)).sum())
        print(f"False-positive rate: {false_positives / normal_count:.4f}")

    if y_true.nunique() == 2:
        print(f"ROC-AUC: {roc_auc_score(y_true, data['anomaly_score']):.4f}")
        print(f"PR-AUC:  {average_precision_score(y_true, data['anomaly_score']):.4f}")

    # Evaluate detection rate for each attack scenario
    if "scenario" in data.columns:

        print("\nDetection rate by scenario:")

        scenario_results = (
            data[data["label"] == 1].groupby("scenario")
            .agg(
                total=("label", "count"),
                actual_anomalies=("label", "sum"),
                detected=("anomaly_detected", "sum")
            )
        )

        scenario_results["detection_rate"] = (
            scenario_results["detected"]
            / scenario_results["actual_anomalies"]
        )

        print(scenario_results)

        scenario_results.to_csv(REPORT_PATH)

        print(f"\nScenario report saved to: {REPORT_PATH}")


if __name__ == "__main__":
    main()
