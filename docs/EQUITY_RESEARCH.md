# CapitalForge equity investor directory

This September 30, 2026 research pass targets $500,000 of corporate equity for a proposed 9.3% interest in 101XVC. It screens family investment firms, corporate equity investors, proptech/seed funds, named investment professionals and US angel-group routes. It adds to the existing broad capital directory.

## Coverage

| Measure | Count |
| --- | ---: |
| Research/application/contact records | 235 |
| Distinct funding vehicles or group routes | 180 |
| Named investment professionals | 86 |
| Records with public business phone and email | 119 |
| Distinct vehicles with paired contacts | 65 |
| Named email plus public business-phone records | 27 |
| Vehicles with published corporate ranges/minimums overlapping $500K | 62 |
| Group routes with published collective ranges overlapping $500K | 7 |
| Records held outside the main screen | 55 |
| Verified available $500K cash | 0 |
| Confirmed acceptance of $500K for 9.3% | 0 |

Counts describe separate dimensions. A named firm partner is a contact at a funding vehicle, not necessarily an independent angel deploying personal money. Several principals may share a firm inbox and office number. Paired contact records are not independent funding commitments. Some research routes have only a website/application; 40 lack both requested contact fields. Missing fields remain blank.

## Files

- `CapitalForge_Equity_Investors.xlsx`: filterable contacts, a compact deal screen and full investment evidence. Sources and restrictions are in Investment evidence, linked by Contact ID.
- `CapitalForge_Equity_Contacts.csv`: all main-screen records.
- `CapitalForge_Equity_Phone_Email.csv`: only records with both public contact fields; the route type identifies firm versus named contact.
- `CapitalForge_Named_Investors.csv`: named professional contacts, including explicitly labeled firm routing.
- `CapitalForge_Equity_CRM_Import.jsonl`: import into the updated CapitalForge; preserves named contacts, source links and qualification details.
- `CapitalForge_Equity_Research.json`: structured facts and provenance.
- `CapitalForge_Equity_Exclusions.csv`: held records, including larger tickets, incompatible mandates and unconfirmed US scope.

## Use in CapitalForge

The updated CRM loads `data/equity_directory.jsonl` automatically when it starts, in addition to the original 6,563-record seed. Restart an existing installation to load the revised app. Search `equity-500k-9.3` in the directory to view this campaign. Importing the supplied JSONL is an alternative. Repeated imports merge known records while preserving stages, owners, contact suppression and prior verified evidence.

Named investor records use `metadata.record_kind=named_investor`. Different people sharing a firm inbox remain separate; the same person at the same company and official website merges on reimport. Ordinary company deduplication is preserved. All new rows start at New; cash and acceptance remain unverified.

## How the screen works

Contacts come from published business websites, professional biographies, public association records or current SEC business-office records explicitly matched to the firm's website. Emails are observed addresses, never naming-pattern guesses. Office numbers, regulatory routing, shared firm inboxes, related operating-company lines and published direct business contacts are labeled separately. No deliverability service, calls or outreach were used.

Published policy is evidence of a possible ticket, not liquid funds or an offer. EBITDA/revenue thresholds, LP subscriptions, transaction values, average/median checks, property-SPV investments and hypothetical portfolio fees are not converted into direct corporate check capacity. The main pool excludes explicit mismatches and unconfirmed US scope; geography, entity and mandate requirements remain in the evidence.

The policy-overlap count includes ranges and minimums that actually cover $500K; it does not mean the firm will buy 9.3%, waive preferred rights, fund a single-customer pilot or accept projected EBITDA as historical earnings. Venture mandates may require a scalable standalone product; owning internal software does not establish that business model. Angel groups may syndicate several investors, and their round targets are separate from collective checks and individual commitments.

Dates on the directory are observation/retrieval dates. Many company policies are undated, so publication vintage is not implied. Primary URL attribution is recorded by contact field and mandate; caches and supplied original attachments are not republished.

## Where to begin

Patterson Thoma publishes $100K–$20M direct investments and no minimum ownership percentage, with working-capital/equity flexibility. It requires achieved revenue success for early-stage companies. Sylvanite publishes minority partnerships in founder-led service businesses; its check size is unknown. CHW publishes US minority growth equity from $500K but requires at least $1M actual revenue and 20% growth. First Seed Ventures and Topaz provide real-estate-sector venture routes whose product, stage and ownership fit still need confirmation. These are reasoned screening priorities, not approvals; their current contact and policy links are in the directory.

## Deal evidence used

The reference proposal is $500K for 930,000 modeled shares / 9.3% on a 10M fully diluted base; the implied post-money equity value is about $5.376M. The optional second $500K/800,000 reserve shares would bring combined ownership to 17.3%, subject to definitive terms. The provided model's saved stage-two scenario uses a $2.5M bank facility, rather than that optional second cash-equity contribution. The two funding cases must be kept distinct.

The provided trial counts 500 qualifying submissions, 100 per state in Texas, Arizona, North Carolina, Illinois and Florida. Fees depend on completed closings. Discussions near submission 450 do not establish a successor award or agreed acquisition. The projected fees, EBITDA, shareholder proceeds and exit values are conditional forecasts, and the equity proposal does not establish a guaranteed 50% return. The original redacted agreement and model were preserved.

## Validation

Source defects in normalized rows: 0. The 235-row equity JSONL imported with 0 invalid rows and retained all named people; the second import added 0 duplicates. The full broad seed and equity seed were also tested together. Twelve backend integration checks passed. Workbook counts reconcile to the directory, formula-error scan found no errors, and every worksheet was visually reviewed. Publicly published contacts still require confirmation before use.
