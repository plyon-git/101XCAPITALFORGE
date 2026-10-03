#!/usr/bin/env python3
"""Validate the frozen contact/export cohort and real-data CRM import."""
import collections
import csv
import hashlib
import json
import sys
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app import App

def main():
    rows=[json.loads(x) for x in (ROOT/'data/investor2500_research.jsonl').read_text().splitlines() if x]
    summary=json.loads((ROOT/'data/investor2500_summary.json').read_text())
    assert len(rows)==summary['prospects']==2500
    assert len({r['prospect_id'] for r in rows})==2500
    for field in ('email','phone','website'):
        counts=collections.Counter(r[field].lower() for r in rows if r[field])
        assert not any(n>1 for n in counts.values()),field
    assert summary['public_emails']==sum(bool(r['email']) for r in rows)
    assert summary['public_phones']==sum(bool(r['phone']) for r in rows)
    assert summary['email_phone_pairs']==sum(bool(r['email'] and r['phone']) for r in rows)
    assert not any(r['primary_contact_verified'] and not(r['email'] or r['phone']) for r in rows)
    with (ROOT/'downloads/CapitalForge_2500_Potential_Investors.csv').open(encoding='utf-8-sig',newline='') as f:
        exported=list(csv.DictReader(f))
    assert len(exported)==2500
    assert [r['prospect_id'] for r in rows]==[r['prospect_id'] for r in exported]
    with tempfile.TemporaryDirectory() as td:
        app=App(td,['localhost','127.0.0.1'])
        reports={name:app.seed(ROOT/'data'/name) for name in ('data_lenders.jsonl','equity_directory.jsonl','trial_capital_directory.jsonl','investor2500_directory.jsonl')}
        with app.db() as db:
            ids=[r[0] for r in db.execute('SELECT id FROM leads WHERE tags LIKE ?',('%'+summary['cohort']+'%',))]
            db.execute("UPDATE leads SET stage='contacted',do_not_contact=1 WHERE id=?",(ids[0],))
        repeated=app.seed(ROOT/'data/investor2500_directory.jsonl')
        with app.db() as db:
            preserved=dict(db.execute('SELECT stage,do_not_contact FROM leads WHERE id=?',(ids[0],)).fetchone())
        assert len(ids)==2500,len(ids)
        assert all(r['invalid']==0 for r in reports.values()),reports
        assert repeated['inserted']==0 and repeated['merged']==2500 and repeated['invalid']==0,repeated
        assert preserved=={'stage':'contacted','do_not_contact':1},preserved
    result={'startup':reports,'campaign_search_count':len(ids),'repeat':repeated,'workflow_preserved':preserved,'research_sha256':hashlib.sha256((ROOT/'data/investor2500_research.jsonl').read_bytes()).hexdigest(),'seed_sha256':hashlib.sha256((ROOT/'data/investor2500_directory.jsonl').read_bytes()).hexdigest(),'csv_rows':len(exported),'duplicate_populated_email_phone_website_fields':0}
    (ROOT/'data/research_audits/investor2500_import_validation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':
    main()
