import pathlib,json,re,urllib.parse,collections
BASE=pathlib.Path(__file__).parent
def phonesplit(v):
    return re.split(r';\s*(?=(?:\+?\d|\())',v or '')
def phonefmt(v):
    d=re.sub(r'\D','',v.split(';')[0])
    if len(d)==11 and d.startswith('1'): d=d[1:]
    if len(d)!=10 or d[:3] in ('000','111','555'): return ''
    if d[3:6]=='555' and 100<=int(d[-4:])<=199: return ''
    return '+1-'+d[:3]+'-'+d[3:6]+'-'+d[6:]
OVERRIDES={
 'Lendr':('support@lendr.online','312-878-5118'),
 'Polaris Commercial Financing Group':('info@polariscfg.com','817-200-7811'),
 'SouthStar Capital':('info@southstar.com','800-763-3021'),
 'Hawthorne Corporate Credit':('info@gohawthorne.com','646-568-9140'),
 'Good Funding':('info@goodfunding.com','888-908-8101'),
 'Fundible':('Support@Fundible.com','855-784-0008'),
 'Rainstar Capital Group':('Greg@rainstarcapitalgroup.com','877-732-3989'),
 'Preferred Funding Group':('Info@preferredfundinggroup.com','800-249-2106'),
 'Fora Financial':('sales@forafinancial.com','888-221-6031'),
 'Rapid Finance':('sales@rapidfinance.com','800-664-0173'),
 'Anchor Funding':('info@anchorfundingllc.com','210-400-1841'),
 'National Funding':('apply@nationalfunding.com','888-733-2383'),
}
MANUAL={
 'Crestmont Capital':dict(email='info@crestmontcapital.com',phone='800-949-0401',source_url='https://www.crestmontcapital.com/terms-conditions/',source_name='Company-published terms, contact section 24',source_ref='turn38search8',state='CA'),
 'Andij Capital Consulting':dict(contact_name='Alex E. Tatem III',email='info@andijcapital.com',phone='757-705-7206',source_url='https://andijcapital.com/',source_name='Company-published contact footer',source_ref='turn31search4',state='VA'),
 'Alpha Commercial Capital':dict(email='info@alphacommercialcapital.com',phone='201-913-4358',source_url='https://alphacommercialcapital.com/contact-us/',source_name='Company-published contact page',source_ref='turn31search0',state='TX'),
 'Kapitus':dict(email='info@kapitus.com',phone='800-780-7133',source_url='https://kapitus.com/wp-content/uploads/2019/01/Small-Business-Financing-Checklist_KAPITUS.pdf',source_name='Company-published financing checklist',source_ref='turn26search29',contact_note='Published email in company PDF; dated 2019 source, revalidate before outreach.'),
 'Credibly':dict(email='customerservice@credibly.com',phone='888-664-1444',source_url='https://www.credibly.com/contact/',source_name='Official company contact page',source_ref='turn28search0',contact_note='Customer-service routing address; funding sales email not exposed unmasked.'),
 'QuickBridge':dict(email='info@quickbridge.com',phone='888-233-9085',source_url='https://www.quickbridge.com/terms-conditions/',source_name='Company Terms and Conditions, support contact',source_ref='turn26search1'),
 'SunBiz Funding':dict(email='info@sunbizfunding.com',phone='754-212-7833',source_url='https://www.sunbizfunding.com/contact-us',source_name='Official company contact page',source_ref='turn28search1'),
 'Spirit Funding':dict(email='info@spiritfundingllc.com',phone='877-378-0042',source_url='https://spiritfundingllc.com/',source_name='Official company homepage public contacts',source_ref='turn28search2'),
}

def normalize(r):
    pages=[]
    if r.get('source_file'):
        f=BASE.parent/r['source_file']
        if f.exists(): pages=json.loads(f.read_text())
    rawemail=r.get('email',''); rawphone=r.get('phone','')
    es=list(dict.fromkeys(v.strip().lower() for v in rawemail.split(';')+r.get('alternate_emails',[])+[e for p in pages for e in p.get('emails',[])] if v.strip()))
    ps=list(dict.fromkeys(phonefmt(v) for v in phonesplit(rawphone)+r.get('alternate_phones',[])+[e for p in pages for e in p.get('phones',[])] if phonefmt(v)))
    if r['company'] in OVERRIDES:
        e,p=OVERRIDES[r['company']]
        if e.lower() in es: es.remove(e.lower()); es.insert(0,e.lower())
        p=phonefmt(p)
        if p in ps: ps.remove(p); ps.insert(0,p)
    site=urllib.parse.urlsplit(r['website']).netloc.lower().removeprefix('www.')
    aliases={'SouthStar Capital':['southstar.com'],'TripleCapital Commercial Finance Group':['usa.com'],'Hawthorne Corporate Credit':['gohawthorne.com','hawthornebc.com'],'Forwardfy Capital':['forwardfy.com'],'CFG Merchant Solutions':['cfgms.com'],'Financely':['financely-group.com']}.get(r['company'],[])
    es=[e for e in es if e.split('@')[-1] in [site]+aliases]
    r['alternate_emails']=es[1:]; r['alternate_phones']=ps[1:]
    r['email']=es[0] if es else ''; r['phone']=ps[0] if ps else ''
    supported=[p for p in pages if r['email'].lower() in [e.lower() for e in p.get('emails',[])]]
    if supported: r['source_url']=supported[0].get('final_url',supported[0]['url'])
    else: r['source_url']=r.get('source_url','').split(';')[0].strip() or r['website']
    r['contact_sources']=[p.get('final_url',p['url']) for p in pages if (r['email'] and r['email'].lower() in [e.lower() for e in p.get('emails',[])]) or (r['phone'] and r['phone'] in [phonefmt(x) for x in p.get('phones',[])])]
    if r['company'] in MANUAL:
        r.update(MANUAL[r['company']]);r['phone']=phonefmt(r['phone']);r['contact_sources'].append(r['source_url'])
    r['contact_status']='public_email_and_phone' if r['email'] and r['phone'] else 'incomplete_contact'
    r['liquid_cash_500k_verified']=False
    r['borrower_approval_status']='not_contacted_not_approved'
    r['priority']='priority_review' if r['category'] in ('contract_financing','unsecured_real_estate_business','unsecured_business','family_office_equity','private_credit','private_credit_equity','commercial_finance_broker') else 'conditional_revenue_review'
    r['country']='US'
    return r

def main():
    files=[BASE/'fit_leads.jsonl',BASE/'fit_additional_leads.jsonl']
    rows=[]
    for f in files:
        if f.exists():rows += [json.loads(v) for v in f.read_text().splitlines() if v]
    rows=list({r['company']:normalize(r) for r in rows}.values())
    # Preserve incomplete candidates separately to avoid presenting missing contacts as complete.
    (BASE/'fit_leads.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
    (BASE/'fit_complete_leads.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows if r['contact_status']=='public_email_and_phone'))
    print('Rows',len(rows),'Complete',sum(r['contact_status']=='public_email_and_phone' for r in rows))
    print('Categories',dict(collections.Counter(r['category'] for r in rows)))
if __name__=='__main__':main()
