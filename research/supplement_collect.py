import urllib.request, urllib.parse, concurrent.futures, os, json, re, time, hashlib
from lxml import html

ROOT=os.path.dirname(os.path.abspath(__file__))
RAW=os.path.join(ROOT,'raw','supplement'); os.makedirs(RAW,exist_ok=True)
UA='Mozilla/5.0 (compatible; public business directory research)'

def fetch(url,kind='page'):
    fn=os.path.join(RAW,hashlib.sha256(url.encode()).hexdigest()+'.html')
    if os.path.exists(fn):return open(fn).read()
    try:
        req=urllib.request.Request(url,headers={'User-Agent':UA})
        r=urllib.request.urlopen(req,timeout=15)
        if 'text' not in r.headers.get('Content-Type','text'):return ''
        t=r.read(3000000).decode(errors='replace');open(fn,'w').write(t);return t
    except Exception as e:
        return ''

def normalized_phone(x):
    x=re.sub(r'^(?:tel:)','',x,flags=re.I).strip()
    return x if 10<=len(re.sub(r'\D','',x))<=16 else ''

def extract(t,url):
    out={'phones':[],'emails':[],'money_evidence':[],'description':''}
    if not t:return out
    r=html.fromstring(t)
    # Cloudflare renders these public contact addresses client-side.
    for e in r.xpath('//*[@data-cfemail]'):
        code=e.get('data-cfemail','')
        try:
            b=bytes.fromhex(code);mail=''.join(chr(c^b[0]) for c in b[1:]);out['emails'].append(mail)
        except (ValueError,IndexError):pass
    for e in r.xpath('//script|//style|//noscript'):e.drop_tree()
    txt=' '.join(x.strip() for x in r.itertext() if x.strip())
    txt=re.sub(r'\[at\]|\(at\)','@',txt,flags=re.I)
    txt=re.sub(r'\[dot\]|\(dot\)','.',txt,flags=re.I)
    for a in r.xpath('//a[@href]'):
        h=a.get('href','')
        if h.lower().startswith('mailto:'):
            mail=urllib.parse.unquote(h[7:].split('?')[0]).strip()
            if re.fullmatch(r'[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}',mail):out['emails'].append(mail)
        if h.lower().startswith('tel:'):
            p=normalized_phone(urllib.parse.unquote(h));
            if p:out['phones'].append(p)
    # Plain-text contacts are public, but exclude asset strings and noise.
    out['emails']+=re.findall(r'(?<![\w.])[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}(?![\w.])',txt)
    out['phones']+=re.findall(r'(?<!\d)(?:\+1[ .-]?)?(?:\([2-9]\d{2}\)|[2-9]\d{2})[ .-][2-9]\d{2}[ .-]\d{4}(?!\d)',txt)
    out['phones']=list(dict.fromkeys(out['phones']));out['emails']=list(dict.fromkeys(x for x in out['emails'] if not x.lower().endswith(('.png','.jpg','.webp')) and not any(z in x.lower() for z in ['@example.','@yourdomain.','@domain.','@email.','@mysite.','@sentry.'])))
    out['description']=txt[:1800]
    for m in re.finditer(r'\$\s*[\d,.]+\s*(?:million|billion|[MBK]\b)',txt,re.I):out['money_evidence'].append(txt[max(0,m.start()-100):m.end()+150])
    return out

def crawl_site(rec):
    u=rec.get('website',''); out=dict(rec)
    out.update({'phone':'','email':'','phone_source_url':'','email_source_url':'','capacity_status':'unverified','qualification_status':'unqualified_research','cash_500k_verified':False,'property_collateral_fit':'unknown','deal_fit_status':'unconfirmed','retrieved_at':'2026-09-30'})
    if not u:return out
    if not u.startswith('http'):u='https://'+u
    t=fetch(u);ex=extract(t,u)
    evidence=[]
    if t:
        r=html.fromstring(t)
        links=[]
        for a in r.xpath('//a[@href]'):
            h=urllib.parse.urljoin(u,a.get('href')); text=a.text_content().strip().lower()
            if urllib.parse.urlparse(h).netloc.removeprefix('www.') != urllib.parse.urlparse(u).netloc.removeprefix('www.'):continue
            if 'contact' in text or '/contact' in h.lower():links.append(h)
        for link in list(dict.fromkeys(links))[:2]:
            if ex['phones'] and ex['emails']:break
            z=extract(fetch(link),link)
            if z['phones'] and not out['phone']:out['phone']=z['phones'][0];out['phone_source_url']=link
            if z['emails'] and not out['email']:out['email']=z['emails'][0];out['email_source_url']=link
            evidence+=z['money_evidence']
    if not out['phone'] and ex['phones']:out['phone']=ex['phones'][0];out['phone_source_url']=u
    if not out['email'] and ex['emails']:out['email']=ex['emails'][0];out['email_source_url']=u
    out['additional_phones']=ex['phones'][1:];out['additional_emails']=ex['emails'][1:]
    out['capacity_evidence_text']=' | '.join((ex['money_evidence']+evidence)[:4])
    out['description']=ex['description'];out['category']='private_real_estate_or_finance_directory_member'
    low=(out['name']+' '+out['description']).lower()
    if any(x in low for x in ['attorney','law firm','legal services','insurance broker','title company','escrow company','lending software','mortgage software','crm software']):out['category']='service_provider_excluded';out['deal_fit_status']='excluded_service_provider'
    elif any(x in low for x in ['factoring','receivable','working capital','business funding','business financing']):out['category']='business_finance';out['deal_fit_status']='business_finance_mandate_unconfirmed'
    elif any(x in low for x in ['real estate loan','hard money','real estate lend','mortgage loan','bridge loan','dscr']):out['category']='property_secured_lender';out['property_collateral_fit']='collateral_mismatch';out['deal_fit_status']='property_collateral_mismatch'
    out['contact_status']='phone_and_email_public' if out['phone'] and out['email'] else 'partial_contact' if out['phone'] or out['email'] else 'contacts_missing'
    return out

def collect_npla():
    pages=[('https://nplaconference.com/private-lending-directory/' if p==1 else f'https://nplaconference.com/private-lending-directory/page/{p}/') for p in range(1,31)]
    recs=[]
    with concurrent.futures.ThreadPoolExecutor(4) as pool:
        for u,t in zip(pages,pool.map(fetch,pages)):
            if not t:continue
            r=html.fromstring(t)
            for a in r.xpath('//article[contains(@class,"bde-loop-item")]'):
                name=a.xpath('.//h6/text()');web=a.xpath('.//a[@href]/@href');addr=a.xpath('.//div[contains(@class,"bde-text")]/text()')
                if name and web:recs.append({'name':name[0].strip(),'website':web[0],'source_url':u,'source_name':'NPLA public private lending directory','address':' '.join(x.strip() for x in addr if x.strip())})
    seen=set();return [r for r in recs if not (r['name'].lower() in seen or seen.add(r['name'].lower()))]

if __name__=='__main__':
    recs=collect_npla();open(os.path.join(ROOT,'npla_seeds.json'),'w').write(json.dumps(recs,indent=2));print('NPLA seeds',len(recs),flush=True)
    completed=[]
    with concurrent.futures.ThreadPoolExecutor(10) as pool:
        for r in pool.map(crawl_site,recs):
            completed.append(r)
            with open(os.path.join(ROOT,'supplement_npla.jsonl'),'a') as f:f.write(json.dumps(r)+'\n')
            if len(completed)%10==0:print('Enriched',len(completed),'complete',sum(bool(x['phone'] and x['email']) for x in completed),flush=True)
    print('FINISHED',len(completed),'complete',sum(bool(x['phone'] and x['email']) for x in completed),flush=True)
