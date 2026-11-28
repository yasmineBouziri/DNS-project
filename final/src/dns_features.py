"""
The final model's features and pipeline. The saved model refers to the class in
this file, so keep it in src/ and do not rename it without retraining.
"""

import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.neighbors import LocalOutlierFactor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from common import FEATURES, NUMERIC_FEATURES

MODE = ["transport", "dnssec"]
RELATIVE = ["query_rate", "avg_latency"]
MODEL_PARAMS = {"n_neighbors": 35, "metric": "manhattan", "novelty": True}
THRESHOLD_QUANTILE = 0.975


class RelativeToMode(BaseEstimator, TransformerMixin):
    """Add each metric divided by its normal median for the same transport x DNSSEC."""

    def fit(self, X, y=None):
        self.medians_ = X.groupby(MODE)[RELATIVE].median()
        return self

    def transform(self, X):
        out = X.copy()
        base = self.medians_.reindex(pd.MultiIndex.from_frame(X[MODE])).to_numpy()
        ratio = X[RELATIVE].to_numpy() / base
        for i, name in enumerate(RELATIVE):
            out[name + "_ratio"] = ratio[:, i]
        return out


def build_final_pipeline():
    numeric = NUMERIC_FEATURES + [name + "_ratio" for name in RELATIVE]
    columns = ColumnTransformer([
        ("categorical", OneHotEncoder(handle_unknown="ignore"), ["transport"]),
        ("numeric", StandardScaler(), numeric),
    ])
    return Pipeline([("relative", RelativeToMode()), ("columns", columns),
                     ("model", LocalOutlierFactor(**MODEL_PARAMS))])


def score(pipeline, data):
    """Higher = more unusual."""
    return -pipeline.decision_function(data[FEATURES])
