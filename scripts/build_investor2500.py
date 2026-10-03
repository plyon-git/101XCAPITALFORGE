#!/usr/bin/env python3
"""Build a sourced, deduplicated prospect campaign from saved research.

Selection is a prospecting order, not a probability, approval or cash score.
The source cohorts are factual extracts, not copies of third-party pages.
"""
from __future__ import annotations
import csv
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research"))
import investor_contact_audit as audit

COHORT = "investor-2500-2026-10-02"
DATE = "2026-10-02"
TARGET = 2500
TRIAL_STATES = {"TX", "FL", "AZ", "NC", "IL"}
CONTINUATION_STATES = TRIAL_STATES | {"AL", "CO", "GA", "IN", "KS", "MO", "OK", "SC", "TN", "UT"}
BAD_EMAIL = re.compile(r"(?:example\.|yourdomain|sentry|wixpress|bugreport@|mymail@mailservice|moatable\.com|website@|noreply|no-reply|support@carrot\.com|^name@email\.com$|yourname@)", re.I)
BAD_ROLE = re.compile(r"^(?:hr|careers?|jobs?|recruiting|webmaster|privacy|legal|abuse|security|copyright|dpo|press|media)@", re.I)
OPERATOR_NAME = re.compile(r"home.?buyers?|house.?buyers?|buy.?houses|cash.?offer|sell.?(my|your|to)|property.?buyers|home.?buying|invest|acquisition|cash.?homes|cash.?for.?homes|buy.?and.?sell", re.I)
NON_INVESTOR_NAME = re.compile(r"insurance|cash.?for.?cars|appraisal|estate.sales|estate.services|liquidat|automot|title.company|photograph|jewel|gold.?buyer|credit.?counsel|air.?condition|roofing", re.I)
SHARED_HOSTS = {"facebook.com", "linkedin.com", "instagram.com", "youtube.com", "sfranalytics.com", "axial.net", "bbb.org", "cashhomebuyersdirectory.com", "privatelendersdirectory.com", "hardmoneyhome.com", "privatelenderlink.com"}

def val(v):
    return "" if v is None else str(v).strip().replace("\u2014", " - ")

def urls(r):
    return audit.all_source_urls(r)

def email(r):
    e = val(r.get("email")).lower()
    return e if audit.EMAIL_RE.fullmatch(e) and not BAD_EMAIL.search(e) and not BAD_ROLE.search(e) else ""

def phone(r):
    p = re.sub(r"\D", "", val(r.get("phone")))
    if len(p) == 11 and p.startswith("1"):
        p = p[1:]
    if len(p) == 10 and p[0] in "23456789" and p[3] in "23456789" and p[3:6] != "555":
        return "+1" + p
    return ""

def official_host(r):
    h = audit.domain(val(r.get("website")))
    return h if h and not any(h == x or h.endswith("." + x) for x in SHARED_HOSTS) else ""

def is_new_operator(r):
    return r.get("campaign_input_kind") == "property_operator"

def classify(r):
    if is_new_operator(r):
        return "Property investor / home-buying operator"
    if r.get("campaign_input_kind") == "property_lender":
        return "Property lender / private real-estate capital prospect"
    if r.get("campaign_input_kind") == "private_capital":
        return "Family office / private operating-company capital prospect"
    return audit.classify(r)

def tier(r):
    m = r.get("metadata") or {}
    c = val(r.get("category") or r.get("lender_type"))
    kind = classify(r)
    if r.get("audit_input_file") == "trial_capital_directory.jsonl":
        return (1, "Reviewed trial-capital route")
    if is_new_operator(r) or kind.startswith("Property operator") or c == "private_money_individual":
        return (2, "Property investor / operator inquiry")
    if r.get("campaign_input_kind") == "private_capital" and r.get("primary_contact_verified") and (email(r) or phone(r)):
        return (3, "Private operating-company capital inquiry")
    if c in {"Family investment firm", "Operating / strategic equity", "Named investor / firm principal", "family_office_equity", "private_credit_equity", "private_credit"}:
        return (3, "Private operating-company capital inquiry")
    if c in {"working_capital", "unsecured_business", "revenue_based", "business_finance", "contract_financing", "unsecured_real_estate_business", "term_loan", "contract_and_receivables"}:
        return (4, "Operating-capital eligibility inquiry")
    if c in audit.PROPERTY_CATEGORIES or r.get("campaign_input_kind") == "property_lender":
        return (5, "Property lender / private-money inquiry")
    if c in {"real_estate_fund_manager", "sbic_private_credit_equity", "private_credit_manager_research"}:
        return (6, "Fund-manager mandate inquiry")
    return (7, "Broader capital mandate inquiry")

def priority_key(r):
    n, _ = tier(r)
    state = val(r.get("state") or (r.get("metadata") or {}).get("state")).upper()
    geo = 0 if state in TRIAL_STATES else 1 if state in CONTINUATION_STATES else 2
    # Within a category, prefer publicly contactable and source-checked records.
    contact = -(3 * bool(email(r)) + 2 * bool(phone(r)) + bool(official_host(r)))
    verified = -int(bool(r.get("primary_activity_verified") or r.get("primary_contact_verified")))
    return (n, geo, verified, contact, -r.get("audit_relevance_score", 0), audit.company_key(r.get("company")))

def read_rows(path):
    return [json.loads(s) for s in path.read_text().splitlines() if s.strip()] if path.exists() else []

def normalize(r, group):
    m = r.get("metadata") or {}
    tr = m.get("trial_capital_review") or {}
    source_urls = urls(r)
    category = classify(r)
    _, priority = tier(r)
    low, high, scope = audit.published_range(r)
    if r.get("published_min") is not None or r.get("published_max") is not None:
        low, high = r.get("published_min"), r.get("published_max")
    scope = val(r.get("range_scope")) or scope
    if not scope:
        scope = "Property-loan range, not a corporate-capital commitment" if tier(r)[0] == 5 else "No direct corporate-capital range established in checked source"
    evidence = val(r.get("evidence")) or val(r.get("notes"))
    evidence = evidence[:900]
    if is_new_operator(r):
        role = "Public property-business route; investor decision maker unconfirmed"
        reason = "Property acquisition or investor activity makes this an operator-capital prospect for the signed trial. Confirm operating-company debt/equity appetite."
        action = "Ask the owner/investor whether they can allocate $100K-$500K to trial marketing and acquisitions, and confirm structure, timing and decision authority."
    elif tier(r)[0] == 5:
        role = audit.contact_role(r)
        reason = "Private real-estate finance experience. Corporate working capital, minority equity or profit participation requires a separate agreement from a property loan."
        action = "Confirm direct principal versus broker, $100K-$500K appetite, and whether capital can fund the operating company without a property mortgage."
    else:
        role = audit.contact_role(r)
        reason = val(tr.get("fit_reason") or r.get("fit_reason") or r.get("notes"))[:700]
        action = val(tr.get("next_action") or r.get("next_action") or m.get("next_action")) or "Confirm $100K-$500K ticket, company-stage and sector eligibility, investment authority, available allocation and proposed terms."
    own_web = val(r.get("website")) if official_host(r) else ""
    contact_url = val(tr.get("contact_url") or r.get("contact_url") or m.get('official_contact_url')) or own_web
    provenance = val(r.get("source_provenance")) or val(m.get("directory_provenance"))
    if not provenance:
        provenance = "Published directory contact; company activity checked where explicitly recorded" if is_new_operator(r) else "Saved public company, industry-directory or regulatory source; source date retained"
    original_name = val(r.get("name") or r.get("named_contact") or r.get("contact_name"))
    related_names = sorted({val(x.get("name") or x.get("named_contact") or x.get("contact_name")) for x in group} - {"", original_name})
    aliases = sorted({val(x.get("company")) for x in group} - {"", val(r.get("company"))})
    # Do not attribute another state's same-name business contacts/sources to
    # this company when different published domains indicate a homonym.
    def unrelated_homonym(x):
        return (audit.company_key(x.get('company')) == audit.company_key(r.get('company'))
            and official_host(x) and official_host(r) and official_host(x) != official_host(r)
            and val(x.get('state')) and val(r.get('state')) and val(x.get('state')) != val(r.get('state')))
    group = [x for x in group if not unrelated_homonym(x)]
    related_names = sorted({val(x.get("name") or x.get("named_contact") or x.get("contact_name")) for x in group} - {"", original_name})
    for x in group:
        source_urls.extend(u for u in urls(x) if u not in source_urls)
    row = dict(
        prospect_id="CF2500-" + hashlib.sha256((audit.company_key(r.get("company")) + "|" + official_host(r)).encode()).hexdigest()[:12].upper(),
        company=val(r.get("company")), name=original_name, email=email(r), phone=phone(r), website=own_web,
        city=val(r.get("city")), state=val(r.get("state") or m.get("state")), category=category,
        original_category=val(r.get("category") or r.get("lender_type") or r.get("route_type")),
        priority=priority, contact_role=role,
        requested_min=100000, requested_max=500000, published_min=low, published_max=high, range_scope=scope,
        check_status="Published source range; proposed allocation and structure require confirmation" if low is not None or high is not None else "$100K-$500K ticket not published / unconfirmed",
        contact_url=contact_url, fit_reason=reason, next_action=action,
        requirements=val(tr.get('blockers') or r.get('blockers') or m.get('requirements'))[:900],
        source_url=source_urls[0], source_urls=source_urls[:20], source_date=val(r.get("source_date") or r.get("retrieved_at") or r.get("checked_at"))[:10],
        checked_at=DATE, source_provenance=provenance,
        email_source_url=val(r.get("email_source") or r.get("email_source_url") or m.get("email_source_url") or (r.get("field_sources") or {}).get("email")) or (source_urls[0] if email(r) else ""),
        phone_source_url=val(r.get("phone_source_url") or r.get("contact_source") or m.get("phone_source_url") or (r.get("field_sources") or {}).get("phone")) or (source_urls[0] if phone(r) else ""),
        evidence=evidence, primary_activity_verified=bool(r.get("primary_activity_verified")),
        primary_contact_verified=bool((r.get("primary_contact_verified") or r.get("phone_first_party_match")) and (email(r) or phone(r))),
        discovery_origin="New public-source collection" if r.get("campaign_input_kind") else "Existing CapitalForge research, newly screened for this campaign",
        origin_file=val(r.get("campaign_input_file") or r.get("audit_input_file")),
        related_published_contacts=related_names, company_aliases=aliases,
        cash_capacity=None, capital_verification="unverified", approval_status="Not contacted / unconfirmed",
    )
    return row

def main():
    all_existing = audit.load_records()
    existing, audit_report = audit.select(all_existing, 10000)
    # The source audit is for phone/email routes. Reviewed official forms are
    # also usable channels in this broader campaign and remain source-labeled.
    existing.extend(r for r in all_existing if r['audit_input_file'] == 'trial_capital_directory.jsonl' and not (email(r) or phone(r)))
    new = read_rows(ROOT / "data/source_cohorts/investor2500_new_contacts.jsonl")
    candidates = existing + new
    accepted, exclusions = [], []
    for r in candidates:
        r.setdefault("audit_input_file", "new_public_sources")
        r.setdefault("audit_record_id", val(r.get("source_url")))
        if not urls(r) or not val(r.get("company")):
            exclusions.append({"company": r.get("company"), "reason": "Missing source/name"}); continue
        if val(r.get('company')).startswith('KC Investor Specialist'):
            exclusions.append({'company':r.get('company'),'reason':'Primary professional profile identifies an agent serving investors; direct investor/operator role not established'}); continue
        if is_new_operator(r) and (NON_INVESTOR_NAME.search(val(r.get("company"))) or not (r.get("primary_activity_verified") or OPERATOR_NAME.search(val(r.get("company"))))):
            exclusions.append({"company": r.get("company"), "reason": "Unrelated or unresolved operator role"}); continue
        if not email(r) and not phone(r) and not official_host(r) and not ((r.get("metadata") or {}).get("trial_capital_review") or {}).get("contact_url"):
            exclusions.append({"company": r.get("company"), "reason": "No published direct business contact route"}); continue
        if tier(r)[0] == 7 and (r.get("category") in audit.LOW_FIT_CATEGORIES):
            exclusions.append({"company": r.get("company"), "reason": "Equipment/receivables-only source is a weaker use-of-proceeds match"}); continue
        accepted.append(r)
    # Connected components prevent an alias or repeated office/contact from
    # returning as an independent prospect through another source.
    parent = list(range(len(accepted)))
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]; i = parent[i]
        return i
    def union(i, j):
        a, b = find(i), find(j)
        if a != b: parent[b] = a
    keys = {}
    for i, r in enumerate(accepted):
        identities = [("company", audit.company_key(r.get("company")))]
        if official_host(r): identities.append(("domain", official_host(r)))
        if email(r): identities.append(("email", email(r)))
        if phone(r): identities.append(("business_phone", phone(r)))
        for key in identities:
            if not key[1]: continue
            if key in keys: union(i, keys[key])
            else: keys[key] = i
    groups = {}
    for i, r in enumerate(accepted): groups.setdefault(find(i), []).append(r)
    grouped = [sorted(group, key=priority_key) for group in groups.values()]
    grouped.sort(key=lambda group: priority_key(group[0]))
    if len(grouped) < TARGET:
        raise RuntimeError(f"Only {len(grouped)} usable distinct prospects, need {TARGET}")
    rows = [normalize(g[0], g) for g in grouped[:TARGET]]
    assert len({audit.company_key(r['company']) for r in rows}) == TARGET
    assert len({r['prospect_id'] for r in rows}) == TARGET
    research_path = ROOT / "data/investor2500_research.jsonl"
    research_path.write_text("".join(json.dumps(r,ensure_ascii=False,separators=(',', ':')) + "\n" for r in rows))
    seed = []
    for rank, r in enumerate(rows, 1):
        review = {k:r[k] for k in ('category','priority','contact_role','check_status','fit_reason','next_action','source_url','checked_at','contact_url','source_provenance')}
        review.update(rank=rank, prospect_id=r['prospect_id'], contact_route="; ".join(x for x in (r['name'],r['email'],r['phone']) if x) or 'Published business website/form',published_range_scope=r['range_scope'])
        seed.append(dict(company=r['company'],name=r['name'],email=r['email'],phone=r['phone'],website=r['website'],city=r['city'],state=r['state'],lender_type=r['category'],financing_types='Confirm corporate debt, equity or profit participation',collateral_requirement='Confirm for operating-company capital',min_check=r['published_min'],max_check=r['published_max'],cash_capacity=None,capital_verification='unverified',verification_status='source_observed',fit='potential',fit_reason=r['fit_reason'],stage='new',source_url=r['source_url'],source_title=r['source_provenance'],source_date=r['source_date'],evidence=r['evidence'],tags=[COHORT,r['priority'],r['category']],sources=[{'url':u,'date':r['source_date']} for u in r['source_urls']],metadata={'investor_campaign_review':review,'campaign_prospect_id':r['prospect_id'],'email_source_url':r['email_source_url'],'phone_source_url':r['phone_source_url']}))
    (ROOT / "data/investor2500_directory.jsonl").write_text("".join(json.dumps(r,ensure_ascii=False,separators=(',', ':')) + "\n" for r in seed))
    fields = ['prospect_id','company','name','category','priority','email','phone','website','city','state','contact_role','contact_url','published_min','published_max','range_scope','check_status','fit_reason','requirements','next_action','source_date','checked_at','source_provenance','email_source_url','phone_source_url','source_urls','evidence','primary_activity_verified','primary_contact_verified','discovery_origin','related_published_contacts','company_aliases','capital_verification','approval_status']
    with (ROOT / "downloads/CapitalForge_2500_Potential_Investors.csv").open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n'); w.writeheader()
        for r in rows:
            out={k:' | '.join(r[k]) if isinstance(r[k],list) else r[k] for k in fields}
            w.writerow({k:"'"+v if isinstance(v,str) and v[:1] in ('=','+','-','@') else v for k,v in out.items()})
    summary = dict(cohort=COHORT,checked_at=DATE,prospects=TARGET,distinct_normalized_companies=TARGET,
        public_emails=sum(bool(r['email']) for r in rows),public_phones=sum(bool(r['phone']) for r in rows),
        email_phone_pairs=sum(bool(r['email'] and r['phone']) for r in rows),
        published_business_websites=sum(bool(r['website']) for r in rows),
        by_priority=dict(Counter(r['priority'] for r in rows)),by_category=dict(Counter(r['category'] for r in rows)),
        new_source_prospects=sum(r['discovery_origin'].startswith('New') for r in rows),
        primary_operator_activity_checks=sum(r['primary_activity_verified'] for r in rows),
        total_input_rows=len(candidates),eligible_distinct_prospect_pool=len(grouped),
        alias_or_duplicate_rows_collapsed=len(accepted)-len(grouped),
        documented_available_cash=0,confirmed_deal_approvals=0,
        selection_basis='Reviewed trial routes, property operators, flexible private capital, operating finance, property lenders, then fund managers. Within groups, trial/continuation geography and source-checked usable business contacts have priority. This is a prospecting order, not verified investor capacity.')
    (ROOT / "data/investor2500_summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n')
    (ROOT / "data/research_audits/investor2500_selection.json").write_text(json.dumps({'summary':summary,'campaign_exclusions':exclusions,'existing_source_exclusions':audit_report['exclusions'],'existing_duplicate_routes_collapsed':audit_report['duplicate_routes_collapsed']},indent=2,ensure_ascii=False)+'\n')
    print(json.dumps(summary,indent=2))

if __name__ == '__main__':
    main()
