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

## The proposed deal

The private workspace starts with the user's supplied proposal:

| Item | Starting value |
| --- | --- |
| Capital sought | $100,000–$500,000 |
| Proposed debt return | 50% total return over 6–12 months |
| Equity alternative | 9.3% company equity for $500,000 |
| Initial contract | 500 properties |
| Fulfillment objective | 60 days |
| Initial estimated fees | $5,000,000 |
| Follow-on estimated fees | $115,000,000, contemplated upon the 450th submission |
| Counterparty size | $2.2 billion, user supplied |
| Property collateral | None offered |

These entries are proposal inputs and estimates, not independently verified contract obligations, guaranteed returns, or lender approvals. The debt proposal and equity alternative are separate unless a later agreement combines them. A $500,000 purchase of 9.3% implies approximately **$5.376 million post-money** and **$4.876 million pre-money** equity valuation, assuming newly issued equity. A secondary share sale has different implications.

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

## Corporate equity investor update

The targeted $500K-for-9.3% research pass adds **180 distinct funding vehicles/group routes** and **86 named professionals** across **235 research/contact records**. **119 records** have both public phone and email, representing **65 distinct vehicles**. Cash availability and acceptance of the proposed ownership are unverified.

The new cohort loads automatically from `data/equity_directory.jsonl`; search `equity-500k-9.3` in the CRM. Different named principals sharing a firm inbox are retained separately. See [equity methodology](docs/EQUITY_RESEARCH.md), [investor workbook](downloads/CapitalForge_Equity_Investors.xlsx), [phone/email contacts](downloads/CapitalForge_Equity_Phone_Email.csv) and [named professionals](downloads/CapitalForge_Named_Investors.csv).
