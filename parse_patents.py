from pathlib import Path
import re
import csv


# =========================================================
# PROJECT PATHS
# =========================================================

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"

XML_FILE = DATA_DIR / "ipg161011.xml"
OUTPUT_FILE = DATA_DIR / "raw_patents.csv"


# =========================================================
# TEXT CLEANING
# =========================================================

def clean_text(text):
    if not text:
        return ""

    # Remove excessive whitespace
    text = re.sub(r"\s+", " ", text)

    return text.strip()


# =========================================================
# XML TAG EXTRACTION
# =========================================================

def extract_tag(text, tag):
    """
    Extract content from a simple XML tag.

    Example:
        <doc-number>09462737</doc-number>

    Returns:
        09462737
    """

    pattern = rf"<{tag}[^>]*>(.*?)</{tag}>"

    match = re.search(
        pattern,
        text,
        re.DOTALL
    )

    if match:
        return clean_text(match.group(1))

    return ""


# =========================================================
# PATENT PARSER
# =========================================================

def parse_patents():

    # -----------------------------------------------------
    # Check XML file
    # -----------------------------------------------------

    if not XML_FILE.exists():

        print("ERROR: ipg161011.xml not found!")

        print(
            f"Expected location: {XML_FILE}"
        )

        return

    print("Reading patent XML file...")
    print("Please wait...")

    # -----------------------------------------------------
    # Read complete XML
    # -----------------------------------------------------

    with open(
        XML_FILE,
        "r",
        encoding="utf-8",
        errors="ignore"
    ) as file:

        content = file.read()

    # -----------------------------------------------------
    # Find individual patent documents
    # -----------------------------------------------------

    patents = re.findall(
        r"<us-patent-grant\b.*?</us-patent-grant>",
        content,
        re.DOTALL
    )

    print(
        "Patent documents found:",
        len(patents)
    )

    rows = []

    # =====================================================
    # PROCESS EACH PATENT
    # =====================================================

    for i, patent in enumerate(
        patents
    ):

        # -------------------------------------------------
        # Basic patent information
        # -------------------------------------------------

        patent_id = extract_tag(
            patent,
            "doc-number"
        )

        title = extract_tag(
            patent,
            "invention-title"
        )

        abstract = extract_tag(
            patent,
            "abstract"
        )

        # -------------------------------------------------
        # Initialize dates
        # -------------------------------------------------

        filing_date = ""
        issue_date = ""

        # =================================================
        # FILING DATE
        # =================================================

        application_match = re.search(
            r"<application-reference.*?<date>(.*?)</date>",
            patent,
            re.DOTALL
        )

        if application_match:

            filing_date = clean_text(
                application_match.group(1)
            )

        # =================================================
        # ISSUE / GRANT DATE
        # =================================================
        #
        # IMPORTANT:
        #
        # Earlier code was incorrectly using:
        #
        # <publication-reference>
        #
        # That gave 20161011 for every patent because
        # ipg161011.xml represents the 11-Oct-2016
        # publication/grant issue batch.
        #
        # The actual patent grant/issue date is stored in:
        #
        # <date-of-grant>
        #
        # =================================================

        grant_match = re.search(
            r"<date-of-grant>(.*?)</date-of-grant>",
            patent,
            re.DOTALL
        )

        if grant_match:

            issue_date = clean_text(
                grant_match.group(1)
            )

        # -------------------------------------------------
        # Save patent record
        # -------------------------------------------------

        rows.append(
            {
                "patent_id": patent_id,
                "title": title,
                "abstract": abstract,
                "filing_date": filing_date,
                "issue_date": issue_date
            }
        )

        # -------------------------------------------------
        # Progress
        # -------------------------------------------------

        if (i + 1) % 500 == 0:

            print(
                f"Processed: {i + 1}"
            )

    # =====================================================
    # WRITE CSV
    # =====================================================

    with open(
        OUTPUT_FILE,
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=[
                "patent_id",
                "title",
                "abstract",
                "filing_date",
                "issue_date"
            ]
        )

        writer.writeheader()

        writer.writerows(rows)

    # =====================================================
    # SUCCESS MESSAGE
    # =====================================================

    print("\nSUCCESS!")

    print(
        "CSV created:"
    )

    print(
        OUTPUT_FILE
    )

    print(
        "Total patents:",
        len(rows)
    )


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    parse_patents()