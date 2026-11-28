"""Recall against false positive rate at four thresholds (selected settings)."""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from common import RESULTS_DIR

OUT = RESULTS_DIR / "phase3"
t = pd.read_csv(OUT / "threshold_tradeoff.csv")
t = t[t.config == "selected"]
fig, ax = plt.subplots(figsize=(9, 5.5))
for key, label, color, marker in [
        ("isolation_forest", "Isolation Forest", "#257de0", "o"),
        ("one_class_svm", "One-Class SVM", "#f47230", "s"),
        ("lof", "LOF", "#00b894", "^")]:
    m = t[t.model == key]
    ax.plot(m.fpr * 100, m.recall * 100, marker=marker, lw=2, ms=8,
            color=color, label=label)
for q, x in t[t.model == "isolation_forest"][["quantile", "fpr"]].values:
    ax.annotate(f"{q * 100:g}th pct", (x * 100, 68), ha="center", fontsize=8, color="#555")
ax.set_ylim(66, 101)
ax.set_xlabel("false positive rate on normal rows (%)")
ax.set_ylabel("mean per-scenario recall (%)")
ax.set_title("Development attacks: threshold trade-off, mean of 30 splits")
ax.grid(alpha=0.25)
ax.spines[["top", "right"]].set_visible(False)
ax.legend(frameon=False, loc="center right")
fig.tight_layout()
fig.savefig(OUT / "threshold_tradeoff.png", dpi=200)
