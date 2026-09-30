import urllib.request,urllib.parse,re,json,html,os,gzip,hashlib,concurrent.futures,time,datetime
RAW='research/bulk/raw';os.makedirs(RAW,exist_ok=True)
NOW=datetime.datetime.now(datetime.timezone.utc).isoformat()
def fetch(url):
 key=hashlib.sha256(url.encode()).hexdigest();path=f'{RAW}/{key}.html.gz'
 if os.path.exists(path):
  with gzip.open(path,'rt') as f:return f.read()
 try:
  with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=25) as r:t=r.read(3_000_000).decode(errors='replace')
  with gzip.open(path,'wt') as f:f.write(t)
  return t
 except Exception:return ''
def txt(t):return html.unescape(re.sub(r'<[^>]+>',' ',t)).strip()
def parse(u,t):
 fs={}
 for raw in re.findall(r'<script[^>]*type=[\"\x27]application/ld\+json[\"\x27][^>]*>(.*?)</script>',t,re.S|re.I):
  try:d=json.loads(raw)
  except Exception:continue
  for obj in d.get('@graph',[d]) if isinstance(d,dict) else []:
   if obj.get('@type')=='FinancialService':fs=obj;break
  if fs:break
 name=fs.get('name') or txt((re.findall(r'<h1[^>]*>(.*?)</h1>',t,re.S)+[''])[0])
 if not name:return None
 addr=fs.get('address') or {}
 if str(addr.get('addressCountry') or '').upper() in ('CA','CANADA','CAN'):return None
 phone=(re.findall(r'href=[\"\x27]tel:([^\"\x27]+)',t,re.I)+[''])[0] or fs.get('telephone') or ''
 email=''
 # Only official inquiry-form recipient. Comments/reviews and unrelated user emails deliberately excluded.
 for f in re.findall(r'\{"objectType":"Field".*?\}',t):
  if '"label":"recipient_email"' in f:
   try:email=json.loads(f).get('value','')
   except Exception:pass
 if email and not re.fullmatch(r'[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}',email):email=''
 web=''
 for attrs in re.findall(r'<a\b([^>]+)>',t,re.S|re.I):
  if 'aria-label="Website"' in attrs:
   m=re.search(r'href=[\"\x27]([^\"\x27]+)',attrs)
   if m:web=html.unescape(m[1]);break
 desc=fs.get('description') or ''
 return {'title':name,'company':name,'contact_name':'','email':email,'phone':phone,'website':web,'source_url':u,'source_name':'PrivateLenderLink','retrieved_at':NOW,'state':str(addr.get('addressRegion') or '').split(',')[0], 'category':'private_real_estate_lender','fit_status':'property_collateral_required_or_likely','capital_status':'unverified','notes':'Published real estate lender directory listing; unsecured operations finance and equity willingness not verified. Cash availability is unverified. '+' '.join(desc.split()[:20]),'field_sources':{'company':u,**({'phone':u} if phone else {}),**({'email':u} if email else {}),**({'website':u} if web else {})},'email_status':'public_inquiry_form_recipient_not_deliverability_tested' if email else 'not_found','profile_address':addr,'directory_profile_snapshot':f'bulk/raw/{hashlib.sha256(u.encode()).hexdigest()}.html.gz'}
s=fetch('https://privatelenderlink.com/lenders/')
us=sorted(set(re.findall(r'https://privatelenderlink.com/profile/[^\"\x27/#]+/',s)))
print('PLL discovered',len(us),flush=True)
out=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
 for i,(u,t) in enumerate(zip(us,ex.map(fetch,us))):
  r=parse(u,t)
  if r:out.append(r)
  if i%75==0:print('PLL progress',i,'records',len(out),flush=True)
with open('research/bulk/pll_leads.jsonl','w') as f:
 for r in out:f.write(json.dumps(r)+'\n')
print('PLL total',len(out),'phones',sum(bool(r['phone']) for r in out),'emails',sum(bool(r['email']) for r in out),'websites',sum(bool(r['website']) for r in out),flush=True)
