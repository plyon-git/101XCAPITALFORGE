# Directory methodology

The directory is a research prospect universe, with an explicit split between public contact evidence, capital evidence, and suitability for the proposed transaction. It is not a list of approved lenders.

## Sources and selection

| Source cohort | Why it is included | What it does not establish |
| --- | --- | --- |
| Official operating-capital and contract-finance company sites | Published programs may support company operations or contract performance | Approval for 101XVC, current liquidity, or acceptance of the proposed return |
| Public private real estate lender directories and official sites | Real estate lending experience and published business contacts | Willingness to finance operations without a property lien |
| SBA SBIC directory | Private credit/equity strategy, currently investing status, contact and reported fund size | Eligibility for this operating company, small-ticket appetite, or available cash |
| SEC Form ADV/IAPD private-fund managers | US active status and a disclosed private real estate, private-equity, or named credit fund mandate | Direct lender status, available cash, a $100K–$500K ticket, or acceptance of minority equity |
| NPLA/finance association and factoring records | Public finance industry membership, program contacts, and referral possibilities | Direct funding status or collectible-receivable eligibility |
| Equipment-finance association records | Potential commercial finance referral or working-capital program research | Suitability for an acquisition campaign without an equipment transaction |

Public directory records can include brokers, conventional institutions, or firms whose precise mandate is unknown. Their classifications are preserved rather than presented as confirmed private lenders. Data with missing contacts is retained as incomplete research, not filled with guessed addresses.

## Minimum-capital screen

The SEC cohort requires US domicile, active registration/reporting status, relevant disclosed private funds, and at least $500,000 of related reported private-fund gross assets. The SBA cohort uses published fund information and currently investing status. Company program limits are recorded where actually published.

These are **capacity or asset screens**, not proof of $500,000 liquid cash. A fund's investments, gross assets, commitments, and annual originations cannot be substituted for available cash. Every seed record has `cash_capacity=null` and `capital_verification=unverified` until a user performs appropriate diligence.

## Contact evidence

- Names and phones come from a public business/regulatory record or company source.
- Emails must be actually published in a public source. No naming-pattern guesses or generated emails are used.
- Company website and directory inquiry addresses are distinguished from regulatory/compliance routing contacts. A named compliance contact is not assumed to make investment decisions.
- Published contact details are not deliverability-tested or call-tested.
- Placeholder phone values such as `N/A` are not counted. US phone numbers are normalized for dialing; original strings and extensions remain in structured metadata.
- Public regulatory filings may be current for status but older for fund information; original filing dates and source dates are retained.
- HR, careers, webmaster, privacy, legal and press-only inboxes are removed from financing-contact counts. Compliance and adviser-brochure contacts remain explicitly marked as professional/regulatory routing, rather than funding decision makers.

## Deduplication and counts

The assembly script merges matching normalized company names, official domains, and primary business emails across sources, then reconciles new connections created by enrichment. This deliberately avoids counting a firm's state listings, offices, separate funds, or multiple source appearances as independent lenders. Related entities sharing a website or inbox may be conservatively grouped. All original source records and aliases remain available in the structured research export.

The summary file reports source rows, deduplicated prospects, valid public phones, valid public emails, and records with both. It separately reports documented available cash and confirmed deal suitability. The phone-and-email count is not called a qualified-lender count.

## Reproduce or extend

`scripts/assemble_directory.py` merges the included source cohorts into the CRM seed and CSV exports. Pass the exact source JSONL paths as arguments:

```bash
python3 scripts/assemble_directory.py data/source_cohorts/fit_leads.jsonl data/source_cohorts/sbic_leads.jsonl --out data
```

Add the other included cohort paths to rebuild the full directory. `data/source_cohorts/manifest.json` lists the complete final inputs and their file hashes. The CRM itself requires only Python; research collectors may also require `curl` or `pdftotext` depending on the source. They do not run automatically when the CRM starts.

Run `python3 scripts/rebuild_directory.py` from this folder to rebuild the frozen directory with the included inputs and exclusions. The collected lender-directory expansion is a bounded subset of discovered profiles; pending profiles are not counted as contacts. Discovery/resume metadata and the historical collectors are under `research/` for optional further research. Their dates, public endpoints, rate limits and dependencies need review before a fresh collection; starting the CRM performs no network collection.

Collection uses public unauthenticated sources, bounded requests, and no invented contact information. Blocked or sign-in-gated directories remain unavailable. The package includes extracted factual fields, source URLs, source hashes where available, and collection scripts; it does not republish entire third-party websites or directories.

## Use for this campaign

Prioritize operating-capital and contract financing mandates, then review earned-receivable financing and private-credit/equity mandates. A prospective assignment fee contingent on a future closing is not automatically an eligible invoice. Real estate or buyout fund membership alone is not enough to qualify a minority operating-company equity proposal.

Store direct responses and supporting documents in the CRM before upgrading cash verification or financing fit. All proposed economics in the deal workspace were supplied by the user and are preserved as proposal inputs.
