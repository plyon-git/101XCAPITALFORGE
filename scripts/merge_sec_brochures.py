#!/usr/bin/env python3
"""Attach actually published Part 2A contact evidence to the screened SEC cohort."""
import argparse
import json
from pathlib import Path

def rows(path):
    return [json.loads(s) for s in Path(path).read_text().split('\n') if s.strip()]

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('base')
    p.add_argument('brochures',nargs='+')
    p.add_argument('--out',required=True)
    args=p.parse_args()
    base=rows(args.base)
    lookup={str(r['sec_crd']):r for r in base}
    attached=0
    for filename in args.brochures:
        for b in rows(filename):
            r=lookup.get(str(b.get('sec_crd')))
            email=b.get('brochure_email','')
            source=b.get('brochure_source_url','')
            if not r or not email or not source:
                continue
            # A company-site contact is preferred; brochure names are routing
            # evidence and do not establish an investment decision maker.
            if r.get('email'):
                continue
            r['email']=email
            r['email_source_url']=source
            r['email_status']='publicly_published_not_delivery_tested'
            r['email_contact_type']='regulatory_routing'
            r['contact_role']=b.get('brochure_contact_role') or 'Published adviser brochure professional contact'
            for k,v in b.items():
                if k.startswith('brochure_') or k in ('profile_source_url','profile_api_source_url'):
                    r[k]=v
            r['source_type']='SEC Form ADV + public Part 2A brochure'
            r['notes']=(r.get('notes','')+' Part 2A address is professional/regulatory routing, not an assumed funding decision maker.').strip()
            attached+=1
    dest=Path(args.out)
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(''.join(json.dumps(r,ensure_ascii=True)+'\n' for r in base))
    print(json.dumps({'records':len(base),'net_new_published_emails':attached,'emails':sum(bool(r.get('email')) for r in base),'out':str(dest)}))

if __name__=='__main__':main()
