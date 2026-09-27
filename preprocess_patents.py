from pathlib import Path
import pandas as pd
import re

BASE_DIR = Path(__file__).resolve().parent.parent

INPUT_FILE = BASE_DIR / "data" / "raw_patents.csv"
OUTPUT_FILE = BASE_DIR / "data" / "processed_patents.csv"


def clean_text(text):
    if pd.isna(text):
        return ""

    text = str(text)
    text = re.sub(r"\s+", " ", text)
    text = text.strip()

    return text


def preprocess():
    print("Loading patent data...")

    df = pd.read_csv(INPUT_FILE)

    print("Original patents:", len(df))

    # Clean text columns
    df["title"] = df["title"].apply(clean_text)
    df["abstract"] = df["abstract"].apply(clean_text)

    # Clean IDs and dates
    df["patent_id"] = df["patent_id"].astype(str).str.strip()

    df["filing_date"] = df["filing_date"].astype(str).str.strip()
    df["issue_date"] = df["issue_date"].astype(str).str.strip()

    # Remove duplicate patents
    df = df.drop_duplicates(subset=["patent_id"])

    # Remove rows without title
    df = df[df["title"] != ""]

    # Create combined text for future search/AI
    df["search_text"] = (
        df["title"] + " " + df["abstract"]
    ).str.strip()

    # Save processed data
    df.to_csv(OUTPUT_FILE, index=False)

    print("\nSUCCESS!")
    print("Processed patents:", len(df))
    print("Output file:")
    print(OUTPUT_FILE)


if __name__ == "__main__":
    preprocess()
