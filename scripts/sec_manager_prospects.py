#!/usr/bin/env python3
"""Reproducible SEC private-fund manager screen and public-site contact enrichment.
No cash, mandate, ticket, or offered-return acceptance is inferred from fund assets.
"""
import csv,glob,json,os,re,io,zipfile,gzip,hashlib,datetime,time,ssl,threading,subprocess
from urllib.request import urlopen,Request
from urllib.parse import urljoin,urlparse,unquote
from xml.etree import ElementTree as ET
from concurrent.futures import ThreadPoolExecutor,as_completed
from collections import defaultdict,Counter
from html import unescape

def atomic_json(path,value):
 temp=path+'.'+str(os.getpid())+'.tmp'
 with open(temp,'w') as f:json.dump(value,f)
 os.replace(temp,path)
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE=os.path.join(ROOT,'research','sec');os.makedirs(BASE,exist_ok=True)
UA='Mozilla/5.0 (compatible; CapitalProspectResearch/1.0; public business contact research)'
MANIFEST='https://reports.adviserinfo.sec.gov/reports/foia/reports_metadata.json'
SEC_PAGE='https://www.sec.gov/help/foiadocsinvafoia'
XML_SOURCE='https://reports.adviserinfo.sec.gov/reports/CompilationReports/IA_FIRM_SEC_Feed_09_29_2026.xml.gz'
RETRIEVED='2026-09-30'

DOMAIN_LOCKS={}
DOMAIN_LOCKS_MUTEX=threading.Lock()

def get(url,limit=5000000,max_seconds=7):
 """One request per domain at a time; reuse URL results, including failures."""
 parsed=urlparse(url)
 url=parsed._replace(scheme=parsed.scheme.lower(),netloc=parsed.netloc.lower()).geturl()
 host=urlparse(url).hostname or url
 with DOMAIN_LOCKS_MUTEX:
  lock=DOMAIN_LOCKS.setdefault(host,threading.Lock())
 cache_dir=os.path.join(BASE,'http_cache');os.makedirs(cache_dir,exist_ok=True)
 key=hashlib.sha256(url.encode()).hexdigest()
 meta_path=os.path.join(cache_dir,key+'.json');body_path=os.path.join(cache_dir,key+'.gz')
 with lock:
  if os.path.exists(meta_path):
   meta=json.load(open(meta_path))
   if meta.get('error'):raise RuntimeError('Cached public URL failure: '+meta['error'])
   if os.path.exists(body_path):return gzip.decompress(open(body_path,'rb').read()),meta['actual'],meta['content_type']
  try:
   budget=max_seconds if limit<=5000000 else 60
   args=['curl','-L','--silent','--show-error','--compressed','--max-time',str(budget),'--connect-timeout','3','--max-filesize',str(limit),'-A',UA,'-w','\n__CAPITALFORGE_META__%{url_effective}\t%{content_type}\t%{http_code}',url]
   res=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=budget+1)
   if res.returncode:raise RuntimeError('curl '+str(res.returncode)+': '+res.stderr.decode(errors='replace')[:180])
   data,marker,meta=res.stdout.rpartition(b'\n__CAPITALFORGE_META__')
   if not marker:raise RuntimeError('Missing HTTP response metadata')
   actual,content_type,status=meta.decode(errors='replace').split('\t')
   if int(status)>=400:raise RuntimeError('HTTP '+status+' for '+actual)
   temp=body_path+'.'+str(os.getpid())+'.tmp'
   open(temp,'wb').write(gzip.compress(data))
   os.replace(temp,body_path)
   atomic_json(meta_path,{'url':url,'actual':actual,'content_type':content_type,'retrieved_at':RETRIEVED})
   return data,actual,content_type
  except Exception as ex:
   atomic_json(meta_path,{'url':url,'error':type(ex).__name__+': '+str(ex)[:200],'retrieved_at':RETRIEVED})
   raise

def num(x):
 try:return float((x or '').strip().replace(',',''))
 except:return 0

def bootstrap_sources():
 os.makedirs(os.path.join(BASE,'current'),exist_ok=True)
 manifest_path=os.path.join(BASE,'reports_metadata.json')
 if not os.path.exists(manifest_path):
  b,_,_=get(MANIFEST,1000000);open(manifest_path,'wb').write(b)
 for name in ['ia09012026-registered.zip','ia09012026-exempt.zip']:
  p=os.path.join(BASE,name)
  if not os.path.exists(p):
   u='https://www.sec.gov/files/investment/data/other/information-about-registered-investment-advisers-exempt-reporting-advisers/'+name
   b,_,_=get(u,100000000);open(p,'wb').write(b)
  z=zipfile.ZipFile(p)
  for f in z.namelist():
   # Trusted SEC archive; copy only roster CSV, never arbitrary path extraction.
   if f.lower().endswith('.csv') and '/' not in f and '\\' not in f:
    target=os.path.join(BASE,'current',f)
    if not os.path.exists(target):open(target,'wb').write(z.read(f))
 p=os.path.join(BASE,'current_sec_20260929.xml.gz');xmlp=os.path.join(BASE,'current_sec_20260929.xml')
 if not os.path.exists(xmlp):
  if not os.path.exists(p):
   b,_,_=get(XML_SOURCE,100000000);open(p,'wb').write(b)
  open(xmlp,'wb').write(gzip.decompress(open(p,'rb').read()))

def get_zips():
 meta=json.load(open(os.path.join(BASE,'reports_metadata.json')))
 jobs=[]
 for f in meta['advFilingData']['2026']['files']:
  u=f"https://reports.adviserinfo.sec.gov/reports/foia/advFilingData/2026/{f['fileName']}"
  jobs.append((u,os.path.join(BASE,f['fileName'])))
 def down(j):
  u,p=j
  if not os.path.exists(p):
   b,_,_=get(u,100000000);open(p,'wb').write(b)
  return p
 with ThreadPoolExecutor(max_workers=4) as pool:
  for p in pool.map(down,jobs):print('DATA',os.path.basename(p),flush=True)
 return [x[1] for x in jobs]

def funds_and_names(zips):
 latest={};funds=defaultdict(list);names={}
 for p in zips:
  z=zipfile.ZipFile(p)
  for f in z.namelist():
   if re.match(r'(?:IA_ADV_Base_A_|ERA_ADV_Base_)',f):
    for r in csv.DictReader(io.StringIO(z.read(f).decode('latin1'))):
     crd=r['1E1'];fid=r['FilingID'];date=datetime.datetime.strptime(r['DateSubmitted'].split(' ')[0],'%m/%d/%Y').isoformat()[:10]
     if crd not in latest or (date,int(fid))>(latest[crd]['date'],int(latest[crd]['fid'])):
      latest[crd]={'fid':fid,'date':date,'source':f"https://reports.adviserinfo.sec.gov/reports/foia/advFilingData/2026/{os.path.basename(p)}"}
   if re.match(r'(?:IA|ERA)_Schedule_D_7B1_',f):
    for r in csv.DictReader(io.StringIO(z.read(f).decode('latin1'))):funds[r['FilingID']].append(r)
   if re.match(r'(?:IA|ERA)_ADV_1J_1K_',f):
    for r in csv.DictReader(io.StringIO(z.read(f).decode('latin1'))):names[r['FilingID']]=r
 return latest,funds,names

def candidates():
 bootstrap_sources()
 current={}
 for _,f in ET.iterparse(os.path.join(BASE,'current_sec_20260929.xml'),events=('end',)):
  if f.tag!='Firm':continue
  info=f.find('Info').attrib;reg=f.find('Rgstn').attrib;addr=f.find('MainAddr').attrib;filing=f.find('Filing').attrib
  current[info['FirmCrdNb']]={'name':info.get('BusNm',''),'legal':info.get('LegalNm',''),'phone':addr.get('PhNb',''),'city':addr.get('City',''),'state':addr.get('State',''),'country':addr.get('Cntry',''),'status':reg.get('St',''),'filing_date':filing.get('Dt',''),'websites':[w.text for w in f.findall('.//WebAddr') if w.text]}
  f.clear()
 latest,funds,names=funds_and_names(get_zips())
 all_rows=[]
 for p in glob.glob(os.path.join(BASE,'current','*.CSV')):
  all_rows.extend(csv.DictReader(open(p,encoding='latin1')))
 out=[]
 for r in all_rows:
  crd=r['Organization CRD#'].strip();x=current.get(crd)
  if not x or x['status'] not in ['APPROVED','ACTIVE'] or x['country']!='United States':continue
  gross=num(r.get('Total Gross Assets of Private Funds'));is_re=r.get('Any Real Estate Funds','').strip()=='Y';is_pe=r.get('Any PE Funds','').strip()=='Y'
  li=latest.get(crd,{})
  fs=funds.get(li.get('fid'),[])
  # Specific 7B1 fund GAV filter, latest snapshot fallback if filing not available.
  related=[f for f in fs if num(f.get('Gross Asset Value'))>=500000 and f.get('Fund Type') in ['Real Estate Fund','Private Equity Fund']]
  credit_re=re.compile(r'\b(private credit|direct lending|private lending|commercial lending|real estate (?:debt|credit)|realty credit|bridge (?:lending|finance)|mortgage|mezzanine|asset.based|receivables|specialty finance|opportunistic credit|structured credit|middle market credit)\b',re.I)
  credit=[f for f in fs if num(f.get('Gross Asset Value'))>=500000 and credit_re.search((f.get('Fund Name','')+' '+f.get('Fund Type Other','')))]
  if not ((is_re or is_pe) and gross>=500000 or credit):continue
  if fs and not (related or credit):continue
  kind='real_estate_fund_manager' if is_re else 'private_credit_manager_research' if credit else 'equity_manager_research'
  web=[]
  for u in x['websites'] or re.split(r'[;,\s]+',r.get('Website Address','')):
   if not u or '@' in u:continue
   if not re.match(r'^https?://',u,re.I):u='https://'+u
   host=urlparse(u).netloc.lower()
   if any(s in host for s in ['linkedin.','facebook.','twitter.','instagram.','youtube.','x.com','tiktok.','weibo.']):continue
   if u not in web:web.append(u)
  role=names.get(li.get('fid'),{})
  contact=role.get('1J1 Name','') or role.get('1K Name','')
  fund_types=sorted(set(f.get('Fund Type','') for f in related+credit))
  if not fund_types:fund_types=[k for k,flag in [('Real Estate Fund',is_re),('Private Equity Fund',is_pe)] if flag]
  specific=[{'name':f.get('Fund Name',''),'type':f.get('Fund Type',''),'gross_assets':num(f.get('Gross Asset Value')),'fund_id':f.get('Fund ID','')} for f in related+credit]
  specific=list({f['fund_id']:f for f in specific}.values())
  rec={'company':x['name'],'name':contact,'phone':x['phone'] if len(re.sub(r'\D','',x['phone']))>=10 else '','email':'','website':web[0] if web else '', 'additional_websites':web[1:4],'city':x['city'],'state':x['state'],'country':'United States','category':kind,'source_url':f'https://adviserinfo.sec.gov/firm/summary/{crd}','source_type':'SEC Form ADV + published business website','source_date':x['filing_date'],'retrieved_at':RETRIEVED,'contact_role':('Chief compliance officer (regulatory contact)' if role.get('1J1 Name') else 'Additional regulatory contact' if role.get('1K Name') else ''),'contact_name_source':li.get('source',''),'fit_status':'research_required','fit_reason':('Disclosed real estate private-fund manager; operating-company/debt/equity mandate unconfirmed.' if is_re else 'Named private-credit fund; unsecured operating-company funding mandate and $100K-$500K ticket unconfirmed.' if credit else 'Disclosed private-equity fund manager; 9.3% operating-company equity proposal requires mandate and ticket qualification.'),'security_requirement':'unknown','capital_min_usd':None,'capital_max_usd':None,'liquid_cash_verified':False,'minimum_cash_status':'unverified','reported_private_fund_gross_assets_usd':gross,'asset_screen_description':'At least $500K disclosed private-fund gross assets; NOT verified cash or deployable capital.','fund_types':fund_types,'fund_evidence':specific,'fund_source_url':li.get('source','') or SEC_PAGE,'fund_data_date':li.get('date','') or x['filing_date'],'sec_crd':crd,'sec_status':x['status'],'phone_status':'SEC_public_business_number_not_call_tested','phone_source_url':XML_SOURCE,'email_source_url':'','email_status':'not_found','email_contact_type':'','notes':'Compliance names are routing contacts, not assumed investment decision-makers. No outreach sent.'}
  out.append(rec)
 open(os.path.join(ROOT,'research','sec_candidates.jsonl'),'w').write(''.join(json.dumps(x)+'\n' for x in out))
 print('SCREEN',len(out),dict(Counter(x['category'] for x in out)),flush=True)
 return out

EMAIL=re.compile(r'(?<![A-Za-z0-9._%+-])([A-Za-z0-9][A-Za-z0-9._%+-]{0,63}@[A-Za-z0-9][A-Za-z0-9.-]+\.[A-Za-z]{2,20})(?![A-Za-z0-9])')
SKIP=re.compile(r'^(example|test|yourname|email|username|someone|name|user)@|@(example|domain|sentry|wixpress|wordpress|email|yourdomain)\.|\.(?:png|jpg|jpeg|gif|webp|svg|css|js)$',re.I)
BADLOCAL=re.compile(r'^(?:privacy|dpo|legal|compliance|careers|jobs|recruiting|abuse|webmaster|support|press|media|unsubscribe|noreply|no-reply|donotreply)$',re.I)
PREF=re.compile(r'^(?:info|contact|inquiries|inquiry|hello|invest|investments|capital|business|sales|team|office|partners|general|admin)$',re.I)

def emails_from_html(s):
 s=unescape(s)
 # Cloudflare public email protection decodes the publicly embedded contact string.
 for code in re.findall(r'data-cfemail=[\"\x27]([a-fA-F0-9]+)',s):
  try:
   b=bytes.fromhex(code);s+=' '+''.join(chr(x^b[0]) for x in b[1:])
  except:pass
 out=[]
 for e in EMAIL.findall(s):
  e=e.strip('.,;:').lower()
  if SKIP.search(e):continue
  if len(e.split('@')[0])>50:continue
  if e not in out:out.append(e)
 return out

def enrich(r):
 key=r['sec_crd'];cache=os.path.join(BASE,'contacts',key+'.json');os.makedirs(os.path.dirname(cache),exist_ok=True)
 if os.path.exists(cache):return json.load(open(cache))
 u=r['website'];errors=[];pages=[];all_em=[];deadline=time.monotonic()+20
 if not u:
  r['email_status']='no_business_website';atomic_json(cache,r);return r
 origins=[u]+r['additional_websites'][:1]
 for origin in origins:
  if all_em or len(pages)>=3 or time.monotonic()>=deadline:break
  try:
   b,actual,typ=get(origin,2500000,max_seconds=max(.5,min(7,deadline-time.monotonic())))
   if 'html' not in typ and not b.lstrip().startswith(b'<'):continue
   s=b.decode('utf-8',errors='replace');pages.append(actual)
   em=emails_from_html(s);all_em += [(e,actual) for e in em]
   # Public on-domain contact/about pages only; avoid crawls of people lists.
   links=[]
   for href,text in re.findall(r'<a\b[^>]*href=[\"\x27]([^\"\x27]+)[\"\x27][^>]*>(.*?)</a>',s,re.I|re.S):
    if not re.search(r'contact|connect|inquir|reach us',href+' '+re.sub('<[^>]*>',' ',text),re.I):continue
    nxt=urljoin(actual,unescape(href))
    if urlparse(nxt).netloc==urlparse(actual).netloc and nxt not in links and nxt!=actual and not nxt.lower().endswith(('.pdf','.jpg','.png')):links.append(nxt)
   if not links:links=[urljoin(actual,'/contact/'),urljoin(actual,'/contact-us/')]
   # Always read one contact page when email is only privacy/support/press.
   for nxt in links[:2]:
    if len(pages)>=3 or time.monotonic()>=deadline:break
    if any(not BADLOCAL.match(e.split('@')[0]) for e,_ in all_em):break
    try:
     bb,aa,tt=get(nxt,1800000,max_seconds=max(.5,min(7,deadline-time.monotonic())))
     if 'html' in tt or bb.lstrip().startswith(b'<'):
      ss=bb.decode('utf-8',errors='replace');pages.append(aa);all_em += [(e,aa) for e in emails_from_html(ss)]
    except Exception as ex:errors.append(type(ex).__name__+': '+str(ex)[:140])
  except Exception as ex:errors.append(type(ex).__name__+': '+str(ex)[:140])
 # Only published business contact emails, exclude privacy/jobs/press/etc routing.
 allowed_hosts={urlparse(w).netloc.lower().removeprefix('www.') for w in [u]+r['additional_websites']+pages}
 generic_hosts={'gmail.com','yahoo.com','outlook.com','hotmail.com','aol.com','proton.me','protonmail.com'}
 good=[(e,s) for e,s in all_em if not BADLOCAL.match(e.split('@')[0]) and (any(e.split('@')[1]==h or e.split('@')[1].endswith('.'+h) or h.endswith('.'+e.split('@')[1]) for h in allowed_hosts) or e.split('@')[1] in generic_hosts)]
 # Favor domain match and generic investor/business routing contacts.
 host=urlparse(u).netloc.lower().removeprefix('www.')
 good.sort(key=lambda es:(0 if es[0].split('@')[1].removeprefix('www.')==host else 1,0 if PREF.match(es[0].split('@')[0]) else 1))
 if good:
  r['email'],r['email_source_url']=good[0];r['email_status']='publicly_published_not_delivery_tested';r['email_contact_type']='business_inbox' if PREF.match(r['email'].split('@')[0]) else 'published_professional_contact'
  r['additional_public_emails']=[{'email':e,'source_url':s} for e,s in good[1:5] if e!=r['email']]
 else:r['email_status']='website_inaccessible_contact_not_verified' if not pages and errors else 'not_found_on_accessible_business_pages'
 r['checked_business_pages']=pages;r['enrichment_errors']=errors[:4];r['enrichment_checked_at']=RETRIEVED
 atomic_json(cache,r)
 return r

if __name__=='__main__':
 import argparse
 try:
  import fcntl
  lock=open(os.path.join(BASE,'research.lock'),'w')
  try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:raise SystemExit('Another SEC contact research process is already running.')
 except ImportError:pass
 ap=argparse.ArgumentParser();ap.add_argument('--screen-only',action='store_true');ap.add_argument('--max-workers',type=int,default=20);a=ap.parse_args()
 rows=candidates()
 if a.screen_only:raise SystemExit
 done=[];t=time.time()
 with ThreadPoolExecutor(max_workers=a.max_workers) as pool:
  fs=[pool.submit(enrich,r) for r in rows]
  for f in as_completed(fs):
   try:done.append(f.result())
   except Exception as ex:print('ERR',str(ex),flush=True)
   if len(done)%100==0:print('CONTACTS',len(done),'email',sum(bool(x['email']) for x in done),'seconds',round(time.time()-t),flush=True)
 done.sort(key=lambda x:(x['category'],x['company']))
 p=os.path.join(ROOT,'research','sec_leads.jsonl');open(p,'w').write(''.join(json.dumps(x)+'\n' for x in done))
 counts={'total':len(done),'email':sum(bool(x['email']) for x in done),'phone':sum(bool(x['phone']) for x in done),'both':sum(bool(x['email'] and x['phone']) for x in done),'categories':dict(Counter(x['category'] for x in done))}
 json.dump(counts,open(os.path.join(ROOT,'research','sec_counts.json'),'w'),indent=2);print('DONE',counts,flush=True)
