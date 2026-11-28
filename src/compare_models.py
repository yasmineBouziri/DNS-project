"""
Compare the saved models on the same test file, then repeat the whole
split/fit/calibrate process 30 times to see how much results depend on the split.

This is a DEVELOPMENT comparison: these attack rows have already been inspected.
"""

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score, average_precision_score, confusion_matrix, f1_score,
    precision_score, recall_score, roc_auc_score,
)

from common import (
    FEATURES, MODEL_CONFIGS, MODELS_DIR, RESULTS_DIR, SOURCE_PATH,
    anomaly_scores, fit_and_calibrate, load_splits, split_data,
)

N_REPEATS = 30
GRAPHS = RESULTS_DIR / "graphs"
LABELS = {"isolation_forest": "Isolation Forest",
          "one_class_svm": "One-Class SVM", "lof": "LOF"}
COLORS = ["#257de0", "#f47230", "#00b894"]


def evaluate(test, scores, threshold):
    y = test["label"].to_numpy()
    pred = (scores >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    metrics = {
        "tn": tn, "fp": fp, "fn": fn, "tp": tp,
        "accuracy": accuracy_score(y, pred),
        "precision": precision_score(y, pred, zero_division=0),
        "recall": recall_score(y, pred),
        "f1": f1_score(y, pred),
        "false_positive_rate": fp / (fp + tn),
        "roc_auc": roc_auc_score(y, scores),
        "pr_auc": average_precision_score(y, scores),
    }
    attacks = test["label"] == 1
    per_scenario = (
        pd.Series(pred, index=test.index)[attacks]
        .groupby(test.loc[attacks, "scenario"]).mean()
    )
    return metrics, per_scenario, pred


def grouped_bars(table, title, path):
    """table: rows = categories, columns = model keys, values 0-1."""
    fig, ax = plt.subplots(figsize=(12, 5.5))
    x = np.arange(len(table))
    for i, (key, color) in enumerate(zip(table.columns, COLORS)):
        bars = ax.bar(x + (i - 1) * 0.27, table[key] * 100, 0.25,
                      label=LABELS[key], color=color)
        ax.bar_label(bars, fmt="%.0f", fontsize=8, padding=2)
    ax.set_xticks(x, table.index, rotation=20, ha="right")
    ax.set_ylim(0, 112)
    ax.set_ylabel("percent")
    ax.set_title(title)
    ax.grid(axis="y", alpha=0.25)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.25), frameon=False)
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def main():
    GRAPHS.mkdir(parents=True, exist_ok=True)
    _, _, test = load_splits()

    summary, scenarios, errors = {}, {}, []
    cm_fig, cm_axes = plt.subplots(1, 3, figsize=(12, 4))
    sd_fig, sd_axes = plt.subplots(1, 3, figsize=(15, 4.5))

    for name, cm_ax, sd_ax in zip(MODEL_CONFIGS, cm_axes, sd_axes):
        art = joblib.load(MODELS_DIR / name / "model.joblib")
        scores = anomaly_scores(art["pipeline"], test)
        threshold = art["threshold"]
        summary[name], scenarios[name], pred = evaluate(test, scores, threshold)

        wrong = test[pred != test["label"]].copy()
        wrong.insert(0, "model", name)
        wrong.insert(1, "error", np.where(wrong["label"] == 1,
                                          "false_negative", "false_positive"))
        wrong["score_minus_threshold"] = (scores - threshold)[pred != test["label"]]
        errors.append(wrong)

        m = summary[name]
        matrix = np.array([[m["tn"], m["fp"]], [m["fn"], m["tp"]]])
        cm_ax.imshow(matrix / matrix.sum(axis=1, keepdims=True),
                     cmap="Blues", vmin=0, vmax=1)
        for (i, j), v in np.ndenumerate(matrix):
            share = v / matrix[i].sum()
            cm_ax.text(j, i, int(v), ha="center", va="center", fontsize=13,
                       color="white" if share > 0.5 else "black")
        cm_ax.set_xticks([0, 1], ["Normal", "Anomaly"])
        cm_ax.set_yticks([0, 1], ["Normal", "Anomaly"])
        cm_ax.set_xlabel("predicted")
        cm_ax.set_ylabel("actual")
        cm_ax.set_title(LABELS[name])

        # Score scales differ between models, so each has its own panel.
        is_attack = test["label"].to_numpy() == 1
        bins = np.histogram_bin_edges(scores, bins=40)
        for mask, label, color in [(~is_attack, "normal", COLORS[0]),
                                   (is_attack, "attack", COLORS[1])]:
            sd_ax.hist(scores[mask], bins=bins, alpha=0.65, label=label, color=color)
        sd_ax.axvline(threshold, color="black", ls="--", lw=1, label="threshold")
        sd_ax.set_yscale("log")
        sd_ax.set_title(LABELS[name])
        sd_ax.set_xlabel("anomaly score")
        sd_ax.set_ylabel("rows (log scale)")
        sd_ax.legend(frameon=False)

    for fig, filename in [(cm_fig, "confusion_matrices.png"),
                          (sd_fig, "score_distributions.png")]:
        fig.tight_layout()
        fig.savefig(GRAPHS / filename, dpi=200)
        plt.close(fig)

    summary = pd.DataFrame(summary).T
    summary.to_csv(RESULTS_DIR / "model_comparison.csv", index_label="model")
    scenarios = pd.DataFrame(scenarios)
    scenarios.to_csv(RESULTS_DIR / "scenario_comparison.csv", index_label="scenario")
    pd.concat(errors).to_csv(RESULTS_DIR / "model_errors.csv", index=False)

    # Repeated splits: all models see the same split at each seed.
    data = pd.read_csv(SOURCE_PATH)
    rows = []
    for seed in range(N_REPEATS):
        train, calibration, test_r = split_data(data, seed)
        for name in MODEL_CONFIGS:
            pipeline, threshold = fit_and_calibrate(name, train, calibration, seed)
            metrics, per_scenario, _ = evaluate(
                test_r, anomaly_scores(pipeline, test_r), threshold)
            rows.append({"seed": seed, "model": name, **metrics, **per_scenario})
    repeats = pd.DataFrame(rows)
    repeats.to_csv(RESULTS_DIR / "repeated_splits.csv", index=False)
    stats = (repeats.drop(columns=["seed", "tn", "fp", "fn", "tp"])
             .groupby("model").agg(["mean", "min", "max"]).T)
    stats.to_csv(RESULTS_DIR / "repeated_splits_summary.csv",
                 index_label=["metric", "statistic"])

    mean = repeats.groupby("model").mean(numeric_only=True).T[list(MODEL_CONFIGS)]
    grouped_bars(mean.loc[["precision", "recall", "f1", "false_positive_rate"]],
                 f"Mean over {N_REPEATS} splits", GRAPHS / "metric_comparison.png")
    grouped_bars(mean.loc[scenarios.index],
                 f"Mean detection rate per attack over {N_REPEATS} splits",
                 GRAPHS / "attack_detection.png")

    pd.set_option("display.width", 150)
    print("\nSaved split:\n", summary.T.astype(float).round(3))
    print("\nSaved split, per attack:\n", scenarios.round(3))
    print(f"\n{N_REPEATS} splits (mean / min / max):\n", stats.round(3).to_string())


if __name__ == "__main__":
    main()
