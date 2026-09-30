# SEC private-fund manager prospect screen

Retrieved 2026-09-30 UTC (2026-09-29 in Denver). These are research prospects, not confirmed willing lenders, investors, or holders of $500,000 in available cash.

## Primary sources and dates

- [SEC Form ADV data landing page](https://adviserinfo.sec.gov/adv), public filing schedules in CSV.
- [SEC current adviser roster](https://www.sec.gov/help/foiadocsinvafoia), September 1, 2026 registered and exempt reporting adviser snapshots.
- [SEC September 29, 2026 current firm compilation](https://reports.adviserinfo.sec.gov/reports/CompilationReports/IA_FIRM_SEC_Feed_09_29_2026.xml.gz), used to require current active/approved status, US principal office, business phone, name and published websites.
- [Official public filing manifest](https://reports.adviserinfo.sec.gov/reports/foia/reports_metadata.json), used to download all available January-August 2026 monthly Form ADV filing archives.
- Each published company email has its exact first-party source page in `email_source_url`; checked pages and errors are retained.

## Firm-level selection

One record per SEC adviser CRD number. Require a US principal office, current status `APPROVED` or `ACTIVE`, and a disclosed real-estate/private-equity private fund or named private-credit/asset-based/mortgage fund. Require at least $500,000 in reported private-fund gross assets. When current-year specific fund records exist, require an eligible related fund itself to show at least $500,000 gross assets. Generic wealth advisers, mutual-fund-only firms, and ordinary public-securities investment managers are excluded.

Private-credit screening uses explicit fund names/descriptions containing private credit, direct/private/commercial lending, real-estate debt/credit, mortgage, mezzanine, asset-based, receivables, specialty finance, opportunistic/structured credit, or middle-market credit. This is a research signal, not proof of willingness to finance this contract. Exact matched fund evidence is retained in `fund_evidence`.

These classes are intentionally distinct:

- `real_estate_fund_manager`: a disclosed real estate private fund; an operating-company investment still requires qualification.
- `private_credit_manager_research`: a disclosed named debt/credit fund; no unsecured-contract mandate is assumed.
- `equity_manager_research`: a disclosed private-equity fund; research needed to determine whether the 9.3% company-equity proposal is within mandate and ticket size.

Adviser firms sharing an investment platform or ultimate owner may remain distinct CRDs; the CRM import can consolidate them using company website/phone. Each adviser appears once, not once per managed fund.

## Contact enrichment

Fetch public company homepage and up to two public on-domain contact pages. The final worker pool visits up to 24 distinct domains concurrently, serializes each individual domain, and caches exact URL responses and failures so firms sharing a platform do not cause repeated requests. First-party redirects from the SEC-published website are allowed. Ignore public social-media profiles and personal addresses. Extract only visibly embedded email addresses, `mailto:` contacts, or Cloudflare-protected publicly embedded contact strings. Prefer published company domain and general/investment/business inboxes. Exclude privacy, legal, DPO, careers, recruiting, support, press/media, webmaster, unsubscribe and no-reply routes. No guessed patterns, address permutations, purchased people records, private emails, bulk email sending, or SMTP delivery probing.

Public SEC Form ADV CSV/XML/PDF exports omit or redact compliance email fields. A regulatory contact name found in public 1J/1K filing tables is labeled by its actual role; it is not represented as an investment decision-maker. Website-published email may belong to a different public professional or business inbox, so the contact-name and email sources are separate.

Public phone numbers come from the current September 29 SEC business profile. Published email does not prove deliverability. Inaccessible pages, absent websites, and missing contact fields remain explicitly marked. Firm business city/state is retained, but street addresses and private residences are not exported to the contact directory.

## Capital qualification limits

`reported_private_fund_gross_assets_usd` is the SEC snapshot's reported aggregate private-fund gross asset value. Fund gross assets can include portfolio assets, debt, feeder/master overlap and encumbered holdings. They are not available cash, committed dry powder, ticket size, or assets belonging to the adviser itself. `liquid_cash_verified` is false and `minimum_cash_status` is unverified for every SEC prospect. No record confirms acceptance of the 50% proposed return, 6-12 month term, 60-day fulfillment timetable, fee projections, equity valuation or unsecured structure.

Reproduce with `python3 scripts/sec_manager_prospects.py --max-workers 24`. Scripts use the Python standard library. The original public archives and exact retrieved metadata are retained under `research/sec/`; their URLs and hashes can be audited separately.

## Optional SEC brochure fallback

For firms with no discovered company-website email, the public IAPD firm profile may link a Part 2A adviser brochure. The profile returns `brochures.brochuredetails` with `brochureVersionID`, `brochureName` and `dateSubmitted`. The exact public brochure URL is retained. Only the first three PDF pages are inspected for a published professional contact address. Compliance and regulatory routes are explicitly labeled, and are not portrayed as finance decision-makers. There are no guesses of redacted Part 1J email addresses.

Brochure email evidence is exported separately by the odd/even CRD research workers and should fill an absent website email only. Prefer the company website email if both sources are available. Keep `brochure_contact_role`, `brochure_source_url`, `brochure_date` and the short source excerpt. Public brochures can be stale, inaccessible, or contain no email; those conditions remain marked.

Email suffixes are checked against the [official IANA root-zone TLD list](https://data.iana.org/TLD/tlds-alpha-by-domain.txt), retrieved September 30 UTC, version 2026092900. PDF sentence punctuation can join an email and the next word, such as `...com.The`; trimming an invalid trailing sentence segment preserves the literal email substring in the source. No alternate email patterns or invented domains are generated.
