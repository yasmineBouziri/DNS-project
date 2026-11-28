"""Create the fixed train / calibration / test files used by all models."""

import pandas as pd

from common import DATA_DIR, SOURCE_PATH, split_data


def main():
    data = pd.read_csv(SOURCE_PATH)
    train, calibration, test = split_data(data)

    ids = [set(train.timestamp), set(calibration.timestamp), set(test.timestamp)]
    assert not (ids[0] & ids[1] or ids[0] & ids[2] or ids[1] & ids[2]), "overlap"

    for name, part in [("train", train), ("calibration", calibration), ("test", test)]:
        part.to_csv(DATA_DIR / f"{name}_data.csv", index=False)
        print(f"{name:12s} rows={len(part):4d} attacks={int(part.label.sum())}")


if __name__ == "__main__":
    main()
