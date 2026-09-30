#!/usr/bin/env python3
"""Public profile / official-site research with bounded requests and field provenance.

This collector never guesses an email, assesses personal wealth, tests mailboxes, sends
messages, signs in, or fetches private endpoints. Optional curl is used for absolute
DNS/redirect/read budgets. Each worker cohort writes only its own output/cache.
"""
from __future__ import annotations
import argparse
import concurrent.futures
import contextlib
import datetime
import gzip
import hashlib
import html
import json
import os
from pathlib import Path
import re
import subprocess
import threading
import time
from urllib.parse import unquote, urljoin, urlsplit

NOW=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
STATES=set("AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY PR VI GU".split())
DOMAIN_LOCK=threading.Lock()
DOMAIN_SEMAPHORES={}
DIRECTORY_HOST="privatelendersdirectory.com"
try:
    import fcntl
except ImportError:
    fcntl=None


@contextlib.contextmanager
def shared_host_slot(url):
    """Share three host slots with sibling collectors on POSIX; thread bounds elsewhere."""
    if fcntl is None:
        yield
        return
    root=Path("/tmp/101xvc-host-limit");root.mkdir(exist_ok=True)
    key=hashlib.sha256(domain(url).encode()).hexdigest()
    handles=[];selected=None
    try:
        handles=[(root/(key+"_slot"+str(index))).open("a+") for index in range(3)]
        while selected is None:
            for handle in handles:
                try:
                    fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB);selected=handle;break
                except BlockingIOError:pass
            if selected is None:time.sleep(0.05)
        yield
    finally:
        if selected:fcntl.flock(selected,fcntl.LOCK_UN)
        for handle in handles:handle.close()


def domain(url):
    try:
        host=(urlsplit(url if "://" in str(url) else "https://"+str(url)).hostname or "").lower().removeprefix("www.")
        return host
    except ValueError:
        return ""


def clean_phone(value):
    digits=re.sub(r"\D","",unquote(str(value or "")).split(";")[0])
    if len(digits)==11 and digits.startswith("1"): digits=digits[1:]
    if len(digits)!=10 or digits[0] not in "23456789" or digits[3] not in "23456789" or digits[3:6]=="555": return ""
    return "+1 "+digits[:3]+"-"+digits[3:6]+"-"+digits[6:]


def plain(markup):
    markup=re.sub(r"<(script|style)\b.*?</\1>"," ",markup,flags=re.I|re.S)
    return re.sub(r"\s+"," ",html.unescape(re.sub(r"<[^>]+>"," ",markup))).strip()


def attributes(markup):
    return {k.lower():html.unescape(v or single) for k,v,single in re.findall(r"([\w-]+)\s*=\s*(?:\"([^\"]*)\"|'([^']*)')",markup)}


def publicly_listed_emails(markup):
    visible=re.sub(r"<(script|style)\b.*?</\1>","",markup,flags=re.I|re.S)
    visible=html.unescape(visible)
    vals=re.findall(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}",visible)
    for encoded in re.findall(r"data-cfemail=[\"']([a-f0-9]+)",markup,re.I):
        try:
            data=bytes.fromhex(encoded);vals.append("".join(chr(c^data[0]) for c in data[1:]))
        except (ValueError,IndexError): pass
    for block in re.findall(r"<script[^>]*application/ld\+json[^>]*>(.*?)</script>",markup,re.I|re.S):
        vals.extend(re.findall(r'"email"\s*:\s*"([^\s\"]+@[^\s\"]+)"',block))
    excluded=("example.","yourdomain.","yoursite.","wixpress.","sentry.","@domain.","@email.","noreply","no-reply","test@","placeholder")
    return sorted({v.strip(".,;").lower() for v in vals if not any(s in v.lower() for s in excluded) and not v.lower().endswith((".png",".jpg",".jpeg",".webp",".svg",".gif"))})


def public_phones(markup):
    values=re.findall(r"href=[\"']tel:([^\"']+)",markup,re.I)
    values.extend(re.findall(r'"telephone"\s*:\s*"([^\"]+)"',markup))
    values.extend(re.findall(r"(?:Phone|Call|Tel|Telephone|Contact)[ :\t\n]*(\+?1?[ .-]*(?:\(\d{3}\)|\d{3})[ .-]\d{3}[ .-]\d{4})",plain(markup),re.I))
    return list(dict.fromkeys(v for raw in values if (v:=clean_phone(raw))))


class Collector:
    def __init__(self,cache,shared_cache=None):
        self.cache=Path(cache);self.cache.mkdir(parents=True,exist_ok=True)
        self.shared_cache=Path(shared_cache) if shared_cache else None
        self.fetch_count=0;self.failure_count=0;self.lock=threading.Lock()

    def fetch(self,url):
        if not str(url).startswith(("https://","http://")): return "",url
        host=domain(url)
        if not host or host in ("localhost","127.0.0.1","::1") or re.match(r"^(?:10\.|192\.168\.|172\.(?:1[6-9]|2\d|3[01])\.)",host): return "",url
        key=hashlib.sha256(url.encode()).hexdigest()+".html.gz"
        paths=[self.cache/key]
        if self.shared_cache:paths.append(self.shared_cache/key)
        for path in paths:
            if path.is_file():
                try:
                    final_url=url
                    metadata=Path(str(path)+".meta.json")
                    if metadata.is_file():
                        final_url=json.loads(metadata.read_text(encoding="utf-8")).get("final_url",url)
                    with gzip.open(path,"rt",encoding="utf-8") as handle:return handle.read(),final_url
                except (OSError,UnicodeError):pass
        with DOMAIN_LOCK:
            # The cross-process directory lock already enforces three requests.
            # Let all workers contend fairly instead of starving this cohort
            # behind a second local two-request waiting queue.
            local_slots=64 if host==DIRECTORY_HOST and fcntl is not None else 2
            semaphore=DOMAIN_SEMAPHORES.setdefault(host,threading.BoundedSemaphore(local_slots))
        with semaphore:
            try:
                with shared_host_slot(url):
                    result=subprocess.run(["curl","--silent","--show-error","--fail","--location","--max-time","12","--connect-timeout","5","--max-redirs","4","--max-filesize","2000000","--proto","=http,https","--proto-redir","=http,https","--user-agent","Mozilla/5.0 (CapitalForge public-business-contact-research)","--write-out","\n__FINAL_URL__%{url_effective}",url],capture_output=True,timeout=14)
                with self.lock:self.fetch_count+=1
                if result.returncode:
                    with self.lock:self.failure_count+=1
                    return "",url
                data=result.stdout.decode("utf-8",errors="replace")
                markup,marker,final=data.rpartition("\n__FINAL_URL__")
                if not marker:markup=data;final=url
                temporary=self.cache/(key+"."+str(threading.get_ident())+".tmp")
                with gzip.open(temporary,"wt",encoding="utf-8") as handle:handle.write(markup)
                temporary.replace(self.cache/key)
                metadata=self.cache/(key+".meta.json")
                metadata.write_text(json.dumps({"url":url,"final_url":final}),encoding="utf-8")
                time.sleep(0.12)
                return markup,final
            except (OSError,subprocess.TimeoutExpired):
                with self.lock:self.failure_count+=1
                return "",url

    def profile(self,candidate):
        url=candidate["profile_url"]
        markup,final=self.fetch(url)
        if not markup:return None,{"company":candidate["company"],"profile_url":url,"reason":"profile_unavailable"}
        business={}
        for block in re.findall(r"<script[^>]*application/ld\+json[^>]*>(.*?)</script>",markup,re.I|re.S):
            try:data=json.loads(block)
            except json.JSONDecodeError:continue
            objects=data.get("@graph",[data]) if isinstance(data,dict) else data if isinstance(data,list) else []
            for obj in objects:
                if isinstance(obj,dict) and obj.get("@type") in ("LocalBusiness","FinancialService"):
                    business=obj;break
            if business:break
        if not business:return None,{"company":candidate["company"],"profile_url":url,"reason":"no_member_structured_data"}
        address=business.get("address") or {}
        if isinstance(address,str):address={"unparsed":address}
        country=address.get("addressCountry","")
        if isinstance(country,dict):country=country.get("name","")
        if country and str(country).upper() not in ("US","USA","UNITED STATES","UNITED STATES OF AMERICA"):
            return None,{"company":candidate["company"],"profile_url":url,"reason":"non_US_profile","country":country}
        name=str(business.get("name") or candidate["company"]).strip()
        description=html.unescape(str(business.get("description") or ""))
        if re.search(r"\b(?:real estate agent|real estate agency|real estate brokerage|sell.side|buy.side|accounting|insurance agency|law firm|tax preparation|credit repair|payday|auto loan)\b",description,re.I) and not re.search(r"\b(?:direct lender|private lender|business financing|business funding|working capital)\b",description,re.I):
            return None,{"company":name,"profile_url":url,"reason":"service_provider_or_unrelated_credit"}
        website=""
        for raw in re.findall(r"<a\b([^>]+)>",markup,re.I|re.S):
            attr=attributes(raw)
            if "weblink" in attr.get("class","").split():website=attr.get("href","");break
        if not website:
            same_as=business.get("sameAs",[])
            if isinstance(same_as,str):same_as=[same_as]
            for candidate_site in same_as:
                host=domain(candidate_site)
                if str(candidate_site).startswith(("http://","https://")) and host and host!=DIRECTORY_HOST and not any(host==excluded or host.endswith("."+excluded) for excluded in ("facebook.com","linkedin.com","twitter.com","x.com","youtube.com","instagram.com","google.com","goo.gl")):
                    website=candidate_site;break
        if website and not website.startswith(("http://","https://")):website="https://"+website
        operational=bool(re.search(r"\b(?:working capital|unsecured|factoring|receivables|purchase order|cash flow|contract financing)\b",description,re.I))
        business_category=candidate.get("listing_category")==4
        role="private_nonbank_lender_directory_claim" if re.search(r"\b(?:direct lender|private lender|private money lender|non.bank lender|hard money lender|balance.sheet lender)\b",description,re.I) else "financing_broker_or_intermediary" if re.search(r"\b(?:broker|arrange financing|lending marketplace|connecting borrowers|network of lenders)\b",description,re.I) else "nonbank_status_unconfirmed"
        if re.search(r"\b(?:bank|credit union|bancorp)\b",name,re.I) or re.search(r"\b(?:FDIC|federally insured bank)\b",description,re.I):role="traditional_bank_or_credit_union"
        phone=clean_phone(business.get("telephone"))
        email=""
        explicit_email=business.get("email","")
        if explicit_email and re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+",str(explicit_email)):email=str(explicit_email).lower()
        row={"company":name,"title":name,"contact_name":"","email":email,"phone":phone,"website":website,
            "state":str(address.get("addressRegion","")).strip(),"city":str(address.get("addressLocality","")).strip(),
            "category":"business_finance_provider" if business_category else "private_real_estate_lender",
            "institutional_vs_broker":role,"nonbank_status":"directory_claim_not_independently_verified" if role=="private_nonbank_lender_directory_claim" else role,
            "fit_status":"operations_finance_candidate_unverified" if operational else "financing_fit_unverified" if business_category else "property_collateral_required_or_likely",
            "capital_status":"unverified","capital_verification":"unverified","cash_capacity":None,
            "collateral_requirement":"Unverified; operations finance mentioned" if operational else "Unverified; property-secured lending likely" if not business_category else "Unverified",
            "source_url":url,"source_name":"PrivateLendersDirectory","retrieved_at":NOW,
            "listing_source_url":candidate.get("listing_source_url",""),"profile_address":address,
            "notes":"Public directory listing; contact ownership, lender/broker role, present operations, deployable $500K cash and unsecured/equity appetite remain unverified. "+" ".join(description.split()[:50]),
            "field_sources":{"company":url,**({"phone":url} if phone else {}),**({"email":url} if email else {}),**({"website":url} if website else {})},
            "email_status":"publicly_listed_not_deliverability_tested" if email else "not_found",
            "directory_profile_snapshot":str(self.cache/(hashlib.sha256(url.encode()).hexdigest()+".html.gz"))}
        return row if role=="traditional_bank_or_credit_union" else self.official_contacts(row),None

    def official_contacts(self,row):
        url=row.get("website","")
        if not url or not domain(url) or (row.get("email") and row.get("phone")):return row
        skip=("facebook.com","linkedin.com","twitter.com","x.com","privatelenderlink.com","hardmoneyhome.com","privatelendersdirectory.com","youtube.com","instagram.com")
        if any(domain(url)==item or domain(url).endswith("."+item) for item in skip):return row
        markup,final=self.fetch(url)
        if not markup:return row
        text=plain(markup)
        if re.search(r"(?:domain (?:is |name )?for sale|buy this domain|this domain is parked|sedoparking)",text,re.I) or not re.search(r"\b(?:lending|lender|mortgage|financing|funding|finance|capital|loan|factoring|receivables|private credit)\b",text,re.I):
            row["website_status"]="unrelated_or_parked_contact_not_used";return row
        row["website_status"]="public_site_retrieved"
        checked=[final]
        pages=[(final,markup)]
        contacts=[]
        for link in re.findall(r"href=[\"']([^\"']+)",markup,re.I):
            target=urljoin(final,html.unescape(link)).split("#")[0]
            path=urlsplit(target).path
            if domain(target)==domain(final) and re.search(r"(?:contact|about|team)",path,re.I) and target not in contacts and not path.lower().endswith((".pdf",".png",".jpg",".svg")):contacts.append(target)
        contacts.sort(key=lambda val:("contact" not in val.lower(),"team" not in val.lower(),len(val)))
        for source,page in pages:
            self.use_contact_fields(row,source,page,domain(final))
        for target in contacts[:2]:
            if row.get("email") and row.get("phone"):break
            page,source=self.fetch(target)
            if page:
                checked.append(source);self.use_contact_fields(row,source,page,domain(final))
        row["contact_pages_checked"]=checked
        return row

    def use_contact_fields(self,row,source,markup,official_domain):
        values=publicly_listed_emails(markup)
        own=[email for email in values if (email_domain:=domain("https://"+email.split("@")[-1]))==official_domain or official_domain.endswith("."+email_domain) or email_domain.endswith("."+official_domain)]
        if not own:
            own=[email for email in values if email.endswith(("@gmail.com","@outlook.com","@yahoo.com","@aol.com"))]
        own.sort(key=lambda email:(not email.startswith(("info@","contact@","loan@","loans@","lending@","funding@","hello@","sales@","investors@")),len(email)))
        if own and not row.get("email"):
            row["email"]=own[0];row["email_candidates"]=own
            row["field_sources"]["email"]=source;row["email_status"]="publicly_listed_not_deliverability_tested"
            row["email_source_snapshot"]=str(self.cache/(hashlib.sha256(source.encode()).hexdigest()+".html.gz"))
        if not row.get("phone"):
            phones=public_phones(markup)
            if phones:row["phone"]=phones[0];row["field_sources"]["phone"]=source


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates",default="research/bulk/pld_discovery.json")
    parser.add_argument("--output",default="research/pld_backend_batch.jsonl")
    parser.add_argument("--cache",default="research/pld_backend_cache")
    parser.add_argument("--shared-cache",default="research/bulk/raw")
    parser.add_argument("--mod",type=int,default=3)
    parser.add_argument("--cohort",type=int,default=2)
    parser.add_argument("--workers",type=int,default=16)
    parser.add_argument("--limit",type=int)
    parser.add_argument("--resume-from",action="append",default=[])
    args=parser.parse_args()
    candidates=json.loads(Path(args.candidates).read_text(encoding="utf-8"))
    candidates=[row for index,row in enumerate(candidates) if index%args.mod==args.cohort]
    if args.limit:candidates=candidates[:args.limit]
    output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True)
    # Resume by exact source URL; completed rows never re-fetched.
    existing_by_source={}
    for resume_path in [output,*[Path(path) for path in args.resume_from]]:
        if not resume_path.exists():continue
        for line in resume_path.read_text(encoding="utf-8").splitlines():
            try:row=json.loads(line)
            except json.JSONDecodeError:pass
            else:
                source=row.get("source_url")
                if source not in existing_by_source:existing_by_source[source]=row
                else:
                    base=existing_by_source[source]
                    for key,value in row.items():
                        if value not in (None,"",[],{}) and base.get(key) in (None,"",[],{}):base[key]=value
                    base.setdefault("field_sources",{}).update(row.get("field_sources",{}))
    existing=list(existing_by_source.values())
    done={row.get("source_url") for row in existing}
    pending=[row for row in candidates if row["profile_url"] not in done]
    collector=Collector(args.cache,args.shared_cache)
    counts={"kept":len(existing),"phone_email":sum(bool(row.get("phone") and row.get("email")) for row in existing),"excluded":0}
    print(json.dumps({"candidates":len(candidates),"pending":len(pending),"cohort":args.cohort}),flush=True)
    exclusions=output.with_suffix(".exclusions.jsonl")
    started=time.monotonic()
    completed_rows=list(existing)
    with output.open("a",encoding="utf-8") as handle,exclusions.open("a",encoding="utf-8") as rejected,concurrent.futures.ThreadPoolExecutor(max_workers=max(1,min(args.workers,32))) as executor:
        futures={executor.submit(collector.profile,row):row for row in pending}
        for index,future in enumerate(concurrent.futures.as_completed(futures)):
            try:row,reason=future.result()
            except Exception as exc:
                row=None;candidate=futures[future];reason={"company":candidate["company"],"profile_url":candidate["profile_url"],"reason":type(exc).__name__}
            if row:
                completed_rows.append(row)
                handle.write(json.dumps(row,ensure_ascii=False)+"\n");handle.flush();counts["kept"]+=1
                if row.get("phone") and row.get("email"):counts["phone_email"]+=1
            else:
                rejected.write(json.dumps(reason)+"\n");rejected.flush();counts["excluded"]+=1
            if index%25==0:
                checkpoint=output.with_suffix(".CHECKPOINT.jsonl")
                checkpoint_tmp=checkpoint.with_suffix(".jsonl.tmp")
                checkpoint_tmp.write_text("".join(json.dumps(item,ensure_ascii=False)+"\n" for item in completed_rows),encoding="utf-8")
                checkpoint_tmp.replace(checkpoint)
                print(json.dumps({"processed":index+1,"seconds":round(time.monotonic()-started),**counts,"fetches":collector.fetch_count,"failures":collector.failure_count}),flush=True)
    report={"retrieved_at":NOW,"candidate_count":len(candidates),**counts,"fetches":collector.fetch_count,"failures":collector.failure_count,"elapsed_seconds":round(time.monotonic()-started)}
    # Materialize a separate complete checkpoint rather than relying on a long-held
    # append descriptor in workspaces that synchronize files during execution.
    final=output.with_suffix(".FINAL.jsonl")
    temporary=final.with_suffix(".jsonl.tmp")
    temporary.write_text("".join(json.dumps(row,ensure_ascii=False)+"\n" for row in completed_rows),encoding="utf-8")
    temporary.replace(final)
    output.with_suffix(".audit.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report),flush=True)


if __name__=="__main__":main()
