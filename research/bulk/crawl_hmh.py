import urllib.request,urllib.parse,re,json,html,os,gzip,hashlib,concurrent.futures,time,datetime,collections
BASE='https://www.hardmoneyhome.com'
RAW='research/bulk/raw';os.makedirs(RAW,exist_ok=True)
NOW=datetime.datetime.now(datetime.timezone.utc).isoformat()
def fetch(url):
 key=hashlib.sha256(url.encode()).hexdigest()
 path=f'{RAW}/{key}.html.gz'
 if os.path.exists(path):
  with gzip.open(path,'rt') as f:return f.read()
 req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (public business contact research)'})
 for attempt in range(2):
  try:
   with urllib.request.urlopen(req,timeout=20) as r:t=r.read(4_000_000).decode(errors='replace')
   with gzip.open(path,'wt') as f:f.write(t)
   return t
  except Exception:
   if attempt==0:time.sleep(.5)
 return ''
def links(t):return [html.unescape(x) for x in re.findall(r'href=[\"\x27]([^\"\x27]+)',t,re.I)]
def text(t):return html.unescape(re.sub(r'<[^>]+>',' ',t)).strip()
home=fetch(BASE+'/')
states=sorted(set(x for x in links(home) if re.match('/hard-money-loans/[a-z-]+$',x)))
print('States',len(states),flush=True)
cities=set()
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
 for state,t in zip(states,ex.map(lambda x:fetch(BASE+x),states)):
  cities.update(x for x in links(t) if re.match(r'/hard-money-loans/[a-z0-9-]+-[a-z]{2}$',x))
print('Cities',len(cities),flush=True)
profiles=set()
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
 for i,t in enumerate(ex.map(lambda x:fetch(BASE+x),sorted(cities))):
  profiles.update(x.split('#')[0] for x in links(t) if x.startswith('/lenders/view/'))
  if i%100==0:print('City progress',i,'Profiles',len(profiles),flush=True)
json.dump(sorted(profiles),open('research/bulk/hmh_profile_urls.json','w'))
print('Discovered profiles',len(profiles),flush=True)
out=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
 for i,(p,t) in enumerate(zip(sorted(profiles),ex.map(lambda x:fetch(BASE+x),sorted(profiles)))):
  if not t:continue
  fs={}
  for raw in re.findall(r'<script[^>]*type=[\"\x27]application/ld\+json[\"\x27][^>]*>(.*?)</script>',t,re.S|re.I):
   try:d=json.loads(raw)
   except Exception:continue
   if isinstance(d,dict) and d.get('@type')=='FinancialService':fs=d;break
  name=fs.get('name') or text((re.findall(r'<h1[^>]*>(.*?)</h1>',t,re.S)+[''])[0])
  if not name:continue
  web=(re.findall(r'<a[^>]*class=[\"\x27]web-url[\"\x27][^>]*href=[\"\x27]([^\"\x27]+)',t,re.I)+[''])[0]
  phone=fs.get('telephone','')
  if not phone:
   phone=(re.findall(r'href=[\"\x27]tel:([^\"\x27]+)',t,re.I)+[''])[0]
  # Restrict contact extraction to profile About text and action controls, excluding reviews and loan examples.
  about=(re.findall(r'<h3>About .*?</h3>(.*?)(?:<h3>|</li>)',t,re.S)+[''])[0]
  emails=sorted(set(re.findall(r'[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}',html.unescape(about))))
  areas=(re.findall(r'<b>Areas Served:</b>(.*?)</p>',t,re.S)+[''])[0]
  guid=(re.findall(r'Loan Amounts:\s*(\$[0-9,]+)\s*-\s*(\$[0-9,]+)',t)+[])
  amounts=[int(x.replace('$','').replace(',','')) for pair in guid for x in pair]
  out.append({'title':name,'company':name,'contact_name':'','email':emails[0] if emails else '', 'phone':phone,'website':html.unescape(web),'source_url':BASE+p,'source_name':'HardMoneyHome','retrieved_at':NOW,'state':fs.get('address',{}).get('addressRegion',''),'category':'private_real_estate_lender','fit_status':'property_collateral_required_or_likely','capital_status':'unverified','notes':'Directory profile describes property loans. Unsecured fulfillment financing/equity participation not verified. Published loan limits do not verify cash on hand.','areas_served':text(areas),'published_loan_max_usd':max(amounts) if amounts else None,'field_sources':{'company':BASE+p,'phone':BASE+p,'website':BASE+p,**({'email':BASE+p} if emails else {})},'email_status':'publicly_listed_not_deliverability_tested' if emails else 'not_found','profile_address':fs.get('address',{}),'directory_profile_snapshot':f'bulk/raw/{hashlib.sha256((BASE+p).encode()).hexdigest()}.html.gz'})
  if i%100==0:print('Profile progress',i,'Extracted',len(out),flush=True)
with open('research/bulk_leads.jsonl','w') as f:
 for r in out:f.write(json.dumps(r)+'\n')
print('Output',len(out),'Phone',sum(bool(r['phone']) for r in out),'Email',sum(bool(r['email']) for r in out),'Website',sum(bool(r['website']) for r in out),flush=True)
