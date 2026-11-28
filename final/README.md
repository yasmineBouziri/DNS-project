# Final Version: DNS Anomaly Detection

This folder is the final, self-contained version of the work. Earlier scripts,
experiments and results stay in the main project folder.

Model: Local Outlier Factor (35 neighbours, Manhattan distance), per-mode
relative query rate and latency, threshold at the 97.5th percentile of normal
calibration scores. Phase 7 (hybrid detector) was not carried out.

## Run (from inside this folder)

```bash
pip install -r requirements.txt
python src/train_model.py
python src/detect.py --input data/final_test_data.csv
python src/evaluate_model.py
python src/visualize.py
```

## Result on the final synthetic test set

| Recall | Precision | F1 | False-positive rate |
|---:|---:|---:|---:|
| 98.9% (617 of 624) | 98.1% | 0.985 | 2.0% (12 of 600) |

All data is synthetic. A simple range rule performs almost as well (98.2% recall,
2.2% false positives), and performance on real DNS traffic is unknown.
