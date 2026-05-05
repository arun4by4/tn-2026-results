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

**Alliance view:**
- Toggles via **"⊞ Alliance / ⊞ Parties"** button in the header; preference saved to `localStorage` key `tn-alliance`
- Collapses parties into 5 alliances: **TVK** (TVK alone), **DMK+** (DMK, INC, VCK, CPI(M), CPI, IUML, DMDK), **ADMK+** (AIADMK, BJP, PMK, AMMK), **NTK** (NTK alone), **Others**
- Affects all three tabs simultaneously: Overview charts/table aggregate by alliance; Constituencies filter dropdown and all party badges switch to alliance labels/colours; Swing Simulator from/to dropdowns and seat-change chips show alliances
- `ALLIANCE_MAP`, `ALLIANCE_COLORS`, `ALLIANCE_ORDER` constants in `index.html`; `resolveShort(party, short)` and `resolveColor(party, color)` helpers return alliance or party values based on `allianceMode`
- `getDisplayPartyData()` aggregates `partyData` by alliance when active; `projCount(item)` in `onSwing()` sums party-level projected counts per alliance

**Swing model**: generalised FROM → TO vote transfer. The slider represents the % of total votes in each constituency that shift from the FROM party to the TO party.

- **FROM / TO dropdowns** list every party that appears in any finishing position (p1–p4) across all 234 constituencies (not just winners/runners). Default blank values mean "All winners" / "All runners", preserving the classic winner→runner behaviour.
- **Flip threshold** is computed per constituency by `computeFlipPct(t, fromVal, toVal)` based on the positions of the FROM and TO parties in that constituency:
  - FROM=winner, TO=runner (default): `margin / (2 × total_votes) × 100`
  - FROM=winner, TO=non-runner: `min(margin / total_votes, (p1−pT) / (2×total_votes)) × 100`
  - FROM=non-winner, TO=any non-winner: `(p1_votes − to_votes) / total_votes × 100`; returns null if FROM party doesn't have enough votes to supply the needed margin
  - TO=winner: null (winner only grows stronger)
  - Constituencies where the FROM or TO party is absent are skipped
- **New winner** is determined by `computeNewWinner()` — applies the delta and finds the party with the most votes after the transfer; may be p3 or p4, not necessarily the runner-up
- Seat counts, the projected bar chart, seat-change chips, majority indicator, and flip table all use the actual new winner (not always runner_party)
- In **alliance mode**, `resolveToParty()` maps each alliance to its highest-placed member party in the constituency before applying the same formula
- Helper functions: `buildTop4Map()` (indexes top4Data by const_no at init), `resolveToParty()`, `computeFlipPct()`, `computeNewWinner()`, `partyDetailsInConstituency()`; `top4Map` global holds the indexed data

**GitHub Actions deployment** (`.github/workflows/deploy.yml`):
- Triggers on push to `main` or manual `workflow_dispatch`
- Manual trigger has a `refetch` boolean: if true, runs all three Python scripts (full re-scrape, ~5 min); if false (default), only runs `convert_to_json.py` from committed CSVs
- Deploys via `actions/deploy-pages@v4` — Pages source must be set to **GitHub Actions** in repo settings (Settings → Pages → Source: GitHub Actions)

**To deploy to GitHub Pages:**
1. Enable Pages: Settings → Pages → Source: **GitHub Actions**
2. Commit everything including `data/` and CSVs (`venv/` is gitignored)
3. Push to `main` — the workflow runs automatically
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
