import mysql.connector
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def get_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="YOUR_MYSQL_PASSWORD",
        database="patent_intelligence"
    )


def load_patents():

    conn = get_connection()

    query = """
        SELECT patent_id, title, abstract, filing_date, issue_date
        FROM patents
    """

    df = pd.read_sql(query, conn)

    conn.close()

    df["abstract"] = df["abstract"].fillna("")

    df["text"] = (
        df["title"].fillna("") + " " +
        df["abstract"].fillna("")
    )

    return df


def find_similar_patents(patent_id, top_n=5):

    df = load_patents()

    if patent_id not in df["patent_id"].values:
        return pd.DataFrame()

    # TF-IDF converts patent text into numerical vectors
    vectorizer = TfidfVectorizer(
        stop_words="english",
        max_features=10000
    )

    tfidf_matrix = vectorizer.fit_transform(
        df["text"]
    )

    patent_index = df.index[
        df["patent_id"] == patent_id
    ][0]

    # Compare selected patent with every patent
    similarity_scores = cosine_similarity(
        tfidf_matrix[patent_index],
        tfidf_matrix
    ).flatten()

    df["similarity"] = similarity_scores

    # Remove the same patent
    df = df[
        df["patent_id"] != patent_id
    ]

    # Highest similarity first
    df = df.sort_values(
        "similarity",
        ascending=False
    )

    return df.head(top_n)
