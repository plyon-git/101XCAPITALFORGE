from contact_utils import *
files=sys.argv[1:];rows=[]
for path in files:
 rows.extend(json.loads(s) for s in open(path) if s.strip())
# Exact website or canonical company dedup with field-preserving merge.
out={}
for r in rows:
 k=domain(r.get('website','')) or re.sub(r'[^a-z0-9]','',r['company'].lower())
 if k in out:
  base=out[k]
  for f in ['email','phone','website']:
   if not base.get(f) and r.get(f):base[f]=r[f];base.setdefault('field_sources',{})[f]=r.get('field_sources',{}).get(f,r['source_url'])
  base.setdefault('additional_sources',[]).append(r['source_url'])
 else:out[k]=r
print('Enrichment input unique',len(out),flush=True)
path='research/bulk/primary_interim_v2.jsonl'
with open(path,'w') as f,concurrent.futures.ThreadPoolExecutor(max_workers=24) as ex:
 for i,future in enumerate(concurrent.futures.as_completed([ex.submit(enrich,r) for r in out.values()])):
  r=future.result()
  if r.get('source_name') in ['HardMoneyHome','PrivateLenderLink']:
   r['institutional_vs_broker']='private_nonbank_lender_directory_claim';r['nonbank_status']='directory_claim_not_independently_verified'
  f.write(json.dumps(r)+'\n');f.flush()
  if i%100==0:print('Enriched progress',i,flush=True)
print('Enrichment saved',path,flush=True)

with open('research/bulk_primary_COMPLETE.jsonl','w') as final_f:
 for r in out.values():final_f.write(json.dumps(r)+'\n')
print('PRIMARY FINAL',len(out),'phone',sum(bool(r.get('phone')) for r in out.values()),'email',sum(bool(r.get('email')) for r in out.values()),'complete',sum(bool(r.get('phone') and r.get('email')) for r in out.values()),flush=True)
