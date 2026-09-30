# Bounded financier-data audit

Read the final 89 fit, 183 SBIC, 386 supplement and 999 primary bulk rows, plus the assembler. Existing cohort files were not changed. The source sample contained 20 records at the assembler's highest complete-contact priority, 20 randomly selected complete private-property records and 10 randomly selected SBIC records, using a fixed seed.

The sample matched 46 email addresses and 47 phone numbers directly in saved source snapshots. Alpha Commercial Capital, Andij Capital Consulting, Credibly and Crestmont Capital rely partly on retained official-source web-search references: their local HTTP retrievals returned errors or omitted the cited contact page. Their source references and exact official URLs remain recorded. No invented email patterns were observed in this bounded review.

Concrete dispositions are in `data-quality-holds.json`: 19 confirmed service-provider or wrong-website records should leave the financier directory. These include lending-software, appraisal, inspection, legal/title and property-management vendors. Three automated `robot.zapier.com` form inboxes—Zinc Financial, Casa Lending and Dunmor—should not count as direct lender emails. Each hold retains a primary URL and cached evidence. Fourteen of these 22 original records had both contact fields; duplicates and company-site replacements can change the final count impact.

Goldleaf Investment Fund I has a specific supported correction: its old contact page displays the template email `brandon@consulting.com` beside a fictitious-style address and example phone. Its separate real contact page publishes `andy@goldleafinvestmentfund.com` with `904-557-6191`. See `data-quality-contact-corrections.json`. Supplement's cleaned derivative has already removed the 19 service/wrong-site holds and corrected Goldleaf.

Sixty-seven PrivateLenderLink records use the first service-area state as a headquarters state. For example, Casa Lending is labeled Alabama while its saved address is Cleveland, ZIP 44114. Preserve the source service-area list and leave the headquarters state empty until independently supported. These metadata corrections are in `data-quality-state-holds.json`; they do not invalidate the published phone or company email.

The assembler emits no verified cash capacities: every CRM cash-capacity field is empty and every capital-verification field is unverified. SBIC fund and vintage arrays survive normalization in metadata. Sixteen SBIC manager-alias groups share published contact emails; the assembler's email-based reconciliation is appropriate for these manager groups and preserves the merged source records.

Two short contact notes currently disappear from the ordinary CSV notes because `normalize()` does not include `contact_note` in its note fields: Kapitus uses a 2019 PDF email source, and Credibly's address routes to customer service. Add `contact_note` to those fields. The original notes remain in JSON metadata, so this is a presentation loss rather than lost evidence.

Fourteen explicitly bank-named supplement candidates are listed in `data-normalization-audit.json`. Classify them separately from private nonbank financiers or exclude them from a private-only count. Bankers Factoring was not flagged merely because of its name. Program limits, fund assets and equipment-finance annual originations remain distinct from currently available cash throughout the normalization.

One additional qualification flag is JC REInvestment Group: its current website describes a cash home buyer rather than a financing product. Its published contacts are correctly sourced, but lending should remain unconfirmed. This review did not treat domain differences alone as mismatches; affiliate and brand-domain contacts can be valid.

The audit was bounded and used cached evidence. It did not test email delivery, confirm telephone ownership by calling, establish liquidity, obtain financing approval, or contact any prospect.
