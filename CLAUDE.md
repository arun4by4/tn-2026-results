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

### convert_to_json.py

Converts the CSV outputs into JSON files consumed by the static web UI.

```
venv/Scripts/python convert_to_json.py
```

- Reads `eci_party_summary.csv`, `eci_top4.csv`, `eci_swings.csv`
- Writes to `data/` directory: `party_summary.json`, `top4.json`, `swings.json`, `meta.json`
- Embeds party colors (`color`) and abbreviations (`short`) directly into each record
- Must be re-run whenever the CSVs change

## Static Web UI (index.html)

Pure static HTML/CSS/JS — works on GitHub Pages with no build step.

**Tabs:**
- **Overview** — 4 metric cards, seats-won horizontal bar chart, vote-share doughnut, full party performance table with 1st/2nd/3rd/4th place counts, total votes, and inline vote-share bar
- **Constituencies** — search (name/candidate/party), filter by winning party, sortable column headers (click to toggle asc/desc); columns: #, Constituency, Winner + vote%, Party, Runner-up + vote%, Party, 3rd Place + vote%, 4th Place + vote%, Margin, Swing to flip; click any row to expand all 4 candidates with vote counts
- **Swing Simulator** — 0–10% slider (0.1% steps), "from party / to party" dropdowns, live grouped bar chart (current vs projected), per-party seat-change chips, majority indicator, scrollable flip table

**Constituency table — mobile vs desktop:**
- Desktop (>768px): full 11-column sortable table, uses full viewport width with no max-width cap
- Mobile (≤768px): card-based layout — each constituency card shows all 4 candidates stacked with badge + name + vote%, plus Margin and Swing chips colour-coded by risk (red/amber/green)

**Dark mode:**
- Default on first load; toggles via **"☀ Light / ☾ Dark"** button in the header
- Implemented via CSS custom properties (`--bg`, `--card`, `--surface`, `--border`, `--text`, `--text-m`, `--text-f`); `[data-theme="dark"]` on `<html>` overrides `:root`
- Preference saved to `localStorage` key `tn-theme`
- Chart.js axis/grid/legend colours updated in `applyChartTheme(isDark)` on every toggle and on initial load

**Swing model**: a seat flips when `swing_pct <= slider value`. `swing_pct = (margin/2) / total_votes × 100`. The "from/to" dropdowns filter by winner_party and runner_party respectively.

**To deploy to GitHub Pages:**
1. Run all three Python scripts to generate CSVs and then JSON
2. Commit everything including the `data/` folder (`venv/` is gitignored)
3. Push to GitHub; enable Pages (Settings → Pages → Branch: main, folder: / root)
4. Site available at `https://<user>.github.io/<repo>/`

**To preview locally** (`fetch()` requires HTTP, not `file://`):
```
python -m http.server 8765
# open http://localhost:8765
```

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
