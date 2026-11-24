
"""
DNS Anomaly Detection - Visualization

Run from project root:
    python src/visualize.py
"""

from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt

from sklearn.metrics import confusion_matrix, ConfusionMatrixDisplay


# --------------------------------------------------
# PATHS
# --------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent

DATA_PATH = ROOT / "results" / "detections.csv"
GRAPH_DIR = ROOT / "results" / "graphs"


# --------------------------------------------------
# LOAD DATA
# --------------------------------------------------

def load_data():

    if not DATA_PATH.exists():
        raise FileNotFoundError(
            "detections.csv not found. Run detect.py first."
        )

    data = pd.read_csv(DATA_PATH)

    required_columns = [
        "timestamp",
        "anomaly_score",
        "anomaly_detected",
        "label",
        "scenario"
    ]

    missing = [
        col for col in required_columns
        if col not in data.columns
    ]

    if missing:
        raise ValueError(f"Missing columns: {missing}")

    data["timestamp"] = pd.to_datetime(
        data["timestamp"], utc=True
    )

    # Convert string representations to booleans if necessary
    if data["anomaly_detected"].dtype == object:
        data["anomaly_detected"] = (
            data["anomaly_detected"]
            .astype(str)
            .str.lower()
            .map({"true": True, "false": False})
        )

    data["label"] = data["label"].astype(int)

    return data


# --------------------------------------------------
# 1. ANOMALY TIMELINE
# --------------------------------------------------

def plot_anomaly_timeline(data):

    fig, ax = plt.subplots(figsize=(14, 6))

    normal = data[~data["anomaly_detected"]]
    anomalies = data[data["anomaly_detected"]]

    ax.scatter(
        normal["timestamp"],
        normal["anomaly_score"],
        label="Not detected",
        alpha=0.6,
        s=18
    )

    ax.scatter(
        anomalies["timestamp"],
        anomalies["anomaly_score"],
        label="Detected anomaly",
        alpha=0.8,
        s=30,
        marker="x"
    )

    # Highlight actual attack observations
    actual_attacks = data[data["label"] == 1]

    if not actual_attacks.empty:
        ymin = data["anomaly_score"].min()
        ymax = data["anomaly_score"].max()

        for _, group in actual_attacks.groupby(
            (actual_attacks.index.to_series().diff() != 1).cumsum()
        ):
            ax.axvspan(
                group["timestamp"].min(),
                group["timestamp"].max(),
                alpha=0.12,
                color="red"
            )

    ax.set_title("DNS Anomaly Scores Over Time")
    ax.set_xlabel("Timestamp")
    ax.set_ylabel("Anomaly Score (higher = more unusual)")
    ax.legend()
    ax.grid(alpha=0.3)

    fig.autofmt_xdate()
    fig.tight_layout()

    fig.savefig(
        GRAPH_DIR / "anomaly_timeline.png",
        dpi=300
    )

    plt.close(fig)


# --------------------------------------------------
# 2. CONFUSION MATRIX
# --------------------------------------------------

def plot_confusion_matrix(data):

    y_true = data["label"]

    y_pred = data["anomaly_detected"].astype(int)

    matrix = confusion_matrix(
        y_true,
        y_pred,
        labels=[0, 1]
    )

    fig, ax = plt.subplots(figsize=(7, 6))

    display = ConfusionMatrixDisplay(
        confusion_matrix=matrix,
        display_labels=["Normal", "Anomaly"]
    )

    display.plot(
        ax=ax,
        cmap="Blues",
        values_format="d",
        colorbar=False
    )

    ax.set_title("DNS Anomaly Detection - Confusion Matrix")

    fig.tight_layout()

    fig.savefig(
        GRAPH_DIR / "confusion_matrix.png",
        dpi=300
    )

    plt.close(fig)


# --------------------------------------------------
# 3. DETECTION RATE PER SCENARIO
# --------------------------------------------------

def plot_scenario_detection(data):

    # Exclude normal traffic
    attacks = data[data["label"] == 1].copy()

    if attacks.empty:
        print("No attack observations available.")
        return

    scenario_results = (
        attacks.groupby("scenario")
        .agg(
            total=("label", "count"),
            detected=("anomaly_detected", "sum")
        )
    )

    scenario_results["detection_rate"] = (
        scenario_results["detected"]
        / scenario_results["total"]
        * 100
    )

    fig, ax = plt.subplots(figsize=(11, 6))

    bars = ax.bar(
        scenario_results.index,
        scenario_results["detection_rate"]
    )

    ax.bar_label(
        bars,
        fmt="%.1f%%",
        padding=3
    )

    ax.set_title("Detection Rate by Attack Scenario")
    ax.set_xlabel("Attack Scenario")
    ax.set_ylabel("Detection Rate (%)")
    ax.set_ylim(0, 110)

    ax.tick_params(axis="x", rotation=30)
    ax.grid(axis="y", alpha=0.3)

    fig.tight_layout()

    fig.savefig(
        GRAPH_DIR / "scenario_detection.png",
        dpi=300
    )

    plt.close(fig)


# --------------------------------------------------
# 4. ANOMALY SCORE DISTRIBUTION
# --------------------------------------------------

def plot_score_distribution(data):

    normal_scores = data.loc[
        data["label"] == 0,
        "anomaly_score"
    ]

    attack_scores = data.loc[
        data["label"] == 1,
        "anomaly_score"
    ]

    fig, ax = plt.subplots(figsize=(10, 6))

    ax.hist(
        normal_scores,
        bins=30,
        alpha=0.6,
        label="Normal traffic"
    )

    ax.hist(
        attack_scores,
        bins=30,
        alpha=0.6,
        label="Attack traffic"
    )

    ax.set_title("Distribution of DNS Anomaly Scores")
    ax.set_xlabel("Anomaly Score")
    ax.set_ylabel("Number of Observations")
    ax.legend()
    ax.grid(alpha=0.3)

    fig.tight_layout()

    fig.savefig(
        GRAPH_DIR / "score_distribution.png",
        dpi=300
    )

    plt.close(fig)


# --------------------------------------------------
# MAIN
# --------------------------------------------------

def main():

    GRAPH_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading detection results...")

    data = load_data()

    print(f"Loaded {len(data)} observations.")

    print("\nGenerating visualizations...")

    plot_anomaly_timeline(data)
    print("[OK] Anomaly timeline")

    plot_confusion_matrix(data)
    print("[OK] Confusion matrix")

    plot_scenario_detection(data)
    print("[OK] Scenario detection")

    plot_score_distribution(data)
    print("[OK] Score distribution")

    print("\nAll graphs generated successfully!")
    print(f"Saved in: {GRAPH_DIR}")


if __name__ == "__main__":
    main()
