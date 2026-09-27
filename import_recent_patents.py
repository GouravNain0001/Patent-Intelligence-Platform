import requests
from bs4 import BeautifulSoup
import mysql.connector
import time
import re


# =========================================================
# DATABASE
# =========================================================

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "1234567",
    "database": "patent_intelligence"
}


# =========================================================
# REAL PATENTS
# =========================================================

PATENTS = {

    # ---------------- AI ----------------
    "US20250068764A1": "AI",
    "US20240037096A1": "AI",
    "US20250087342A1": "Healthcare AI",
    "US20240362499A1": "AI",
    "US20240386041A1": "AI",
    "US20250165755A1": "AI",

    # ---------------- HEALTHCARE ----------------
    "US20240404659A1": "Healthcare AI",
    "US20240215945A1": "Healthcare AI",
    "US20240203560A1": "Healthcare AI",
    "US20240412866A1": "Healthcare AI",
    "US20240428941A1": "Healthcare AI",

    # ---------------- SEMICONDUCTOR ----------------
    "US20240014284A1": "Semiconductor",
    "US20240250031A1": "Semiconductor",
    "US20240427489A1": "Semiconductor",
    "US20240014311A1": "Semiconductor",
    "US20240413222A1": "Semiconductor",

    # ---------------- ELECTRIC VEHICLE ----------------
    "US20240262176A1": "Electric Vehicle",
    "US20240239220A1": "Electric Vehicle",
    "US20240222760A1": "Electric Vehicle",
    "US20240297360A1": "Electric Vehicle",
    "US20250058617A1": "Electric Vehicle",
    "US20240326613A1": "Electric Vehicle",
    "US20250135989A1": "Electric Vehicle",

    # ---------------- COMMUNICATION ----------------
    "US20240064043A1": "Communication",
    "US20230080036A1": "Communication",
    "US20230379872A1": "Communication",

    # ---------------- RENEWABLE ENERGY ----------------
    "US20250072123A1": "Renewable Energy",
    "US20250081632A1": "Renewable Energy",
    "US20230025362A1": "Renewable Energy"
}


# =========================================================
# GOOGLE PATENTS SCRAPER
# =========================================================

def fetch_patent(publication_number, domain):

    url = (
        f"https://patents.google.com/"
        f"patent/{publication_number}/en"
    )

    pdf_url = (
        f"https://patents.google.com/"
        f"patent/{publication_number}/en.pdf"
    )

    headers = {
        "User-Agent":
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/120 Safari/537.36"
    }

    try:

        response = requests.get(
            url,
            headers=headers,
            timeout=30
        )

        response.raise_for_status()

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )


        # -------------------------------------------------
        # TITLE
        # -------------------------------------------------

        title = ""

        meta = soup.find(
            "meta",
            attrs={"name": "DC.title"}
        )

        if meta:
            title = meta.get("content", "")

        if not title:

            h1 = soup.find("h1")

            if h1:
                title = h1.get_text(
                    " ",
                    strip=True
                )


        # -------------------------------------------------
        # ABSTRACT
        # -------------------------------------------------

        abstract = ""

        meta = soup.find(
            "meta",
            attrs={"scheme": "abstract"}
        )

        if meta:
            abstract = meta.get(
                "content",
                ""
            )


        if not abstract:

            abstract_tag = soup.find(
                "div",
                class_="abstract"
            )

            if abstract_tag:
                abstract = abstract_tag.get_text(
                    " ",
                    strip=True
                )


        # -------------------------------------------------
        # DATES
        # -------------------------------------------------

        filing_date = ""
        publication_date = ""

        # Extract all DC.date meta tags
        date_metas = soup.find_all("meta", attrs={"name": "DC.date"})
        for meta_tag in date_metas:
            scheme = meta_tag.get("scheme", "").lower()
            content = meta_tag.get("content", "").strip()
            if scheme == "datesubmitted":
                if not filing_date:
                    filing_date = content
            else:
                if not publication_date and content:
                    publication_date = content

        # Additional meta tag fallbacks for publication date
        if not publication_date:
            for attr_key, attr_val in [
                ("name", "citation_publication_date"),
                ("name", "DC.date.issued"),
                ("scheme", "datePublished"),
                ("scheme", "issue"),
                ("scheme", "date")
            ]:
                tag = soup.find("meta", attrs={attr_key: attr_val})
                if tag and tag.get("content"):
                    publication_date = tag.get("content").strip()
                    break

        # Fallback to publication number year (e.g. US20240037096A1 -> 2024)
        if not publication_date and publication_number:
            match = re.search(r"US(\d{4})", publication_number, re.IGNORECASE)
            if match:
                publication_date = f"{match.group(1)}-01-01"


        # -------------------------------------------------
        # ASSIGNEE
        # -------------------------------------------------

        assignee = ""

        assignee_meta = soup.find(
            "meta",
            attrs={
                "scheme": "assignee"
            }
        )

        if assignee_meta:
            assignee = assignee_meta.get("content", "")

        if not assignee:
            assignee_meta = soup.find(
                "meta",
                attrs={
                    "name": "DC.contributor"
                }
            )
            if assignee_meta:
                assignee = assignee_meta.get("content", "")


        # -------------------------------------------------
        # CLEAN
        # -------------------------------------------------

        title = title.strip()
        abstract = abstract.strip()
        filing_date = filing_date.strip()
        publication_date = publication_date.strip()
        assignee = assignee.strip()


        return {
            "publication_number":
                publication_number,

            "title":
                title,

            "abstract":
                abstract,

            "filing_date":
                filing_date,

            "publication_date":
                publication_date,

            "domain":
                domain,

            "assignee":
                assignee,

            "source_url":
                url,

            "pdf_url":
                pdf_url
        }


    except Exception as e:

        print(
            f"ERROR: {publication_number} -> {e}"
        )

        return None


# =========================================================
# DATABASE INSERT
# =========================================================

def insert_patent(data):

    conn = mysql.connector.connect(
        **DB_CONFIG
    )

    cursor = conn.cursor()


    query = """
    INSERT INTO recent_patents
    (
        publication_number,
        title,
        abstract,
        filing_date,
        publication_date,
        domain,
        assignee,
        source_url,
        pdf_url
    )
    VALUES
    (
        %s,%s,%s,%s,%s,%s,%s,%s,%s
    )
    ON DUPLICATE KEY UPDATE

        title = VALUES(title),
        abstract = VALUES(abstract),
        filing_date = VALUES(filing_date),
        publication_date = VALUES(publication_date),
        domain = VALUES(domain),
        assignee = VALUES(assignee),
        source_url = VALUES(source_url),
        pdf_url = VALUES(pdf_url)
    """


    values = (
        data["publication_number"],
        data["title"],
        data["abstract"],
        data["filing_date"],
        data["publication_date"],
        data["domain"],
        data["assignee"],
        data["source_url"],
        data["pdf_url"]
    )


    cursor.execute(
        query,
        values
    )

    conn.commit()

    cursor.close()
    conn.close()


# =========================================================
# MAIN
# =========================================================

print()
print("=" * 45)
print("Starting recent patent import...")
print("=" * 45)
print()


success = 0


for publication_number, domain in PATENTS.items():

    print(
        f"Fetching {publication_number}..."
    )

    data = fetch_patent(
        publication_number,
        domain
    )


    if data:

        insert_patent(data)

        print(
            f"SUCCESS: {publication_number}"
        )

        success += 1

    else:

        print(
            f"FAILED: {publication_number}"
        )


    time.sleep(1)


print()
print("=" * 45)
print(
    f"Recent patent import completed"
)
print(
    f"Imported / updated: {success}"
)
print("=" * 45)
print()
