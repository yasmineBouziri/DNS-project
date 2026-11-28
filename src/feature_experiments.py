"""
Phase 4: do different features help? Development data only.

"relative" divides query_rate and avg_latency by the normal TRAINING median of
the same transport x DNSSEC mode, so 1.0 means "typical for this mode".
Medians are learned inside the pipeline from training rows only.
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from common import (DATA_DIR, FEATURES, NUMERIC_FEATURES, QUANTILE, RESULTS_DIR,
                    SOURCE_PATH, build_pipeline, split_data)

OUT = RESULTS_DIR / "phase4"
SEEDS = range(200, 230)
MODE = ["transport", "dnssec"]
RELATIVE = ["query_rate", "avg_latency"]
SKEWED = ["query_rate", "avg_latency", "avg_response_size", "error_rate", "servfail_rate"]
SELECTED = {  # from Phase 3
    "isolation_forest": dict(n_estimators=300, max_samples=1.0, max_features=0.5, n_jobs=1),
    "one_class_svm": dict(kernel="rbf", nu=0.1, gamma=0.3),
    "lof": dict(n_neighbors=5, metric="euclidean"),
}

data = pd.read_csv(SOURCE_PATH)
dev = pd.read_csv(DATA_DIR / "dev_attacks.csv")


class Features(BaseEstimator, TransformerMixin):
    def __init__(self, relative="none", log=False):
        self.relative, self.log = relative, log

    def fit(self, X, y=None):
        self.medians_ = X.groupby(MODE)[RELATIVE].median()
        return self

    def transform(self, X):
        out = X.copy()
        if self.relative != "none":
            base = self.medians_.reindex(pd.MultiIndex.from_frame(X[MODE])).to_numpy()
            ratio = X[RELATIVE].to_numpy() / base
            if self.relative == "replace":
                out[RELATIVE] = ratio
            else:
                for i, name in enumerate(RELATIVE):
                    out[name + "_ratio"] = ratio[:, i]
        if self.log:
            for name in SKEWED:
                out[name] = np.log1p(out[name])
        return out


VARIANTS = {
    "current": {},
    "relative_replace": {"relative": "replace"},
    "relative_add": {"relative": "add"},
    "log": {"log": True},
    **{f"without_{f}": {"drop": f} for f in ["transport"] + NUMERIC_FEATURES},
}


def make(name, spec, seed):
    relative, drop = spec.get("relative", "none"), spec.get("drop")
    numeric = [f for f in NUMERIC_FEATURES if f != drop]
    if relative == "add":
        numeric += [f + "_ratio" for f in RELATIVE]
    base = build_pipeline(name, seed)
    steps = [] if name == "isolation_forest" else [("scale", StandardScaler())]
    parts = [("num", Pipeline(steps) if steps else "passthrough", numeric)]
    if drop != "transport":
        parts.insert(0, ("cat", OneHotEncoder(handle_unknown="ignore"), ["transport"]))
    model = base.named_steps["model"].set_params(**SELECTED[name])
    return Pipeline([("features", Features(relative, spec.get("log", False))),
                     ("columns", ColumnTransformer(parts)), ("model", model)])


def run(name, variant, seed):
    train, calibration, test = split_data(data, seed)
    normal = test[test.label == 0]
    p = make(name, VARIANTS[variant], seed).fit(train[FEATURES])
    threshold = np.quantile(-p.decision_function(calibration[FEATURES]), QUANTILE)
    hit = pd.Series(-p.decision_function(dev[FEATURES]) >= threshold)
    per = hit.groupby(dev.scenario).mean()
    return {"model": name, "variant": variant, "seed": seed,
            "fpr": np.mean(-p.decision_function(normal[FEATURES]) >= threshold),
            "recall": per.mean(), **per.to_dict()}


def range_rule(seed, relative):
    train, _, test = split_data(data, seed)
    step = Features("replace" if relative else "none").fit(train)
    columns = [f for f in NUMERIC_FEATURES if f != "dnssec"]
    low, high = step.transform(train)[columns].min(), step.transform(train)[columns].max()
    flag = lambda f: ((step.transform(f)[columns] < low)
                      | (step.transform(f)[columns] > high)).any(axis=1)
    per = flag(dev).groupby(dev.scenario).mean()
    return {"model": "range_rule", "variant": "relative_replace" if relative else "current",
            "seed": seed, "fpr": flag(test[test.label == 0]).mean(),
            "recall": per.mean(), **per.to_dict()}


def plots(normal):
    numeric = [f for f in NUMERIC_FEATURES if f != "dnssec"]
    fig, axes = plt.subplots(3, 3, figsize=(13, 10))
    for ax, f in zip(axes.flat, numeric):
        ax.boxplot([normal[normal.transport == t][f] for t in ("classic", "dot", "doh")],
                   tick_labels=["classic", "dot", "doh"])
        ax.set_title(f)
    fig.suptitle("Normal traffic by transport")
    fig.tight_layout()
    fig.savefig(OUT / "normal_by_transport.png", dpi=150)
    plt.close(fig)
    within = normal[numeric] - normal.groupby(MODE)[numeric].transform("mean")
    corr = within.corr()
    fig, ax = plt.subplots(figsize=(8, 7))
    image = ax.imshow(corr, cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_xticks(range(len(numeric)), numeric, rotation=45, ha="right")
    ax.set_yticks(range(len(numeric)), numeric)
    for (i, j), v in np.ndenumerate(corr.to_numpy()):
        ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=7,
                color="white" if abs(v) > 0.6 else "black")
    ax.set_title("Correlation within normal mode")
    fig.colorbar(image, shrink=0.7)
    fig.tight_layout()
    fig.savefig(OUT / "correlations.png", dpi=150)
    plt.close(fig)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    plots(data[data.label == 0])
    rows = Parallel(n_jobs=-1)(delayed(run)(m, v, s)
                               for m in SELECTED for v in VARIANTS for s in SEEDS)
    rows += [range_rule(s, r) for r in (False, True) for s in SEEDS]
    runs = pd.DataFrame(rows)
    mean = runs.drop(columns="seed").groupby(["model", "variant"], sort=False).mean()
    mean.to_csv(OUT / "feature_experiments.csv")
    pd.set_option("display.width", 200)
    print(mean[["recall", "fpr", "high_latency", "traffic_spike", "dns_tunneling",
                "dnssec_failure"]].round(3).to_string())


if __name__ == "__main__":
    main()
