"""
Phase 6: evaluation on the sealed final test set.

Fixed BEFORE this script was first run: LOF with relative features,
n_neighbors=35, manhattan, threshold = 97.5th percentile of calibration scores.
The other two models and the range rule are reported for comparison only.
Do not change settings in response to these results; if you do, this data is
no longer an independent test.
"""

import json

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import (accuracy_score, average_precision_score,
                             confusion_matrix, f1_score, precision_score,
                             recall_score, roc_auc_score)

from common import DATA_DIR, FEATURES, MODELS_DIR, NUMERIC_FEATURES, RESULTS_DIR, load_splits
from feature_experiments import VARIANTS, Features, make

OUT = RESULTS_DIR / "final"
CHOSEN = "lof"
QUANTILE = 0.975
LABELS = {"lof": "LOF (chosen)", "one_class_svm": "One-Class SVM",
          "isolation_forest": "Isolation Forest", "range_rule": "Range rule"}
COLORS = ["#00b894", "#f47230", "#257de0", "#888888"]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    train, calibration, _ = load_splits()
    test = pd.read_csv(DATA_DIR / "final_test_data.csv")
    config = json.loads((RESULTS_DIR / "phase5" / "selected_config.json").read_text())
    y = test.label.to_numpy()
    predictions, scores, thresholds = {}, {}, {}

    for name in ["lof", "one_class_svm", "isolation_forest"]:
        c = config[name]
        pipeline = make(name, VARIANTS[c["features"]], 42)
        pipeline.set_params(**{f"model__{k}": v for k, v in c["params"].items()})
        pipeline.fit(train[FEATURES])
        thresholds[name] = float(np.quantile(
            -pipeline.decision_function(calibration[FEATURES]), QUANTILE))
        scores[name] = -pipeline.decision_function(test[FEATURES])
        predictions[name] = (scores[name] >= thresholds[name]).astype(int)
        if name == CHOSEN:
            path = MODELS_DIR / "final" / "model.joblib"
            path.parent.mkdir(parents=True, exist_ok=True)
            joblib.dump({"name": name, "pipeline": pipeline,
                         "threshold": thresholds[name], "threshold_quantile": QUANTILE,
                         "features": FEATURES, "config": c, "seed": 42}, path)

    step = Features("replace").fit(train)
    columns = [f for f in NUMERIC_FEATURES if f != "dnssec"]
    fitted = step.transform(train)[columns]
    values = step.transform(test)[columns]
    predictions["range_rule"] = ((values < fitted.min()) | (values > fitted.max())
                                 ).any(axis=1).astype(int).to_numpy()

    summary, per_scenario, per_level, per_mode = {}, {}, {}, {}
    for name, pred in predictions.items():
        tn, fp, fn, tp = confusion_matrix(y, pred).ravel()
        row = {"tn": tn, "fp": fp, "fn": fn, "tp": tp,
               "accuracy": accuracy_score(y, pred),
               "precision": precision_score(y, pred), "recall": recall_score(y, pred),
               "f1": f1_score(y, pred), "false_positive_rate": fp / (fp + tn)}
        if name in scores:
            row["roc_auc"] = roc_auc_score(y, scores[name])
            row["pr_auc"] = average_precision_score(y, scores[name])
        summary[name] = row
        hit = pd.Series(pred)
        attack = y == 1
        per_scenario[name] = hit[attack].groupby(test.scenario[attack]).mean()
        per_level[name] = hit[attack].groupby(test.severity[attack]).mean()
        mode = test.transport + "/" + test.dnssec.astype(str)
        per_mode[name] = hit[~attack].groupby(mode[~attack]).mean()

    tables = {"summary": pd.DataFrame(summary).T,
              "per_scenario": pd.DataFrame(per_scenario),
              "per_severity": pd.DataFrame(per_level),
              "false_positive_rate_by_mode": pd.DataFrame(per_mode)}
    for filename, table in tables.items():
        table.to_csv(OUT / f"{filename}.csv")
        print(f"\n{filename}\n", table.astype(float).round(3).to_string())

    pred = predictions[CHOSEN]
    wrong = test[pred != y].copy()
    wrong["error"] = np.where(wrong.label == 1, "false_negative", "false_positive")
    wrong["score_minus_threshold"] = scores[CHOSEN][pred != y] - thresholds[CHOSEN]
    wrong.to_csv(OUT / "chosen_model_errors.csv", index=False)
    print("\nChosen model errors\n",
          wrong.groupby(["error", "scenario", "severity", "transport"]).size())

    fig, axes = plt.subplots(1, 4, figsize=(15, 3.8))
    for ax, (name, row) in zip(axes, summary.items()):
        m = np.array([[row["tn"], row["fp"]], [row["fn"], row["tp"]]])
        share = m / m.sum(axis=1, keepdims=True)
        ax.imshow(share, cmap="Blues", vmin=0, vmax=1)
        for (i, j), v in np.ndenumerate(m):
            ax.text(j, i, int(v), ha="center", va="center", fontsize=13,
                    color="white" if share[i, j] > 0.5 else "black")
        ax.set_xticks([0, 1], ["Normal", "Anomaly"])
        ax.set_yticks([0, 1], ["Normal", "Anomaly"])
        ax.set_xlabel("predicted")
        ax.set_ylabel("actual")
        ax.set_title(LABELS[name])
    fig.tight_layout()
    fig.savefig(OUT / "confusion_matrices.png", dpi=170)
    plt.close(fig)

    for filename, table, title in [
            ("per_attack.png", tables["per_scenario"], "Final test: detection per attack (%)"),
            ("metrics.png", tables["summary"].T.loc[
                ["precision", "recall", "f1", "false_positive_rate"]], "Final test metrics (%)")]:
        fig, ax = plt.subplots(figsize=(13, 5))
        x = np.arange(len(table))
        for i, (name, color) in enumerate(zip(LABELS, COLORS)):
            bars = ax.bar(x + (i - 1.5) * 0.2, table[name].astype(float) * 100, 0.19,
                          color=color, label=LABELS[name])
            ax.bar_label(bars, fmt="%.0f", fontsize=7)
        ax.set_xticks(x, table.index, rotation=15, ha="right")
        ax.set_ylim(0, 112)
        ax.set_title(title)
        ax.spines[["top", "right"]].set_visible(False)
        ax.legend(ncol=4, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.2))
        fig.tight_layout()
        fig.savefig(OUT / filename, dpi=170)
        plt.close(fig)

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.3))
    for ax, name in zip(axes, scores):
        # LOF scores span several orders of magnitude
        values = scores[name]
        bins = np.histogram_bin_edges(values, bins=60)
        if name == "lof":  # narrow bins near the threshold, wider far from it
            bins = np.r_[np.linspace(values.min(), 1, 60),
                         np.geomspace(1, values.max(), 40)[1:]]
        for label, text, color in [(0, "normal", "#257de0"), (1, "attack", "#f47230")]:
            ax.hist(values[y == label], bins=bins, alpha=0.65, label=text, color=color)
        ax.axvline(thresholds[name], color="black", ls="--", lw=1, label="threshold")
        if name == "lof":
            ax.set_xscale("symlog", linthresh=1)
        ax.set_yscale("log")
        ax.set_title(LABELS[name])
        ax.set_xlabel("anomaly score")
        ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(OUT / "score_distributions.png", dpi=170)
    plt.close(fig)


if __name__ == "__main__":
    main()
