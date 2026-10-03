#!/usr/bin/env python3
"""Audit existing CapitalForge records without changing any repository data.

Scores rank research relevance and usable published routing contacts. They do not
represent approval, investment appetite, liquid capital, or verified legitimacy.
Only existing saved data are read; this script does not perform web requests.
"""
from __future__ import annotations
import argparse
import collections
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlparse

BASE = Path(__file__).resolve().parents[1]
DATA = BASE / "data"
FILES = ("public_directory.jsonl", "equity_directory.jsonl", "trial_capital_directory.jsonl")
MANAGER_CATEGORIES = {"real_estate_fund_manager", "equity_manager_research", "private_credit_manager_research"}
PROPERTY_CATEGORIES = {"private_real_estate_lender", "property_secured_lender", "private_real_estate_or_finance_directory_member"}
LOW_FIT_CATEGORIES = {"equipment_finance_funding_source", "factoring_receivables"}
OPERATOR_RE = re.compile(r"cash home buyer|we (?:buy|flip|invest in|purchase) (?:houses|homes|properties|real estate)|(?:i am|we are) (?:a |an )?(?:real estate investor|house flipper)|real estate investment company", re.I)
AUTOMATION_RE = re.compile(r"robot\.zapier\.com|noreply|no-reply|example\.(?:com|org|net)|@sentry\.|\.(?:png|jpg|webp)$", re.I)
EMAIL_RE = re.compile(r"^[^\s@<>]+@[^\s@<>]+\.[A-Za-z]{2,}$")

def value(v):
    return "" if v is None else str(v).strip()

def company_key(s):
    s = value(s).casefold().replace("&", " and ")
    s = re.sub(r"\b(?:llc|l\.l\.c|inc|incorporated|ltd|limited|lp|l\.p|llp|corp|corporation)\b", " ", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()

def phone_key(s):
    s = re.sub(r"\D", "", value(s))
    if len(s) == 10:
        return "1" + s
    return s if len(s) >= 10 else ""

def domain(s):
    try:
        return urlparse(value(s)).hostname.lower().removeprefix("www.")
    except (AttributeError, ValueError):
        return ""

def metadata(r):
    return r.get("metadata") or {}

def row_text(r):
    m = metadata(r)
    return " ".join(value(r.get(k)) for k in ("notes", "description", "fit_reason", "evidence")) + " " + " ".join(value(m.get(k)) for k in ("mandate", "requirements"))

def all_source_urls(r):
    m = metadata(r)
    out = [r.get("source_url"), m.get("mandate_source_url"), m.get("profile_source_url")]
    out.extend(r.get("source_urls") or [])
    out.extend(s.get("url") if isinstance(s, dict) else s for s in r.get("sources") or [])
    return list(dict.fromkeys(value(s) for s in out if value(s).startswith(("http://", "https://"))))

def usable_email(r):
    e = value(r.get("email")).lower()
    return e if EMAIL_RE.fullmatch(e) and not AUTOMATION_RE.search(e) else ""

def load_records():
    records = []
    for filename in FILES:
        path = DATA / filename
        if not path.exists():
            continue
        for n, line in enumerate(path.read_text().splitlines(), 1):
            if not line.strip():
                continue
            r = json.loads(line)
            r["audit_input_file"] = filename
            r["audit_input_line"] = n
            r["audit_record_id"] = value(r.get("directory_id")) or value(metadata(r).get("contact_id")) or hashlib.sha256(f"{filename}:{n}".encode()).hexdigest()[:14]
            records.append(r)
    return records

def source_holds():
    path = DATA / "research_audits" / "data-quality-holds.json"
    excluded = {}
    if path.exists():
        for r in json.loads(path.read_text()).get("holds", []):
            if value(r.get("recommended_action")).startswith("exclude_"):
                excluded[company_key(r.get("company"))] = r.get("hold_reason")
    # A cached description retained in public_directory identifies landlord
    # insurance, not an investor or financier. No funding mandate is shown.
    excluded[company_key("Steadily")] = "Saved primary-site description identifies landlord insurance; no investor or financing mandate established."
    excluded[company_key("CAPITAL COMMERCIAL RE GROUP")] = "Existing final audit identifies property brokerage services without a financing mandate."
    return excluded

def contact_role(r):
    role = value(r.get("email_contact_type"))
    label = value(r.get("email_recipient_role")) or value(r.get("contact_role")) or value(metadata(r).get("title"))
    if role == "regulatory_routing" or re.search(r"compliance|regulatory", label, re.I):
        return "regulatory_or_compliance_routing_not_investment_decision_maker"
    if role == "business_inbox" or not value(r.get("name") or r.get("contact_name")):
        return "firm_business_routing"
    return "published_professional_contact_directness_unconfirmed"

def classify(r):
    c = value(r.get("category") or r.get("lender_type"))
    t = row_text(r)
    if c == "private_money_individual":
        return "Private-money individual; investment structure unconfirmed"
    if OPERATOR_RE.search(t) and c not in MANAGER_CATEGORIES:
        return "Property operator or real-estate investment company; finance willingness unconfirmed"
    if r["audit_input_file"] == "equity_directory.jsonl":
        return c or "Equity research prospect"
    if r["audit_input_file"] == "trial_capital_directory.jsonl":
        return value(metadata(r).get("trial_capital_review", {}).get("category")) or c
    if c == "real_estate_fund_manager":
        return "Real-estate fund manager; $100K-$500K mandate unconfirmed"
    if c == "equity_manager_research":
        return "Private-equity fund manager; $100K-$500K mandate unconfirmed"
    if c == "private_credit_manager_research":
        return "Private-credit fund manager; $100K-$500K mandate unconfirmed"
    if c in PROPERTY_CATEGORIES:
        return "Property lender or directory member; operating-company capital unconfirmed"
    if c == "sbic_private_credit_equity":
        return "SBIC debt/equity manager; ticket and eligibility unconfirmed"
    if c in LOW_FIT_CATEGORIES:
        return "Equipment or receivables lender; likely use-of-proceeds mismatch"
    return "Operating-capital lender, broker or finance route; eligibility unconfirmed"

def published_range(r):
    m = metadata(r)
    tr = m.get("trial_capital_review") or {}
    lo = r.get("min_check", r.get("loan_min", r.get("capital_min_usd")))
    hi = r.get("max_check", r.get("loan_max", r.get("capital_max_usd")))
    if hi is None:
        hi = r.get("published_loan_max_usd")
    if tr:
        lo, hi = tr.get("published_min"), tr.get("published_max")
    scope = value(tr.get("range_scope")) or value(m.get("check_scope"))
    return lo, hi, scope

def score(r, phone_company_groups=None):
    """Deterministic, explicitly heuristic prospect relevance score."""
    kind = classify(r)
    category = value(r.get("category") or r.get("lender_type"))
    s = 0
    if r["audit_input_file"] == "trial_capital_directory.jsonl":
        s = 95 if "equity" in value(r.get("financing_types")).lower() else 65
    elif r["audit_input_file"] == "equity_directory.jsonl":
        s = {"Family investment firm": 91, "Operating / strategic equity": 90, "Named investor / firm principal": 86, "Angel group / syndication route": 81, "Corporate equity firm": 78, "Venture / proptech firm": 69}.get(category, 65)
    elif category == "private_money_individual":
        s = 88
    elif kind.startswith("Property operator"):
        s = 84
    elif category == "real_estate_fund_manager":
        s = 64
    elif category == "sbic_private_credit_equity":
        s = 60
    elif category in PROPERTY_CATEGORIES:
        s = 55
    elif category == "equity_manager_research":
        s = 45
    elif category == "private_credit_manager_research":
        s = 44
    elif category in LOW_FIT_CATEGORIES:
        s = 10
    else:
        s = 52
    e, p = usable_email(r), phone_key(r.get("phone"))
    s += 12 if e else 0
    s += 5 if p else 0
    s += 4 if e and p else 0
    if contact_role(r).startswith("regulatory"):
        s -= 10
    if r.get("fit_status") in {"potential_contract_review", "potential_equity_review", "individual_mandate_unconfirmed"}:
        s += 5
    lo, hi, _ = published_range(r)
    if isinstance(hi, (int, float)) and hi >= 100000 and (lo is None or isinstance(lo, (int, float)) and lo <= 500000):
        s += 4
    elif isinstance(lo, (int, float)) and lo > 500000:
        s -= 12
    # The number is reported gross assets, never cash. This is merely a
    # small-check mandate-priority heuristic, not a liquidity assessment.
    gav = r.get("reported_private_fund_gross_assets_usd")
    if category in MANAGER_CATEGORIES and isinstance(gav, (int, float)) and gav > 1_000_000_000:
        s -= 5
    if phone_company_groups and len(phone_company_groups.get(p, ())) >= 4:
        s -= 12
    if re.search(r"bank|equipment|factoring|insurance", category, re.I):
        s -= 6
    return s

def duplicate_groups(rows, key_fn):
    d = collections.defaultdict(list)
    for r in rows:
        k = key_fn(r)
        if k:
            d[k].append(r)
    return {k: v for k, v in d.items() if len(v) > 1}

def select(rows, limit=2500):
    """Return sourced contact routes; collapse shared email and phone-only route.

    A phone-only row and an email row for the same company are one route unless
    a named investment professional has a different published direct email.
    Distinct advisers sharing a phone are flagged and held from this proposal.
    """
    holds = source_holds()
    phone_groups = collections.defaultdict(set)
    for r in rows:
        if phone_key(r.get("phone")):
            phone_groups[phone_key(r.get("phone"))].add(company_key(r.get("company")))
    eligible, excluded = [], []
    for r in rows:
        reason = holds.get(company_key(r.get("company")))
        if r.get("do_not_contact"):
            reason = "Existing do_not_contact flag"
        if not all_source_urls(r):
            reason = "Missing public source URL"
        if not usable_email(r) and not phone_key(r.get("phone")):
            reason = "No usable published email or phone"
        if r.get("category") in MANAGER_CATEGORIES and len(phone_groups.get(phone_key(r.get("phone")), ())) >= 8:
            reason = "Unexplained phone shared by >=8 differently named manager records; manual affiliation/source review required"
        if reason:
            excluded.append({"record_id": r["audit_record_id"], "company": r.get("company"), "reason": reason})
        else:
            eligible.append(r)
    ordered = sorted(eligible, key=lambda r: (-score(r, phone_groups), company_key(r.get("company")), usable_email(r), r["audit_record_id"]))
    seen_emails, seen_phone_only, seen_orgs = set(), set(), set()
    deduped, merged = [], []
    for r in ordered:
        e, p, org = usable_email(r), phone_key(r.get("phone")), company_key(r.get("company"))
        duplicate = e in seen_emails if e else p in seen_phone_only or org in seen_orgs
        if duplicate:
            merged.append({"record_id": r["audit_record_id"], "company": r.get("company"), "reason": "Duplicate shared-email or phone-only company/contact route"})
            continue
        if e:
            seen_emails.add(e)
        elif p:
            seen_phone_only.add(p)
        seen_orgs.add(org)
        r["audit_classification"] = classify(r)
        r["audit_contact_role"] = contact_role(r)
        r["audit_relevance_score"] = score(r, phone_groups)
        r["audit_phone_affiliation_review"] = len(phone_groups.get(p, ())) >= 4
        deduped.append(r)
    return deduped[:limit], {"eligible_before_dedupe": len(eligible), "deduplicated_eligible_routes": len(deduped), "exclusions": excluded, "duplicate_routes_collapsed": merged}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(DATA / "research_audits" / "investor2500_existing_audit.json"))
    parser.add_argument("--limit", type=int, default=2500)
    parser.add_argument("--selected-records-output", default="")
    args = parser.parse_args()
    rows = load_records()
    selected, detail = select(rows, args.limit)
    category_stats = collections.defaultdict(lambda: collections.Counter())
    for r in rows:
        c = value(r.get("category") or r.get("lender_type"))
        category_stats[c]["rows"] += 1
        category_stats[c]["usable_email"] += bool(usable_email(r))
        category_stats[c]["usable_phone"] += bool(phone_key(r.get("phone")))
        category_stats[c]["email_phone_pair"] += bool(usable_email(r) and phone_key(r.get("phone")))
    emails = duplicate_groups(rows, usable_email)
    phones = duplicate_groups(rows, lambda r: phone_key(r.get("phone")))
    organizations = duplicate_groups(rows, lambda r: company_key(r.get("company")))
    phone_clusters = []
    for p, rs in phones.items():
        orgs = sorted({value(r.get("company")) for r in rs})
        if len({company_key(o) for o in orgs}) >= 4:
            phone_clusters.append({"phone": p, "rows": len(rs), "organizations": orgs, "status": "Affiliation or source review required; shared number alone does not establish fraud or false data"})
    operator_rows = [{"record_id": r["audit_record_id"], "company": r.get("company"), "source_url": r.get("source_url"), "has_usable_contact": bool(usable_email(r) or phone_key(r.get("phone"))), "evidence_excerpt": OPERATOR_RE.search(row_text(r)).group(0)} for r in rows if r.get("category") not in MANAGER_CATEGORIES and OPERATOR_RE.search(row_text(r))]
    report = {
        "scope": "Read-only audit of saved sources. Source publication only; no new web verification, deliverability tests, calls, liquidity verification, investor acceptance or deal approval.",
        "input_counts": dict(collections.Counter(r["audit_input_file"] for r in rows)),
        "total_input_rows": len(rows),
        "category_contact_counts": dict(category_stats),
        "explicit_private_money_individual_rows": sum(r.get("category") == "private_money_individual" for r in rows),
        "property_operator_language_matches": operator_rows,
        "interpretation": "Existing data contain some real property operators and individual private-money contacts, but most property rows describe lenders serving flippers, not flippers themselves. Fund managers are genuine source-listed research categories; regulatory contacts do not establish investment decision-maker identity or small-ticket mandate. The 235 equity rows include repeated firm inboxes and 180 source-reported vehicles, not 235 independent investors.",
        "duplicate_patterns": {"usable_email_groups": len(emails), "extra_rows_sharing_email": sum(len(rs)-1 for rs in emails.values()), "phone_groups": len(phones), "extra_rows_sharing_phone": sum(len(rs)-1 for rs in phones.values()), "normalized_company_groups": len(organizations), "extra_rows_sharing_normalized_company": sum(len(rs)-1 for rs in organizations.values()), "largest_email_groups": [{"email": e, "rows": len(rs), "companies": sorted({value(r.get("company")) for r in rs})} for e, rs in sorted(emails.items(), key=lambda t: -len(t[1]))[:15]]},
        "phone_affiliation_review_clusters": sorted(phone_clusters, key=lambda r:-r["rows"]),
        "bad_or_automation_primary_emails": [{"company": r.get("company"), "email": r.get("email"), "source_url": r.get("source_url")} for r in rows if value(r.get("email")) and not usable_email(r)],
        "contact_role_counts": dict(collections.Counter(contact_role(r) for r in rows)),
        "rules": [
            "Use only public/source-published contacts. Never infer email from a person or naming pattern.",
            "Require an existing public source and at least one usable email or telephone for the contact list.",
            "Exclude existing service/wrong-site holds and landlord-insurance vendor Steadily.",
            "Keep property lenders as lenders/referral qualification contacts. Do not relabel them as minority-equity investors or house flippers.",
            "Treat first-person home-buying/property-investment language as an operator prospect, retaining original lender classification as source context.",
            "Name compliance and brochure contacts as routing contacts unless a current source establishes an investment role.",
            "Collapse shared firm inbox rows; multiple named partners sharing one inbox are names at one contact route.",
            "Flag numbers shared across four or more organizations; hold unexplained >=8-organization manager clusters pending affiliation/source review.",
            "Rank direct family/flexible equity and property operators first; real-estate funds and operating-finance routes next; property lenders and general manager research after.",
            "Published limits and reported gross fund assets are not liquid available cash or approval. Unpublished tickets remain unpublished.",
            "Produce 2,500 potential capital contacts only if enough sourced routes remain, labeling category and uncertain fit rather than claiming verified investor appetite."
        ],
        "selection_summary": {"requested": args.limit, "selected_contact_routes": len(selected), "distinct_normalized_organizations": len({company_key(r.get("company")) for r in selected}), "usable_emails": sum(bool(usable_email(r)) for r in selected), "usable_phones": sum(bool(phone_key(r.get("phone"))) for r in selected), "email_phone_pairs": sum(bool(usable_email(r) and phone_key(r.get("phone"))) for r in selected), "by_classification": dict(collections.Counter(r["audit_classification"] for r in selected)), "by_input_file": dict(collections.Counter(r["audit_input_file"] for r in selected)), "score_min": min((r["audit_relevance_score"] for r in selected), default=None)},
        "selection_detail": detail,
        "proposed_selected_records": [{"record_id": r["audit_record_id"], "input_file": r["audit_input_file"], "input_line": r["audit_input_line"], "company": r.get("company"), "classification": r["audit_classification"], "contact_role": r["audit_contact_role"], "relevance_score": r["audit_relevance_score"]} for r in selected],
    }
    Path(args.output).write_text(json.dumps(report, indent=2, ensure_ascii=False))
    if args.selected_records_output:
        Path(args.selected_records_output).write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in selected)+"\n")
    print(json.dumps({"output": args.output, **report["selection_summary"], "eligible_before_dedupe": detail["eligible_before_dedupe"], "deduplicated_eligible_routes": detail["deduplicated_eligible_routes"], "excluded_records": len(detail["exclusions"]), "collapsed_duplicate_routes": len(detail["duplicate_routes_collapsed"]), "phone_affiliation_review_clusters": len(phone_clusters)}, indent=2))

if __name__ == "__main__":
    main()
