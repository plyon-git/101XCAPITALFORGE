from supplement_collect import *

def profile(u):
    t=fetch(u);r=html.fromstring(t) if t else None
    if r is None:return None
    for x in r.xpath('//script|//style|//noscript'):x.drop_tree()
    txt=' '.join(r.text_content().split())
    name=r.xpath('//h1/text()');name=name[0].strip() if name else u.rstrip('/').split('/')[-1]
    # The directory has one publisher telephone in the footer, which is not a lender contact.
    website=''
    for a in r.xpath('//a[@href]'):
        if a.text_content().strip().lower()=='company website':website=a.get('href');break
    cp=re.search(r'Contact Person (.*?) (?:Request a Quote|Company Details)',txt)
    mx=re.search(r'Maximum credit facility:\s*\$([\d,]+)',txt)
    mn=re.search(r'Minimum credit facility:\s*\$([\d,]+)',txt)
    details=re.search(r'Company Details (.*?) Company website',txt)
    phones=re.findall(r'\(\d{3}\)\s*\d{3}-\d{4}|(?<!\d)\d{3}-\d{3}-\d{4}(?!\d)',details.group(1) if details else '')
    rec={'name':name,'website':website,'source_url':u,'source_name':'FactoringClub public factoring directory','named_contact':cp.group(1) if cp else '',
         'directory_phone':phones[0] if phones else '', 'lending_max':int(mx.group(1).replace(',','')) if mx else None,'lending_min':int(mn.group(1).replace(',','')) if mn else None,
         'directory_description':txt[txt.find('About '+name):txt.find('Standard Terms')][:1800]}
    if any(x in txt for x in [' Ontario ',' Canada ','British Columbia','Quebec']):rec['country']='Canada'
    else:rec['country']='US'
    rec=crawl_site(rec)
    if not rec['phone'] and phones:rec['phone']=phones[0];rec['phone_source_url']=u
    rec['category']='factoring_receivables';rec['property_collateral_fit']='no_property_collateral_mandate_unconfirmed';rec['deal_fit_status']='receivables_eligibility_unconfirmed';rec['qualification_status']='unqualified_research'
    if rec['lending_max'] and rec['lending_max']>=500000:rec['capacity_status']='published_credit_facility_500k_plus_not_cash';rec['capacity_evidence_url']=u
    rec['contact_status']='phone_and_email_public' if rec['phone'] and rec['email'] else 'partial_contact' if rec['phone'] or rec['email'] else 'contacts_missing'
    return rec

if __name__=='__main__':
    sitemap=fetch('https://factoringclub.com/listings-sitemap1.xml')
    urls=re.findall(r'<loc>([^<]+)</loc>',sitemap)
    extra=fetch('https://factoringclub.com/po_finance_listings-sitemap1.xml')
    urls+=re.findall(r'<loc>([^<]+)</loc>',extra)
    print('Factoring profiles',len(urls),flush=True)
    results=[]
    with concurrent.futures.ThreadPoolExecutor(8) as pool:
        for rec in pool.map(profile,urls):
            if not rec:continue
            results.append(rec)
            with open(os.path.join(ROOT,'supplement_factoring.jsonl'),'a') as f:f.write(json.dumps(rec)+'\n')
            if len(results)%10==0:print('Factoring complete',len(results),'both',sum(bool(x['phone'] and x['email']) for x in results),flush=True)
    print('FINISHED',len(results),'both',sum(bool(x['phone'] and x['email']) for x in results),flush=True)
