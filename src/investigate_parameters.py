"""
Phase 3 parameter investigation.

Data: the 900 original normal rows (re-split 70/15/15 for every seed) and the
mild/moderate attacks in dev_attacks.csv. final_test_data.csv is never read.

Models are fitted on normal rows only. Attack rows are used to CHOOSE between
configurations, so the scores reported here are development scores.

Selection rule, fixed before running: among configurations with mean false
positive rate <= 6.5%, take the highest mean per-scenario recall (every
scenario weighs the same). The top configuration is then re-checked on 30
splits that were not used to choose it.
"""

import itertools

import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from sklearn.metrics import average_precision_score
from sklearn.preprocessing import RobustScaler, StandardScaler

from common import (
    DATA_DIR, FEATURES, MODEL_CONFIGS, QUANTILE, RESULTS_DIR, SOURCE_PATH,
    anomaly_scores, build_pipeline, split_data,
)

OUT = RESULTS_DIR / "phase3"
SEARCH_SEEDS = range(10)
CONFIRM_SEEDS = range(100, 130)
MAX_FPR = 0.065
QUANTILES = (0.90, 0.95, 0.975, 0.99)

GRIDS = {
    "isolation_forest": {
        "n_estimators": [50, 150, 300, 500],
        "max_samples": [64, 128, 256, 0.5, 1.0],
        "max_features": [0.5, 0.75, 1.0],
        "bootstrap": [False, True],
    },
    "one_class_svm": {
        "kernel": ["rbf", "sigmoid", "poly", "linear"],
        "nu": [0.01, 0.05, 0.1, 0.2],
        "gamma": ["scale", 0.01, 0.03, 0.1, 0.3],
    },
    "lof": {
        "n_neighbors": [5, 10, 20, 35, 50, 100, 200],
        "metric": ["euclidean", "manhattan", "chebyshev", "cosine"],
    },
}

data = pd.read_csv(SOURCE_PATH)
dev = pd.read_csv(DATA_DIR / "dev_attacks.csv")


def combos(name):
    keys = list(GRIDS[name])
    out = [dict(zip(keys, v)) for v in itertools.product(*GRIDS[name].values())]
    for c in out:
        if c.get("kernel") == "linear":  # gamma has no effect
            c["gamma"] = "scale"
    return [dict(t) for t in dict.fromkeys(tuple(c.items()) for c in out)]


def fit(name, params, seed, scaler=None):
    train, calibration, test = split_data(data, seed)
    pipeline = build_pipeline(name, seed)
    pipeline.set_params(**{f"model__{k}": v for k, v in params.items()})
    if name == "isolation_forest":
        pipeline.set_params(model__n_jobs=1)
    if scaler is not None:
        pipeline.set_params(preprocessor__numeric__scaler=scaler)
    pipeline.fit(train[FEATURES])
    return pipeline, train, calibration, test[test.label == 0]


def run(name, params, seed, quantiles=(QUANTILE,), scaler=None):
    pipeline, _, calibration, normal = fit(name, params, seed, scaler)
    cal = anomaly_scores(pipeline, calibration)
    s_normal, s_attack = anomaly_scores(pipeline, normal), anomaly_scores(pipeline, dev)
    pr_auc = average_precision_score(
        np.r_[np.zeros(len(s_normal)), np.ones(len(s_attack))], np.r_[s_normal, s_attack])
    rows = []
    for q in quantiles:
        threshold = np.quantile(cal, q)
        hit = pd.Series(s_attack >= threshold)
        by_scenario = hit.groupby(dev.scenario).mean()
        by_level = hit.groupby(dev.severity).mean()
        rows.append({"seed": seed, "quantile": q,
                     "fpr": np.mean(s_normal >= threshold),
                     "recall": by_scenario.mean(), "pr_auc": pr_auc,
                     "recall_mild": by_level["mild"],
                     "recall_moderate": by_level["moderate"],
                     **by_scenario.to_dict()})
    return rows


def evaluate(name, params, seeds, **kw):
    return pd.DataFrame([r for s in seeds for r in run(name, params, s, **kw)])


def search(name):
    grid = combos(name)
    results = Parallel(n_jobs=-1)(
        delayed(evaluate)(name, p, SEARCH_SEEDS) for p in grid)
    table = pd.DataFrame([
        {**p, **r[["fpr", "recall", "recall_mild", "recall_moderate", "pr_auc"]].mean()}
        for p, r in zip(grid, results)])
    table.to_csv(OUT / f"grid_{name}.csv", index=False)
    ok = table[table.fpr <= MAX_FPR]
    best = grid[ok.sort_values(["recall", "pr_auc"], ascending=False).index[0]]
    print(f"\n{name}: {len(grid)} configurations, {len(ok)} within the FPR limit")
    for p in GRIDS[name]:
        print(f"  effect of {p} (mean over the other settings)")
        print(table.groupby(table[p].astype(str))[["recall", "fpr", "pr_auc"]]
              .mean().round(3).to_string())
    print("  top 5 within limit\n", ok.nlargest(5, "recall").round(3).to_string(index=False))
    return best


def per_mode_check(best):
    """Does one global model treat the six transport/DNSSEC modes fairly?"""
    rows, purity = [], []
    for name, params in best.items():
        for seed in CONFIRM_SEEDS:
            pipeline, train, calibration, normal = fit(name, params, seed)
            threshold = np.quantile(anomaly_scores(pipeline, calibration), QUANTILE)
            for part, frame in (("fpr", normal), ("recall", dev)):
                hit = anomaly_scores(pipeline, frame) >= threshold
                for (t, d), idx in frame.groupby(["transport", "dnssec"]).indices.items():
                    sub = frame.iloc[idx]
                    # equal weight per scenario, as in the main recall figure
                    value = (pd.Series(hit[idx]).groupby(sub.scenario.to_numpy())
                             .mean().mean())
                    rows.append({"model": name, "variant": "global", "seed": seed,
                                 "mode": f"{t}/{d}", "measure": part, "value": value})
            if name == "lof":
                Z = pipeline[:-1].transform(train[FEATURES])
                nn = pipeline[-1].kneighbors(n_neighbors=params["n_neighbors"],
                                             return_distance=False)
                mode = (train.transport + "/" + train.dnssec.astype(str)).to_numpy()
                purity.append({
                    "same_mode": np.mean(mode[nn] == mode[:, None]),
                    "same_transport": np.mean(
                        train.transport.to_numpy()[nn]
                        == train.transport.to_numpy()[:, None])})

    # LOF with one model per mode, thresholds from pooled calibration scores
    for seed in CONFIRM_SEEDS:
        train, calibration, test = split_data(data, seed)
        frames = {"cal": calibration, "fpr": test[test.label == 0], "recall": dev}
        scores = {k: pd.Series(np.nan, index=f.index) for k, f in frames.items()}
        for t, d in itertools.product(("classic", "dot", "doh"), (0, 1)):
            pipeline = build_pipeline("lof", seed)
            pipeline.set_params(**{f"model__{k}": v for k, v in best["lof"].items()})
            pipeline.set_params(model__n_neighbors=min(best["lof"]["n_neighbors"], 50))
            pipeline.fit(train[(train.transport == t) & (train.dnssec == d)][FEATURES])
            for k, f in frames.items():
                m = (f.transport == t) & (f.dnssec == d)
                scores[k][m] = anomaly_scores(pipeline, f[m])
        threshold = scores["cal"].quantile(QUANTILE)
        for part in ("fpr", "recall"):
            f = frames[part]
            for (t, d), g in f.groupby(["transport", "dnssec"]):
                value = ((scores[part][g.index] >= threshold)
                         .groupby(g.scenario).mean().mean())
                rows.append({"model": "lof", "variant": "one_per_mode", "seed": seed,
                             "mode": f"{t}/{d}", "measure": part, "value": value})

    table = pd.DataFrame(rows)
    table.to_csv(OUT / "per_mode.csv", index=False)
    print("\nPer transport/DNSSEC mode (30 splits)\n",
          table.pivot_table("value", ["measure", "mode"], ["model", "variant"])
          .round(3).to_string())
    print("\nOverall by variant\n",
          table.groupby(["model", "variant", "measure"]).value.mean().round(3))
    print("\nLOF neighbour purity", pd.DataFrame(purity).mean().round(3).to_dict())


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    best = {name: search(name) for name in GRIDS}

    confirm, thresholds = [], []
    for name in GRIDS:
        initial = {k: v for k, v in MODEL_CONFIGS[name].items() if k in GRIDS[name]}
        if name == "lof":
            initial["metric"] = "euclidean"  # same as minkowski, p=2
        for label, params in (("initial", initial), ("selected", best[name])):
            r = evaluate(name, params, CONFIRM_SEEDS, quantiles=QUANTILES)
            r.insert(0, "model", name)
            r.insert(1, "config", label)
            thresholds.append(r)
            confirm.append({"model": name, "config": label, "params": str(params)})
    runs = pd.concat(thresholds)
    runs.to_csv(OUT / "confirmation_runs.csv", index=False)
    mean = runs.drop(columns="seed").groupby(["model", "config", "quantile"]).mean()
    mean.to_csv(OUT / "threshold_tradeoff.csv")
    print("\nSelected:", best)
    pd.DataFrame(confirm).to_csv(OUT / "configs.csv", index=False)
    print("\nConfirmation at 95th percentile (30 new splits)\n",
          mean.xs(QUANTILE, level="quantile").T.round(3).to_string())
    spread = runs[runs["quantile"] == QUANTILE].groupby(["model", "config"])[["recall", "fpr"]]
    print(spread.agg(["min", "max"]).round(3).to_string())
    print("\nThreshold trade-off (selected)\n",
          mean.xs("selected", level="config")[["fpr", "recall"]].round(3).to_string())

    print("\nScaling (selected parameters)")
    rows = []
    for name in ("one_class_svm", "lof"):
        for label, scaler in (("none", "passthrough"), ("standard", StandardScaler()),
                              ("robust", RobustScaler())):
            r = evaluate(name, best[name], CONFIRM_SEEDS, scaler=scaler)
            rows.append({"model": name, "scaler": label,
                         **r[["recall", "fpr", "pr_auc"]].mean()})
    pd.DataFrame(rows).to_csv(OUT / "scaling.csv", index=False)
    print(pd.DataFrame(rows).round(3).to_string(index=False))

    print("\ncontamination check: predictions changed after recalibration?")
    for name in ("isolation_forest", "lof"):
        flags = []
        for c in ("auto", 0.01, 0.10):
            p, _, cal, _ = fit(name, {**best[name], "contamination": c}, 0)
            flags.append(anomaly_scores(p, dev)
                         >= np.quantile(anomaly_scores(p, cal), QUANTILE))
        print(f"  {name}: {int(sum((f != flags[0]).sum() for f in flags))} rows differ")

    # Reference: a trivial rule, any numeric value outside the training range
    ref = []
    num = [f for f in FEATURES if f != "transport"]
    for seed in CONFIRM_SEEDS:
        train, _, test = split_data(data, seed)
        out = lambda f: ((f[num] > train[num].max()) | (f[num] < train[num].min())).any(axis=1)
        ref.append({"recall": out(dev).groupby(dev.scenario).mean().mean(),
                    "fpr": out(test[test.label == 0]).mean()})
    print("\nRange rule reference:", pd.DataFrame(ref).mean().round(3).to_dict())

    per_mode_check(best)


if __name__ == "__main__":
    main()
