import fcntl,contextlib,threading,subprocess,urllib.request,urllib.parse,re,json,html,os,gzip,hashlib,concurrent.futures,time,datetime,sys,collections
RAW='research/bulk/raw';os.makedirs(RAW,exist_ok=True)
def domain(url):
 try:return urllib.parse.urlparse(url).hostname.lower().removeprefix('www.')
 except Exception:return ''
UNRELATED_EMAIL_DOMAINS={'zapier.com','robot.zapier.com','privatelendersdirectory.com','hardmoneyhome.com','privatelenderlink.com','lenderlink.com','example.com','sentry.io','wixpress.com'}
RECIPIENT_ROLE_MISMATCH=re.compile(r'^(?:hr|careers?|jobs?|recruiting|webmaster|privacy|legal|abuse|security|compliance|copyright|dpo|press|media|noreply|no-reply)@',re.I)
FETCH_STATUS={}
@contextlib.contextmanager
def host_slot(u):
 host=domain(u);root='/tmp/101xvc-host-limit';os.makedirs(root,exist_ok=True);key=hashlib.sha256(host.encode()).hexdigest()
 handles=[];selected=None
 try:
  handles=[open(f'{root}/{key}_slot{i}','a+') for i in range(3)]
  while selected is None:
   for f in handles:
    try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);selected=f;break
    except BlockingIOError:pass
   if selected is None:time.sleep(.05)
  yield
 finally:
  if selected:fcntl.flock(selected,fcntl.LOCK_UN)
  for f in handles:f.close()
def fetch(u):
 p=f'{RAW}/{hashlib.sha256(u.encode()).hexdigest()}.html.gz';meta=p+'.meta.json'
 if os.path.exists(p):
  try:
   with gzip.open(p,'rt') as f:t=f.read()
   final=json.load(open(meta)).get('final_url',u) if os.path.exists(meta) else u
   FETCH_STATUS[u]=200;return t,final
  except Exception:pass
 try:
  with host_slot(u):
   r=subprocess.run(['curl','--silent','--show-error','--fail','--location','--max-time','12','--connect-timeout','6','--max-redirs','5','--max-filesize','2500000','--user-agent','Mozilla/5.0','--write-out','\n__FETCH_META__%{url_effective}\t%{http_code}',u],capture_output=True,timeout=14)
  raw=r.stdout.decode(errors='replace');out,marker,tail=raw.rpartition('\n__FETCH_META__')
  final,sep,code=tail.rpartition('\t');status=int(code) if code.isdigit() else 0;FETCH_STATUS[u]=status or 'network_error'
  if r.returncode or not marker:return '',u
  tmp=p+f'.{os.getpid()}.{threading.get_ident()}.tmp'
  with gzip.open(tmp,'wt') as f:f.write(out)
  os.replace(tmp,p)
  json.dump({'url':u,'final_url':final,'http_status':status},open(meta,'w'))
  return out,final
 except Exception:FETCH_STATUS[u]='network_error';return '',u
def emails(t):
 visible=re.sub(r'<(script|style)\b.*?</\1>','',t,flags=re.S|re.I)
 visible=re.sub(r'<[^>]+>',' ',visible)
 visible=re.sub(r'\s*(?:\[at\]|\(at\))\s*','@',visible,flags=re.I)
 visible=re.sub(r'\s*(?:\[dot\]|\(dot\))\s*','.',visible,flags=re.I)
 vals=re.findall(r'[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}',html.unescape(visible))
 vals.extend(urllib.parse.unquote(e).split('?')[0] for e in re.findall(r'href=[\"\x27]mailto:([^\"\x27]+)',t,re.I))
 for enc in re.findall(r'data-cfemail=[\"\x27]([a-f0-9]+)',t,re.I):
  try:
   b=bytes.fromhex(enc);vals.append(''.join(chr(v^b[0]) for v in b[1:]))
  except Exception:pass
 for raw in re.findall(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>',t,re.S|re.I):
  vals.extend(re.findall(r'"email"\s*:\s*"([^" ]+@[^" ]+)"',raw))
 return sorted(set(v.strip('.').lower() for v in vals if not any(x in v.lower() for x in ('example.','yourdomain.','yoursite.','wixpress.','sentry.','@domain.','@email.','noreply','no-reply','test@','png@','jpeg@','placeholder'))))
def phones(t):
 vals=re.findall(r'href=[\"\x27]tel:([^\"\x27]+)',t,re.I)
 vals.extend(re.findall(r'"telephone"\s*:\s*"([^\"]+)"',t))
 # Formatting proves publicly visible phone, but avoid unlabeled dates/IDs and numbers with 555 exchange.
 z=html.unescape(re.sub('<[^>]+>',' ',re.sub(r'<(script|style)\b.*?</\1>','',t,flags=re.S|re.I)))
 vals.extend(re.findall(r'(?:Phone|Call|Tel|Telephone|Contact)[ :\t\n]*(\+?1?[ .-]*(?:\(\d{3}\)|\d{3})[ .-]\d{3}[ .-]\d{4})',z,re.I))
 out=[]
 for p in vals:
  digits=re.sub(r'\D','',urllib.parse.unquote(p).split(';')[0])
  if len(digits)==11 and digits.startswith('1'):digits=digits[1:]
  if len(digits)==10 and digits[3:6]!='555' and digits[:1] in '23456789' and digits[3:4] in '23456789':
   val='('+digits[:3]+') '+digits[3:6]+'-'+digits[6:]
   if val not in out:out.append(val)
 return out
def enrich(r):
 email_host=str(r.get('email','')).split('@')[-1].lower()
 if r.get('email'):
  r['email_recipient_role']='recipient_role_mismatch' if RECIPIENT_ROLE_MISMATCH.search(r['email']) else 'business_recipient_role_unverified'
 if any(email_host==bad or email_host.endswith('.'+bad) for bad in UNRELATED_EMAIL_DOMAINS):
  r['automation_contact_route']=r.get('email');r['email']='';r['email_status']='not_found';r.setdefault('field_sources',{}).pop('email',None)
 if r.get('email') and r.get('phone'):return r
 u=r.get('website','')
 if not u:return r
 if not u.startswith(('https://','http://')):u='https://'+u
 if not domain(u):return r
 if u.startswith('http://'):u='https://'+u[7:]
 if any(x in domain(u) for x in ('facebook.com','linkedin.com','twitter.com','privatelenderlink.com','hardmoneyhome.com','privatelendersdirectory.com')):return r
 t,final=fetch(u)
 if not t and u.startswith('https://') and FETCH_STATUS.get(u) in ['network_error',0,None]:t,final=fetch('http://'+u[8:])
 if not t:return r
 if not re.search(r'\b(?:lending|lender|mortgage|financing|funding|finance|capital|loan|factoring|receivables|private credit)\b',t,re.I) or re.search(r'(?:domain (?:is |name )?for sale|buy this domain|this domain is parked|sedoparking)',t,re.I):
  r['website_status']='unrelated_or_parked_domain_contact_not_used';return r
 r['website_status']='public_site_retrieved';checked=[final]
 def apply_page(src,x):
  vals=[e for e in emails(x) if re.fullmatch(r'[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}',e) and not any(e.split('@')[-1]==bad or e.split('@')[-1].endswith('.'+bad) for bad in UNRELATED_EMAIL_DOMAINS)]
  page_host=domain(final)
  own=[e for e in vals if (lambda mail_host: mail_host==page_host or page_host.endswith('.'+mail_host) or mail_host.endswith('.'+page_host))(domain('https://'+e.split('@')[-1]))]
  if not own:own=[e for e in vals if e.endswith(('@gmail.com','@yahoo.com','@aol.com','@outlook.com'))]
  own.sort(key=lambda e:(bool(RECIPIENT_ROLE_MISMATCH.search(e)),not e.startswith(('info@','contact@','loans@','lending@','funding@','hello@','sales@','invest@','investors@')),len(e)))
  if own and not r.get('email'):
   r['email_recipient_role']='recipient_role_mismatch' if RECIPIENT_ROLE_MISMATCH.search(own[0]) else 'business_recipient_role_unverified'
   r['email']=own[0];r.setdefault('field_sources',{})['email']=src;r['email_status']='publicly_listed_not_deliverability_tested';r['email_candidates']=own
  if not r.get('phone'):
   p=phones(x)
   if p:r['phone']=p[0];r.setdefault('field_sources',{})['phone']=src
 apply_page(final,t)
 if r.get('email') and r.get('phone'):
  r['contact_pages_checked']=checked;return r
 urls=[]
 for link in re.findall(r'href=[\"\x27]([^\"\x27]+)',t,re.I):
  target=urllib.parse.urljoin(final,html.unescape(link)).split('#')[0]
  if domain(target)==domain(final) and re.search(r'(?:contact|team|about)',urllib.parse.urlparse(target).path,re.I) and target not in urls and not target.endswith(('.pdf','.jpg','.png')):urls.append(target)
 urls.sort(key=lambda x:('contact' not in x.lower(),'team' not in x.lower(),len(x)))
 for target in urls[:2]:
  if r.get('email') and r.get('phone'):break
  x,f=fetch(target)
  if x:checked.append(f);apply_page(f,x)
 r['contact_pages_checked']=checked;return r
