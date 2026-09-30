"""Public PLD profile / official-site contact extraction, assigned index modulo 3 == 1.

Never sends inquiries, logs in, bypasses blocked pages, guesses email patterns, or
labels publicly advertised lending capacity as liquid cash.
"""
import concurrent.futures, datetime, hashlib, html, json, os, re, sys, time, urllib.parse
sys.path.insert(0,'research/bulk')
from contact_utils import fetch, enrich, domain, emails, phones, FETCH_STATUS

NOW=datetime.datetime.now(datetime.timezone.utc).isoformat()
OUT='research/pld_supplement_v3_batch.jsonl'
EXCLUDE='research/pld_supplement_v3_exclusions.jsonl'
PROGRESS='research/pld_supplement_v3_progress.json'

def classify(name,description,business):
    if re.search(r'\b(?:bank|bancorp|credit union)\b',name,re.I):return 'traditional_bank_or_credit_union'
    if re.search(r'\b(?:direct lender|private lender|private money lender|non.bank lender|hard money lender|balance.sheet lender)\b',description,re.I):return 'private_nonbank_lender_directory_claim'
    if re.search(r'\b(?:broker|arrange financing|lending marketplace|connecting borrowers|network of lenders)\b',description,re.I):return 'financing_broker_or_intermediary'
    return 'nonbank_status_unconfirmed'

def profile(seed):
    if re.search(r'\b(?:bank|bancorp|credit union|insurance|accounting|CPA|title company|title agency|law firm|realty|realtors)\b',seed['company'],re.I):
        return None,{'company':seed['company'],'source_url':seed['profile_url'],'reason':'conventional_bank_or_service_provider_name'}
    u=seed['profile_url'];t,final=fetch(u);fs={}
    for raw in re.findall(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>',t,re.S|re.I):
        try:d=json.loads(raw)
        except (ValueError,TypeError):continue
        if not isinstance(d,dict):continue
        for obj in d.get('@graph',[d]):
            if isinstance(obj,dict) and obj.get('@type')=='LocalBusiness':fs=obj;break
        if fs:break
    if not fs:return None,{'company':seed['company'],'source_url':u,'reason':'public_profile_unavailable_or_no_business_fields','http_status':FETCH_STATUS.get(u,'unknown')}
    addr=fs.get('address') or {};name=fs.get('name') or seed['company'];description=fs.get('description') or ''
    if addr.get('addressCountry','US') not in ['US','USA','United States','United States of America']:
        return None,{'company':name,'source_url':u,'reason':'non_us'}
    if re.search(r'\b(?:real estate agent|real estate agency|real estate brokerage|sell.side|buy.side|accounting|insurance agency|law firm|tax preparation|credit repair)\b',description,re.I) and not re.search(r'\b(?:direct lender|private lender|business financing|business funding|working capital)\b',description,re.I):
        return None,{'company':name,'source_url':u,'reason':'service_provider_description'}
    website=''
    for tag in re.findall(r'<a\b([^>]+)>',t,re.S|re.I):
        attrs=dict((a.lower(),html.unescape(b or c)) for a,b,c in re.findall(r'([\w-]+)\s*=\s*(?:"([^"]*)"|\x27([^\x27]*)\x27)',tag))
        if 'weblink' in attrs.get('class','').split():website=attrs.get('href','');break
    if not website:
        for candidate in fs.get('sameAs',[]):
            if isinstance(candidate,str) and candidate.startswith(('https://','http://')) and not any(x in domain(candidate) for x in ['privatelendersdirectory.com','facebook.com','linkedin.com','twitter.com','instagram.com','youtube.com']):
                website=candidate;break
    ph=fs.get('telephone') or ''
    # Empty/unclaimed profiles use a literal N/A phone placeholder.
    valid_ph=phones('<script type="application/ld+json">'+json.dumps({'telephone':ph})+'</script>')
    ph=valid_ph[0] if valid_ph else ''
    if not ph and not website:
        return None,{'company':name,'source_url':u,'reason':'public_profile_has_no_phone_or_company_website'}
    business=seed['listing_category']==4;role=classify(name,description,business)
    if role=='traditional_bank_or_credit_union':return None,{'company':name,'source_url':u,'reason':'conventional_bank_or_credit_union'}
    ops=bool(re.search(r'\b(?:working capital|unsecured|factoring|receivables|purchase order|cash flow|contract financing)\b',description,re.I))
    row={'title':name,'company':name,'contact_name':'','phone':ph,'email':'','website':website,'source_url':u,'source_name':'PrivateLendersDirectory','retrieved_at':NOW,'state':addr.get('addressRegion',''),
         'category':'business_finance_provider' if business else 'private_real_estate_lender','fit_status':'operations_finance_candidate_unverified' if ops else 'financing_fit_unverified' if business else 'property_collateral_required_or_likely',
         'capital_status':'unverified','institutional_vs_broker':role,'nonbank_status':'directory_claim_not_independently_verified' if role=='private_nonbank_lender_directory_claim' else role,
         'notes':'Public directory listing; current phone ownership, email deliverability, private cash availability, $500K cash threshold, fulfillment financing eligibility and equity willingness have not been verified. '+description[:900],
         'profile_address':addr,'listing_source_url':seed['listing_source_url'],'field_sources':{'company':u,**({'phone':u} if ph else {}),**({'website':u} if website else {})},'email_status':'not_found'}
    return row,None

def prefetch_contact(row):
    """Use an already complete public home-page contact before fetching more pages."""
    if not row.get('website'):return row
    u=row['website']
    if not u.startswith(('https://','http://')):u='https://'+u
    if u.startswith('http://'):u='https://'+u[7:]
    d=domain(u)
    if not d or any(x in d for x in ['facebook.com','linkedin.com','twitter.com','privatelendersdirectory.com','hardmoneyhome.com','privatelenderlink.com']):return row
    t,final=fetch(u)
    if t and re.search(r'\b(?:lending|lender|mortgage|financing|funding|finance|capital|loan|factoring|receivables|private credit)\b',t,re.I) and not re.search(r'domain (?:is |name )?for sale|buy this domain|this domain is parked|sedoparking',t,re.I):
        vals=emails(t);own=[e for e in vals if domain('https://'+e.split('@')[-1])==domain(final)]
        if not own:own=[e for e in vals if e.endswith(('@gmail.com','@yahoo.com','@aol.com','@outlook.com'))]
        own.sort(key=lambda e:(not e.startswith(('info@','contact@','loans@','lending@','funding@','hello@','sales@','invest@','investors@')),len(e)))
        if own:
            row['email']=own[0];row['email_candidates']=own;row['email_status']='publicly_listed_not_deliverability_tested';row['field_sources']['email']=final;row['website_status']='public_site_retrieved';row['contact_pages_checked']=[final]
        if not row.get('phone'):
            ph=phones(t)
            if ph:row['phone']=ph[0];row['field_sources']['phone']=final
    if not (row.get('email') and row.get('phone')) and FETCH_STATUS.get(u) not in [401,403,429]:row=enrich(row)
    for k in ['email_source_snapshot','directory_profile_snapshot']:row.pop(k,None)
    return row

def task(seed):
    try:
        row,rejection=profile(seed)
        return (prefetch_contact(row),None) if row else (None,rejection)
    except Exception as e:return None,{'company':seed['company'],'source_url':seed['profile_url'],'reason':'extraction_error','error':str(e)[:200]}

if __name__=='__main__':
    seeds=[r for i,r in enumerate(json.load(open('research/bulk/pld_discovery.json'))) if i%3==1]
    completed=set();all_rows={};metrics={'assigned':len(seeds),'processed':0,'kept':0,'complete':0,'phone':0,'email':0,'excluded':0,'started_at':NOW}
    if os.path.exists(OUT):
        for ln in open(OUT):
            if not ln.strip():continue
            r=json.loads(ln);completed.add(r['source_url']);all_rows[r['source_url']]=r;metrics['kept']+=1;metrics['complete']+=bool(r.get('phone') and r.get('email'));metrics['phone']+=bool(r.get('phone'));metrics['email']+=bool(r.get('email'))
    if os.path.exists(EXCLUDE):
        for ln in open(EXCLUDE):
            if not ln.strip():continue
            r=json.loads(ln)
            if r.get('reason')!='public_profile_has_no_phone_or_company_website':completed.add(r['source_url']);metrics['excluded']+=1
    pending=sorted([r for r in seeds if r['profile_url'] not in completed],key=lambda r: r['listing_category']!=4);metrics['processed']=len(completed)
    print('Assigned',len(seeds),'pending',len(pending),'already processed',len(completed),flush=True)
    start=time.time()
    with open(OUT,'a') as out,open(EXCLUDE,'a') as rejected,concurrent.futures.ThreadPoolExecutor(24) as pool:
        for future in concurrent.futures.as_completed([pool.submit(task,r) for r in pending]):
            row,rej=future.result();metrics['processed']+=1
            if row:
                all_rows[row['source_url']]=row;out.write(json.dumps(row)+'\n');out.flush();metrics['kept']+=1;metrics['complete']+=bool(row.get('phone') and row.get('email'));metrics['phone']+=bool(row.get('phone'));metrics['email']+=bool(row.get('email'))
            else:rejected.write(json.dumps(rej)+'\n');rejected.flush();metrics['excluded']+=1
            if metrics['processed']%25==0:
                metrics['elapsed_seconds']=round(time.time()-start,1);json.dump(metrics,open(PROGRESS,'w'));print(json.dumps(metrics),flush=True)
    final_path=OUT.replace('.jsonl','.FINAL.jsonl')
    with open(final_path,'w') as f:f.write(''.join(json.dumps(r)+'\n' for r in all_rows.values()))
    metrics['kept']=len(all_rows);metrics['complete']=sum(bool(r.get('phone') and r.get('email')) for r in all_rows.values());metrics['phone']=sum(bool(r.get('phone')) for r in all_rows.values());metrics['email']=sum(bool(r.get('email')) for r in all_rows.values())
    metrics['finished_at']=datetime.datetime.now(datetime.timezone.utc).isoformat();metrics['elapsed_seconds']=round(time.time()-start,1);metrics['final_file']=final_path;json.dump(metrics,open(PROGRESS,'w'));print('FINISHED',json.dumps(metrics),flush=True)
