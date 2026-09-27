import streamlit as st
import mysql.connector
import pandas as pd
import re
import os
import urllib.parse
from datetime import datetime
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="Patent Intelligence Platform",
    page_icon="🔬",
    layout="wide"
)

# =========================================================
# DATABASE
# =========================================================

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "1234567",
    "database": "patent_intelligence"
}

def get_connection():
    return mysql.connector.connect(**DB_CONFIG)

# =========================================================
# HELPERS
# =========================================================

def clean_text(text):
    if text is None:
        return ""
    text = re.sub(r"<[^>]+>", " ", str(text))
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def parse_date_value(value):
    """
    Convert common patent date formats into a pandas Timestamp.
    Supports:
    - YYYYMMDD
    - YYYY-MM-DD
    - YYYY/MM/DD
    - datetime/date values
    - strings containing a date
    """
    if value is None:
        return pd.NaT

    if isinstance(value, float) and pd.isna(value):
        return pd.NaT

    raw = str(value).strip()

    if raw.lower() in {"", "nan", "nat", "none", "null"}:
        return pd.NaT

    # Patent datasets commonly store dates as YYYYMMDD.
    if re.fullmatch(r"\d{8}", raw):
        parsed = pd.to_datetime(raw, format="%Y%m%d", errors="coerce")
        if pd.notna(parsed):
            return parsed

    # Normal date/datetime formats.
    parsed = pd.to_datetime(raw, errors="coerce")
    return parsed


def format_date(date):
    parsed = parse_date_value(date)

    if pd.notna(parsed):
        return parsed.strftime("%d %B %Y")

    # Keep the original value visible if it is a non-empty,
    # unrecognized database value.
    if date is None:
        return ""

    raw = str(date).strip()
    if raw.lower() in {"", "nan", "nat", "none", "null"}:
        return ""

    return raw

def safe_score(score):
    try:
        return float(score) * 100
    except Exception:
        return 0.0

def similarity_label(score):
    percentage = safe_score(score)
    if percentage >= 75:
        return "Very High", "Strong textual overlap"
    elif percentage >= 50:
        return "High", "Significant textual overlap"
    elif percentage >= 25:
        return "Moderate", "Some meaningful textual overlap"
    return "Low", "Limited textual overlap"

def similarity_bar(score):
    try:
        return min(max(float(score), 0.0), 1.0)
    except Exception:
        return 0.0

def display_value(value, fallback="Unknown"):
    text = clean_text(value)
    return text if text else fallback

# =========================================================
# LEGACY DATABASE
# =========================================================

def get_total_patents():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM patents")
    total = cursor.fetchone()[0]
    cursor.close()
    conn.close()
    return total

def search_patents(keyword, filing_year, limit):
    conn = get_connection()
    cursor = conn.cursor()

    query = """
        SELECT patent_id, title, abstract, filing_date, issue_date
        FROM patents
        WHERE (
            title LIKE %s
            OR abstract LIKE %s
            OR patent_id LIKE %s
        )
    """

    params = [f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"]

    if filing_year != "All":
        query += " AND filing_date LIKE %s"
        params.append(f"{filing_year}%")

    query += " LIMIT %s"
    params.append(limit)

    cursor.execute(query, tuple(params))
    results = cursor.fetchall()

    cursor.close()
    conn.close()
    return results

# =========================================================
# RECENT PATENTS
# =========================================================

def get_recent_patents():
    conn = get_connection()

    query = """
        SELECT
            publication_number,
            title,
            abstract,
            filing_date,
            publication_date,
            domain,
            assignee,
            source_url,
            pdf_url
        FROM recent_patents
        ORDER BY publication_date DESC
    """

    df = pd.read_sql(query, conn)
    conn.close()
    if not df.empty:
        df["_parsed_publication_date"] = df["publication_date"].apply(parse_date_value)
        df = df.sort_values("_parsed_publication_date", ascending=False, na_position="last")
        df = df.drop(columns=["_parsed_publication_date"])
    return df

# =========================================================
# RECENT TF-IDF DATA
# =========================================================

@st.cache_data
def load_recent_similarity_data():
    conn = get_connection()

    query = """
        SELECT
            publication_number,
            title,
            abstract,
            domain,
            assignee,
            filing_date,
            publication_date,
            source_url,
            pdf_url
        FROM recent_patents
    """

    df = pd.read_sql(query, conn)
    conn.close()

    if df.empty:
        return df, None, None

    df["title"] = df["title"].fillna("")
    df["abstract"] = df["abstract"].fillna("")

    df["search_text"] = (
        df["title"].apply(clean_text)
        + " "
        + df["abstract"].apply(clean_text)
    )

    vectorizer = TfidfVectorizer(
        stop_words="english",
        max_features=10000,
        min_df=1
    )

    matrix = vectorizer.fit_transform(df["search_text"])
    return df, vectorizer, matrix

def compare_recent_patents(patent_a, patent_b):
    df, vectorizer, matrix = load_recent_similarity_data()

    if df.empty:
        return None

    a = df.index[
        df["publication_number"].astype(str) == str(patent_a)
    ]
    b = df.index[
        df["publication_number"].astype(str) == str(patent_b)
    ]

    if len(a) == 0 or len(b) == 0:
        return None

    return cosine_similarity(
        matrix[a[0]],
        matrix[b[0]]
    )[0][0]

def find_similar_recent_patents(publication_number, top_n=5):
    df, vectorizer, matrix = load_recent_similarity_data()

    if df.empty:
        return pd.DataFrame()

    matches = df.index[
        df["publication_number"].astype(str)
        == str(publication_number)
    ]

    if len(matches) == 0:
        return pd.DataFrame()

    patent_index = matches[0]

    scores = cosine_similarity(
        matrix[patent_index],
        matrix
    ).flatten()

    result = df.copy()
    result["similarity"] = scores

    result = result[
        result["publication_number"].astype(str)
        != str(publication_number)
    ]

    return result.sort_values(
        "similarity",
        ascending=False
    ).head(top_n)

# =========================================================
# KEYWORDS
# =========================================================

def get_common_keywords(text_a, text_b):
    words_a = set(
        re.findall(r"\b[a-zA-Z]{4,}\b", clean_text(text_a).lower())
    )
    words_b = set(
        re.findall(r"\b[a-zA-Z]{4,}\b", clean_text(text_b).lower())
    )

    stop_words = {
        "this", "that", "with", "from", "using", "into",
        "such", "where", "which", "their", "there", "have",
        "been", "also", "than", "then", "they", "method",
        "system", "device", "data"
    }

    common = words_a & words_b - stop_words

    return sorted(
        common,
        key=lambda x: (-len(x), x)
    )[:15]

# =========================================================
# LEGACY SIMILARITY
# =========================================================

@st.cache_data
def load_legacy_similarity_data():
    conn = get_connection()

    query = """
        SELECT patent_id, title, abstract, filing_date, issue_date
        FROM patents
    """

    df = pd.read_sql(query, conn)
    conn.close()

    if df.empty:
        return df, None, None

    df["title"] = df["title"].fillna("")
    df["abstract"] = df["abstract"].fillna("")

    df["search_text"] = (
        df["title"].apply(clean_text)
        + " "
        + df["abstract"].apply(clean_text)
    )

    vectorizer = TfidfVectorizer(
        stop_words="english",
        max_features=10000,
        min_df=1
    )

    matrix = vectorizer.fit_transform(df["search_text"])
    return df, vectorizer, matrix

def find_similar_legacy_patents(patent_id, top_n=5):
    df, vectorizer, matrix = load_legacy_similarity_data()

    if df.empty:
        return pd.DataFrame()

    matches = df.index[
        df["patent_id"].astype(str) == str(patent_id)
    ]

    if len(matches) == 0:
        return pd.DataFrame()

    patent_index = matches[0]

    scores = cosine_similarity(
        matrix[patent_index],
        matrix
    ).flatten()

    result = df.copy()
    result["similarity"] = scores

    result = result[
        result["patent_id"].astype(str)
        != str(patent_id)
    ]

    return result.sort_values(
        "similarity",
        ascending=False
    ).head(top_n)

# =========================================================
# COMPANY INTELLIGENCE
# =========================================================

def get_company_patents(assignee_keyword, limit=100):
    conn = get_connection()
    query = """
        SELECT publication_number, title, abstract, domain, assignee,
               filing_date, publication_date, source_url, pdf_url
        FROM recent_patents
        WHERE assignee LIKE %s
        ORDER BY publication_date DESC
        LIMIT %s
    """
    df = pd.read_sql(query, conn, params=(f"%{assignee_keyword}%", limit))
    conn.close()
    return df

def get_top_assignees():
    conn = get_connection()
    query = """
        SELECT COALESCE(NULLIF(TRIM(assignee), ''), 'Unknown') AS assignee,
               COUNT(*) AS patents
        FROM recent_patents
        GROUP BY COALESCE(NULLIF(TRIM(assignee), ''), 'Unknown')
        ORDER BY patents DESC
        LIMIT 10
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df

# =========================================================
# ANALYTICS
# =========================================================

def get_filing_year_data():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT LEFT(filing_date, 4) AS year, COUNT(*) AS patents
        FROM patents
        WHERE filing_date IS NOT NULL AND filing_date != ''
        GROUP BY LEFT(filing_date, 4)
        ORDER BY year
    """)

    results = cursor.fetchall()
    cursor.close()
    conn.close()
    return results

def get_top_keywords():
    conn = get_connection()
    cursor = conn.cursor()

    keywords = [
        "communication", "computer", "software", "network",
        "system", "method", "data", "device", "mobile",
        "wireless", "artificial", "intelligence", "battery",
        "vehicle", "healthcare", "semiconductor", "solar"
    ]

    data = []

    for keyword in keywords:
        cursor.execute("""
            SELECT COUNT(*)
            FROM patents
            WHERE title LIKE %s OR abstract LIKE %s
        """, (f"%{keyword}%", f"%{keyword}%"))

        data.append((keyword, cursor.fetchone()[0]))

    cursor.close()
    conn.close()
    return data

# =========================================================
# LOGIN / ADMIN AUTHENTICATION
# =========================================================

# Demo credentials for project presentation. Change these locally if needed.
ADMIN_USERNAME = os.getenv("PATENT_ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("PATENT_ADMIN_PASSWORD", "admin123")

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.markdown("# 🔐 Patent Intelligence Platform")
    st.markdown("### Admin Login")
    st.info("Please login to access the Patent Intelligence Dashboard.")

    with st.form("login_form"):
        username = st.text_input("Username", placeholder="Enter username")
        password = st.text_input("Password", type="password", placeholder="Enter password")
        login_clicked = st.form_submit_button("🔑 Login", use_container_width=True)

    if login_clicked:
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            st.session_state.authenticated = True
            st.session_state.username = username
            st.success("Login successful!")
            st.rerun()
        else:
            st.error("Invalid username or password.")

    st.caption("Authorized access only | Patent Intelligence Platform")
    st.stop()

# Sidebar user/session controls
with st.sidebar:
    st.success(f"👤 Logged in as: {st.session_state.get('username', 'Admin')}")
    if st.button("🚪 Logout", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.pop("username", None)
        st.rerun()

# =========================================================
# HEADER
# =========================================================

st.title("🔬 Patent Intelligence Platform")

st.write(
    "Search, compare and analyze patent information "
    "using MySQL, NLP and TF-IDF similarity."
)

st.divider()

# =========================================================
# DASHBOARD NAVIGATION
# =========================================================

st.markdown("### 🧭 Dashboard Navigation")

nav_options = [
    "🆕 Recent Patents",
    "🧠 Similarity Analysis",
    "🔗 Similar Patents",
    "📚 Legacy Database",
    "🏢 Company Intelligence",
    "📊 Analytics"
]

selected_section = st.radio(
    "Navigate to",
    nav_options,
    horizontal=True,
    key="top_navigation",
    label_visibility="collapsed"
)

st.divider()

# =========================================================
# METRICS
# =========================================================

try:
    legacy_total = get_total_patents()
    recent_df = get_recent_patents()
    recent_total = len(recent_df)
except Exception as e:
    st.error(f"Database connection error: {e}")
    st.stop()

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Legacy Patents", legacy_total)

with col2:
    st.metric("Recent Patents", recent_total)

with col3:
    st.metric("Database", "MySQL")

with col4:
    st.metric("System", "Online")

st.caption("🔐 Admin credentials are read from environment variables when configured.")

# =========================================================
if selected_section == "🆕 Recent Patents":
    # RECENT PATENT SEARCH
    # =========================================================

    st.divider()
    st.header("🆕 Recent Patent Intelligence")

    st.write(
        "Explore recent patents from 2023–2025 "
        "across multiple technology domains."
    )

    if not recent_df.empty:

        search_col, domain_col, year_col, assignee_col = st.columns(4)

        with search_col:
            recent_keyword = st.text_input(
                "Search Recent Patents",
                placeholder="AI, battery, semiconductor..."
            )

        with domain_col:
            domains = ["All"] + sorted(
                recent_df["domain"]
                .fillna("Unknown")
                .astype(str)
                .unique()
                .tolist()
            )

            selected_domain = st.selectbox(
                "Domain",
                domains
            )

        with year_col:

            # Convert every publication date safely, regardless of whether
            # MySQL returns YYYYMMDD, YYYY-MM-DD, or a datetime value.
            publication_dates = recent_df["publication_date"].apply(parse_date_value)

            # Extract valid publication years.
            year_values = sorted(
                publication_dates
                .dropna()
                .dt.year
                .astype(int)
                .unique()
                .tolist()
            )

            years = ["All"] + [str(year) for year in year_values]

            selected_year = st.selectbox(
                "Publication Year",
                years,
                key="recent_publication_year"
            )

        with assignee_col:
            assignees = ["All"] + sorted(
                recent_df["assignee"]
                .fillna("Unknown")
                .astype(str)
                .replace("", "Unknown")
                .unique()
                .tolist()
            )
            selected_assignee = st.selectbox("Assignee", assignees)

        filtered_recent = recent_df.copy()

        if recent_keyword:
            keyword_mask = (
                filtered_recent["title"]
                .fillna("")
                .str.contains(
                    recent_keyword,
                    case=False,
                    na=False
                )
                |
                filtered_recent["abstract"]
                .fillna("")
                .str.contains(
                    recent_keyword,
                    case=False,
                    na=False
                )
            )

            filtered_recent = filtered_recent[keyword_mask]

        if selected_domain != "All":
            filtered_recent = filtered_recent[
                filtered_recent["domain"] == selected_domain
            ]

        if selected_year != "All":

            filtered_publication_dates = (
                filtered_recent["publication_date"]
                .apply(parse_date_value)
            )

            filtered_recent = filtered_recent[
                filtered_publication_dates.dt.year == int(selected_year)
            ]

        if selected_assignee != "All":
            filtered_recent = filtered_recent[
                filtered_recent["assignee"].fillna("Unknown").astype(str) == selected_assignee
            ]

        st.write(
            f"### 🔎 {len(filtered_recent)} recent patents found"
        )

        # =====================================================
        # CSV EXPORT - NEW FEATURE
        # =====================================================

        if not filtered_recent.empty:

            export_columns = [
                "publication_number",
                "title",
                "domain",
                "assignee",
                "filing_date",
                "publication_date",
                "source_url",
                "pdf_url"
            ]

            export_columns = [
                col for col in export_columns
                if col in filtered_recent.columns
            ]

            export_df = filtered_recent[export_columns].copy()

            csv_data = export_df.to_csv(
                index=False
            ).encode("utf-8")

            st.download_button(
                label="📥 Download Filtered Patents as CSV",
                data=csv_data,
                file_name="filtered_patents.csv",
                mime="text/csv",
                width="stretch"
            )

        if filtered_recent.empty:
            st.info("No recent patents match the selected search and filters. Try a broader keyword or reset a filter.")
        else:
            st.caption("Showing the most relevant records from the current filtered dataset.")

            for _, patent in filtered_recent.iterrows():
                title = clean_text(patent["title"]) or "Untitled Patent"
                abstract = clean_text(patent["abstract"])
                publication_number = display_value(patent["publication_number"])
                domain = display_value(patent["domain"])
                assignee = display_value(patent["assignee"])

                with st.container(border=True):
                    st.subheader(title)
                    st.caption(f"Publication No. {publication_number}")

                    info1, info2, info3 = st.columns(3)
                    with info1:
                        st.write(f"**🌐 Domain**  \n{domain}")
                    with info2:
                        st.write(f"**🏢 Assignee**  \n{assignee}")
                    with info3:
                        st.write(f"**📅 Publication**  \n{format_date(patent['publication_date']) or 'Unknown'}")

                    if abstract:
                        st.markdown("**Abstract**")
                        preview = abstract[:600] + ("..." if len(abstract) > 600 else "")
                        st.write(preview)
                    else:
                        st.caption("No abstract available for this record.")

                    button_col1, button_col2 = st.columns(2)
                    with button_col1:
                        pdf_url = str(patent["pdf_url"])
                        if pdf_url and pdf_url.lower() not in {"nan", "none", "null", ""}:
                            st.link_button("📄 Open Original Patent PDF", pdf_url, width="stretch")
                    with button_col2:
                        source_url = str(patent["source_url"])
                        if source_url and source_url.lower() not in {"nan", "none", "null", ""}:
                            st.link_button("🌐 Open Google Patents", source_url, width="stretch")

    # =========================================================
if selected_section == "🧠 Similarity Analysis":
    # PATENT COMPARISON
    # =========================================================

    st.divider()
    st.header("🧠 Patent Similarity Analysis")
    st.write("Compare two recent patents using TF-IDF + Cosine Similarity.")

    if not recent_df.empty:
        recent_df = recent_df.fillna("")
        patent_options = [
            f"{row['publication_number']} | {clean_text(row['title']) or 'Untitled Patent'}"
            for _, row in recent_df.iterrows()
        ]

        col_a, col_b = st.columns(2)
        with col_a:
            st.subheader("Patent A")
            selected_a = st.selectbox("Select first patent", patent_options, key="patent_a")
        with col_b:
            st.subheader("Patent B")
            selected_b = st.selectbox(
                "Select second patent", patent_options,
                index=1 if len(patent_options) > 1 else 0, key="patent_b"
            )

        publication_a = selected_a.split(" | ", 1)[0]
        publication_b = selected_b.split(" | ", 1)[0]

        compare_clicked = st.button("⚖️ Compare Patents", type="primary", width="stretch")

        if compare_clicked:
            if publication_a == publication_b:
                st.warning("Please select two different patents to compare.")
            else:
                score = compare_recent_patents(publication_a, publication_b)
                if score is None:
                    st.error("Similarity could not be calculated for the selected patents.")
                else:
                    percentage = safe_score(score)
                    level, interpretation = similarity_label(score)
                    patent_a_row = recent_df[recent_df["publication_number"].astype(str) == publication_a].iloc[0]
                    patent_b_row = recent_df[recent_df["publication_number"].astype(str) == publication_b].iloc[0]

                    st.divider()
                    st.subheader("📊 Similarity Result")
                    score_col1, score_col2, score_col3 = st.columns(3)
                    with score_col1:
                        st.metric("Similarity Score", f"{percentage:.2f}%")
                    with score_col2:
                        st.metric("Similarity Level", level)
                    with score_col3:
                        st.metric("Method", "TF-IDF + Cosine")

                    st.progress(similarity_bar(score))
                    st.caption(f"Interpretation: {interpretation}.")

                    left, right = st.columns(2)
                    for container, label, row in [(left, "Patent A", patent_a_row), (right, "Patent B", patent_b_row)]:
                        with container:
                            st.subheader(f"📄 {label}")
                            st.caption(display_value(row["publication_number"]))
                            st.write(f"**Title:** {display_value(row['title'], 'Untitled Patent')}")
                            st.write(f"**Domain:** {display_value(row['domain'])}")
                            st.write(f"**Assignee:** {display_value(row['assignee'])}")
                            abstract = clean_text(row["abstract"])
                            if abstract:
                                st.markdown("**Abstract**")
                                st.write(abstract[:700] + ("..." if len(abstract) > 700 else ""))
                                if len(abstract) > 700:
                                    with st.expander("📖 Read complete abstract"):
                                        st.write(abstract)

                            pdf_url = str(row["pdf_url"])
                            source_url = str(row["source_url"])
                            link_col1, link_col2 = st.columns(2)
                            with link_col1:
                                if pdf_url.lower() not in {"", "nan", "none", "null"}:
                                    st.link_button(f"📄 Open {label} PDF", pdf_url, width="stretch")
                            with link_col2:
                                if source_url.lower() not in {"", "nan", "none", "null"}:
                                    st.link_button(f"🌐 Open {label} Google Patents", source_url, width="stretch")

                    st.divider()
                    st.subheader("🔑 Common Keywords")
                    common_keywords = get_common_keywords(
                        str(patent_a_row["title"]) + " " + str(patent_a_row["abstract"]),
                        str(patent_b_row["title"]) + " " + str(patent_b_row["abstract"])
                    )
                    if common_keywords:
                        st.write(" • ".join(common_keywords))
                    else:
                        st.info("No major common keywords found between the selected patents.")
    else:
        st.info("Recent patent data is not available for similarity analysis.")

    # =========================================================
if selected_section == "🔗 Similar Patents":
    # TOP 5 SIMILAR PATENTS
    # =========================================================

    st.divider()
    st.header("🔗 Find Similar Patents")
    st.write("Select one patent to discover its top 5 most similar patents.")

    if not recent_df.empty:
        similarity_options = [
            f"{row['publication_number']} | {clean_text(row['title']) or 'Untitled Patent'}"
            for _, row in recent_df.iterrows()
        ]
        selected_similarity = st.selectbox("Select Patent", similarity_options, key="similarity_patent")
        similarity_id = selected_similarity.split(" | ", 1)[0]

        if st.button("🔍 Find Top 5 Similar Patents", type="primary", width="stretch"):
            similar = find_similar_recent_patents(similarity_id, top_n=5)
            if similar.empty:
                st.info("No similar patents found for the selected record.")
            else:
                st.success(f"Found {len(similar)} similar patents, ranked by cosine similarity.")
                for rank, (_, row) in enumerate(similar.iterrows(), start=1):
                    score = float(row["similarity"])
                    percentage = safe_score(score)
                    level, _ = similarity_label(score)
                    title = clean_text(row["title"]) or "Untitled Patent"
                    abstract = clean_text(row["abstract"])

                    with st.container(border=True):
                        rank_col, title_col, score_col = st.columns([0.8, 5.2, 1.5])
                        with rank_col:
                            st.metric("Rank", f"#{rank}")
                        with title_col:
                            st.subheader(title)
                            st.caption(f"Publication: {display_value(row['publication_number'])}")
                        with score_col:
                            st.metric("Similarity", f"{percentage:.2f}%")

                        st.progress(similarity_bar(score))
                        st.caption(f"Similarity level: {level}")

                        info1, info2 = st.columns(2)
                        with info1:
                            st.write(f"**🌐 Domain:** {display_value(row['domain'])}")
                        with info2:
                            st.write(f"**🏢 Assignee:** {display_value(row['assignee'])}")

                        if abstract:
                            st.markdown("**Abstract preview**")
                            st.write(abstract[:450] + ("..." if len(abstract) > 450 else ""))
                            if len(abstract) > 450:
                                with st.expander("📖 Read complete abstract"):
                                    st.write(abstract)

                        pdf_url = str(row.get("pdf_url", ""))
                        source_url = str(row.get("source_url", ""))
                        link_col1, link_col2 = st.columns(2)
                        with link_col1:
                            if pdf_url.lower() not in {"", "nan", "none", "null"}:
                                st.link_button("📄 Open Original Patent PDF", pdf_url, width="stretch")
                        with link_col2:
                            if source_url.lower() not in {"", "nan", "none", "null"}:
                                st.link_button("🌐 Open Google Patents", source_url, width="stretch")
    else:
        st.info("Recent patent data is not available for similarity search.")

    # =========================================================
if selected_section == "📚 Legacy Database":
    # LEGACY SEARCH
    # =========================================================

    st.divider()
    st.header("📚 Legacy Patent Database")

    st.write(
        "Search the original patent dataset containing "
        "5988 records."
    )

    legacy_keyword = st.text_input(
        "Enter Patent Keyword",
        placeholder="communication, computer, game..."
    )

    filter_col1, filter_col2 = st.columns(2)

    with filter_col1:

        filing_year = st.selectbox(
            "Filing Year",
            [
                "All", "2010", "2011", "2012", "2013",
                "2014", "2015", "2016", "2017", "2018",
                "2019", "2020"
            ],
            key="legacy_filing"
        )

    with filter_col2:

        result_limit = st.selectbox(
            "Number of Results",
            [10, 20, 50, 100],
            index=1
        )

    if legacy_keyword:

        results = search_patents(
            legacy_keyword,
            filing_year,
            result_limit
        )

        st.write(
            f"### 🔎 {len(results)} results found"
        )

        if not results:

            st.warning("No patents found.")

        else:

            for patent in results:

                patent_id = patent[0]
                title = clean_text(patent[1])
                abstract = clean_text(patent[2])

                filing = format_date(patent[3])
                issue = format_date(patent[4])

                with st.container(border=True):

                    st.subheader(title)

                    st.write(
                        f"**Patent ID:** {patent_id}"
                    )

                    st.write(
                        f"**Filing Date:** {filing} | "
                        f"**Issue Date:** {issue}"
                    )

                    st.write("**Abstract:**")

                    preview = abstract[:500]

                    if len(abstract) > 500:
                        preview += "..."

                    st.write(preview)

                    # Patent links
                    patent_query = urllib.parse.quote_plus(str(patent_id))
                    google_patents_url = f"https://patents.google.com/?q={patent_query}"

                    link_col1, link_col2 = st.columns(2)
                    with link_col1:
                        st.link_button(
                            "🌐 Open Google Patents",
                            google_patents_url,
                            width="stretch"
                        )
                    with link_col2:
                        st.link_button(
                            "🔎 Search Patent Online",
                            google_patents_url,
                            width="stretch"
                        )

                    if len(abstract) > 500:
                        with st.expander("📖 Read complete abstract"):
                            st.write(abstract)

    # =========================================================
if selected_section == "🏢 Company Intelligence":
    st.divider()
    st.header("🏢 Company / Assignee Intelligence")
    st.caption("Explore a company’s recent patent portfolio, technology domains, and individual filings.")

    company_query = st.text_input("Company / Assignee", placeholder="Microsoft, Google, Samsung, IBM...", key="company_query")
    company_limit = st.selectbox("Maximum patents", [10, 25, 50, 100], index=1, key="company_limit")

    if not company_query.strip():
        st.info("💡 Enter a company or assignee name to explore its patent portfolio.")
    else:
        company_df = get_company_patents(company_query.strip(), company_limit)
        if company_df.empty:
            st.warning(f"No recent patents found for **{company_query.strip()}**. Try a different spelling or assignee name.")
        else:
            total_domains = company_df["domain"].fillna("Unknown").replace("", "Unknown").nunique()
            latest_date = format_date(company_df.iloc[0]["publication_date"])
            st.success(f"Found {len(company_df):,} recent patents for **{company_query.strip()}**.")

            c1, c2, c3 = st.columns(3)
            with c1: st.metric("📚 Patents", f"{len(company_df):,}")
            with c2: st.metric("🌐 Technology Domains", f"{total_domains:,}")
            with c3: st.metric("🗓️ Latest Publication", latest_date)

            st.divider()
            st.subheader("🌐 Technology Portfolio")
            domain_counts = company_df["domain"].fillna("Unknown").replace("", "Unknown").value_counts()
            if not domain_counts.empty:
                chart_col, insight_col = st.columns([2.2, 1])
                with chart_col: st.bar_chart(domain_counts)
                with insight_col:
                    st.markdown("**Portfolio snapshot**")
                    for domain, count in domain_counts.head(5).items():
                        st.write(f"• **{domain}** — {count} patent{'s' if count != 1 else ''}")

            st.divider()
            st.subheader("📄 Recent Company Patents")
            for rank, (_, patent) in enumerate(company_df.iterrows(), start=1):
                title = clean_text(patent["title"]) or "Untitled Patent"
                abstract = clean_text(patent["abstract"])
                with st.container(border=True):
                    top1, top2 = st.columns([0.7, 6.3])
                    with top1: st.metric("Rank", f"#{rank}")
                    with top2:
                        st.subheader(title)
                        st.caption(f"Publication: {display_value(patent['publication_number'])}")
                    meta1, meta2, meta3 = st.columns(3)
                    with meta1: st.write(f"**🌐 Domain**\n{display_value(patent['domain'])}")
                    with meta2: st.write(f"**🏢 Assignee**\n{display_value(patent.get('assignee', company_query.strip()))}")
                    with meta3: st.write(f"**🗓️ Publication**\n{format_date(patent['publication_date'])}")
                    if abstract:
                        st.markdown("**Abstract preview**")
                        st.write(abstract[:500] + ("..." if len(abstract) > 500 else ""))
                        if len(abstract) > 500:
                            with st.expander("📖 Read complete abstract"):
                                st.write(abstract)
                    else:
                        st.caption("No abstract available for this record.")

                    publication_number = display_value(patent.get("publication_number", ""), "")
                    source_url = display_value(patent.get("source_url", ""), "")
                    pdf_url = display_value(patent.get("pdf_url", ""), "")

                    if not source_url and publication_number:
                        source_url = "https://patents.google.com/patent/" + urllib.parse.quote(publication_number)
                    if not pdf_url and publication_number:
                        pdf_url = "https://patents.google.com/patent/" + urllib.parse.quote(publication_number) + "/en?oq=" + urllib.parse.quote(publication_number)

                    if source_url or pdf_url:
                        link_col1, link_col2 = st.columns(2)
                        with link_col1:
                            if source_url:
                                st.link_button("🌐 Open Google Patents", source_url, width="stretch")
                        with link_col2:
                            if pdf_url:
                                st.link_button("📄 Open Patent PDF", pdf_url, width="stretch")


if selected_section == "📊 Analytics":
    st.divider()
    st.header("📊 Patent Analytics")
    st.caption("Visual insights from recent and legacy patent records stored in the database.")

    if not recent_df.empty:
        st.subheader("🆕 Recent Patent Overview")
        a1, a2, a3 = st.columns(3)
        with a1: st.metric("Recent Patents", f"{len(recent_df):,}")
        with a2: st.metric("Technology Domains", f"{recent_df['domain'].fillna('Unknown').replace('', 'Unknown').nunique():,}")
        with a3: st.metric("Assignees", f"{recent_df['assignee'].fillna('Unknown').replace('', 'Unknown').nunique():,}")

        st.divider()
        chart1, chart2 = st.columns(2)
        with chart1:
            st.subheader("🌐 Patents by Domain")
            domain_chart = recent_df["domain"].fillna("Unknown").replace("", "Unknown").value_counts()
            if not domain_chart.empty: st.bar_chart(domain_chart)
            else: st.info("No domain data available.")
        with chart2:
            st.subheader("🏢 Top Assignees")
            top_assignees = get_top_assignees()
            if not top_assignees.empty: st.bar_chart(top_assignees.set_index("assignee"))
            else: st.info("No assignee data available.")

        st.subheader("📅 Recent Patents by Publication Year")
        recent_years = (recent_df["publication_date"].apply(parse_date_value).dropna().dt.year.astype(int).value_counts().sort_index())
        if not recent_years.empty: st.bar_chart(recent_years)
        else: st.info("Publication-year data is not available.")

    st.divider()
    st.subheader("📚 Legacy Filing Trend")
    filing_data = get_filing_year_data()
    if filing_data:
        filing_df = pd.DataFrame(filing_data, columns=["Year", "Patents"])
        filing_df["Year"] = filing_df["Year"].astype(str)
        st.bar_chart(filing_df.set_index("Year"))
    else: st.info("No legacy filing-year data available.")

    st.divider()
    st.subheader("🔝 Common Patent Keywords")
    keyword_data = get_top_keywords()
    if keyword_data:
        keyword_df = pd.DataFrame(keyword_data, columns=["Keyword", "Patents"]).sort_values("Patents", ascending=False)
        st.bar_chart(keyword_df.set_index("Keyword"))
    else: st.info("No keyword analytics available.")

    st.caption("Note: Issue Year analytics is intentionally omitted because the current legacy issue-date field is not reliable enough for a meaningful trend chart.")

# FOOTER
# =========================================================

st.divider()

st.caption(
    "Patent Intelligence Platform | "
    "MySQL | Streamlit | TF-IDF | NLP"
)

