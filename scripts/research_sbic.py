#!/usr/bin/env python3
"""Retrieve the public SBA SBIC business-contact directory (standard library only)."""
import argparse
import concurrent.futures
import datetime
import html
import json
import re
import time
import urllib.request
from pathlib import Path

BASE = 'https://legacy.sba.gov/funding-programs/investment-capital/sbic-directory'

def clean(s):
    return ' '.join(html.unescape(re.sub(r'<[^>]+>', ' ', s)).split())

def parse(body, url):
    table = re.search(r'<table\b.*?</table>', body, re.S)
    if not table:
        return []
    out = []
    for row in re.findall(r'<tr\b[^>]*>(.*?)</tr>', table[0], re.S):
        cells = re.findall(r'<td\b[^>]*>(.*?)</td>', row, re.S)
        if len(cells) != 8:
            continue
        first = re.findall(r'<div>(.*?)</div>', cells[0], re.S)
        if len(first) < 2:
            continue
        fund = clean(first[0])
        location = fund.rsplit(' ', 2)
        manager = clean(first[1]).removeprefix('Managed by:').strip()
        email = re.search(r'href="mailto:([^"]+)"', cells[7])
        phone = re.search(r'href="tel:([^"]+)"', cells[7])
        contact = re.search(r'<a\b[^>]*href="mailto:[^"]*"[^>]*>(.*?)</a>', cells[7], re.S)
        money = lambda s: int(re.sub(r'[^0-9]', '', clean(s))) if re.sub(r'[^0-9]', '', clean(s)) else None
        out.append({
            'company': manager, 'contact_name': clean(contact[1]) if contact else '',
            'email': html.unescape(email[1]) if email else '',
            'phone': phone[1] if phone else '', 'website': '',
            'state': location[-1] if location[-1].isupper() and len(location[-1]) == 2 else '',
            'category': 'sbic_private_credit_equity',
            'fit_status': 'research_required', 'capital_status': 'reported_fund_assets_not_cash',
            'source_name': 'U.S. Small Business Administration SBIC directory',
            'source_url': url, 'retrieved_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'contact_role': 'SBA-published fund contact',
            'reported_fund_size': money(cells[2]), 'average_investment': money(cells[3]),
            'investment_strategy': clean(cells[4]), 'fund_style': clean(cells[5]),
            'making_new_investments': clean(cells[6]),
            'notes': f"SBA-listed SBIC manager. {clean(cells[4])}; {clean(cells[5])}. "
                     f"Making new investments: {clean(cells[6])}. Reported fund size is not available cash. "
                     "$100K-$500K ticket, real-estate operating-company eligibility, collateral, and proposed economics require direct confirmation.",
            'funds': [{'name': fund, 'vintage': clean(cells[1]), 'size': money(cells[2]),
                       'average_investment': money(cells[3]), 'making_new_investments': clean(cells[6])}],
            'evidence': [{'url': url, 'fields': ['company','contact_name','email','phone','reported_fund_size','investment_strategy'],
                          'excerpt': clean(row)[:1500]}]
        })
    return out

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', default='data/sbic_leads.jsonl')
    p.add_argument('--cache', default='data/source_cache/sbic')
    p.add_argument('--pages', type=int, default=45)
    args = p.parse_args()
    cache = Path(args.cache); cache.mkdir(parents=True, exist_ok=True)
    def page(i):
        url = BASE if i == 0 else f'{BASE}?page={i}'
        path = cache / f'page_{i}.html'
        if path.exists():
            body = path.read_text()
        else:
            time.sleep(.25)
            req = urllib.request.Request(url, headers={'User-Agent': 'CapitalForge/1.0 public business directory research'})
            try:
                with urllib.request.urlopen(req, timeout=35) as r:
                    body = r.read().decode('utf-8')
                path.write_text(body)
            except Exception as exc:
                print(f'Page {i}: {type(exc).__name__}: {exc}', flush=True)
                return []
        return parse(body, url)
    firms = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        for records in pool.map(page, range(args.pages)):
            for item in records:
                key = re.sub(r'[^a-z0-9]', '', item['company'].lower())
                if key in firms:
                    old = firms[key]
                    if item['making_new_investments'] == 'Yes' and old['making_new_investments'] != 'Yes':
                        item['funds'] += old['funds']; item['evidence'] += old['evidence']; firms[key] = item
                    else:
                        old['funds'] += item['funds']; old['evidence'] += item['evidence']
                else:
                    firms[key] = item
    rows = [r for r in firms.values() if r['making_new_investments'] == 'Yes']
    output = Path(args.output); output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows))
    print(json.dumps({'distinct_managers':len(firms), 'currently_investing_managers':len(rows),
                      'both_phone_email':sum(bool(r['phone'] and r['email']) for r in rows), 'output':str(output)}))

if __name__ == '__main__':
    main()
