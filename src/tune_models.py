"""
Phase 5: tuning with the relative features. Development data only.

Custom search (GridSearchCV is not used because training has no attack rows):
for each setting and seed, fit on normal training rows, set the threshold on
normal calibration rows, then measure false positives on other normal rows and
recall on the development attacks.

Selection rule: mean false positive rate <= 6.5%, then highest mean
per-scenario recall (PR-AUC breaks ties). Search seeds and confirmation seeds
are different. The final test set is never read.
"""

import itertools
import json

import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from sklearn.metrics import average_precision_score

from common import FEATURES, RESULTS_DIR, split_data
from feature_experiments import VARIANTS, data, dev, make

OUT = RESULTS_DIR / "phase5"
SEARCH, CONFIRM = range(300, 310), range(400, 430)
MAX_FPR = 0.065
QUANTILES = (0.95, 0.975, 0.99)

GRIDS = {
    "isolation_forest": (["relative_add"], {
        "n_estimators": [150, 300], "max_samples": [0.5, 1.0],
        "max_features": [0.5, 0.75, 1.0]}),
    "one_class_svm": (["relative_replace", "relative_add"], {
        "nu": [0.01, 0.03, 0.05, 0.1], "gamma": [0.01, 0.03, 0.1, 0.3, 1.0]}),
    "lof": (["relative_replace", "relative_add"], {
        "n_neighbors": [3, 5, 10, 20, 35, 50],
        "metric": ["euclidean", "manhattan", "chebyshev"]}),
}


def evaluate(name, variant, params, seed, quantiles=(0.95,)):
    train, calibration, test = split_data(data, seed)
    normal = test[test.label == 0]
    pipeline = make(name, VARIANTS[variant], seed)
    pipeline.set_params(**{f"model__{k}": v for k, v in params.items()})
    pipeline.fit(train[FEATURES])
    score = lambda f: -pipeline.decision_function(f[FEATURES])
    cal, s_normal, s_attack = score(calibration), score(normal), score(dev)
    pr_auc = average_precision_score(
        np.r_[np.zeros(len(s_normal)), np.ones(len(s_attack))], np.r_[s_normal, s_attack])
    rows = []
    for q in quantiles:
        threshold = np.quantile(cal, q)
        hit = pd.Series(s_attack >= threshold)
        per = hit.groupby(dev.scenario).mean()
        tp, fp = hit.sum(), (s_normal >= threshold).sum()
        precision, recall_all = tp / (tp + fp), hit.mean()
        rows.append({"quantile": q, "fpr": fp / len(s_normal), "recall": per.mean(),
                     "precision": precision,
                     "f1": 2 * precision * recall_all / (precision + recall_all),
                     "pr_auc": pr_auc, **per.to_dict()})
    return rows


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    pd.set_option("display.width", 200)
    chosen = {}
    for name, (variants, grid) in GRIDS.items():
        combos = [(v, dict(zip(grid, values))) for v in variants
                  for values in itertools.product(*grid.values())]
        results = Parallel(n_jobs=-1)(
            delayed(evaluate)(name, v, p, s) for v, p in combos for s in SEARCH)
        runs = pd.DataFrame([r[0] for r in results])
        mean = runs.groupby(np.arange(len(runs)) // len(SEARCH)).mean()
        table = pd.concat([pd.DataFrame([{"features": v, **p} for v, p in combos]),
                           mean[["fpr", "recall", "precision", "f1", "pr_auc"]]], axis=1)
        table.to_csv(OUT / f"search_{name}.csv", index=False)
        ok = table[table.fpr <= MAX_FPR].sort_values(["recall", "pr_auc"], ascending=False)
        variant, params = combos[ok.index[0]]
        chosen[name] = {"features": variant, "params": params}
        print(f"\n{name}: {len(combos)} settings, {len(ok)} within the limit\n",
              ok.head(5).round(3).to_string(index=False))

    rows = []
    for name, c in chosen.items():
        results = Parallel(n_jobs=-1)(delayed(evaluate)(
            name, c["features"], c["params"], s, QUANTILES) for s in CONFIRM)
        rows += [{"model": name, **r} for result in results for r in result]
    confirm = pd.DataFrame(rows).groupby(["model", "quantile"]).mean()
    confirm.to_csv(OUT / "confirmation.csv")
    (OUT / "selected_config.json").write_text(json.dumps(chosen, indent=2))
    print("\nSelected:", json.dumps(chosen))
    print("\nConfirmation on 30 new splits\n", confirm.T.round(3).to_string())


if __name__ == "__main__":
    main()
