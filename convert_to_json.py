"""
Converts ECI result CSVs to JSON files consumed by the static web app (index.html).

Run this after fetch_eci_results.py + analyze_eci.py have produced their CSVs.

Output: data/ directory with JSON files used by index.html
"""

import csv
import json
import os

os.makedirs("data", exist_ok=True)

# Colorblind-friendly palette (Okabe-Ito + Tol Muted extended).
# Hues are spread across the full wheel; luminance also varies so
# parties remain distinguishable without colour perception.
# Key changes over v1:
#   NTK  #334155→#8B5CF6  (near-black → violet, visible on dark bg)
#   CPI  #DC2626→#EC4899  (dark red   → pink,   distinct from DMK)
#   CPI(M)#B91C1C→#6366F1 (darker red → indigo, distinct from CPI)
#   DMDK #D97706→#A3E635  (amber      → lime,   distinct from BJP)
#   AMMK #7C3AED→#2DD4BF  (purple     → teal,   freed purple for NTK/PMK)
#   BJP  #F97316→#EA580C  (orange     → deeper orange, more sep from TVK)
PARTY_COLORS = {
    "Tamilaga Vettri Kazhagam":                    "#F59E0B",  # amber   (TVK gold/yellow)
    "Dravida Munnetra Kazhagam":                   "#F43F5E",  # rose    (DMK red — brighter, more visible)
    "All India Anna Dravida Munnetra Kazhagam":    "#22C55E",  # green   (AIADMK)
    "Indian National Congress":                    "#0EA5E9",  # sky     (INC blue)
    "Bharatiya Janata Party":                      "#EA580C",  # d-orange(BJP saffron, separated from TVK)
    "Naam Tamilar Katchi":                         "#8B5CF6",  # violet  (was near-black — now visible)
    "Pattali Makkal Katchi":                       "#A855F7",  # purple  (PMK)
    "Viduthalai Chiruthaigal Katchi":              "#06B6D4",  # cyan    (VCK)
    "Communist Party of India":                    "#EC4899",  # pink    (CPI — moved out of red family)
    "Communist Party of India (Marxist)":          "#6366F1",  # indigo  (CPI(M) — moved out of red family)
    "Indian Union Muslim League":                  "#38BDF8",  # l-blue  (IUML — lighter than INC)
    "Desiya Murpokku Dravida Kazhagam":            "#A3E635",  # lime    (DMDK — moved out of amber family)
    "Amma Makkal Munnettra Kazagam":               "#2DD4BF",  # teal    (AMMK — freed the purple slot)
    "Independent":                                 "#94A3B8",  # slate
    "None of the Above":                           "#64748B",  # d-slate
}

PARTY_SHORT = {
    "Tamilaga Vettri Kazhagam":                    "TVK",
    "Dravida Munnetra Kazhagam":                   "DMK",
    "All India Anna Dravida Munnetra Kazhagam":    "AIADMK",
    "Indian National Congress":                    "INC",
    "Bharatiya Janata Party":                      "BJP",
    "Naam Tamilar Katchi":                         "NTK",
    "Pattali Makkal Katchi":                       "PMK",
    "Viduthalai Chiruthaigal Katchi":              "VCK",
    "Communist Party of India":                    "CPI",
    "Communist Party of India (Marxist)":          "CPI(M)",
    "Indian Union Muslim League":                  "IUML",
    "Desiya Murpokku Dravida Kazhagam":            "DMDK",
    "Amma Makkal Munnettra Kazagam":               "AMMK",
    "Independent":                                 "IND",
    "None of the Above":                           "NOTA",
}


def read_csv(path):
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def to_int(v):
    try:
        return int(v) if v and v.strip() else None
    except (ValueError, TypeError):
        return None


def to_float(v):
    try:
        return float(v) if v and v.strip() else None
    except (ValueError, TypeError):
        return None


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print(f"  {path}  ({len(data) if isinstance(data, list) else 'object'})")


# ── party_summary.json ────────────────────────────────────────
rows = read_csv("eci_party_summary.csv")
party_summary = []
for r in rows:
    party_summary.append({
        "party":       r["party"],
        "short":       PARTY_SHORT.get(r["party"], r["party"][:10]),
        "color":       PARTY_COLORS.get(r["party"], "#94A3B8"),
        "seats_won":   to_int(r["seats_won"]) or 0,
        "seats_2nd":   to_int(r["seats_2nd"]) or 0,
        "seats_3rd":   to_int(r["seats_3rd"]) or 0,
        "seats_4th":   to_int(r["seats_4th"]) or 0,
        "total_votes": to_int(r["total_votes"]) or 0,
        "vote_pct":    to_float(r["vote_pct"]) or 0.0,
    })
write_json("data/party_summary.json", party_summary)

# ── top4.json ─────────────────────────────────────────────────
rows = read_csv("eci_top4.csv")
top4 = []
for r in rows:
    entry = {
        "const_no":    to_int(r["const_no"]),
        "constituency": r["constituency"],
        "total_votes": to_int(r["total_votes"]),
        "margin":      to_int(r["margin"]),
        "swing_to_flip": to_int(r["swing_to_flip"]),
        "swing_pct":   to_float(r["swing_pct"]),
    }
    for p in range(1, 5):
        pfx = f"p{p}"
        party = r.get(f"{pfx}_party", "") or ""
        entry[f"{pfx}_candidate"] = r.get(f"{pfx}_candidate", "") or ""
        entry[f"{pfx}_party"]     = party
        entry[f"{pfx}_votes"]     = to_int(r.get(f"{pfx}_votes", ""))
        entry[f"{pfx}_pct"]       = to_float(r.get(f"{pfx}_pct", ""))
        entry[f"{pfx}_color"]     = PARTY_COLORS.get(party, "#94A3B8")
        entry[f"{pfx}_short"]     = PARTY_SHORT.get(party, party[:10])
    top4.append(entry)
write_json("data/top4.json", top4)

# ── swings.json ───────────────────────────────────────────────
rows = read_csv("eci_swings.csv")
swings = []
for r in rows:
    wp = r.get("winner_party", "") or ""
    rp = r.get("runner_party", "") or ""
    swings.append({
        "const_no":      to_int(r["const_no"]),
        "constituency":  r["constituency"],
        "margin":        to_int(r["margin"]),
        "swing_to_flip": to_int(r["swing_to_flip"]),
        "swing_pct":     to_float(r["swing_pct"]),
        "total_votes":   to_int(r["total_votes"]),
        "winner":        r.get("winner", ""),
        "winner_party":  wp,
        "winner_color":  PARTY_COLORS.get(wp, "#94A3B8"),
        "winner_short":  PARTY_SHORT.get(wp, wp[:10]),
        "winner_votes":  to_int(r.get("winner_votes")),
        "winner_pct":    to_float(r.get("winner_pct")),
        "runner_up":     r.get("runner_up", ""),
        "runner_party":  rp,
        "runner_color":  PARTY_COLORS.get(rp, "#94A3B8"),
        "runner_short":  PARTY_SHORT.get(rp, rp[:10]),
        "runner_votes":  to_int(r.get("runner_votes")),
        "runner_pct":    to_float(r.get("runner_pct")),
    })
write_json("data/swings.json", swings)

# ── meta.json ─────────────────────────────────────────────────
total_votes = sum(r["total_votes"] or 0 for r in top4)
write_json("data/meta.json", {
    "election":             "Tamil Nadu Legislative Assembly Election 2026",
    "state":                "Tamil Nadu",
    "total_constituencies": 234,
    "declared":             233,
    "data_date":            "2026-05-04",
    "total_votes_cast":     total_votes,
})

print("\nDone. Run index.html via a local server or push to GitHub Pages.")
