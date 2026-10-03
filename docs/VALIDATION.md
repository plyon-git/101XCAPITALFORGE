# Validation

Verified locally on 2026-09-30 with synthetic accounts and workflow records in an isolated runtime. The supplied directory files were not changed by testing.

The backend suite passed 11 integration tests covering authentication, roles, CSRF, lead and task validation, imports, workflow-preserving merges, suppression, audit and backups. Persistent HTTP connections were also checked through backup download, logout and subsequent login.

Browser checks passed for first-administrator setup, login and session persistence; directory search, pagination and combined filters; relationship creation, assigned owner ID, evidence, notes, stage and fit changes; suppression; linked follow-ups; pipeline navigation; CSV export and import; mandate editing; team access; the last-administrator safeguard; audit; backup download; password changes and logout. Viewer mutations were blocked, analysts could maintain relationships, and mandate editing remained administrator-only. No JavaScript errors were observed.

The browser imported 1,000 JSONL records in four sequential requests of 250 rows. All 1,000 unique records were confirmed across two API pages of 500. Five CSV edge records retained their exact values through a BOM, quoted commas, doubled quotes, embedded newlines and empty fields. JSON object imports and invalid-record feedback were checked. Existing workflow, suppression and recorded capacity survived merge imports.

Desktop views were inspected at 1440×1040. Mobile login, navigation, the directory and relationship drawer were checked at 390×844: the document did not overflow horizontally, the drawer fit the viewport and tables scrolled inside their cards. Downloaded backups contained no active sessions or authentication-failure history.

Assigned-owner labels currently display the user ID when a name is unavailable; the owner dropdown and persisted assignment work correctly. Live website hosting and real financier qualification were outside this local validation. No outreach was sent.

The complete frozen directory was then imported into a fresh isolated database. The measured count, contact-pair count, zero invalid rows and zero unexpected merges are recorded in `FINAL_DATA_VALIDATION.json`. This validates file/schema compatibility; it does not validate liquidity, recipient authority or financing acceptance.

## October 2 trial funding update

- Sixteen backend and startup integration checks pass, including mandate range validation, exact legacy-default migration, preservation of customized mandates, trial cohort startup/restart import, notes/tasks, roles, authentication and backup restoration.
- JavaScript syntax and Git whitespace checks pass.
- Full actual data import: 6,563 original records inserted; 233 equity records inserted and two merged; 35 trial review routes added through 23 insertions and 12 merges, zero invalid rows.
- Cohort search data contains all 35 reviewed routes. A repeat trial import adds zero records, merges all 35 and preserves a recorded stage and contact suppression.
- Reviewed route data includes 18 equity/private routes, 16 business-debt routes and one SBA program channel. Provider/affiliation groups total 32; these are research channels, not confirmed allocations.
- Public-source review checked current mandates and contact routes. CEF's 90-120-day timeline, industry exclusions and program-specific contact are recorded. Bluevine partner loans and OnDeck/Headway access are distinguished from independent provider commitments.
- A local portal/startup check ran against a temporary database only.

## October 3 agreement economics correction

- Both agreements were read together: original sections 2.14(d), 2.23 and 2.19 supply the $20,000 estimated gross transaction profit threshold and 50% assignment share; amendment sections 1.A and 3 supply the controlling 500-closing trial. The resulting underwriting base is $5,000,000 in gross 101XVC assignment fees before its own costs under original section 5.3.
- Seventeen integration tests pass, including read-only contract inputs, the separate sensitivity assumptions, exact prior-default migration and preservation of customized stored mandates. JavaScript syntax and Git whitespace checks pass.
- The canonical sourcing data, generated directory/export, app mandate and documentation use the same agreement-derived calculation. The 35 financing routes and their qualification requirements remain in place.

## October 2 broader prospect campaign

- Nineteen integration tests pass, including campaign startup and repeat imports that preserve workflow, ownership, suppression, documented capacity, original/trial research, notes and tasks. JavaScript syntax passes.
- The final cohort contains 2,500 distinct selected businesses, 820 public emails, 2,312 public phones and 735 complete contact pairs. Source links and contact roles accompany all rows. The list includes 1,424 property-investor/operator/private-money inquiries; available cash and investment appetite remain unconfirmed.
- Final source QA removed form-placeholder/vendor emails, collapsed shared-phone aliases, corrected overstated first-party contact flags and excluded an agent-only listing from the operator cohort. Direct emails, business phones and domains are unique among populated final fields.
- The full real-data seed and repeat-import result is recorded in `data/research_audits/investor2500_import_validation.json`. An isolated database contains all 2,500 campaign search results, zero invalid campaign rows and preserved workflow/suppression after a repeat import.
- The Excel export contains all 2,500 unique prospect IDs across 42 columns. Every source-data cell was compared with the canonical research; the table filter, frozen header/company columns, six-option Status dropdown and blank editable Notes were checked. Both tabs were rendered and inspected. Live contact-count and agreement-base formulas recalculate correctly, with zero formula errors.
