import concurrent.futures, urllib.request, urllib.parse, json, re, html, time, pathlib
from html.parser import HTMLParser

BASE=pathlib.Path(__file__).parent
class TextParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.text=[]; self.links=[]; self.skip=0; self.cf=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag in ('script','style'): self.skip+=1
        if tag=='a' and 'href' in a: self.links.append(a['href'])
        if a.get('data-cfemail'): self.cf.append(a['data-cfemail'])
    def handle_endtag(self,tag):
        if tag in ('script','style'): self.skip=max(0,self.skip-1)
    def handle_data(self,data):
        if not self.skip and data.strip(): self.text.append(data.strip())

def cf_decode(v):
    try:
        k=int(v[:2],16); return ''.join(chr(int(v[i:i+2],16)^k) for i in range(2,len(v),2))
    except: return ''

def fetch(url):
    try:
        req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; business contact research)'})
        with urllib.request.urlopen(req,timeout=22) as r:
            body=r.read(2500000).decode('utf-8','replace'); final=r.geturl(); status=r.status
        p=TextParser(); p.feed(body); t='\n'.join(p.text)
        emails=set(re.findall(r'[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}',t))
        emails.update(urllib.parse.unquote(v.split(':',1)[1].split('?')[0]) for v in p.links if v.lower().startswith('mailto:'))
        emails.update(cf_decode(v) for v in p.cf)
        emails={e.strip() for e in emails if e and not e.lower().endswith(('.png','.jpg','.webp','.svg')) and not any(x in e.lower() for x in ('example','wixpress','sentry','domain.com','yourcompany','email.com','mysite','company.com','website.com'))}
        phones=set(urllib.parse.unquote(v.split(':',1)[1]) for v in p.links if v.lower().startswith('tel:'))
        phones.update(re.findall(r'(?:\+?1[\s.\-]?)?(?:\(\d{3}\)|\b\d{3})[\s.\-]\d{3}[\s.\-]\d{4}\b',t))
        return {'url':url,'final_url':final,'status':status,'emails':sorted(emails),'phones':sorted(phones),'text':t,'links':p.links}
    except Exception as e: return {'url':url,'error':str(e),'emails':[],'phones':[],'text':'','links':[]}

def process(c):
    urls=[c['website']]+c.get('urls',[])
    pages=[fetch(urls[0])]
    contacts=[]
    for h in pages[0].get('links',[]):
        if any(s in h.lower() for s in ('contact','about-us','team')) and not h.startswith(('mailto:','tel:')):
            u=urllib.parse.urljoin(c['website'],h)
            if urllib.parse.urlsplit(u).netloc==urllib.parse.urlsplit(c['website']).netloc and u not in urls: contacts.append(u)
    urls+=list(dict.fromkeys(contacts))[:2]
    pages += [fetch(u) for u in urls[1:]]
    safe=re.sub(r'[^a-z0-9]+','_',c['company'].lower()).strip('_')
    (BASE/'fit_sources').mkdir(exist_ok=True)
    (BASE/'fit_sources'/f'{safe}.json').write_text(json.dumps(pages,ensure_ascii=False))
    chosen=[p for p in pages if p['emails'] and p['phones']]
    if not chosen: chosen=[p for p in pages if p['emails'] or p['phones']]
    emails=list(dict.fromkeys(e for p in chosen for e in p['emails']))
    phones=list(dict.fromkeys(e for p in chosen for e in p['phones']))
    priority=lambda e: (0 if e.lower().startswith(('info@','sales@','hello@','funding@','contact@','support@')) else 1,e)
    emails.sort(key=priority)
    out={k:v for k,v in c.items() if k!='urls'}
    out.update(contact_name='',email='; '.join(emails),phone='; '.join(phones),source_url='; '.join(p['final_url'] for p in chosen if 'final_url' in p),source_name='Company website public contacts and product pages',retrieved_at='2026-09-30',state='',capital_status='published_program_capacity_not_liquidity' if c.get('loan_max',0) and c['loan_max']>=500000 else 'capacity_unverified',evidence_urls=urls,contact_status='public_email_and_phone' if emails and phones else 'incomplete_contact',source_file=f'research/fit_sources/{safe}.json')
    print(c['company'],len(emails),len(phones),flush=True)
    return out

if __name__=='__main__':
    candidates=json.loads((BASE/'fit_candidates.json').read_text())
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex: rows=list(ex.map(process,candidates))
    (BASE/'fit_leads.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
    print('TOTAL',len(rows),'COMPLETE',sum(r['contact_status']=='public_email_and_phone' for r in rows))
