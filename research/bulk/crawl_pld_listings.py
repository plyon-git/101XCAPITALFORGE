import urllib.request,urllib.parse,re,json,html,os,gzip,hashlib,concurrent.futures,time,datetime,collections
RAW='research/bulk/raw';os.makedirs(RAW,exist_ok=True);NOW=datetime.datetime.now(datetime.timezone.utc).isoformat();BASE='https://www.privatelendersdirectory.com'
def fetch(url):
 path=f'{RAW}/{hashlib.sha256(url.encode()).hexdigest()}.html.gz'
 if os.path.exists(path):
  with gzip.open(path,'rt') as f:return f.read()
 try:
  with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=20) as r:t=r.read(2_000_000).decode(errors='replace')
  with gzip.open(path,'wt') as f:f.write(t)
  return t
 except Exception:return ''
def txt(t):return html.unescape(re.sub(r'<[^>]+>',' ',t)).strip()
def norm(name):
 name=re.sub(r'\s+(?:PRIVATE|HARD MONEY|REAL ESTATE INVESTMENT)\s+LENDER.*$','',name,flags=re.I)
 return re.sub('[^a-z0-9]','',name.lower())
def attrs(t):
 return dict((a.lower(),html.unescape(b or c)) for a,b,c in re.findall(r'([\w-]+)\s*=\s*(?:"([^"]*)"|\x27([^\x27]*)\x27)',t))
# Categories: real estate investment lending and business lending only, excluding directory's realty/broker categories.
jobs=[]
for cat in [1,4]:
 u=BASE+f'/search_results?sid={cat}&sort=name%20ASC';t=fetch(u)
 count=int((re.findall(r'<span class="total__js">(.*?)</span>',t)+['0'])[0].replace(',',''))
 print('PLD category',cat,'listed',count,flush=True)
 jobs.extend((cat,BASE+f'/search_results?sid={cat}&sort=name%20ASC&page={p}') for p in range(1,(count+9)//10+1))
records={};excluded=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
 for i,((cat,u),t) in enumerate(zip(jobs,ex.map(lambda x:fetch(x[1]),jobs))):
  for raw in re.findall(r'<a\b([^>]+)>',t,re.S|re.I):
   a=attrs(raw)
   if 'search_view_listing_button' not in a.get('class',''):continue
   name=a.get('title','').replace('View Listing - ','');p=urllib.parse.urljoin(BASE,a.get('href',''))
   if not name or not p.startswith(BASE+'/'):continue
   # Obvious service providers and conventional retail mortgage/bank entities cannot be counted as private lenders.
   if re.search(r'\b(?:REALT[YOR]|REALTY|REALTORS|INSURANCE|COMPLIANCE|ACCOUNTING|CPA|TITLE|EXP REALTY|BOOKKEEP|BUSINESS BROKER|MERGERS|ADVISORY|LAW FIRM)\b',name,re.I):
    excluded.append({'company':name,'source_url':p,'reason':'name_indicates_non_lender_service_provider'});continue
   n=norm(name)
   if n not in records:records[n]={'company':name,'profile_url':p,'listing_source_url':u,'listing_category':cat}
  if i%75==0:print('PLD pages',i,'unique candidate companies',len(records),flush=True)
json.dump(list(records.values()),open('research/bulk/pld_discovery.json','w'))
json.dump(excluded,open('research/bulk/pld_exclusions.json','w'))
print('PLD unique candidates discovered',len(records),flush=True)
