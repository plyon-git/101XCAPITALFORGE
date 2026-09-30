#!/usr/bin/env python3
"""Merge sourced business leads without guessing missing contacts or capital."""
import argparse
import collections
import csv
import datetime
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

BAD_DOMAINS = {'example.com','example.org','sentry.io','wixpress.com','wordpress.org','schema.org',
               'zapier.com','zapiermail.com','sendgrid.net','mailgun.net','mailgun.org','formspree.io',
               'privatelenderlink.com','hardmoneyhome.com','privatelendersdirectory.com'}
SHARED_DOMAINS = {'linkedin.com','facebook.com','instagram.com','twitter.com','x.com','sites.google.com','youtube.com','line.me','vimeo.com'}
UNSUITABLE_MAILBOX = re.compile(r'^(?:hr|careers?|jobs?|recruit(?:ing|ment)?|webmaster|privacy|legal|press|media)(?:[._-].*)?$',re.I)

def text(value):
    return '' if value is None else str(value).strip()

def name_key(s):
    s = re.sub(r'\b(llc|llp|lp|inc|incorporated|limited|ltd|corp|corporation)\b', '', s.lower())
    return re.sub(r'[^a-z0-9]', '', s)

def emails(s):
    return list(dict.fromkeys(m.lower() for m in re.findall(r'[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}',text(s),re.I)
                             if not any(m.split('@')[-1].lower()==d or m.split('@')[-1].lower().endswith('.'+d) for d in BAD_DOMAINS)
                             and not re.match(r'(?:no[._-]?reply|donotreply)@',m,re.I)))

def routing_email(mail):
    return not UNSUITABLE_MAILBOX.fullmatch(mail.split('@')[0])

def phones(s):
    candidates = re.split(r'[;|\n]', text(s))
    result=[]
    for phone in candidates:
        phone=re.split(r'\s*(?:ext(?:ension)?|[x#])\.?\s*\d+',phone,maxsplit=1,flags=re.I)[0]
        digits = re.sub(r'\D', '', phone)
        if len(digits) in (10,11) and (len(digits)==10 or digits[0]=='1'):
            canonical='+1'+digits[-10:]
            if canonical not in result:
                result.append(canonical)
        elif phone.strip().startswith('+') and 10<=len(digits)<=15:
            canonical='+'+digits
            if canonical not in result:result.append(canonical)
    return result

def domain(url):
    try:
        h = urlsplit(url if '://' in url else 'https://'+url).hostname or ''
        h = h.lower().removeprefix('www.')
        if any(h==s or h.endswith('.'+s) for s in SHARED_DOMAINS):
            return ''
        return h
    except ValueError:
        return ''

def normalize_url(value):
    s=text(value).split(';')[0].strip()
    if not s:
        return ''
    if '://' not in s:
        s='https://'+s
    try:
        u=urlsplit(s)
        if u.scheme.lower() not in ('http','https') or not u.hostname or any(c.isspace() for c in s):
            return ''
        return urlunsplit((u.scheme.lower(),u.netloc.lower(),u.path,u.query,u.fragment))
    except ValueError:
        return ''

def safe_cell(v):
    s=text(v)
    return "'"+s if s.lstrip().startswith(('=','+','-','@')) else s

def normalize(raw, filename):
    r=dict(raw)
    company=text(raw.get('company') or raw.get('name') or raw.get('firm_name'))
    if not company:
        return None
    r['company']=company
    r['contact_name']=text(raw.get('contact_name') or (raw.get('name') if raw.get('company') else ''))
    published_mail=emails(raw.get('email') or raw.get('emails'))
    mail=[m for m in published_mail if routing_email(m)]
    tel=phones(raw.get('phone') or raw.get('phones'))
    r['email']=mail[0] if mail else ''
    r['phone']=tel[0] if tel else ''
    r['emails']=mail
    r['phones']=tel
    r['original_email']=text(raw.get('email'))
    all_candidates=re.findall(r'[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}',text(raw.get('email')),re.I)
    rejected=[m for m in all_candidates if m.lower() not in mail]
    if rejected:r['rejected_email_candidates']=rejected
    role_rejected=[m for m in published_mail if not routing_email(m)]
    if role_rejected:
        r['recipient_role_mismatch_emails']=role_rejected
        r['recipient_role_note']='HR, employment, webmaster, privacy, legal or press-only inbox is not a financing inquiry contact.'
    r['original_phone']=text(raw.get('phone'))
    r['source_dataset']=filename
    r['original_website']=text(raw.get('website'))
    candidates=[raw.get('website')]+(raw.get('additional_websites') if isinstance(raw.get('additional_websites'),list) else [])
    valid_websites=[normalize_url(v) for v in candidates if normalize_url(v)]
    r['website']=next((v for v in valid_websites if domain(v)),valid_websites[0] if valid_websites else '')
    address=raw.get('profile_address')
    if isinstance(address,dict):
        r['directory_reported_state']=raw.get('state')
        r['state']=text(address.get('addressRegion'))
        r['city']=text(address.get('addressLocality')) or text(raw.get('city'))
        r['profile_address']={k:address[k] for k in ('addressLocality','addressRegion','addressCountry') if address.get(k)}
    sources=raw.get('evidence_urls',[])
    if not isinstance(sources,list):
        sources=[]
    sources += re.findall(r'https?://[^\s;]+',text(raw.get('source_url')))
    for field in ('phone_source_url','email_source_url','fund_source_url','contact_name_source'):
        sources += re.findall(r'https?://[^\s;]+',text(raw.get(field)))
    for value in raw.get('field_sources',{}).values() if isinstance(raw.get('field_sources'),dict) else []:
        sources += re.findall(r'https?://[^\s;]+',text(value))
    if isinstance(raw.get('field_sources'),dict):
        for field in ('email','phone'):
            if not r.get(field+'_source_url') and raw['field_sources'].get(field):
                r[field+'_source_url']=raw['field_sources'][field]
    evidence=raw.get('evidence',[])
    if not isinstance(evidence,list):
        evidence=[evidence]
    for e in evidence:
        if isinstance(e,dict) and e.get('url'):
            sources.append(e['url'])
    sources=list(dict.fromkeys(sources))
    r['source_url']=sources[0] if sources else ''
    r['source_urls']=sources
    r['evidence']=evidence
    r['source_name']=text(raw.get('source_name') or raw.get('source_type'))
    r['retrieved_at']=text(raw.get('retrieved_at'))
    r['capital_status']=text(raw.get('capital_status') or raw.get('capacity_status')) or 'unverified'
    r['fit_status']=text(raw.get('fit_status') or raw.get('deal_fit_status') or raw.get('property_collateral_fit')) or 'research_required'
    r['category']=text(raw.get('category')) or 'research_prospect'
    r['contact_status']='public_email_and_phone' if mail and tel else 'incomplete_contact'
    r['stage']='new'
    r['do_not_contact']=False
    r['available_cash_verified']=False
    r['qualification_status']='unqualified_research'
    note_parts=[text(raw.get(k)) for k in ('fit_reason','asset_screen_description','description','notes','contact_note') if raw.get(k)]
    if raw.get('property_collateral_fit'):
        note_parts.append('Collateral assessment: '+text(raw['property_collateral_fit']))
    r['notes']='\n'.join(dict.fromkeys(note_parts))
    r['reported_private_fund_gav']=raw.get('reported_private_fund_gav') or raw.get('reported_private_fund_gross_assets_usd')
    role=text(raw.get('institutional_vs_broker') or raw.get('lender_role') or raw.get('source_role'))
    if re.search(r'\bbank\b|\bbankfinancial\b',company,re.I) or name_key(company)=='bayfirst':
        role='bank_or_bank_affiliated_financier'
    elif not role:
        role='mandate_and_direct_funding_status_unconfirmed'
    r['institutional_vs_broker']=role
    if any(s in role for s in ('traditional_bank','bank_or_bank','credit_union')) or r['category']=='conventional_bank_candidate':
        r['original_category']=r['category']
        r['category']='bank_or_bank_affiliated_finance_candidate'
    if r.get('recipient_role_note'):r['notes']+='\n'+r['recipient_role_note']
    return r

def correct_contacts(raw, corrections):
    r=dict(raw)
    key=name_key(text(r.get('company') or r.get('name') or r.get('firm_name')))
    for c in corrections:
        if name_key(c['company'])!=key:continue
        field=c['field']
        old=text(r.get(field))
        if c.get('only_if_value') is not None:
            matches=(phones(old)==phones(c['only_if_value'])) if field=='phone' else old.lower()==c['only_if_value'].lower()
            if not matches:continue
        r.setdefault('contact_corrections',[]).append({'field':field,'original':old,'corrected':c['value'],'reason':c['reason'],'source_url':c['source_url']})
        r[field]=c['value']
        if c['value']:r[field+'_source_url']=c['source_url']
        r['notes']=(text(r.get('notes'))+'\nContact correction: '+c['reason']).strip()
    return r

def merge(a,b):
    for field in ('emails','phones','source_urls','evidence'):
        vals=a.get(field,[])+b.get(field,[])
        a[field]=list({json.dumps(v,sort_keys=True):v for v in vals}.values())
    if not a['email'] and b['email']:
        a['email']=b['email']
        for field in ('email_source_url','email_status','email_contact_type','contact_role','brochure_source_url','brochure_contact_role','brochure_date','brochure_email_source_excerpt'):
            if b.get(field):a[field]=b[field]
    a['phone']=a['phone'] or b['phone']
    a['website']=a['website'] or b['website']
    a['contact_name']=a['contact_name'] or b['contact_name']
    a['source_datasets']=list(dict.fromkeys(a.get('source_datasets',[a['source_dataset']])+[b['source_dataset']]))
    a['also_listed_as']=list(dict.fromkeys(a.get('also_listed_as',[])+[b['company']]))
    if b['notes'] and b['notes'] not in a['notes']:
        a['notes'] += '\n'+b['notes']
    a.setdefault('merged_source_records',[]).append(b)
    a['contact_status']='public_email_and_phone' if a['email'] and a['phone'] else 'incomplete_contact'
    return a

def priority(r):
    c=r['category'].lower();fit=r['fit_status'].lower()
    if any(x in c for x in ('unsecured','contract','working_capital','revenue')): p=80
    elif 'factor' in c or 'receiv' in c: p=65
    elif any(x in c for x in ('real_estate_fund','private_credit','credit_manager')): p=50
    elif any(x in c for x in ('equity','sbic')): p=40
    else: p=20
    if any(x in fit for x in ('mismatch','property_secured','ineligible','property_collateral_required','property_backed')): p=10
    return p+(10 if r['email'] and r['phone'] else 0)

def crm_record(r):
    category=r['category'].lower()
    fit_raw=r['fit_status'].lower()
    mismatch=any(s in fit_raw for s in ('mismatch','property_secured','ineligible','property_collateral_required','property_backed')) or r['category'] in ('property_secured_lender','equipment_finance_funding_source')
    potential=any(s in category for s in ('unsecured','contract','working_capital','revenue','factor','receiv'))
    fit='poor' if mismatch else ('potential' if potential else 'unreviewed')
    excerpts=[]
    for e in r['evidence']:
        if isinstance(e,dict) and e.get('excerpt'):
            excerpts.append(text(e['excerpt']))
    tags=[r['category'],'available_cash_unverified','published_contacts_not_deliverability_tested']
    if mismatch:tags.append('property_collateral_mismatch')
    tags.append(r['institutional_vs_broker'])
    if 'sbic' in category: tags.append('sbic_eligibility_review')
    if 'equity' in category or 'fund_manager' in category:tags.append('investment_mandate_review')
    metadata=r
    if len(json.dumps(metadata,ensure_ascii=False))>90000:
        metadata=dict(r)
        metadata['full_research_reference']='data/public_directory.jsonl record '+r['directory_id']
        metadata['condensed_for_crm']=True
        metadata.pop('merged_source_records',None)
        for key,value in list(metadata.items()):
            if isinstance(value,list) and len(value)>20:
                metadata[key+'_complete_count']=len(value)
                metadata[key]=value[:20]
        if len(json.dumps(metadata,ensure_ascii=False))>90000:
            metadata={k:r.get(k) for k in ('directory_id','category','contact_role','capital_status','fit_status','notes','reported_private_fund_gav','reported_fund_size','source_urls','emails','phones')}
            metadata['full_research_reference']='data/public_directory.jsonl record '+r['directory_id']
            metadata['condensed_for_crm']=True
    return {
        'company':r['company'],'name':r['contact_name'],'email':r['email'],'phone':r['phone'],
        'website':r['website'],'city':text(r.get('city')),'state':text(r.get('state')),
        'lender_type':r['category'].replace('_',' ').title(),
        'financing_types':text(r.get('investment_strategy')) or r['category'].replace('_',' '),
        'collateral_requirement':text(r.get('collateral')) or text(r.get('collateral_requirement')) or 'Not confirmed; assess property lien, UCC lien, guarantees and equity separately.',
        'min_check':r.get('loan_min'),'max_check':r.get('loan_max'),'cash_capacity':None,
        'capital_verification':'unverified','fit':fit,'fit_reason':r['notes'],
        'stage':'new','do_not_contact':False,
        'source_url':r['source_url'],'source_title':r['source_name'],
        'source_date':r['retrieved_at'],'verification_status':'source_observed',
        'evidence':'\n\n'.join(excerpts)[:20000],
        'sources':[{'url':u,'title':r['source_name'],'date':r['retrieved_at']} for u in r['source_urls']][:200],
        'tags':tags,'metadata':metadata
    }

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('inputs', nargs='+')
    p.add_argument('--out',default='data')
    p.add_argument('--exclude-file',default=str(Path(__file__).resolve().parents[1]/'data'/'research_exclusions.json'))
    p.add_argument('--correction-file',default=str(Path(__file__).resolve().parents[1]/'data'/'research_corrections.json'))
    args=p.parse_args()
    dest=Path(args.out);dest.mkdir(parents=True,exist_ok=True)
    raw_count=0; duplicate_count=0; missing_source=0; output=[]; name_index={};domain_index={};email_index={}
    excluded=[]
    exclude_path=Path(args.exclude_file)
    holds=json.loads(exclude_path.read_text()) if exclude_path.exists() else []
    hold_keys={name_key(h['company']):h for h in holds}
    correction_path=Path(args.correction_file)
    corrections=json.loads(correction_path.read_text()) if correction_path.exists() else []
    per_source={}
    for filename in args.inputs:
        path=Path(filename)
        if not path.exists():
            raise SystemExit(f'Missing input: {path}')
        rows=[json.loads(s) for s in path.read_text().split('\n') if s.strip()]
        per_source[path.name]={'source_rows':len(rows)}
        for raw in rows:
            raw_count+=1
            r=normalize(correct_contacts(raw,corrections),path.name)
            if not r:
                continue
            if name_key(r['company']) in hold_keys:
                excluded.append({'company':r['company'],'reason':hold_keys[name_key(r['company'])].get('reason'),'dataset':path.name})
                continue
            if not r['source_url']:
                missing_source+=1
                continue
            nk=name_key(r['company']); dk=domain(r['website']); ek=r['email']
            ix=name_index.get(nk)
            if ix is None and dk: ix=domain_index.get(dk)
            if ix is None and ek: ix=email_index.get(ek)
            if ix is not None:
                merge(output[ix],r); duplicate_count+=1
            else:
                ix=len(output);output.append(r)
            name_index[nk]=ix
            if dk:domain_index[dk]=ix
            if ek:email_index[ek]=ix
    # A later enrichment can connect two earlier records through a newly found
    # public email. Reconcile those connections before counting distinct firms.
    while True:
        reconciled=[]; keys={}; merged_this_pass=0
        for r in output:
            identifiers=['name:'+name_key(r['company'])]
            if domain(r['website']): identifiers.append('domain:'+domain(r['website']))
            if r['email']: identifiers.append('email:'+r['email'])
            ix=next((keys[k] for k in identifiers if k in keys),None)
            if ix is None:
                ix=len(reconciled);reconciled.append(r)
            else:
                merge(reconciled[ix],r);merged_this_pass+=1
            for k in identifiers:keys[k]=ix
        output=reconciled;duplicate_count+=merged_this_pass
        if not merged_this_pass:break
    output.sort(key=lambda r:(-priority(r),r['company'].lower()))
    for i,r in enumerate(output):
        r['directory_id']='CF-'+hashlib.sha256(name_key(r['company']).encode()).hexdigest()[:12].upper()
        r['priority_score']=priority(r)
    complete=[r for r in output if r['email'] and r['phone']]
    nonbank_complete=[r for r in complete if r['category']!='bank_or_bank_affiliated_finance_candidate']
    categories=dict(collections.Counter(r['category'] for r in output))
    roles=dict(collections.Counter(r['institutional_vs_broker'] for r in output))
    summary={'generated_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
             'total_distinct_prospects':len(output),'public_phone_and_email':len(complete),
             'public_phone_and_email_excluding_recognized_bank_candidates':len(nonbank_complete),
             'public_phone':sum(bool(r['phone']) for r in output),'public_email':sum(bool(r['email']) for r in output),
             'verified_500k_available_cash':0,'fully_qualified_for_deal':0,
             'source_rows':raw_count,'merged_duplicate_records':duplicate_count,'excluded_missing_source':missing_source,
             'excluded_irrelevant_records':len(excluded),'research_exclusions':excluded,
             'categories':categories,'source_roles':roles,'sources':per_source,
             'non_funding_mailboxes_removed':sum(bool(r.get('recipient_role_mismatch_emails')) for r in output),
             'scope':'Public-source debt and equity capital research prospects. Program capacity and reported fund assets are not available cash. Contacts are published, not email-deliverability tested. Deal fit has not been confirmed.'}
    (dest/'data_lenders.jsonl').write_text(''.join(json.dumps(crm_record(r),ensure_ascii=True)+'\n' for r in output))
    (dest/'public_directory.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=True)+'\n' for r in output))
    (dest/'directory_summary.json').write_text(json.dumps(summary,indent=2))
    fields=['directory_id','company','contact_name','contact_role','email','phone','website','state','category','institutional_vs_broker','fit_status','capital_status','priority_score','loan_min','loan_max','reported_fund_size','reported_private_fund_gav','average_investment','email_source_url','phone_source_url','source_name','source_url','retrieved_at','notes']
    operating=[r for r in output if any(x in r['category'] for x in ('unsecured','working_capital','contract','revenue','factoring','receivables','business_finance'))]
    real_estate=[r for r in output if 'real_estate_lender' in r['category'] or r['category']=='property_secured_lender']
    investors=[r for r in output if any(x in r['category'] for x in ('equity','fund_manager','private_credit_manager','sbic'))]
    cohorts=[('capital_prospects.csv',output),('contact_complete.csv',complete),('nonbank_contact_candidates.csv',nonbank_complete),
             ('operating_capital_candidates.csv',operating),('real_estate_lender_research.csv',real_estate),
             ('credit_and_equity_manager_research.csv',investors)]
    for filename,rows in cohorts:
        with (dest/filename).open('w',newline='',encoding='utf-8-sig') as f:
            w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
            for r in rows:
                record={k:safe_cell(r.get(k)) for k in fields}
                if r['phone'].startswith('+1'):
                    d=r['phone'][2:]
                    record['phone']=f'1-{d[:3]}-{d[3:6]}-{d[6:]}'
                w.writerow(record)
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
