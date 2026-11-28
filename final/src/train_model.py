"""
Train and calibrate the final DNS anomaly detector (Local Outlier Factor).

Run from project root:
    python src/train_model.py

Fits on normal traffic only, sets the threshold on separate normal traffic and
saves everything needed to reproduce predictions.
"""

import json

import joblib
import numpy as np
import pandas as pd
import sklearn

from common import FEATURES, MODELS_DIR, RESULTS_DIR, SEED, SOURCE_PATH, split_data
from dns_features import (MODEL_PARAMS, THRESHOLD_QUANTILE, build_final_pipeline,
                          score)
from validate_data import validate_data

MODEL_PATH = MODELS_DIR / "dns_detector.joblib"
TEST_PATH = RESULTS_DIR / "test_data.csv"


def main():
    data = pd.read_csv(SOURCE_PATH)
    valid, errors = validate_data(data)
    if not valid:
        raise ValueError(f"Invalid training data: {errors}")

    train, calibration, test = split_data(data, SEED)
    if train.label.any() or calibration.label.any():
        raise ValueError("Training and calibration data must be normal only.")

    pipeline = build_final_pipeline().fit(train[FEATURES])
    threshold = float(np.quantile(score(pipeline, calibration), THRESHOLD_QUANTILE))

    info = {
        "model": "LocalOutlierFactor",
        "model_params": MODEL_PARAMS,
        "features": FEATURES,
        "threshold": threshold,
        "threshold_quantile": THRESHOLD_QUANTILE,
        "seed": SEED,
        "training_rows": len(train),
        "calibration_rows": len(calibration),
        "sklearn_version": sklearn.__version__,
    }
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"pipeline": pipeline, **info}, MODEL_PATH)
    MODEL_PATH.with_suffix(".json").write_text(json.dumps(info, indent=2))

    TEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    test.to_csv(TEST_PATH, index=False)

    print(f"Training rows: {len(train)}   calibration rows: {len(calibration)}")
    print(f"Threshold ({THRESHOLD_QUANTILE:.1%} of calibration scores): {threshold:.6f}")
    print(f"Saved model: {MODEL_PATH}")
    print(f"Saved held-out data: {TEST_PATH}")


if __name__ == "__main__":
    main()
