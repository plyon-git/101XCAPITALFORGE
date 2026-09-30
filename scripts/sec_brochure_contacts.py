#!/usr/bin/env python3
"""Optional public SEC Part2A contact fallback, clearly regulatory routing.
Does not guess 1J email or claim this is a finance decision-maker.
"""
import os,sys,json,glob,re,time,subprocess,hashlib,threading
from urllib.request import Request,urlopen
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor,as_completed
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE=os.path.join(ROOT,'research','sec','brochures');os.makedirs(BASE,exist_ok=True)
LOCKS={};MUTEX=threading.Lock();LAST_REQUEST={}
EMA=re.compile(r'\b([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,20})\b')
TLD_PATH=os.path.join(ROOT,'research','sec','iana_tlds.txt')
TLDS={x.strip().lower() for x in open(TLD_PATH) if not x.startswith('#')} if os.path.exists(TLD_PATH) else {'com','org','net','us','io','co','ai','capital','fund','group','finance','xyz'}
def normalize_email(e):
 local,host=e.lower().rsplit('@',1);parts=host.split('.')
 while len(parts)>2 and parts[-1] not in TLDS:parts.pop()
 return local+'@'+'.'.join(parts) if len(parts)>=2 and parts[-1] in TLDS else ''
BAD=re.compile(r'^(?:privacy|dpo|careers|jobs|recruiting|noreply|no-reply|abuse|press|media|webmaster|example|user|yourname|email)@',re.I)
def get(url,limit=8000000):
 host=urlparse(url).hostname
 with MUTEX:lock=LOCKS.setdefault(host,threading.Lock())
 with lock:
  delay=.75-(time.monotonic()-LAST_REQUEST.get(host,0))
  if delay>0:time.sleep(delay)
  LAST_REQUEST[host]=time.monotonic()
  headers={'User-Agent':'Mozilla/5.0'}
  if host=='api.adviserinfo.sec.gov':headers['Origin']='https://adviserinfo.sec.gov'
  args=['curl','-L','--silent','--show-error','--compressed','--max-time','8','--connect-timeout','3','--max-filesize',str(limit),'-A','Mozilla/5.0','-w','\n__SEC_BROCHURE_META__%{http_code}']
  for k,v in headers.items():
   if k!='User-Agent':args += ['-H',k+': '+v]
  args.append(url)
  x=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=9)
  if x.returncode:raise RuntimeError('curl '+str(x.returncode)+': '+x.stderr.decode(errors='replace')[:180])
  b,_,status=x.stdout.rpartition(b'\n__SEC_BROCHURE_META__')
  if int(status)>=400:raise RuntimeError('HTTP '+status.decode()+' for '+url)
  return b

def run(r):
 crd=r['sec_crd'];cache=os.path.join(BASE,crd+'.json')
 if os.path.exists(cache):return json.load(open(cache))
 website_cache=os.path.join(ROOT,'research','sec','contacts',crd+'.json')
 if os.path.exists(website_cache):
  try:
   if json.load(open(website_cache)).get('email'):return {'sec_crd':crd,'company':r['company'],'brochure_email':'','status':'website_email_available_brochure_not_requested'}
  except:pass
 out={'sec_crd':crd,'company':r['company'],'brochure_email':'','brochure_source_url':'','brochure_contact_role':'','brochure_date':'','brochure_email_source_excerpt':'','source_type':'SEC public Form ADV Part2A brochure','retrieved_at':'2026-09-30'}
 try:
  u='https://api.adviserinfo.sec.gov/search/firm/'+crd+'?hl=true&nrows=12&query=smith&r=25&sort=score+desc&wt=json'
  x=json.loads(get(u,500000));j=json.loads(x['hits']['hits'][0]['_source']['iacontent']);out['profile_source_url']=u
  docs=j.get('brochures',{}).get('brochuredetails',[])
  if not docs:out['status']='no_public_brochure';return out
  doc=docs[0];out['brochure_date']=doc.get('dateSubmitted','');out['brochure_name']=doc.get('brochureName','')
  u='https://files.adviserinfo.sec.gov/IAPD/Content/Common/crd_iapd_Brochure.aspx?BRCHR_VRSN_ID='+str(doc['brochureVersionID'])
  out['brochure_source_url']=u
  p=os.path.join(BASE,crd+'.pdf');open(p,'wb').write(get(u))
  t=os.path.join(BASE,crd+'.txt');subprocess.run(['pdftotext','-f','1','-l','3','-layout',p,t],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  s=open(t,errors='replace').read();out['brochure_source_url']=u
  # The document cover's contact email is a publicly supplied professional contact.
  # Do not extract other firms/auditors/vendors from the back of the brochure.
  em=[]
  for m in EMA.finditer(s):
   e=normalize_email(m.group(1).strip('.,'))
   if not e:continue
   domain=e.split('@')[1]
   if BAD.match(e) or domain in ['sec.gov','finra.org','example.com']:continue
   if e not in [a[0] for a in em]:em.append((e,m.start()))
  if em:
   e,pos=em[0];out['brochure_email']=e;out['brochure_email_source_excerpt']=' '.join(re.sub(r'\s+',' ',s[max(0,pos-80):pos+len(e)+80]).strip().split()[:25])
   out['brochure_contact_role']='Compliance/regulatory contact' if re.search(r'compliance|\bcco\b',e,re.I) or re.search('compliance officer',out['brochure_email_source_excerpt'],re.I) else 'Published adviser brochure professional contact'
   out['status']='publicly_published_not_delivery_tested'
  else:out['status']='no_email_in_first_3_public_brochure_pages'
 except Exception as ex:out['status']='brochure_inaccessible';out['error']=type(ex).__name__+': '+str(ex)[:200]
 finally:
  tmp=cache+'.tmp';json.dump(out,open(tmp,'w'));os.replace(tmp,cache)
 return out

if __name__=='__main__':
 import argparse
 ap=argparse.ArgumentParser();ap.add_argument('--limit',type=int,default=100);ap.add_argument('--all-categories',action='store_true');ap.add_argument('--parity',choices=['all','odd','even'],default='all');ap.add_argument('--registered-only',action='store_true');a=ap.parse_args()
 rows=[json.loads(s) for s in open(os.path.join(ROOT,'research','sec_candidates.jsonl'))]
 done={}
 for p in glob.glob(os.path.join(ROOT,'research','sec','contacts','*.json')):
  try:
   r=json.load(open(p));done[r['sec_crd']]=r
  except:pass
 # Target primary RE and debt managers; ignore broad equity cohort by default.
 rows=[r for r in rows if (not a.registered_only or r['sec_status']=='APPROVED') and (a.parity=='all' or int(r['sec_crd'])%2==(1 if a.parity=='odd' else 0)) and (a.all_categories or r['category']!='equity_manager_research') and not done.get(r['sec_crd'],{}).get('email')]
 # Prioritize records that have already exhausted website contact enrichment.
 rows.sort(key=lambda r:(r['sec_crd'] not in done,r['category'],r['company']))
 rows=rows[:a.limit];out=[];start=time.time()
 with ThreadPoolExecutor(max_workers=4) as pool:
  for f in as_completed([pool.submit(run,r) for r in rows]):
   out.append(f.result())
   if len(out)%25==0:print('BROCHURES',len(out),'email',sum(bool(x['brochure_email']) for x in out),'seconds',round(time.time()-start),flush=True)
 # Preserve earlier mixed-parity pilot records alongside this worker's odd cohort.
 prior=[]
 for pp in glob.glob(os.path.join(BASE,'*.json')):
  try:prior.append(json.load(open(pp)))
  except:pass
 combined={r['sec_crd']:r for r in prior+out}
 p=os.path.join(ROOT,'research','sec_brochure_leads.jsonl');open(p,'w').write(''.join(json.dumps(r)+'\n' for r in combined.values()))
 print('DONE',len(out),'email',sum(bool(x['brochure_email']) for x in out),flush=True)
