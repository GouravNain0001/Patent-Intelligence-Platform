import pandas as pd
from pathlib import Path


# Project root directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Data directory
DATA_DIR = BASE_DIR / "data"

# Input and output files
RAW_FILE = DATA_DIR / "raw_patents.csv"
CLEAN_FILE = DATA_DIR / "clean_patents.csv"


def load_data():
    print("Loading patent dataset...")

    if not RAW_FILE.exists():
        print("ERROR: raw_patents.csv not found!")
        print(f"Put your dataset here: {RAW_FILE}")
        return

    df = pd.read_csv(RAW_FILE)

    print("\nDataset loaded successfully!")
    print("Rows:", len(df))
    print("Columns:", len(df.columns))

    print("\nColumns:")
    print(df.columns.tolist())

    print("\nFirst 5 records:")
    print(df.head())

    return df


def clean_data(df):

    print("\nCleaning data...")

    # Remove duplicate rows
    df = df.drop_duplicates()

    # Remove completely empty rows
    df = df.dropna(how="all")

    # Convert column names to lowercase
    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(" ", "_")
    )

    print("Cleaning completed.")
    print("Remaining rows:", len(df))

    return df


def save_data(df):

    df.to_csv(CLEAN_FILE, index=False)

    print("\nClean dataset saved at:")
    print(CLEAN_FILE)


if __name__ == "__main__":

    df = load_data()

    if df is not None:
        df = clean_data(df)
        save_data(df)

        print("\nSTEP 6 completed successfully!")
        