"""
Fetches Tamil Nadu (S22) election results from ECI for pages 1–12
and saves all constituency results to a CSV file.

Uses curl_cffi to impersonate a real browser TLS profile, bypassing
fingerprint-based blocks on the ECI site.

Usage:
    python fetch_eci_results.py

Output:
    eci_results.csv
"""

import csv
import time
import sys
from bs4 import BeautifulSoup, NavigableString
from curl_cffi import requests

BASE_URL = "https://results.eci.gov.in/ResultAcGenMay2026/statewiseS22{n}.htm"
OUTPUT_CSV = "eci_results.csv"
PAGES = range(1, 13)  # 1 to 12 inclusive

HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://results.eci.gov.in/",
}

COLUMNS = [
    "Constituency",
    "Const. No.",
    "Leading Candidate",
    "Leading Party",
    "Trailing Candidate",
    "Trailing Party",
    "Margin",
    "Round",
    "Status",
]


def fetch_page(url: str, retries: int = 3, delay: float = 2.0) -> str | None:
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(
                url,
                headers=HEADERS,
                impersonate="chrome124",
                timeout=30,
            )
            if resp.status_code == 200:
                return resp.text
            print(f"  HTTP {resp.status_code} for {url} (attempt {attempt})")
        except Exception as exc:
            print(f"  Error fetching {url}: {exc} (attempt {attempt})")
        if attempt < retries:
            time.sleep(delay)
    return None


def cell_text(td) -> str:
    """
    Extract clean text from a result table TD.
    For plain cells the text is a direct NavigableString.
    For party-name cells the name lives in the first <td> of an inner table.
    """
    # Try direct text nodes first
    direct = "".join(
        str(c) for c in td.children if isinstance(c, NavigableString)
    ).strip()
    if direct:
        return direct

    # Party-name cells: party name is the first inner <td>
    inner_table = td.find("table")
    if inner_table:
        first_inner_td = inner_table.find("td")
        if first_inner_td:
            return first_inner_td.get_text(strip=True)

    return td.get_text(separator=" ", strip=True)


def parse_results(html: str, page_num: int) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")

    # The main results table is always the first table with a <thead>
    main_table = None
    for t in soup.find_all("table"):
        if t.find("thead"):
            main_table = t
            break

    if not main_table:
        print(f"  Page {page_num}: main results table not found.")
        return []

    tbody = main_table.find("tbody")
    if not tbody:
        print(f"  Page {page_num}: no tbody found.")
        return []

    rows_out = []
    for tr in tbody.find_all("tr", recursive=False):
        tds = tr.find_all("td", recursive=False)
        if len(tds) < len(COLUMNS):
            continue
        row = {"page": page_num}
        for col, td in zip(COLUMNS, tds):
            row[col] = cell_text(td)
        rows_out.append(row)

    return rows_out


def main():
    all_rows: list[dict] = []

    for n in PAGES:
        url = BASE_URL.format(n=n)
        print(f"Fetching page {n}: {url}")
        html = fetch_page(url)
        if html is None:
            print(f"  Skipping page {n} (fetch failed).")
            continue
        rows = parse_results(html, page_num=n)
        print(f"  Page {n}: {len(rows)} constituencies extracted.")
        all_rows.extend(rows)
        time.sleep(1)

    if not all_rows:
        print("No data collected. Exiting.")
        sys.exit(1)

    fieldnames = ["page"] + COLUMNS
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"\nDone. {len(all_rows)} rows written to '{OUTPUT_CSV}'.")


if __name__ == "__main__":
    main()
