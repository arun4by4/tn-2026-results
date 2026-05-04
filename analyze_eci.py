"""
Analyzes Tamil Nadu 2026 assembly election results.

Steps:
  1. Reads eci_results.csv for the constituency list.
  2. Fetches ConstituencywiseS22{N}.htm for each constituency (all candidates
     with vote counts). Saves raw data to eci_detailed.csv.
  3. Produces three analyses:
       a. Per-constituency top-4 table  (eci_top4.csv)
       b. Party performance summary     (printed + eci_party_summary.csv)
       c. Vote-swing / seat-flip table  (printed + eci_swings.csv)

Usage:
    python analyze_eci.py [--no-fetch]   # --no-fetch skips download step

Output files (in same directory):
    eci_detailed.csv   — all candidates, all votes
    eci_top4.csv       — top-4 per constituency
    eci_party_summary.csv
    eci_swings.csv
"""

import csv
import sys
import time
import argparse
import os
from collections import defaultdict

from curl_cffi import requests
from bs4 import BeautifulSoup

# ── Config ────────────────────────────────────────────────────────────────────
SUMMARY_URL = "https://results.eci.gov.in/ResultAcGenMay2026/statewiseS22{n}.htm"
CONST_URL   = "https://results.eci.gov.in/ResultAcGenMay2026/ConstituencywiseS22{n}.htm"
SUMMARY_CSV = "eci_results.csv"
DETAILED_CSV = "eci_detailed.csv"
TOP4_CSV     = "eci_top4.csv"
PARTY_CSV    = "eci_party_summary.csv"
SWING_CSV    = "eci_swings.csv"

FETCH_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://results.eci.gov.in/",
}

# Swing thresholds (absolute votes from winner to runner-up to flip the seat)
SWING_BRACKETS = [
    (0,     500,   "Knife-edge  (<500)"),
    (500,  2000,   "Very tight  (500–2 000)"),
    (2000, 5000,   "Tight       (2 000–5 000)"),
    (5000,15000,   "Comfortable (5 000–15 000)"),
    (15000,999999, "Safe        (>15 000)"),
]


# ── Fetch helpers ─────────────────────────────────────────────────────────────
def fetch_html(url: str, retries: int = 3, delay: float = 2.0) -> str | None:
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, headers=FETCH_HEADERS, impersonate="chrome124", timeout=30)
            if resp.status_code == 200:
                return resp.text
            print(f"    HTTP {resp.status_code} (attempt {attempt})")
        except Exception as exc:
            print(f"    Error: {exc} (attempt {attempt})")
        if attempt < retries:
            time.sleep(delay)
    return None


def parse_constituency_page(html: str, const_no: str, const_name: str) -> list[dict]:
    """Return list of candidate dicts sorted by Total Votes descending."""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if not table:
        return []

    candidates = []
    tbody = table.find("tbody") or table
    for tr in tbody.find_all("tr", recursive=False):
        tds = tr.find_all("td", recursive=False)
        if len(tds) < 6:
            continue
        cells = [td.get_text(strip=True) for td in tds]
        try:
            total = int(cells[5].replace(",", ""))
        except ValueError:
            total = 0
        candidates.append({
            "const_no":      const_no,
            "constituency":  const_name,
            "ballot_sn":     cells[0],
            "candidate":     cells[1],
            "party":         cells[2],
            "evm_votes":     cells[3].replace(",", ""),
            "postal_votes":  cells[4].replace(",", ""),
            "total_votes":   total,
            "vote_pct":      cells[6] if len(cells) > 6 else "",
        })

    candidates.sort(key=lambda r: r["total_votes"], reverse=True)
    for rank, c in enumerate(candidates, 1):
        c["rank"] = rank
    return candidates


# ── Step 1 – load summary CSV ─────────────────────────────────────────────────
def load_summary() -> list[dict]:
    with open(SUMMARY_CSV, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


# ── Step 2 – fetch all constituency pages ─────────────────────────────────────
def fetch_all(constituencies: list[dict]) -> list[dict]:
    all_candidates = []
    total = len(constituencies)
    for idx, row in enumerate(constituencies, 1):
        const_no   = row["Const. No."]
        const_name = row["Constituency"]
        url = CONST_URL.format(n=const_no)
        print(f"  [{idx:3d}/{total}] {const_name} (#{const_no})")
        html = fetch_html(url)
        if html is None:
            print(f"    SKIPPED.")
            continue
        cands = parse_constituency_page(html, const_no, const_name)
        all_candidates.extend(cands)
        time.sleep(0.8)

    return all_candidates


def save_detailed(candidates: list[dict]) -> None:
    if not candidates:
        return
    fields = ["const_no","constituency","rank","candidate","party",
              "evm_votes","postal_votes","total_votes","vote_pct","ballot_sn"]
    with open(DETAILED_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(candidates)
    print(f"\n  Saved {len(candidates)} candidate rows -> {DETAILED_CSV}")


def load_detailed() -> list[dict]:
    with open(DETAILED_CSV, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["total_votes"] = int(r["total_votes"]) if r["total_votes"] else 0
        r["rank"]        = int(r["rank"]) if r["rank"] else 0
    return rows


# ── Step 3a – top-4 per constituency ─────────────────────────────────────────
def build_top4(candidates: list[dict]) -> list[dict]:
    by_const: dict[str, list[dict]] = defaultdict(list)
    for c in candidates:
        by_const[c["const_no"]].append(c)

    top4_rows = []
    for const_no, cands in sorted(by_const.items(), key=lambda x: int(x[0])):
        cands_sorted = sorted(cands, key=lambda c: c["total_votes"], reverse=True)
        total = sum(c["total_votes"] for c in cands_sorted)
        row: dict = {
            "const_no":    const_no,
            "constituency": cands_sorted[0]["constituency"],
            "total_votes": total,
        }
        for pos in range(1, 5):
            prefix = f"p{pos}"
            if pos <= len(cands_sorted):
                c = cands_sorted[pos - 1]
                pct = round(c["total_votes"] / total * 100, 2) if total else 0
                row[f"{prefix}_candidate"] = c["candidate"]
                row[f"{prefix}_party"]     = c["party"]
                row[f"{prefix}_votes"]     = c["total_votes"]
                row[f"{prefix}_pct"]       = pct
            else:
                row[f"{prefix}_candidate"] = ""
                row[f"{prefix}_party"]     = ""
                row[f"{prefix}_votes"]     = ""
                row[f"{prefix}_pct"]       = ""
        # winner margin
        if len(cands_sorted) >= 2:
            margin = cands_sorted[0]["total_votes"] - cands_sorted[1]["total_votes"]
            row["margin"] = margin
            row["swing_to_flip"] = (margin + 1) // 2  # votes that must move winner->runner-up
            row["swing_pct"]     = round(row["swing_to_flip"] / total * 100, 2) if total else 0
        else:
            row["margin"] = ""
            row["swing_to_flip"] = ""
            row["swing_pct"] = ""
        top4_rows.append(row)
    return top4_rows


def save_top4(rows: list[dict]) -> None:
    fields = [
        "const_no","constituency","total_votes","margin","swing_to_flip","swing_pct",
        "p1_candidate","p1_party","p1_votes","p1_pct",
        "p2_candidate","p2_party","p2_votes","p2_pct",
        "p3_candidate","p3_party","p3_votes","p3_pct",
        "p4_candidate","p4_party","p4_votes","p4_pct",
    ]
    with open(TOP4_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"  Saved -> {TOP4_CSV}")


# ── Step 3b – party performance summary ──────────────────────────────────────
def party_summary(candidates: list[dict]) -> list[dict]:
    stats: dict[str, dict] = defaultdict(lambda: {
        "party": "",
        "seats_1st": 0, "seats_2nd": 0, "seats_3rd": 0, "seats_4th": 0,
        "total_votes": 0,
    })
    total_votes_all = sum(c["total_votes"] for c in candidates if c["rank"] == 1)
    # total_votes_all is sum of top-1 = same as sum of all valid votes? No, let's sum all.
    all_votes = sum(c["total_votes"] for c in candidates)

    for c in candidates:
        p = c["party"]
        stats[p]["party"] = p
        stats[p]["total_votes"] += c["total_votes"]
        rank = c["rank"]
        if rank == 1:
            stats[p]["seats_1st"] += 1
        elif rank == 2:
            stats[p]["seats_2nd"] += 1
        elif rank == 3:
            stats[p]["seats_3rd"] += 1
        elif rank == 4:
            stats[p]["seats_4th"] += 1

    rows = []
    for p, s in stats.items():
        vote_pct = round(s["total_votes"] / all_votes * 100, 2) if all_votes else 0
        rows.append({
            "party":       p,
            "seats_won":   s["seats_1st"],
            "seats_2nd":   s["seats_2nd"],
            "seats_3rd":   s["seats_3rd"],
            "seats_4th":   s["seats_4th"],
            "total_votes": s["total_votes"],
            "vote_pct":    vote_pct,
        })
    rows.sort(key=lambda r: (-r["seats_won"], -r["total_votes"]))
    return rows


def save_party_summary(rows: list[dict]) -> None:
    fields = ["party","seats_won","seats_2nd","seats_3rd","seats_4th","total_votes","vote_pct"]
    with open(PARTY_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  Saved -> {PARTY_CSV}")


def print_party_summary(rows: list[dict]) -> None:
    print("\n" + "=" * 90)
    print("PARTY PERFORMANCE SUMMARY")
    print("=" * 90)
    hdr = f"{'Party':<45} {'Won':>4} {'2nd':>4} {'3rd':>4} {'4th':>4} {'Votes':>10} {'Vote%':>7}"
    print(hdr)
    print("-" * 90)
    for r in rows:
        if r["seats_won"] == 0 and r["seats_2nd"] == 0 and r["vote_pct"] < 0.5:
            continue  # skip micro parties with negligible presence
        print(
            f"{r['party']:<45} "
            f"{r['seats_won']:>4} "
            f"{r['seats_2nd']:>4} "
            f"{r['seats_3rd']:>4} "
            f"{r['seats_4th']:>4} "
            f"{r['total_votes']:>10,} "
            f"{r['vote_pct']:>6.2f}%"
        )
    print("=" * 90)


# ── Step 3c – swing / seat-flip analysis ─────────────────────────────────────
def swing_analysis(top4_rows: list[dict]) -> list[dict]:
    rows = []
    for r in top4_rows:
        if not r.get("swing_to_flip"):
            continue
        rows.append({
            "const_no":      r["const_no"],
            "constituency":  r["constituency"],
            "winner":        r.get("p1_candidate", ""),
            "winner_party":  r.get("p1_party", ""),
            "winner_votes":  r.get("p1_votes", ""),
            "winner_pct":    r.get("p1_pct", ""),
            "runner_up":     r.get("p2_candidate", ""),
            "runner_party":  r.get("p2_party", ""),
            "runner_votes":  r.get("p2_votes", ""),
            "runner_pct":    r.get("p2_pct", ""),
            "margin":        r["margin"],
            "swing_to_flip": r["swing_to_flip"],
            "swing_pct":     r["swing_pct"],
            "total_votes":   r["total_votes"],
        })
    rows.sort(key=lambda r: r["swing_to_flip"])
    return rows


def save_swing(rows: list[dict]) -> None:
    fields = [
        "const_no","constituency","margin","swing_to_flip","swing_pct","total_votes",
        "winner","winner_party","winner_votes","winner_pct",
        "runner_up","runner_party","runner_votes","runner_pct",
    ]
    with open(SWING_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  Saved -> {SWING_CSV}")


def print_swing_analysis(swing_rows: list[dict]) -> None:
    print("\n" + "=" * 90)
    print("SEAT-FLIP SWING ANALYSIS  (votes winner->runner-up needed to flip)")
    print("=" * 90)

    # Bracket summary
    print("\nBracket breakdown:")
    for lo, hi, label in SWING_BRACKETS:
        seats = [r for r in swing_rows if lo <= r["swing_to_flip"] < hi]
        parties = defaultdict(int)
        for s in seats:
            parties[s["winner_party"]] += 1
        party_str = ", ".join(f"{p}: {n}" for p, n in
                              sorted(parties.items(), key=lambda x: -x[1]))
        print(f"  {label:30s} -> {len(seats):3d} seats  [{party_str}]")

    # Most vulnerable seats (swing_to_flip < 2000)
    vulnerable = [r for r in swing_rows if r["swing_to_flip"] < 2000]
    if vulnerable:
        print(f"\n{'TOP VULNERABLE SEATS (swing < 2 000 votes)'}")
        print(f"  {'Constituency':<22} {'Winner Party':<30} {'Runner-up Party':<30} {'Margin':>7} {'Swing':>6} {'Swing%':>7}")
        print("  " + "-" * 105)
        for r in vulnerable[:30]:
            print(
                f"  {r['constituency']:<22} "
                f"{r['winner_party']:<30} "
                f"{r['runner_party']:<30} "
                f"{r['margin']:>7,} "
                f"{r['swing_to_flip']:>6,} "
                f"{r['swing_pct']:>6.2f}%"
            )

    # Hypothetical swings: how many seats change at uniform +X% swing
    print("\nHypothetical uniform swing: seats that would flip if X% of votes move winner->runner-up")
    print(f"  {'Swing %':>8}  {'Seats flip':>10}  {'Net beneficiary parties'}")
    print("  " + "-" * 60)
    for pct in [0.5, 1.0, 1.5, 2.0, 3.0, 5.0]:
        flip = [r for r in swing_rows if r["swing_pct"] <= pct]
        gainers: dict[str, int] = defaultdict(int)
        for r in flip:
            gainers[r["runner_party"]] += 1
        g_str = ", ".join(f"{p}: +{n}" for p, n in sorted(gainers.items(), key=lambda x: -x[1]))
        print(f"  {pct:>7.1f}%  {len(flip):>10}  {g_str}")

    print("=" * 90)


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-fetch", action="store_true",
                        help="Skip fetching, use existing eci_detailed.csv")
    args = parser.parse_args()

    # Step 1: load summary
    print("Loading summary CSV …")
    constituencies = load_summary()
    print(f"  {len(constituencies)} constituencies found.")

    # Step 2: fetch or load detailed data
    if args.no_fetch and os.path.exists(DETAILED_CSV):
        print(f"\nLoading existing {DETAILED_CSV} …")
        candidates = load_detailed()
        print(f"  {len(candidates)} candidate rows loaded.")
    else:
        print(f"\nFetching {len(constituencies)} constituency pages …")
        candidates = fetch_all(constituencies)
        save_detailed(candidates)

    if not candidates:
        print("No candidate data. Exiting.")
        sys.exit(1)

    # Step 3: analysis
    print("\nBuilding top-4 table …")
    top4 = build_top4(candidates)
    save_top4(top4)

    print("Building party summary …")
    party_rows = party_summary(candidates)
    save_party_summary(party_rows)
    print_party_summary(party_rows)

    print("\nBuilding swing analysis …")
    swing_rows = swing_analysis(top4)
    save_swing(swing_rows)
    print_swing_analysis(swing_rows)

    print(f"\nAll done. Output files: {DETAILED_CSV}, {TOP4_CSV}, {PARTY_CSV}, {SWING_CSV}")


if __name__ == "__main__":
    main()
