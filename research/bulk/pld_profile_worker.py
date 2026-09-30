import os,sys,json,re,html,hashlib,concurrent.futures,datetime,collections
sys.path.insert(0,os.path.dirname(__file__))
from contact_utils import fetch,enrich,phones
NOW=datetime.datetime.now(datetime.timezone.utc).isoformat()
def attrs(t):return dict((a.lower(),html.unescape(b or c)) for a,b,c in re.findall(r'([\w-]+)\s*=\s*(?:"([^"]*)"|\x27([^\x27]*)\x27)',t))
def role_for(name,description):
 if re.search(r'\b(?:bank|bancorp|credit union)\b',name,re.I):return 'traditional_bank_or_credit_union_candidate'
 if re.search(r'\b(?:direct lender|private lender|private money lender|non.bank lender|hard money lender|balance.sheet lender|private capital investor)\b',description+' '+name,re.I):return 'private_nonbank_lender_directory_claim'
 if re.search(r'\b(?:broker|arrange financing|lending marketplace|connecting borrowers|network of lenders|advisory)\b',description,re.I):return 'financing_broker_or_intermediary'
 return 'nonbank_status_unconfirmed'
def profile(r):
 u=r['profile_url'];t,final=fetch(u);fs={}
 for raw in re.findall(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>',t,re.S|re.I):
  try:d=json.loads(raw)
  except Exception:continue
  if isinstance(d,dict):
   for obj in d.get('@graph',[d]):
    if obj.get('@type')=='LocalBusiness':fs=obj;break
  if fs:break
 if not fs:return {'company':r['company'],'profile_url':u,'error':'profile_unavailable_or_member_schema_not_found'}
 addr=fs.get('address') or {};desc=fs.get('description') or '';name=fs.get('name') or r['company']
 if addr.get('addressCountry','US') not in ('US','USA','United States','United States of America'):return {'company':name,'profile_url':u,'error':'non_US_directory_address'}
 if re.search(r'\b(?:real estate agent|real estate agency|real estate brokerage|sell.side|buy.side|accounting|insurance agency|law firm|tax preparation|credit repair)\b',desc,re.I) and not re.search(r'\b(?:direct lender|private lender|business financing|business funding|working capital)\b',desc,re.I):return {'company':name,'profile_url':u,'error':'description_indicates_non_lender_service_provider'}
 web=''
 for raw in re.findall(r'<a\b([^>]+)>',t,re.S|re.I):
  a=attrs(raw)
  if a.get('class')=='weblink':web=a.get('href','');break
 if not web:
  for candidate in fs.get('sameAs',[]):
   if isinstance(candidate,str) and candidate.startswith(('http://','https://')) and not any(x in candidate.lower() for x in ['privatelendersdirectory.com','facebook.com','linkedin.com','instagram.com','twitter.com','youtube.com']):web=candidate;break
 phone=fs.get('telephone') or ''
 if phone and len(re.sub(r'\D','',phone)) not in [10,11]:phone=''
 email=fs.get('email') or ''
 if not re.fullmatch(r'[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}',email):email=''
 role=role_for(name,desc);business=r['listing_category']==4
 operational=bool(re.search(r'\b(?:working capital|unsecured|factoring|receivables|purchase order|cash flow|contract financing)\b',desc,re.I))
 row={'title':name,'company':name,'contact_name':'','email':email,'phone':phone,'website':web,'source_url':u,'source_name':'PrivateLendersDirectory','retrieved_at':NOW,'state':addr.get('addressRegion',''),'category':'conventional_bank_candidate' if role.startswith('traditional') else 'business_finance_provider' if business else 'private_real_estate_lender','institutional_vs_broker':role,'nonbank_status':'directory_claim_not_independently_verified' if role=='private_nonbank_lender_directory_claim' else 'unconfirmed','fit_status':'operations_finance_candidate_unverified' if operational else 'property_collateral_required_or_likely' if not business else 'financing_fit_unverified','capital_status':'unverified','notes':'Public directory listing. Lender/broker role, available cash, unsecured fulfillment eligibility and equity willingness need direct confirmation. Directory description: '+' '.join(desc.split()[:20]),'field_sources':{'company':u,**({'phone':u} if phone else {}),**({'website':u} if web else {}),**({'email':u} if email else {})},'email_status':'publicly_listed_not_deliverability_tested' if email else 'not_found','profile_address':addr,'listing_source_url':r['listing_source_url'],'directory_profile_snapshot':f'bulk/raw/{hashlib.sha256(u.encode()).hexdigest()}.html.gz','source_classification_evidence':{'private_nonbank_claim':role=='private_nonbank_lender_directory_claim','operations_finance_keyword':operational,'directory_category':'business_lending' if business else 'real_estate_investment_lending'}}
 # Bank candidates are retained separately for audit and receive no private-capital outreach qualification.
 if not role.startswith('traditional'):row=enrich(row)
 return row
if __name__=='__main__':
 batch=int(sys.argv[1]);output=sys.argv[2];workers=int(sys.argv[3]) if len(sys.argv)>3 else 16
 allrows=json.load(open('research/bulk/pld_discovery.json'));rows=[r for i,r in enumerate(allrows) if i%3==batch]
 done={}
 if os.path.exists(output):
  for line in open(output):
   try:r=json.loads(line);done[r.get('source_url') or r.get('profile_url')]=r
   except Exception:pass
 pending=[r for r in rows if r['profile_url'] not in done]
 print('PLD batch',batch,'assigned',len(rows),'already done',len(done),'pending',len(pending),flush=True)
 with open(output,'a') as f,concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
  for i,future in enumerate(concurrent.futures.as_completed([ex.submit(profile,r) for r in pending])):
   try:r=future.result()
   except Exception as e:r={'error':'worker_exception','detail':str(e)[:200]}
   done[r.get('source_url') or r.get('profile_url') or f'error_{i}']=r
   f.write(json.dumps(r)+'\n');f.flush()
   if i%100==0:print('PLD batch',batch,'progress',i,'done',len(done),flush=True)
 final_output=output+'.FINAL.jsonl'
 with open(final_output,'w') as final_f:
  for r in done.values():final_f.write(json.dumps(r)+'\n')
 print('PLD batch',batch,'COMPLETE',final_output,'rows',len(done),flush=True)
