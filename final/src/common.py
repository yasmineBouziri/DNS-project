"""
Everything the three models must share: features, splits, preprocessing,
threshold calibration and scoring. Change the methodology here and it changes
for all models at once.
"""

from pathlib import Path

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import IsolationForest
from sklearn.impute import SimpleImputer
from sklearn.model_selection import train_test_split
from sklearn.neighbors import LocalOutlierFactor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.svm import OneClassSVM

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
MODELS_DIR = ROOT / "models"
RESULTS_DIR = ROOT / "results"
SOURCE_PATH = DATA_DIR / "simulated_dns_data.csv"

CATEGORICAL_FEATURES = ["transport"]
NUMERIC_FEATURES = [
    "dnssec", "query_rate", "avg_latency", "error_rate", "servfail_rate",
    "nxdomain_rate", "avg_response_size", "unique_domain_ratio",
    "cpu_usage", "memory_usage",
]
FEATURES = CATEGORICAL_FEATURES + NUMERIC_FEATURES

SEED = 42
QUANTILE = 0.95  # threshold = 95th percentile of normal calibration scores

# Initial, untuned configurations. Tuning is a later phase.
MODEL_CONFIGS = {
    "isolation_forest": {"n_estimators": 150, "contamination": "auto"},
    "one_class_svm": {"kernel": "rbf", "nu": 0.05, "gamma": "scale"},
    "lof": {"n_neighbors": 20, "metric": "minkowski", "novelty": True},
}


def split_data(data, seed=SEED):
    """Normal rows: 70/15/15, balanced by transport x DNSSEC. Attacks: test only."""
    normal = data[data["label"] == 0]
    attacks = data[data["label"] == 1]
    mode = normal["transport"] + "_" + normal["dnssec"].astype(str)

    train, rest = train_test_split(
        normal, test_size=0.30, random_state=seed, stratify=mode
    )
    calibration, normal_test = train_test_split(
        rest, test_size=0.50, random_state=seed, stratify=mode[rest.index]
    )
    test = pd.concat([normal_test, attacks])
    return train, calibration, test


def load_splits():
    paths = [DATA_DIR / f"{n}_data.csv" for n in ("train", "calibration", "test")]
    if not all(p.exists() for p in paths):
        raise FileNotFoundError("Splits not found. Run prepare_data.py first.")
    return [pd.read_csv(p) for p in paths]


def build_pipeline(name, seed=SEED):
    params = MODEL_CONFIGS[name]
    numeric_steps = [("imputer", SimpleImputer(strategy="median"))]

    if name == "isolation_forest":  # tree splits do not depend on scale
        model = IsolationForest(random_state=seed, n_jobs=-1, **params)
    else:  # SVM and LOF use distances, so features must be comparable
        numeric_steps.append(("scaler", StandardScaler()))
        cls = OneClassSVM if name == "one_class_svm" else LocalOutlierFactor
        model = cls(**params)

    categorical = Pipeline([
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("onehot", OneHotEncoder(handle_unknown="ignore")),
    ])
    preprocessor = ColumnTransformer([
        ("categorical", categorical, CATEGORICAL_FEATURES),
        ("numeric", Pipeline(numeric_steps), NUMERIC_FEATURES),
    ])
    return Pipeline([("preprocessor", preprocessor), ("model", model)])


def anomaly_scores(pipeline, data):
    """Same convention for every model: higher = more unusual."""
    return -pipeline.decision_function(data[FEATURES])


def fit_and_calibrate(name, train, calibration, seed=SEED):
    if train["label"].any() or calibration["label"].any():
        raise ValueError("Training and calibration data must be normal only.")
    pipeline = build_pipeline(name, seed).fit(train[FEATURES])
    scores = anomaly_scores(pipeline, calibration)
    threshold = float(pd.Series(scores).quantile(QUANTILE))
    return pipeline, threshold


def train_and_save(name):
    train, calibration, _ = load_splits()
    pipeline, threshold = fit_and_calibrate(name, train, calibration)
    path = MODELS_DIR / name / "model.joblib"
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({
        "name": name,
        "pipeline": pipeline,
        "threshold": threshold,
        "threshold_quantile": QUANTILE,
        "features": FEATURES,
        "config": MODEL_CONFIGS[name],
        "seed": SEED,
    }, path)
    print(f"{name}: threshold={threshold:.6f} saved to {path.relative_to(ROOT)}")
