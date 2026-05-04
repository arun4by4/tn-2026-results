# TN 2026 Election Results Scraper

Tamil Nadu Legislative Assembly Election (May 2026) — data scraping and analysis.
Source: Election Commission of India (results.eci.gov.in). State code S22.

## Environment

- Python venv at `venv/` — activate with `venv/Scripts/activate` or call scripts directly via `venv/Scripts/python`
- Dependencies: `curl_cffi`, `beautifulsoup4` (installed in venv)
- ECI blocks standard `requests` with HTTP 403 — always use `curl_cffi` with `impersonate="chrome124"`

## Scripts

### fetch_eci_results.py

Fetches the 12 statewise summary pages and saves one row per constituency.

```
venv/Scripts/python fetch_eci_results.py
```

- Source URLs: `statewiseS221.htm` through `statewiseS2212.htm` (20 constituencies/page, 234 total)
- Output: `eci_results.csv` — 234 rows, one per constituency
- Columns: `page`, `Constituency`, `Const. No.`, `Leading Candidate`, `Leading Party`, `Trailing Candidate`, `Trailing Party`, `Margin`, `Round`, `Status`
- Parsing note: party-name cells embed a nested `<table>` tooltip; the actual name is the first `<td>` inside that inner table

### analyze_eci.py

Fetches individual constituency pages (all candidates + vote counts), then produces three analyses.

```
venv/Scripts/python analyze_eci.py           # fetch fresh + analyze
venv/Scripts/python analyze_eci.py --no-fetch  # reuse eci_detailed.csv, skip network
```

- Source URLs: `ConstituencywiseS22{N}.htm` where N = constituency number from `Const. No.` column
- Requires `eci_results.csv` to exist (run fetch script first)
- Makes 234 HTTP requests with 0.8s delay (~5 min total)

**Output files:**

| File | Contents |
|---|---|
| `eci_detailed.csv` | Every candidate in every constituency — rank, EVM votes, postal votes, total votes, vote % |
| `eci_top4.csv` | Top-4 finishers per constituency with vote %, margin, swing-to-flip votes and % |
| `eci_party_summary.csv` | Per-party: seats won, 2nd/3rd/4th place counts, total votes, overall vote % |
| `eci_swings.csv` | All 234 seats sorted by swing-to-flip (ascending) |

**Printed analyses:**
- Party performance table (filtered to parties with >0.5% vote share or any seats)
- Swing brackets: knife-edge / very tight / tight / comfortable / safe
- Vulnerable seats list (swing < 2000 votes)
- Hypothetical uniform swing table at 0.5%, 1%, 1.5%, 2%, 3%, 5%

## Data Notes

- Constituency numbers (1–234) map directly to the URL suffix in `ConstituencywiseS22{N}.htm`
- `eci_detailed.csv` candidate `rank` is by total votes descending (not ballot order)
- Swing-to-flip = `(margin + 1) // 2` — votes that must physically move from winner to runner-up
- Swing % = swing-to-flip / total_votes_cast_in_constituency
- NTK (Naam Tamilar Katchi) contested 234 seats, won 0, finished 4th in 227 — large vote-share with no seat conversion

## 2026 Results Snapshot (as of fetch date 2026-05-04)

| Party | Seats | Vote% |
|---|---|---|
| Tamilaga Vettri Kazhagam (TVK) | 107 | 34.92% |
| Dravida Munnetra Kazhagam (DMK) | 60 | 24.19% |
| All India Anna Dravida Munnetra Kazhagam (AIADMK) | 47 | 21.21% |
| Naam Tamilar Katchi (NTK) | 0 | 4.00% |
| Indian National Congress (INC) | 5 | 3.37% |
| Bharatiya Janata Party (BJP) | 1 | 2.97% |
| Pattali Makkal Katchi (PMK) | 4 | 2.17% |

- 233/234 results declared; 1 DMK seat still counting at fetch time
- Tightest seat: TIRUPPATTUR (DMK wins by 30 votes)
- A 2% uniform swing would flip 91 seats
