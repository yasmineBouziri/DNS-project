
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent

REQUIRED_COLUMNS = [
    "timestamp",
    "transport",
    "dnssec",
    "query_rate",
    "avg_latency",
    "error_rate",
    "servfail_rate",
    "nxdomain_rate",
    "avg_response_size",
    "unique_domain_ratio",
    "cpu_usage",
    "memory_usage"
]

VALID_TRANSPORTS = ["classic", "dot", "doh"]

NUMERIC_COLUMNS = [
    "dnssec",
    "query_rate",
    "avg_latency",
    "error_rate",
    "servfail_rate",
    "nxdomain_rate",
    "avg_response_size",
    "unique_domain_ratio",
    "cpu_usage",
    "memory_usage"
]


def validate_data(df):

    errors = []

    # 1. Check required columns
    missing = [
        col for col in REQUIRED_COLUMNS
        if col not in df.columns
    ]

    if missing:
        errors.append(f"Missing columns: {missing}")
        return False, errors

    # 2. Check empty values
    if df[REQUIRED_COLUMNS].isnull().any().any():
        errors.append("Dataset contains missing values.")

    # 3. Check timestamp format
    timestamps = pd.to_datetime(
        df["timestamp"],
        errors="coerce",
        utc=True
    )

    if timestamps.isnull().any():
        errors.append("Invalid timestamp values.")

    # 4. Check transport
    invalid_transport = ~df["transport"].isin(VALID_TRANSPORTS)

    if invalid_transport.any():
        errors.append("Invalid transport values.")

    # 5. Check numeric columns
    for col in NUMERIC_COLUMNS:
        converted = pd.to_numeric(df[col], errors="coerce")

        if converted.isnull().any():
            errors.append(f"{col} contains non-numeric values.")
        else:
            df[col] = converted

    # 6. Check metric ranges
    percentage_columns = [
        "error_rate",
        "servfail_rate",
        "nxdomain_rate",
        "cpu_usage",
        "memory_usage"
    ]

    for col in percentage_columns:
        if not df[col].between(0, 100).all():
            errors.append(f"{col} must be between 0 and 100.")

    if not df["unique_domain_ratio"].between(0, 1).all():
        errors.append("unique_domain_ratio must be between 0 and 1.")

    if not df["dnssec"].isin([0, 1]).all():
        errors.append("dnssec must contain only 0 or 1.")

    non_negative_columns = [
        "query_rate",
        "avg_latency",
        "avg_response_size"
    ]

    for col in non_negative_columns:
        if (df[col] < 0).any():
            errors.append(f"{col} cannot be negative.")

    return len(errors) == 0, errors


def main():

    input_path = ROOT / "data" / "simulated_dns_data.csv"

    df = pd.read_csv(input_path)

    valid, errors = validate_data(df)

    print(f"\nDataset: {input_path.name}")
    print(f"Rows: {len(df)}")

    if valid:
        print("\n DATA VALIDATION PASSED!")
        print("The dataset is ready for the detection pipeline.")
    else:
        print("\n DATA VALIDATION FAILED!")

        for error in errors:
            print(f"- {error}")


if __name__ == "__main__":
    main()
