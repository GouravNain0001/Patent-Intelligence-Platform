from pathlib import Path
import pandas as pd
import mysql.connector

BASE_DIR = Path(__file__).resolve().parent.parent
CSV_FILE = BASE_DIR / "data" / "processed_patents.csv"


def create_database():

    print("Loading processed patents...")

    df = pd.read_csv(CSV_FILE)

    print("Patents loaded:", len(df))

    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="1234567",
        database="patent_intelligence"
    )

    cursor = conn.cursor()

    insert_query = """
        INSERT INTO patents
        (patent_id, title, abstract, filing_date, issue_date, search_text)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            title = VALUES(title),
            abstract = VALUES(abstract),
            filing_date = VALUES(filing_date),
            issue_date = VALUES(issue_date),
            search_text = VALUES(search_text)
    """

    data = []

    for _, row in df.iterrows():
        data.append((
            str(row["patent_id"]),
            str(row["title"]),
            str(row["abstract"]) if pd.notna(row["abstract"]) else "",
            str(row["filing_date"]),
            str(row["issue_date"]),
            str(row["search_text"])
        ))

    cursor.executemany(insert_query, data)

    conn.commit()

    cursor.close()
    conn.close()

    print("\nSUCCESS!")
    print("MySQL database: patent_intelligence")
    print("Table: patents")
    print("Total patents:", len(data))


if __name__ == "__main__":
    create_database()
