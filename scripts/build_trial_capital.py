#!/usr/bin/env python3
"""Build the current trial CRM cohort and portable export from reviewed public sources."""
import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COHORT = 'trial-100k-500k-2026-10-02'

def range_text(row):
    low, high = row.get('published_min'), row.get('published_max')
    if low is None and high is None:
        return 'Not published; confirm $100K-$500K inquiry' if 'LP equity' not in row.get('range_scope','') else row['range_scope']
    if low is None:
        return f'Up to ${high:,.0f}'
    if high is None:
        return f'From ${low:,.0f}; maximum not published'
    return f'${low:,.0f} to ${high:,.0f}'

def main():
    research = json.loads((ROOT/'data/trial_capital_research.json').read_text())
    rows = research['routes']
    crm, exported = [], []
    for row in rows:
        review = dict(row)
        review['published_range_text'] = range_text(row)
        review['contact_route'] = '; '.join(v for v in [row.get('named_contact'),row.get('email'),row.get('phone')] if v) or 'Official application/contact form'
        review['source_url'] = row['source_urls'][0]
        review['financing_type'] = row['route_type']
        crm.append(dict(company=row['company'], name='', email=row.get('email',''), phone=row.get('phone',''),
            website=row['website'], lender_type=row['route_type'], financing_types=row['route_type'],
            collateral_requirement=row.get('collateral_guarantee','Confirm collateral, guarantees and requested structure'),
            min_check=row.get('published_min'),max_check=row.get('published_max'),cash_capacity=None,
            capital_verification='unverified',verification_status='source_observed',fit='potential',stage='new',
            fit_reason=row['fit_reason']+' '+row['blockers'],source_url=row['source_urls'][0],
            source_title=row['company']+' official program or investment mandate',source_date='2026-10-02',
            evidence=row['evidence'],tags=[COHORT,row['source_group']],
            sources=[dict(url=url,date='2026-10-02',title='Current official funding review') for url in row['source_urls']],
            metadata=dict(record_kind='organization',trial_capital_review=review)))
        exported.append({key:row.get(key,'') for key in ['company','source_group','route_type','priority','published_min','published_max','range_scope','named_contact','email','phone','website','contact_url','application_url','fit_reason','eligibility','blockers','collateral_guarantee','pricing','next_action','affiliation_group','checked_at']} |
            dict(published_range=range_text(row),source_urls=' | '.join(row['source_urls']),capital_verification='Unverified; no offered/available amount confirmed'))
    (ROOT/'data/trial_capital_directory.jsonl').write_text(''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in crm))
    with (ROOT/'downloads/CapitalForge_Trial_Capital_100K_500K.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(exported[0]))
        w.writeheader()
        w.writerows({key: ("\'"+value if isinstance(value,str) and value[:1] in ("=","+","-","@") else value) for key,value in row.items()} for row in exported)
    provider_groups={row['affiliation_group'] for row in rows if row['source_group']!='program_channel'}
    summary=dict(checked_at='2026-10-02',cohort=COHORT,reviewed_routes=len(rows),
        brand_or_program_routes=dict(Counter(row['source_group'] for row in rows)),
        provider_or_affiliation_groups=len(provider_groups),
        routes_with_public_email=sum(bool(row.get('email')) for row in rows),
        routes_with_public_phone=sum(bool(row.get('phone')) for row in rows),
        routes_with_both_public_contacts=sum(bool(row.get('email') and row.get('phone')) for row in rows),
        published_product_ranges_or_minimums_overlapping_request=sum(
            (row.get('published_min') is not None or row.get('published_max') is not None)
            and (row.get('published_min') or 0)<=500000
            and (row.get('published_max') is None or row['published_max']>=100000) for row in rows),
        confirmed_deal_approvals=0,documented_available_cash=0,
        notes='Routes include conditional sector/eligibility prospects and multiple products at one provider. Counts do not represent independent funding commitments.')
    (ROOT/'data/trial_capital_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    doc=ROOT/'docs/TRIAL_FUNDING_RESEARCH.md'
    text=doc.read_text().split('\n<!-- generated-route-table -->')[0]
    text+='\n<!-- generated-route-table -->\n\n## Reviewed routes\n\n'
    text+=f"{summary['reviewed_routes']} reviewed routes across {summary['provider_or_affiliation_groups']} provider or affiliation groups, plus the SBA program channel. No deal approvals or available cash have been confirmed.\n\n"
    text+='| Source | Published range | Priority | Public route |\n| --- | --- | --- | --- |\n'
    for row in rows:
        esc=lambda s:str(s).replace('|',' / ').replace('\n',' ')
        text+=f"| {esc(row['company'])} | {esc(range_text(row))} | {esc(row['priority'])} | [Contact]({row['contact_url']}) |\n"
    doc.write_text(text)
    print(json.dumps(summary,indent=2))

if __name__=='__main__':
    main()
