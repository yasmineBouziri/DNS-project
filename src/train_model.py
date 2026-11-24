
"""
Train and calibrate an Isolation Forest for DNS anomaly detection.

Run from project root:
    python src/train_model.py

Trains only on normal traffic.
Uses held-out normal traffic to calibrate the anomaly threshold.
Saves a separate test dataset containing held-out normal + attack rows.
"""

from pathlib import Path

import joblib
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.ensemble import IsolationForest
from sklearn.impute import SimpleImputer
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


ROOT = Path(__file__).resolve().parent.parent

DATA_PATH = ROOT / "data" / "simulated_dns_data.csv"
MODEL_PATH = ROOT / "models" / "isolation_forest.joblib"
TEST_PATH = ROOT / "results" / "test_data.csv"

CATEGORICAL_FEATURES = ["transport"]

NUMERIC_FEATURES = [
    "dnssec",
    "query_rate",
    "avg_latency",
    "error_rate",
    "servfail_rate",
    "nxdomain_rate",
    "avg_response_size",
    "unique_domain_ratio",
    "cpu_usage",
    "memory_usage",
]

FEATURES = CATEGORICAL_FEATURES + NUMERIC_FEATURES

RANDOM_STATE = 42
N_ESTIMATORS = 150

# Initial calibration target: 5% of held-out normal observations
# should fall above the threshold.
TARGET_FALSE_POSITIVE_RATE = 0.05


def build_pipeline():
    categorical_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore")),
        ]
    )

    numeric_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
        ]
    )

    preprocessor = ColumnTransformer(
        transformers=[
            ("categorical", categorical_pipeline, CATEGORICAL_FEATURES),
            ("numeric", numeric_pipeline, NUMERIC_FEATURES),
        ]
    )

    isolation_forest = IsolationForest(
        n_estimators=N_ESTIMATORS,
        contamination="auto",
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )

    return Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("model", isolation_forest),
        ]
    )


def main():
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Dataset not found: {DATA_PATH}")

    data = pd.read_csv(DATA_PATH)

    required = FEATURES + ["label", "scenario", "timestamp"]
    missing = [col for col in required if col not in data.columns]

    if missing:
        raise ValueError(f"Missing columns: {missing}")

    normal = data[data["label"] == 0].copy()
    attacks = data[data["label"] == 1].copy()

    if normal.empty or attacks.empty:
        raise ValueError("Dataset must contain both normal and attack rows.")

    # Split normal data: 70% training, 30% calibration/testing.
    normal_train, normal_test = train_test_split(
        normal,
        test_size=0.30,
        random_state=RANDOM_STATE,
        shuffle=True,
    )

    # The model sees only normal training observations.
    X_train = normal_train[FEATURES]

    print(f"Normal training observations: {len(normal_train)}")
    print(f"Normal held-out observations: {len(normal_test)}")
    print(f"Attack test observations: {len(attacks)}")

    pipeline = build_pipeline()

    print("\nTraining Isolation Forest...")
    pipeline.fit(X_train)

    # Higher score = more anomalous.
    normal_scores = -pipeline.decision_function(normal_test[FEATURES])

    # Set the threshold using ONLY held-out normal observations.
    threshold = float(
    pd.Series(normal_scores).quantile(
        1 - TARGET_FALSE_POSITIVE_RATE
    )
)

    # Final test set: unseen normal + all attack observations.
    test_data = pd.concat(
        [normal_test, attacks],
        ignore_index=True,
    )

    TEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    test_data.to_csv(TEST_PATH, index=False)

    # Store both the pipeline and calibrated threshold.
    artifact = {
        "pipeline": pipeline,
        "threshold": threshold,
        "target_false_positive_rate": TARGET_FALSE_POSITIVE_RATE,
        "features": FEATURES,
    }

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, MODEL_PATH)

    print("\nTraining and calibration complete!")
    print(f"Calibrated anomaly threshold: {threshold:.6f}")
    print(f"Target false-positive rate: {TARGET_FALSE_POSITIVE_RATE:.0%}")
    print(f"Saved model: {MODEL_PATH}")
    print(f"Saved test dataset: {TEST_PATH}")


if __name__ == "__main__":
    main()
