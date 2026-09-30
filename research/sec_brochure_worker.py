#!/usr/bin/env python3
"""Extract published professional routing emails from public SEC Part 2A covers.

Owns EVEN CRDs only and separate output/cache files. Fund assets never establish
available cash. No guessed emails, outreach, or Form ADV redaction bypasses.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import signal
import subprocess
import threading
import time
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "research/sec_brochure_frontend_cache"
OUTPUT = ROOT / "research/sec_brochure_frontend.jsonl"
EMAIL = re.compile(r"\b([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,20})\b")
BAD_LOCAL = re.compile(r"^(?:privacy|dpo|careers|jobs|recruiting|noreply|no-reply|abuse|press|media|webmaster|example|user|yourname|email|support|legal|legaldepartment|legal-department|counsel|generalcounsel|hr|humanresources|human-resources)@", re.I)
BAD_DOMAINS = {"sec.gov", "finra.org", "example.com", "example.org", "microsoft.com", "adobe.com", "gmail.com", "yahoo.com", "hotmail.com", "aol.com", "outlook.com", "compliance.ai", "comply.com", "complysci.com", "riainabox.com", "complianceconsultantsinc.com", "mycomplianceoffice.com"}
UA = "Mozilla/5.0 (compatible; CapitalForgeResearch/1.0; 101XVC public adviser contact review)"
TLDS = {"com", "org", "net", "edu", "gov", "us", "io", "co", "ai", "finance", "capital"}
REPAIR_CLIENT_COMPATIBILITY = False
STOP = threading.Event()


def utcnow():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def atomic_json(path, value):
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    temp.replace(path)


def short_excerpt(text, email, maximum=25):
    words = text.split()
    if len(words) <= maximum:
        return text
    position = next((index for index, word in enumerate(words) if email.lower() in word.lower()), min(12, len(words) - 1))
    begin = max(0, min(position - 12, len(words) - maximum))
    return " ".join(words[begin:begin + maximum])


def classify_export(row):
    """Keep source evidence but separate contacts unsuitable for a funding route."""
    email = row.get("brochure_email", "")
    original = row.get("brochure_email_source_excerpt", "")
    if len(original.split()) > 25:
        row = dict(row)
        row["brochure_email_source_excerpt"] = short_excerpt(original, email or row.get("excluded_published_email", ""))
    if not email:
        return row
    local = email.split("@", 1)[0].lower()
    excerpt = row.get("brochure_email_source_excerpt", "")
    role = ""
    if re.fullmatch(r"legal|legaldepartment|legal-department|counsel|generalcounsel", local):
        role = "legal_only"
    elif re.fullmatch(r"hr|humanresources|human-resources|careers|jobs|recruiting", local):
        role = "hr_only"
    elif re.fullmatch(r"privacy|dpo", local):
        role = "privacy_only"
    elif re.search(r"(?:general|legal) counsel|legal affairs|attorney", excerpt, re.I) and not re.search(r"compliance|\bcco\b|investor|investments|portfolio|business development|\bCEO\b|\bCOO\b|\bCFO\b", excerpt, re.I):
        role = "legal_only"
    if not role:
        return row
    result = dict(row)
    result.update(excluded_published_email=email, excluded_email_role=role, email="", brochure_email="", email_contact_type=role, email_status="excluded_" + role, brochure_status="excluded_" + role)
    return result


class RateLimiter:
    """One rate across API and PDF hosts, not a separate allowance per host."""
    def __init__(self, rate):
        self.interval = 1.0 / rate
        self.lock = threading.Lock()
        self.last = 0.0

    def wait(self):
        with self.lock:
            delay = self.interval - (time.monotonic() - self.last)
            if delay > 0:
                time.sleep(delay)
            self.last = time.monotonic()


def download(url, destination, limiter):
    limiter.wait()
    host = urlsplit(url).hostname
    # This public classic PDF endpoint rejects the identified research UA with
    # a 404; a known public brochure accepts the exact plain browser UA.
    user_agent = "Mozilla/5.0" if host == "files.adviserinfo.sec.gov" else UA
    command = ["curl", "--silent", "--show-error", "--fail", "--location", "--max-time", "8", "--connect-timeout", "3", "--max-filesize", "12000000", "--user-agent", user_agent]
    if urlsplit(url).hostname == "api.adviserinfo.sec.gov":
        command += ["--header", "Origin: https://adviserinfo.sec.gov"]
    command += ["--output", str(destination), url]
    result = subprocess.run(command, capture_output=True, text=True, timeout=12)
    if result.returncode:
        raise RuntimeError(result.stderr.strip()[:240] or f"curl exit {result.returncode}")


def domain(value):
    try:
        host = (urlsplit(value if "://" in value else "https://" + value).hostname or "").lower()
        return host.removeprefix("www.")
    except ValueError:
        return ""


def select_email(text, candidate):
    """Prefer exact firm website domains; never accept a known regulator/vendor."""
    websites = [candidate.get("website", ""), *(candidate.get("additional_websites") or [])]
    firm_domains = {domain(value) for value in websites if value}
    choices = []
    seen = set()
    for match in EMAIL.finditer(text):
        email = match.group(1).lower().rstrip(".,")
        local, email_domain = email.split("@", 1)
        # PDF text extraction can join the next sentence directly to an email.
        # Prefer a disclosed firm domain before validating against IANA suffixes.
        for firm in sorted(firm_domains, key=len, reverse=True):
            if email_domain.startswith(firm + "."):
                email_domain = firm
                break
        while "." in email_domain and email_domain.rsplit(".", 1)[1] not in TLDS:
            email_domain = email_domain.rsplit(".", 1)[0]
        if "." not in email_domain or email_domain.rsplit(".", 1)[1] not in TLDS:
            continue
        email = local + "@" + email_domain
        if email in seen or BAD_LOCAL.match(email):
            continue
        seen.add(email)
        if email_domain in BAD_DOMAINS or any(email_domain.endswith("." + bad) for bad in BAD_DOMAINS):
            continue
        excerpt = re.sub(r"\s+", " ", text[max(0, match.start() - 160):match.end() + 180]).strip()
        same_domain = any(email_domain == firm or email_domain.endswith("." + firm) or firm.endswith("." + email_domain) for firm in firm_domains)
        local = email.split("@", 1)[0]
        compliance = bool(re.search(r"compliance|\bcco\b", local) or re.search(r"chief compliance|compliance officer", excerpt, re.I))
        # With a disclosed website, unrelated email domains require clear contact
        # context on the brochure cover. Avoid auditors and compliance vendors.
        if firm_domains and not same_domain and not compliance:
            continue
        if re.search(r"independent auditor|outside counsel|third.party provider|vendor|administrator contact", excerpt, re.I) and not same_domain:
            continue
        score = (0 if same_domain else 1, 0 if compliance else 1, match.start())
        choices.append((score, email, excerpt, compliance))
    if not choices:
        return None
    _, email, excerpt, compliance = min(choices)
    return email, excerpt, "Compliance/regulatory contact" if compliance else "Published adviser brochure professional contact"


def run(candidate, limiter):
    if STOP.is_set():
        return None
    crd = str(candidate["sec_crd"])
    cache = CACHE / f"{crd}.json"
    previous = None
    if cache.exists():
        previous = json.loads(cache.read_text())
        compatibility_failure = previous.get("brochure_source_url") and "error: 404" in previous.get("brochure_error", "") and previous.get("brochure_request_user_agent") != "Mozilla/5.0"
        if not (REPAIR_CLIENT_COMPATIBILITY and compatibility_failure):
            return classify_export(previous)
    site_cache = ROOT / f"research/sec/contacts/{crd}.json"
    if site_cache.exists():
        try:
            if json.loads(site_cache.read_text()).get("email"):
                return None
        except (ValueError, OSError):
            pass
    output = dict(candidate)
    output.update(brochure_email="", brochure_source_url="", brochure_date="", brochure_contact_role="", brochure_email_source_excerpt="", brochure_status="pending", brochure_retrieved_at=utcnow())
    output["brochure_request_user_agent"] = "Mozilla/5.0"
    if previous:
        output["brochure_previous_attempts"] = [{"status": previous.get("brochure_status"), "error": previous.get("brochure_error"), "retrieved_at": previous.get("brochure_retrieved_at"), "source_url": previous.get("brochure_source_url"), "request_user_agent": previous.get("brochure_request_user_agent", UA)}]
    try:
        profile_url = f"https://api.adviserinfo.sec.gov/search/firm/{crd}?hl=true&nrows=12&query=smith&r=25&sort=score+desc&wt=json"
        profile_path = CACHE / f"{crd}.profile.json"
        download(profile_url, profile_path, limiter)
        response = json.loads(profile_path.read_text())
        hits = response.get("hits", response.get("response", {}).get("hits", {})).get("hits", [])
        if not hits:
            output["brochure_status"] = "no_public_profile"
            return output
        content = hits[0]["_source"].get("iacontent", "{}")
        content = json.loads(content) if isinstance(content, str) else content
        documents = content.get("brochures", {}).get("brochuredetails", [])
        output["profile_api_source_url"] = profile_url
        if not documents:
            output["brochure_status"] = "no_public_brochure"
            return output
        document = documents[0]
        brochure_url = f"https://files.adviserinfo.sec.gov/IAPD/Content/Common/crd_iapd_Brochure.aspx?BRCHR_VRSN_ID={document['brochureVersionID']}"
        output.update(brochure_source_url=brochure_url, brochure_date=document.get("dateSubmitted", ""), brochure_name=document.get("brochureName", ""))
        pdf_path = CACHE / f"{crd}.pdf"
        text_path = CACHE / f"{crd}.txt"
        download(brochure_url, pdf_path, limiter)
        if not pdf_path.read_bytes().startswith(b"%PDF-"):
            raise RuntimeError("The official brochure endpoint did not return a PDF")
        subprocess.run(["pdftotext", "-f", "1", "-l", "3", "-layout", str(pdf_path), str(text_path)], check=True, capture_output=True, timeout=12)
        text = text_path.read_text(errors="replace")
        output["brochure_sha256"] = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
        selected = select_email(text, candidate)
        if not selected:
            output["brochure_status"] = "no_acceptable_email_in_first_three_pages"
            return output
        email, excerpt, role = selected
        output.update(email=email, brochure_email=email, email_source_url=brochure_url, email_status="publicly_published_not_delivery_tested", email_contact_type="regulatory_routing", brochure_contact_role=role, brochure_email_source_excerpt=excerpt, brochure_status="publicly_published_not_delivery_tested", source_type="SEC Form ADV + public Part 2A brochure", liquid_cash_verified=False, minimum_cash_status="unverified")
        output["notes"] = (candidate.get("notes", "") + " Part 2A contact is professional regulatory routing, not an assumed investment decision-maker. Published fund assets are not available cash.").strip()
    except Exception as error:
        output["brochure_status"] = "brochure_inaccessible"
        output["brochure_error"] = f"{type(error).__name__}: {error}"[:300]
    finally:
        atomic_json(cache, output)
    return classify_export(output)


def save(rows):
    merged = {}
    for path in CACHE.glob("*.json"):
        if path.name.endswith(".profile.json"):
            continue
        try:
            row = json.loads(path.read_text())
            merged[str(row["sec_crd"])] = classify_export(row)
        except (OSError, ValueError, KeyError):
            pass
    merged.update({str(row["sec_crd"]): classify_export(row) for row in rows})
    temp = OUTPUT.with_suffix(".jsonl.tmp")
    with temp.open("w", encoding="utf-8") as stream:
        for row in sorted(merged.values(), key=lambda row: int(row["sec_crd"])):
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    temp.replace(OUTPUT)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=50, help="0 means all eligible even CRDs")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--rate", type=float, default=1.0, help="Combined SEC API/PDF requests per second; coordinate other workers")
    parser.add_argument("--retry-client-compatibility", action="store_true", help="Retry only this worker's old custom-UA 404s after a verified client-compatibility fix")
    args = parser.parse_args()
    signal.signal(signal.SIGTERM, lambda *_: STOP.set())
    signal.signal(signal.SIGINT, lambda *_: STOP.set())
    if not 0 < args.rate <= 2:
        parser.error("Use a rate greater than zero and no more than two")
    if not shutil.which("curl") or not shutil.which("pdftotext"):
        parser.error("curl and pdftotext are required")
    CACHE.mkdir(exist_ok=True)
    global REPAIR_CLIENT_COMPATIBILITY
    REPAIR_CLIENT_COMPATIBILITY = args.retry_client_compatibility
    limiter = RateLimiter(args.rate)
    tld_path = CACHE / "iana-tlds.txt"
    if not tld_path.exists():
        download("https://data.iana.org/TLD/tlds-alpha-by-domain.txt", tld_path, limiter)
    global TLDS
    TLDS = {line.strip().lower() for line in tld_path.read_text().splitlines() if line.strip() and not line.startswith("#")}
    candidates = [json.loads(line) for line in (ROOT / "research/sec_candidates.jsonl").read_text().splitlines() if line.strip()]
    selected = []
    completed_sites = set()
    for row in candidates:
        crd = str(row["sec_crd"])
        if int(crd) % 2 or (ROOT / f"research/sec/brochures/{crd}.json").exists():
            continue
        site = ROOT / f"research/sec/contacts/{crd}.json"
        if site.exists():
            completed_sites.add(crd)
            try:
                if json.loads(site.read_text()).get("email"):
                    continue
            except (ValueError, OSError):
                pass
        selected.append(row)
    priority = {"real_estate_fund_manager": 0, "private_credit_manager_research": 1, "equity_manager_research": 2}
    selected.sort(key=lambda row: (str(row["sec_crd"]) not in completed_sites, priority.get(row.get("category"), 3), row["company"]))
    if args.limit:
        selected = selected[:args.limit]
    results = []
    start = time.monotonic()
    print(f"EVEN BROCHURE COHORT {len(selected)}; global rate {args.rate}/sec", flush=True)
    with ThreadPoolExecutor(max_workers=max(1, min(args.workers, 8))) as pool:
        for index, future in enumerate(as_completed([pool.submit(run, row, limiter) for row in selected]), 1):
            result = future.result()
            if result is not None:
                results.append(result)
            if index % 25 == 0 or index == len(selected):
                save(results)
                print(f"BROCHURES {index}/{len(selected)}; published emails {sum(bool(row.get('brochure_email')) for row in results)}; elapsed {round(time.monotonic()-start)}s", flush=True)
    save(results)
    manifest = {"cohort_scheduled": len(selected), "attempted": len(results), "records": len(results), "published_emails": sum(bool(row.get("brochure_email")) for row in results), "global_requests_per_second": args.rate, "cohort": "even CRDs excluding shared pilot and completed website email", "interrupted": STOP.is_set(), "completed_at": utcnow(), "all_cash_capacity_unverified": True}
    atomic_json(ROOT / "research/sec_brochure_frontend_manifest.json", manifest)
    print(json.dumps(manifest), flush=True)


if __name__ == "__main__":
    main()
