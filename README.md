# CapitalForge by 101XVC

A locally hosted private-capital CRM for the 101XVC acquisition and fulfillment financing campaign. The same application can run on your computer or on a conventional server under your own domain.

## Start on your computer

1. Install **Python 3.11 or newer** from [python.org](https://www.python.org/downloads/). No Python packages, subscriptions, API keys, or CDN are required.
2. Extract the complete ZIP. Keep `app.py`, `static/`, and `data/` together.
3. On macOS, double-click `start-mac.command`. If macOS does not allow it to run, open Terminal in this folder and run `python3 app.py`. On Windows, double-click `start-windows.bat`. On Linux, run `sh start-linux.sh`.
4. Once the terminal says the server is ready, open **http://127.0.0.1:8787/app**.
5. Create your administrator account. There is no default password. Use the administrator settings to add analysts or viewers.
6. Keep the terminal open while you work. Stop the server with Ctrl+C. Your records persist in `runtime/capitalforge.sqlite3` and reload the next time you start.

If port 8787 is occupied, run `python3 app.py --port 8788` and open the corresponding address. On Windows, use `py -3 app.py --port 8788`.

## What is included

- Public HTML entry page and private login portal.
- Searchable, paginated directory with company, contact, phone, email, website, source, financing type, capital verification, and collateral fit.
- Pipeline stages, lead notes, follow-up tasks, ownership, and suppression controls.
- CSV/JSON import, duplicate merging, and CSV export.
- A private deal workspace with the proposed financing terms and economics.
- Administrator, analyst, and read-only viewer roles; password hashing, sessions, CSRF protection, audit records, and database snapshots.
- Original structured research, directory source links, collection scripts, and methodology.
- A Docker and Caddy configuration for your own HTTPS domain. See [HOSTING.md](HOSTING.md).

The CRM stores its own data locally. It does not send emails or texts. Clicking a website or starting an email uses your browser or email client.

## Read the directory correctly

The frozen snapshot contains **6,563 distinct research prospects**, including **3,089 with both published phone and email**. The nonbank contact export contains **3,077** after recognized bank candidates are removed. Documented $500K available cash and confirmed deal eligibility are both **zero**.

See `data/directory_summary.json` for the measured final count. `data/capital_prospects.csv` contains every deduplicated research prospect. `data/contact_complete.csv` contains only records with both a public phone and public email. `data/nonbank_contact_candidates.csv` further removes recognized bank candidates; it still includes brokers and fund managers whose direct funding status needs review. `data/public_directory.jsonl` retains detailed source fields, alternate contacts, reported assets, and original fit notes. `data/data_lenders.jsonl` is the automatic CRM seed.

The data combines operating-capital financiers, factoring/receivables firms, real estate lenders, private-credit investors, SBIC managers, and private real estate/equity fund managers. A company appearing in a directory is a research lead. A fund manager is not automatically a direct lender. A broker is not automatically the capital provider.

**Available cash is not inferred from fund assets, annual loan originations, a licensing record, or advertised maximum loan size.** No record starts with documented $500,000 available cash or confirmed eligibility for this transaction. Published email means the address was observed in a public business source, not that deliverability has been tested. Missing phone or email fields remain blank.

The complete-contact export is a capital research universe, rather than a claim that every listed company is a direct private lender. It includes private-equity managers because the proposal has an equity alternative. Regulatory brochure emails are marked as routing contacts. Employment, webmaster, privacy, legal and press-only inboxes are excluded from financing-contact counts.

Property-backed loan programs may be a collateral mismatch for acquisition marketing and operating expenses. Factoring generally requires an eligible receivable; future assignment fees contingent on a closing need separate underwriting. Private-equity managers require ticket-size, sector, control, and investment-mandate review.

## Current trial funding mandate

The current campaign seeks **$100,000 to $500,000 of operating capital** for acquisition sourcing, marketing and execution of the 500-closing trial. The trial allocation is 100 closed properties in each of Texas, Arizona, North Carolina, Illinois and Florida.

| Item | Current basis |
| --- | --- |
| Capital sought | $100,000 to $500,000 |
| Trial completion | 500 closed properties, 100 per trial state |
| User-projected trial collections | $3.9 million to $7.2 million; supplied average $5 million |
| Forecast basis | Confirm whether figures mean 101XVC fees or another transaction measure; not net profit |
| Prior equity proposal | $500,000 for 9.3%, subject to documentation |
| Discussion milestone | Earlier of 200th closed property or 450th qualifying submission |
| Proposed continuation | 3,000 closed properties, 200 each across 15 states |
| Proposed Contract 2 | 11,250 closed properties including continuation; 8,250 remaining after it |
| Successor status | Non-binding expression of interest requiring definitive agreements |

The October 2, 2026 amendment changes the completion and negotiation milestones. It does not specify a dollar revenue award or payment timetable. The original agreement supplies the remaining economics and obligations. The signed source document is not included in this public repository.

The current default workspace removes the older 60-day fulfillment target, 50% proposed debt-return default and $115 million successor-fee estimate. Completely unchanged old default mandates migrate; customized mandates remain intact. Review a customized installation under **Deal workspace > Edit mandate** before relying on its stored figures. Debt and equity remain separate financing paths, and documented eligibility requires financier review.

A $500,000 primary investment for 9.3% implies approximately $5.376 million post-money and $4.876 million pre-money, before any structure-specific adjustments.

See [use steps](docs/USE_CAPITALFORGE.md) and [current capital sourcing](docs/TRIAL_FUNDING_RESEARCH.md). Search `trial-100k-500k-2026-10-02` in the lender directory to find the current reviewed cohort. Restart after updating the application and data files to import it automatically.

## Qualify before moving a prospect forward

Confirm the funding decision maker, direct-lender or broker status, available capital, actual check size, the treatment of contingent fees, acceptable collateral and guarantees, operating-company or equity eligibility, timing, and proposed economics. Save the response and source in the lead record. Use `documented` capital only when documentation supports actual available capital, rather than a reported fund-size screen.

Suggested sequence: review the operating-capital cohort first; assess contract/receivables eligibility next; review private-credit and real estate equity mandates; use property-backed lenders for introductions or a revised structure when appropriate.

## Backups and updates

Use the administrator backup control before a large import. Database snapshots are written under `runtime/backups/`; they omit live login sessions. See `docs/BACKEND_SECURITY.md` for restore instructions. Stop the application before copying or restoring its live database. Keep a copy of your complete `runtime/` directory when moving computers.

Automatic seed imports merge known contacts and preserve workflow stages, ownership, suppression, and verified research. A later source collection does not reset those fields. Source dates remain visible so you can assess freshness.

## Repository layout

```text
app.py                     HTTP API, authentication and SQLite persistence
static/                    Offline HTML, CSS and JavaScript frontend
data/                      Directory, CRM seed, counts and research provenance
scripts/                   Research, normalization and hosting helpers
tests/                     Operational API/security checks
docs/                      API and security notes
Dockerfile, compose.yaml   Conventional server deployment
deploy/Caddyfile           HTTPS reverse proxy
runtime/                   Your local database and backups, created at first launch
```

Run the checks with `python3 -m unittest discover -s tests -v`. See `docs/API.md` for the integration API. The application is intended for a small internal team; it is not a multitenant subscription service.

## September 30 corporate equity research snapshot

The targeted $500K-for-9.3% research pass adds **180 distinct funding vehicles/group routes** and **86 named professionals** across **235 research/contact records**. **119 records** have both public phone and email, representing **65 distinct vehicles**. Cash availability and acceptance of the proposed ownership are unverified.

The new cohort loads automatically from `data/equity_directory.jsonl`; search `equity-500k-9.3` in the CRM. Different named principals sharing a firm inbox are retained separately. See [equity methodology](docs/EQUITY_RESEARCH.md), [investor workbook](downloads/CapitalForge_Equity_Investors.xlsx), [phone/email contacts](downloads/CapitalForge_Equity_Phone_Email.csv) and [named professionals](downloads/CapitalForge_Named_Investors.csv).

The September 30 directory is historical research. Use the October 2 trial funding review for current priorities, milestones and published program checks. New review evidence is retained separately from original lead research.
