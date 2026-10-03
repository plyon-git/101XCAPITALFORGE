# 2,500 potential capital prospects

The campaign broadens the $100K-$500K raise to property investors, cash-home-buying operators, private-money lenders, flexible private-capital firms and fund managers. It supports the signed 500-closing trial's agreement-derived underwriting base: $20,000 estimated gross transaction profit per deal x 500 closings x 50% = $5 million in gross 101XVC assignment fees before its own costs.

## Use the list

1. Download the updated feature branch while PR #1 is pending, replace the code/data files and restart CapitalForge. Keep the existing `runtime` folder to preserve your account and CRM.
2. Open **Lender directory**, search `investor-2500-2026-10-02`, and leave capacity evidence set to **All**. The campaign imports automatically after the original and trial cohorts.
3. Open a record and read **Prospect campaign review** for its category, contact role, fit, source and next step. Existing research and the narrower 35-route trial review remain visible separately.
4. Start with reviewed trial-capital routes and property operators in the five trial states. Qualify the requested allocation and operating-company debt/equity structure with the owner or investment decision maker. A property mortgage program may require a separate corporate-capital arrangement.
5. Record the response, proposed structure, amount, funding date and supporting evidence in the CRM. Set a follow-up task or suppression flag as appropriate.

The Excel workbook provides filters and editable outreach status/notes. The CSV is a portable research export. All contacts are published business routes. Missing names, emails, phones and check sizes stay blank. Published contact details have not been call-tested or deliverability-tested. No outreach has been sent.

## Selection and source meaning

The target is 2,500 distinct prospect organizations or individual capital businesses, with aliases and repeated offices collapsed by normalized company, business domain, published inbox and shared business phone. Shared routing numbers conservatively group related contacts; the list does not count them as separate outreach targets. Multiple named partners sharing a firm inbox do not become independent investors. Where different states/domains indicate a same-name business, only the selected business's contact evidence is attributed to its record.

Reviewed trial sources come first. New public property-operator searches broaden the list to the flippers and cash buyers requested by the user. Existing private lenders, real-estate fund managers, private investors and operating-finance sources are screened for useful public contact routes and ranked for this campaign. Source dates remain attached; selecting an existing record does not represent a new verification of its entire mandate.

Public home-buyer directories contain service providers and brokers as well as investors. Unrelated insurance, auto, jewelry, photography and other entries are excluded. Operator listings with clear business-role evidence remain prospecting leads; first-party activity checks are separately recorded. Regulatory/compliance contacts remain routing contacts and are not called investment decision makers.

The original existing-source audit holds unexplained multi-firm manager phone clusters, removes automation/template emails and excludes documented wrong-role businesses. A company website published by a directory can be a provisional route even when it was unreachable during the check. The provenance field identifies that case.

Requested tickets are $100K-$500K. Published property-loan limits, fund assets, LP subscription minimums and corporate investment tickets retain their own scope. These do not establish cash available to 101XVC or approval for this transaction. The list deliberately includes potential contacts whose structure and appetite need qualification.

Additional public SFR operator profiles and platform-only family-office listings are retained in a separate discovery reserve. A source profile alone does not count toward the 2,500 business-contact campaign. Public company routes were verified for a subset of that reserve and added to the contact candidates.

## Files and rebuild

- `data/investor2500_research.jsonl`: selected factual research and source evidence.
- `data/investor2500_directory.jsonl`: idempotent CRM seed.
- `data/investor2500_summary.json`: exact campaign counts.
- `data/source_cohorts/investor2500_new_contacts.jsonl`: newly collected public contact candidates.
- `data/source_cohorts/investor2500_discovery_reserve.jsonl`: source-listed organizations requiring business-contact enrichment.
- `data/research_audits/investor2500_selection.json`: exclusions and source audit.
- `downloads/CapitalForge_2500_Potential_Investors.csv` and `.xlsx`: portable list and filterable workbook.

Run `python3 scripts/build_investor2500.py` to rebuild the research, seed, CSV and summary from the saved inputs. The workbook builder uses the Codex spreadsheet runtime and is a separate optional authoring step. The CRM itself needs only Python and performs no network research at startup. Use `--investor-seed-file ""` to skip this campaign or pass another JSONL path.

<!-- generated-campaign-counts -->

## Selected cohort counts

| Measure | Count |
| --- | ---: |
| Distinct selected prospects | 2,500 |
| Published business emails | 820 |
| Published business phones | 2,312 |
| Both email and phone | 735 |
| Published business websites | 2,324 |
| Newly collected prospects selected | 1,546 |
| First-party operator activity checks | 190 |

| Campaign category | Count |
| --- | ---: |
| Reviewed trial-capital route | 29 |
| Property investor / operator inquiry | 1,424 |
| Private operating-company capital inquiry | 102 |
| Operating-capital eligibility inquiry | 81 |
| Property lender / private-money inquiry | 864 |
