import mysql.connector


def get_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="1234567",
        database="patent_intelligence"
    )


def search_patents(keyword):

    conn = get_connection()
    cursor = conn.cursor()

    query = """
        SELECT patent_id, title, abstract, filing_date, issue_date
        FROM patents
        WHERE title LIKE %s
           OR abstract LIKE %s
           OR patent_id LIKE %s
        LIMIT 20
    """

    search_term = f"%{keyword}%"

    cursor.execute(
        query,
        (search_term, search_term, search_term)
    )

    results = cursor.fetchall()

    cursor.close()
    conn.close()

    return results


if __name__ == "__main__":

    keyword = input("Enter patent keyword: ").strip()

    if not keyword:
        print("Please enter a keyword.")
    else:

        results = search_patents(keyword)

        print("\nSearch Results:")
        print("-" * 80)

        if not results:
            print("No patents found.")

        else:
            for patent in results:

                patent_id = patent[0]
                title = patent[1]
                abstract = patent[2] or ""
                filing_date = patent[3]
                issue_date = patent[4]

                print(f"\nPatent ID: {patent_id}")
                print(f"Title: {title}")
                print(f"Abstract: {abstract[:300]}")
                print(f"Filing Date: {filing_date}")
                print(f"Issue Date: {issue_date}")
                print("-" * 80)
            