#!/usr/bin/env python3
"""CapitalForge by 101XVC: a portable, dependency-free local capital CRM."""
from __future__ import annotations

import argparse
import csv
import hashlib
import hmac
import io
import ipaddress
import json
import mimetypes
import os
import re
import secrets
import sqlite3
import socket
import sys
import threading
import time
from datetime import datetime, timezone
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

ROOT = Path(__file__).resolve().parent
STAGES = ("new", "reviewing", "qualified", "contacted", "due_diligence", "terms", "closed", "passed")
FITS = ("unreviewed", "potential", "strong", "poor")
ROLES = ("admin", "analyst", "viewer")
CAPITAL_STATUSES = ("unverified", "stated", "documented")
VERIFICATION_STATUSES = ("unverified", "source_observed", "verified")
LEAD_TEXT_FIELDS = ("company", "name", "email", "phone", "website", "city", "state", "lender_type",
    "financing_types", "collateral_requirement", "capital_verification", "fit", "fit_reason", "stage",
    "source_url", "source_title", "source_date", "verification_status", "evidence")
LEAD_NUM_FIELDS = ("min_check", "max_check", "cash_capacity")
LEAD_FIELDS = LEAD_TEXT_FIELDS + LEAD_NUM_FIELDS + ("do_not_contact", "tags", "sources", "metadata", "owner_id")
COOKIE_NAME = "capitalforge_session"
PASSWORD_ITERATIONS = 600_000
MAX_BODY = 20 * 1024 * 1024
SESSION_LIFETIME = 12 * 3600
LEGACY_DEFAULT_DEAL = {
    "title": "101XVC 500-property fulfillment financing", "raise_min": 100000, "raise_max": 500000,
    "equity_raise": 500000, "equity_percent": 9.3, "target_return_percent": 50,
    "target_months_min": 6, "target_months_max": 12, "initial_property_count": 500,
    "estimated_initial_fees": 5000000, "follow_on_estimated_fees": 115000000,
    "follow_on_trigger": "450th submission", "counterparty_description": "$2.2B company (user supplied)",
    "fulfillment_days": 60, "collateral": "Not secured against individual properties",
    "terms_status": "User-supplied proposal; counterparty size and economics not independently verified; returns are targets, not guarantees.",
    "notes": "Evaluate unsecured operating capital, receivables/contract financing and equity appetite separately. Verify cash availability of at least $500,000 through appropriate diligence."
}
PRIOR_TRIAL_DEFAULT_DEAL = {
    "mandate_version": "2026-10-02",
    "title": "101XVC 500-closed-property trial financing",
    "raise_min": 100000, "raise_max": 500000,
    "equity_raise": 500000, "equity_percent": 9.3,
    "equity_status": "Prior proposal: $500,000 for 9.3%; not confirmed as revised financing terms.",
    "target_return_percent": None, "target_months_min": None, "target_months_max": None,
    "initial_property_count": 500,
    "trial_state_allocation": "100 closed properties each in Texas, Arizona, North Carolina, Illinois and Florida",
    "estimated_initial_fees_min": 3900000, "estimated_initial_fees": 5000000,
    "estimated_initial_fees_max": 7200000,
    "projection_basis": "User estimate of trial proceeds; gross versus net basis has not been specified. Not contract face value, collected cash or established net profit.",
    "follow_on_estimated_fees": None,
    "follow_on_trigger": "Good faith discussions at the earlier of the 200th closed property or 450th qualifying submission",
    "continuation_property_count": 3000, "follow_on_property_count": 11250,
    "follow_on_remaining_property_count": 8250,
    "continuation_state_allocation": "200 closed properties each in Alabama, Arizona, Colorado, Florida, Georgia, Illinois, Indiana, Kansas, Missouri, North Carolina, Oklahoma, South Carolina, Tennessee, Texas and Utah",
    "follow_on_status": "Article 15 is non-binding except for good faith discussions. Proposed continuation and Contract 2 require definitive documents. Contract 2's proposed 11,250 closed properties include the 3,000-property continuation, leaving 8,250 thereafter.",
    "counterparty_description": "Acquisition Holdings, LLC / New Western",
    "fulfillment_days": None,
    "collateral": "Not secured against individual properties; any business-asset or fee security requires separate review",
    "terms_status": "Current $100,000-$500,000 raise; financing structure, return and timing remain to be negotiated. Trial projection is a user estimate.",
    "notes": "Use of proceeds: marketing and acquisition execution for the 500-closed-property trial. Evaluate working capital, equity and permitted fee/receivables financing separately. Confirm gross versus net projection basis, acquisition costs, closing schedule and assignment-fee cash collections before underwriting. Document capacity for the requested $100,000-$500,000 allocation."
}
CONTRACT_ECONOMICS = {
    "contract_estimated_gross_profit_threshold": 20000,
    "contract_trial_closed_properties": 500,
    "contract_assignment_share_percent": 50,
    "contract_base_gross_assignment_fees": 20000 * 500 * 50 / 100,
    "contract_source_refs": "Original Agreement sections 2.14(d), 2.23, 2.19 and 5.3; Amendment sections 1.A and 3",
    "contract_cash_collection_basis": "Actual assignment fees equal 50% of the actual Gross Transaction Spread at closing. Lower underwriting thresholds require written approval. 101XVC bears its own acquisition and operating costs; its fee is not net of Acquisition Holdings' costs."
}
DEFAULT_DEAL = {
    **PRIOR_TRIAL_DEFAULT_DEAL, **CONTRACT_ECONOMICS,
    "mandate_version": "2026-10-02-economics",
    "projection_basis": "Contract-derived underwriting base: $20,000 Estimated Gross Transaction Profit threshold x 500 closed trial properties x 50% assignment fee share = $5,000,000 gross assignment fees to 101XVC before its own acquisition and operating costs. The $3.9M-$7.2M range is a separate user sensitivity scenario, with $5M supplied average.",
    "terms_status": "Current $100,000-$500,000 raise; financing structure, return and timing remain to be negotiated. The $5M gross assignment fee underwriting base follows the contract formula; actual collections follow realized spreads at closing.",
    "notes": "Use of proceeds: marketing and acquisition execution for 500 closed trial properties. Original Agreement section 2.14(d) sets at least $20,000 Estimated Gross Transaction Profit, subject to written exceptions; section 2.23 defines the estimated disposition price minus acquisition price; section 2.19 assigns 50% of the actual Gross Transaction Spread to 101XVC. Amendment section 1.A requires 500 closed properties, with its terms controlling under section 3. The contract-derived underwriting base is $5M gross assignment fees before 101XVC's own costs under original section 5.3. Confirm acquisition costs, actual closing spreads, collection timing and eligible security when underwriting the $100,000-$500,000 allocation."
}
OPTIONAL_DEAL_NUM_FIELDS = frozenset(("target_return_percent", "target_months_min", "target_months_max",
    "fulfillment_days", "follow_on_estimated_fees", "estimated_initial_fees_min", "estimated_initial_fees_max"))
DEAL_NUM_FIELDS = frozenset(key for key, value in DEFAULT_DEAL.items()
    if isinstance(value, (float, int))) | OPTIONAL_DEAL_NUM_FIELDS


def utcnow():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def json_text(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), PASSWORD_ITERATIONS).hex()
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt}${digest}"


def password_ok(password, encoded):
    try:
        method, iterations, salt, expected = encoded.split("$")
        if method != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iterations)).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def email_normalize(value):
    return str(value or "").strip().lower()


def safe_csv_cell(value):
    value = "" if value is None else str(value)
    if value.lstrip().startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n")):
        return "'" + value
    return value


def canonical_company(value):
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def website_host(value):
    if not value:
        return ""
    url = str(value).strip()
    return (urlsplit(url if "://" in url else "https://" + url).hostname or "").lower().removeprefix("www.")


def is_named_investor(lead):
    metadata = lead.get("metadata") or {}
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except (TypeError, json.JSONDecodeError):
            return False
    return isinstance(metadata, dict) and metadata.get("record_kind") == "named_investor"


def dedup_key(lead):
    if is_named_investor(lead):
        name = str(lead.get("name") or "").strip()
        if not name:
            raise ApiError(400, "Named investor records require a contact name")
        # A shared firm inbox or mainline identifies a route, not an individual.
        person = "".join(char for char in name.casefold() if char.isalnum()) or name.casefold()
        identity = [canonical_company(lead.get("company")), person, website_host(lead.get("website"))]
        return "named_investor:" + hashlib.sha256(json_text(identity).encode()).hexdigest()
    email = email_normalize(lead.get("email"))
    if email:
        return "email:" + email
    company = canonical_company(lead.get("company"))
    name = canonical_company(lead.get("name"))
    host = website_host(lead.get("website"))
    phone = re.sub(r"\D", "", str(lead.get("phone") or ""))
    if company:
        return "company:" + company + ":" + (host or phone or name)
    if name and phone:
        return "person:" + name + ":" + phone
    return "record:" + hashlib.sha256(json_text(lead).encode()).hexdigest()


class ApiError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message


class App:
    def __init__(self, data_dir=None, allowed_hosts=None, secure_cookies=False, bootstrap_token=None, trusted_proxies=None):
        self.data_dir = Path(data_dir or ROOT / "runtime").resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.backup_dir = self.data_dir / "backups"
        self.backup_dir.mkdir(exist_ok=True, mode=0o700)
        try:
            self.data_dir.chmod(0o700)
            self.backup_dir.chmod(0o700)
        except OSError:
            pass
        self.db_path = self.data_dir / "capitalforge.sqlite3"
        self.allowed_hosts = set(allowed_hosts or ("localhost", "127.0.0.1", "::1"))
        self.secure_cookies = secure_cookies
        self.bootstrap_token = bootstrap_token
        self.trusted_proxies = set(trusted_proxies or ())
        self._dummy_password = password_hash(secrets.token_urlsafe(32))
        self.initialize()

    def db(self):
        conn = sqlite3.connect(str(self.db_path), timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def initialize(self):
        with self.db() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'analyst', active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                csrf TEXT NOT NULL, expires_at REAL NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS auth_failures (ip TEXT NOT NULL, occurred_at REAL NOT NULL);
            CREATE INDEX IF NOT EXISTS auth_failure_ip ON auth_failures(ip,occurred_at);
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY, dedup_key TEXT NOT NULL UNIQUE,
                company TEXT NOT NULL DEFAULT '', name TEXT NOT NULL DEFAULT '', email TEXT NOT NULL DEFAULT '',
                phone TEXT NOT NULL DEFAULT '', website TEXT NOT NULL DEFAULT '', city TEXT NOT NULL DEFAULT '',
                state TEXT NOT NULL DEFAULT '', lender_type TEXT NOT NULL DEFAULT '', financing_types TEXT NOT NULL DEFAULT '',
                collateral_requirement TEXT NOT NULL DEFAULT '', min_check REAL, max_check REAL, cash_capacity REAL,
                capital_verification TEXT NOT NULL DEFAULT 'unverified', fit TEXT NOT NULL DEFAULT 'unreviewed',
                fit_reason TEXT NOT NULL DEFAULT '', stage TEXT NOT NULL DEFAULT 'new', do_not_contact INTEGER NOT NULL DEFAULT 0,
                source_url TEXT NOT NULL DEFAULT '', source_title TEXT NOT NULL DEFAULT '', source_date TEXT NOT NULL DEFAULT '',
                verification_status TEXT NOT NULL DEFAULT 'unverified', evidence TEXT NOT NULL DEFAULT '',
                tags TEXT NOT NULL DEFAULT '[]', sources TEXT NOT NULL DEFAULT '[]', metadata TEXT NOT NULL DEFAULT '{}', owner_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS leads_company ON leads(company);
            CREATE INDEX IF NOT EXISTS leads_stage ON leads(stage);
            CREATE INDEX IF NOT EXISTS leads_fit ON leads(fit);
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY, lead_id INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
                body TEXT NOT NULL, author_id INTEGER REFERENCES users(id) ON DELETE SET NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY, lead_id INTEGER REFERENCES leads(id) ON DELETE CASCADE,
                title TEXT NOT NULL, due_date TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'open',
                assigned_to INTEGER REFERENCES users(id) ON DELETE SET NULL,
                created_by INTEGER REFERENCES users(id) ON DELETE SET NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS audit (
                id INTEGER PRIMARY KEY, actor_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                action TEXT NOT NULL, entity_type TEXT NOT NULL, entity_id TEXT NOT NULL DEFAULT '',
                detail TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY,value TEXT NOT NULL);
            INSERT OR IGNORE INTO settings(key,value) VALUES('schema_version','1');
            """)
            db.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('deal',?)", (json_text(DEFAULT_DEAL),))
            # Update only the exact original defaults. Any user change retains the saved mandate.
            saved_deal = json.loads(db.execute("SELECT value FROM settings WHERE key='deal'").fetchone()[0])
            if saved_deal in (LEGACY_DEFAULT_DEAL, PRIOR_TRIAL_DEFAULT_DEAL):
                db.execute("UPDATE settings SET value=? WHERE key='deal'", (json_text(DEFAULT_DEAL),))
                self.audit(db, None, "migrate", "deal", detail={"mandate_version": DEFAULT_DEAL["mandate_version"], "reason": "Unchanged prior defaults"})
            if "metadata" not in {row[1] for row in db.execute("PRAGMA table_info(leads)")}:
                db.execute("ALTER TABLE leads ADD COLUMN metadata TEXT NOT NULL DEFAULT '{}'")
        try:
            self.db_path.chmod(0o600)
        except OSError:
            pass

    def seed(self, path=None):
        path = Path(path or ROOT / "data" / "data_lenders.jsonl")
        if not path.exists():
            return {"inserted": 0, "merged": 0, "invalid": 0}
        rows, invalid = [], 0
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    invalid += 1
        with self.db() as db:
            report = self.import_rows(db, rows, None, seed=True)
        report["invalid"] += invalid
        return report

    def audit(self, db, user_id, action, entity_type, entity_id="", detail=None):
        db.execute("INSERT INTO audit(actor_id,action,entity_type,entity_id,detail,created_at) VALUES(?,?,?,?,?,?)",
            (user_id, action, entity_type, str(entity_id), json_text(detail or {}), utcnow()))

    def serialize_lead(self, row):
        data = dict(row)
        data.pop("dedup_key", None)
        data["do_not_contact"] = bool(data["do_not_contact"])
        for field in ("tags", "sources", "metadata"):
            try:
                data[field] = json.loads(data[field])
            except (TypeError, json.JSONDecodeError):
                data[field] = {} if field == "metadata" else []
        return data

    def public_user(self, row):
        return {k: row[k] for k in ("id", "name", "email", "role", "active", "created_at")}

    def validate_lead(self, payload, partial=False):
        if not isinstance(payload, dict):
            raise ApiError(400, "A JSON object is required")
        aliases = {"company_name": "company", "business_name": "company", "contact_name": "name", "contact_email": "email",
            "phone_number": "phone", "contact_phone": "phone", "source": "source_url", "capacity": "cash_capacity",
            "capital_verification_status": "capital_verification", "contact_status": "verification_status", "fit_status": "fit"}
        payload = {aliases.get(k, k): v for k, v in payload.items()}
        data = {}
        for field in LEAD_FIELDS:
            if field not in payload:
                continue
            value = payload[field]
            if field in LEAD_TEXT_FIELDS:
                if isinstance(value, list):
                    value = "; ".join(str(v) for v in value)
                data[field] = str(value or "").strip()[:20000 if field in ("evidence", "fit_reason") else 2000]
            elif field in LEAD_NUM_FIELDS:
                if value is None or value == "":
                    data[field] = None
                else:
                    try:
                        number = float(str(value).replace(",", "").replace("$", ""))
                    except (ValueError, TypeError):
                        raise ApiError(400, f"{field} must be a nonnegative number")
                    if not 0 <= number <= 1e15:
                        raise ApiError(400, f"{field} must be a nonnegative finite number")
                    data[field] = number
            elif field == "do_not_contact":
                data[field] = int(value is True or str(value).lower() in ("1", "true", "yes"))
            elif field in ("tags", "sources"):
                if isinstance(value, str):
                    try:
                        value = json.loads(value)
                    except json.JSONDecodeError:
                        value = [v.strip() for v in value.split(",") if v.strip()] if field == "tags" else [{"url": value}]
                if not isinstance(value, list) or len(value) > 200:
                    raise ApiError(400, f"{field} must be an array with no more than 200 entries")
                data[field] = json_text(value)
            elif field == "metadata":
                if isinstance(value, str):
                    try:
                        value = json.loads(value)
                    except json.JSONDecodeError:
                        raise ApiError(400, "metadata must be a JSON object")
                if not isinstance(value, dict) or len(json_text(value)) > 100000:
                    raise ApiError(400, "metadata must be an object no larger than 100,000 characters")
                data[field] = json_text(value)
            elif field == "owner_id":
                try:
                    data[field] = int(value) if value not in (None, "") else None
                except (ValueError, TypeError):
                    raise ApiError(400, "owner_id must be a user ID")
        if "email" in data:
            data["email"] = email_normalize(data["email"])
            if data["email"] and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", data["email"]):
                raise ApiError(400, "Invalid email address")
        for field, allowed in (("stage", STAGES), ("fit", FITS), ("capital_verification", CAPITAL_STATUSES), ("verification_status", VERIFICATION_STATUSES)):
            if field in data and data[field] not in allowed:
                raise ApiError(400, f"Invalid {field}; allowed: {', '.join(allowed)}")
        if not partial and not (data.get("company") or data.get("name")):
            raise ApiError(400, "Provide a company or contact name")
        extras = {k: v for k, v in payload.items() if k not in LEAD_FIELDS and k not in ("id", "created_at", "updated_at", "dedup_key")}
        if extras:
            metadata = json.loads(data.get("metadata", "{}"))
            metadata.update(extras)
            if len(json_text(metadata)) > 100000:
                raise ApiError(400, "Additional metadata exceeds 100,000 characters")
            data["metadata"] = json_text(metadata)
        for field in ("website", "source_url"):
            if data.get(field):
                raw_url = data[field]
                if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", raw_url) and not raw_url.startswith(("http://", "https://")):
                    raise ApiError(400, f"{field} must be an HTTP or HTTPS URL")
                try:
                    parsed = urlsplit(raw_url if "://" in raw_url else "https://" + raw_url)
                    valid_port = parsed.port
                except ValueError:
                    raise ApiError(400, f"{field} contains an invalid URL")
                if parsed.scheme not in ("http", "https") or not parsed.hostname or re.search(r"\s", raw_url):
                    raise ApiError(400, f"{field} must be an HTTP or HTTPS URL")
                if "://" not in data[field]:
                    data[field] = "https://" + data[field]
        return data

    def insert_lead(self, db, data):
        data = dict(data)
        now = utcnow()
        data.update(dedup_key=dedup_key(data), created_at=now, updated_at=now)
        columns = list(data)
        cur = db.execute(f"INSERT INTO leads({','.join(columns)}) VALUES({','.join('?' for _ in columns)})", list(data.values()))
        return cur.lastrowid

    def find_duplicate(self, db, data):
        key = dedup_key(data)
        row = db.execute("SELECT * FROM leads WHERE dedup_key=?", (key,)).fetchone()
        if row:
            return row
        if is_named_investor(data):
            return None
        if data.get("email"):
            for row in db.execute("SELECT * FROM leads WHERE lower(email)=?", (data["email"],)):
                if not is_named_investor(dict(row)):
                    return row
        if data.get("company") and data.get("website"):
            for row in db.execute("SELECT * FROM leads WHERE lower(company)=lower(?)", (data["company"],)):
                if not is_named_investor(dict(row)) and website_host(row["website"]) == website_host(data["website"]):
                    return row
        return None

    def import_rows(self, db, rows, user_id, seed=False):
        if not isinstance(rows, list) or len(rows) > 25000:
            raise ApiError(400, "rows must be an array containing at most 25,000 records")
        report = {"inserted": 0, "merged": 0, "invalid": 0, "errors": []}
        for index, payload in enumerate(rows):
            try:
                data = self.validate_lead(payload)
                if not seed and data.get("owner_id"):
                    if not db.execute("SELECT id FROM users WHERE id=? AND active=1", (data["owner_id"],)).fetchone():
                        raise ApiError(400, "Unknown owner")
                duplicate = self.find_duplicate(db, data)
                if duplicate:
                    updates = {}
                    # Imports never reset workflow, ownership, suppression, or verified research.
                    preserved = {"stage", "fit", "capital_verification", "verification_status", "owner_id"}
                    for field, value in data.items():
                        if field in preserved:
                            continue
                        if field == "do_not_contact":
                            if value:
                                updates[field] = 1
                        elif field in ("tags", "sources"):
                            old = json.loads(duplicate[field])
                            for item in json.loads(value):
                                if item not in old:
                                    old.append(item)
                            updates[field] = json_text(old[:200])
                        elif field == "metadata":
                            old = json.loads(duplicate[field])
                            for key, value in json.loads(value).items():
                                old.setdefault(key, value)
                            updates[field] = json_text(old)
                        elif value is not None and value != "" and duplicate[field] in (None, ""):
                            updates[field] = value
                    # Always retain new provenance even if an existing source is present.
                    if data.get("source_url") and data.get("source_url") != duplicate["source_url"]:
                        sources = json.loads(updates.get("sources", duplicate["sources"]))
                        source = {"url": data["source_url"], "title": data.get("source_title", ""), "date": data.get("source_date", "")}
                        if source not in sources:
                            sources.append(source)
                        updates["sources"] = json_text(sources[:200])
                    if updates:
                        updates["updated_at"] = utcnow()
                        db.execute(f"UPDATE leads SET {','.join(k+'=?' for k in updates)} WHERE id=?", list(updates.values()) + [duplicate["id"]])
                    report["merged"] += 1
                else:
                    self.insert_lead(db, data)
                    report["inserted"] += 1
            except (ApiError, sqlite3.IntegrityError) as exc:
                report["invalid"] += 1
                if len(report["errors"]) < 30:
                    report["errors"].append({"row": index + 1, "error": getattr(exc, "message", str(exc))})
        self.audit(db, user_id, "seed_import" if seed else "import", "leads", detail={k: v for k, v in report.items() if k != "errors"})
        return report


class Handler(BaseHTTPRequestHandler):
    server_version = "CapitalForge"
    sys_version = ""
    protocol_version = "HTTP/1.1"

    @property
    def app(self):
        return self.server.app

    def log_message(self, format, *args):
        # Do not log URLs, passwords, cookies or contact data.
        sys.stderr.write(f"[{utcnow()}] {self.command} response {args[1] if len(args)>1 else ''}\n")

    def headers_common(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if self.app.secure_cookies:
            self.send_header("Strict-Transport-Security", "max-age=31536000")

    def respond(self, status, payload=None, content_type="application/json; charset=utf-8", extra_headers=None):
        body = payload if isinstance(payload, bytes) else json_text(payload).encode("utf-8")
        self.send_response(status)
        self.headers_common()
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for key, value in (extra_headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def body(self):
        if hasattr(self,"_request_payload"):
            return self._request_payload
        if self.headers.get("Transfer-Encoding"):
            raise ApiError(400, "Transfer encoding is unsupported")
        try:
            size = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise ApiError(400, "Invalid body length")
        if size < 0 or size > MAX_BODY:
            self.close_connection = True
            raise ApiError(413, "Request exceeds 20 MB")
        raw = self.rfile.read(size)
        if size and "application/json" not in self.headers.get("Content-Type", ""):
            raise ApiError(415, "Use application/json")
        try:
            obj = json.loads(raw or b"{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise ApiError(400, "Malformed JSON")
        if not isinstance(obj, dict):
            raise ApiError(400, "A JSON object is required")
        self._request_payload = obj
        return obj

    def check_host_origin(self):
        host = self.headers.get("Host", "")
        try:
            hostname = (urlsplit("http://" + host).hostname or "").lower()
        except ValueError:
            raise ApiError(400, "Invalid Host header")
        if hostname not in self.app.allowed_hosts:
            raise ApiError(403, "Host is not permitted; configure CAPITALFORGE_ALLOWED_HOSTS")
        if self.command not in ("GET", "HEAD"):
            origin = self.headers.get("Origin")
            if origin:
                try:
                    parsed = urlsplit(origin)
                    if parsed.scheme not in ("http", "https") or parsed.netloc.lower() != host.lower():
                        raise ApiError(403, "Cross-origin writes are forbidden")
                except ValueError:
                    raise ApiError(403, "Invalid Origin header")
            if self.headers.get("Sec-Fetch-Site") == "cross-site":
                raise ApiError(403, "Cross-site writes are forbidden")

    def peer_ip(self):
        # Never trust forwarding headers for bootstrap or auth rate limits.
        return self.client_address[0]

    def current_session(self, db):
        try:
            cookies = SimpleCookie()
            cookies.load(self.headers.get("Cookie", ""))
            morsel = cookies.get(COOKIE_NAME)
            token = morsel.value if morsel else ""
        except Exception:
            token = ""
        if not token:
            return None, None
        row = db.execute("SELECT s.csrf,s.expires_at,u.* FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND u.active=1", (token_hash(token),)).fetchone()
        if not row or row["expires_at"] < time.time():
            return None, None
        return row, token

    def auth(self, db, roles=None, mutation=False):
        user, token = self.current_session(db)
        if not user:
            raise ApiError(401, "Sign in required")
        if roles and user["role"] not in roles:
            raise ApiError(403, "Your role does not permit this action")
        if mutation:
            csrf = self.headers.get("X-CSRF-Token", "")
            if not csrf or not hmac.compare_digest(csrf, user["csrf"]):
                raise ApiError(403, "A valid CSRF token is required")
        return user, token

    def session_response(self, db, user, status=200):
        raw, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        db.execute("DELETE FROM sessions WHERE expires_at<?", (time.time(),))
        db.execute("INSERT INTO sessions(token_hash,user_id,csrf,expires_at,created_at) VALUES(?,?,?,?,?)", (token_hash(raw),user["id"],csrf,time.time()+SESSION_LIFETIME,utcnow()))
        db.commit()
        cookie = f"{COOKIE_NAME}={raw}; Path=/; HttpOnly; SameSite=Strict; Max-Age={SESSION_LIFETIME}"
        if self.app.secure_cookies:
            cookie += "; Secure"
        self.respond(status, {"user": self.app.public_user(user), "csrf": csrf}, extra_headers={"Set-Cookie": cookie})

    def write_permission(self, db):
        return self.auth(db, ("admin", "analyst"), mutation=True)[0]

    def lead_filter(self, query):
        clauses, params = [], []
        q = query.get("q", [""])[0].strip()[:200]
        if q:
            clauses.append("(company LIKE ? ESCAPE '\\' OR name LIKE ? ESCAPE '\\' OR email LIKE ? ESCAPE '\\' OR phone LIKE ? ESCAPE '\\' OR state LIKE ? ESCAPE '\\' OR lender_type LIKE ? ESCAPE '\\' OR tags LIKE ? ESCAPE '\\')")
            escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            params.extend(["%" + escaped + "%"] * 7)
        for key in ("stage", "fit", "state", "capital_verification", "verification_status", "lender_type"):
            value = query.get(key, [""])[0]
            if value:
                if key == "fit" and "," in value:
                    options = value.split(",")[:4]
                    clauses.append("fit IN (" + ",".join("?" for _ in options) + ")")
                    params.extend(options)
                else:
                    clauses.append(key + "=?")
                    params.append(value)
        if query.get("do_not_contact", [""])[0] in ("0", "1", "true", "false"):
            clauses.append("do_not_contact=?")
            params.append(int(query["do_not_contact"][0] in ("1", "true")))
        if query.get("contact_complete", [""])[0] == "1":
            clauses.append("email<>'' AND phone<>''")
        if query.get("capital_min", [""])[0]:
            try:
                amount = float(query["capital_min"][0])
            except ValueError:
                raise ApiError(400, "Invalid capital_min")
            if not 0 <= amount <= 1e15:
                raise ApiError(400, "Invalid capital_min")
            clauses.append("cash_capacity>=?")
            params.append(amount)
        return (" WHERE " + " AND ".join(clauses) if clauses else ""), params

    def pagination(self, query, default=50, maximum=500):
        try:
            limit = min(maximum, max(1, int(query.get("limit", [str(default)])[0])))
            offset = max(0, int(query.get("offset", ["0"])[0]))
        except ValueError:
            raise ApiError(400, "Invalid pagination")
        return limit, offset

    def do_GET(self): self.dispatch()
    def do_HEAD(self): self.dispatch()
    def do_POST(self): self.dispatch()
    def do_PATCH(self): self.dispatch()
    def do_DELETE(self): self.dispatch()

    def dispatch(self):
        try:
            if hasattr(self,"_request_payload"):
                del self._request_payload
            self.connection.settimeout(20)
            self.check_host_origin()
            parsed = urlsplit(self.path)
            path, query = unquote(parsed.path), parse_qs(parsed.query)
            aliases = {"/api/auth/status": "/api/status", "/api/dashboard": "/api/stats", "/api/export": "/api/export.csv", "/api/auth/login": "/api/login", "/api/auth/logout": "/api/logout", "/api/auth/setup": "/api/setup"}
            path = aliases.get(path, path)
            if path.startswith("/api/"):
                if self.command in ("POST","PATCH","DELETE"):
                    self.body()
                with self.app.db() as db:
                    self.api(db, path, query)
            elif self.command in ("GET", "HEAD"):
                self.static(path)
            else:
                raise ApiError(404, "Not found")
        except ApiError as exc:
            self.close_connection = True
            self.respond(exc.status, {"error": exc.message})
        except sqlite3.IntegrityError:
            self.respond(409, {"error": "This change conflicts with an existing record or references an unknown record"})
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as exc:
            sys.stderr.write(f"[{utcnow()}] Request error: {type(exc).__name__}\n")
            self.close_connection = True
            self.respond(500, {"error": "Internal server error"})

    def api(self, db, path, query):
        method = self.command
        if path == "/api/status" and method in ("GET", "HEAD"):
            user, _ = self.current_session(db)
            self.respond(200, {"setup_required": not bool(db.execute("SELECT 1 FROM users LIMIT 1").fetchone()), "user": self.app.public_user(user) if user else None, "csrf": user["csrf"] if user else None, "name": "CapitalForge", "version": "1.0.0"})
            return
        if path == "/api/setup" and method == "POST":
            payload = self.body()
            request_host = (urlsplit("http://" + self.headers.get("Host", "")).hostname or "").lower()
            local = ipaddress.ip_address(self.peer_ip()).is_loopback and request_host in ("localhost", "127.0.0.1", "::1")
            if not local:
                provided = payload.get("bootstrap_token", "")
                if not self.app.bootstrap_token or not hmac.compare_digest(str(provided),self.app.bootstrap_token):
                    raise ApiError(403, "Create the first administrator locally before exposing the server")
            name, email, password = self.validate_user(payload)
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM users LIMIT 1").fetchone():
                raise ApiError(409, "Setup is already complete")
            now = utcnow()
            cur = db.execute("INSERT INTO users(name,email,password_hash,role,created_at,updated_at) VALUES(?,?,?,?,?,?)", (name,email,password_hash(password),"admin",now,now))
            self.app.audit(db,cur.lastrowid,"setup","user",cur.lastrowid)
            user = db.execute("SELECT * FROM users WHERE id=?", (cur.lastrowid,)).fetchone()
            self.session_response(db,user,201)
            return
        if path == "/api/login" and method == "POST":
            payload = self.body()
            ip = self.peer_ip()
            db.execute("DELETE FROM auth_failures WHERE occurred_at<?", (time.time()-900,))
            failures = db.execute("SELECT COUNT(*) FROM auth_failures WHERE ip=?", (ip,)).fetchone()[0]
            if failures >= 15:
                raise ApiError(429, "Too many sign-in attempts; try again after 15 minutes")
            user = db.execute("SELECT * FROM users WHERE email=? AND active=1", (email_normalize(payload.get("email")),)).fetchone()
            supplied_password = str(payload.get("password", ""))
            if len(supplied_password) > 1024:
                supplied_password = ""
            valid = password_ok(supplied_password, user["password_hash"] if user else self.app._dummy_password)
            if not user or not valid:
                db.execute("INSERT INTO auth_failures(ip,occurred_at) VALUES(?,?)", (ip,time.time()))
                db.commit()
                raise ApiError(401, "Email or password is incorrect")
            db.execute("DELETE FROM auth_failures WHERE ip=?", (ip,))
            self.app.audit(db,user["id"],"login","user",user["id"])
            self.session_response(db,user)
            return
        if path == "/api/me" and method == "GET":
            user, _ = self.auth(db)
            self.respond(200,{"user":self.app.public_user(user),"csrf":user["csrf"]})
            return
        if path == "/api/logout" and method == "POST":
            user, token = self.auth(db,mutation=True)
            db.execute("DELETE FROM sessions WHERE token_hash=?", (token_hash(token),))
            self.app.audit(db,user["id"],"logout","user",user["id"])
            db.commit()
            self.respond(200,{"ok":True},extra_headers={"Set-Cookie":f"{COOKIE_NAME}=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0"})
            return
        user, _ = self.auth(db)
        if path == "/api/leads" and method == "GET":
            where, params = self.lead_filter(query)
            limit, offset = self.pagination(query)
            total = db.execute("SELECT COUNT(*) FROM leads"+where,params).fetchone()[0]
            allowed_sort = {"company":"company COLLATE NOCASE", "updated_at":"updated_at DESC", "created_at":"created_at DESC", "id":"id", "state":"state,company"}
            sort = allowed_sort.get(query.get("sort", ["company"])[0],"company COLLATE NOCASE")
            rows = db.execute("SELECT * FROM leads"+where+" ORDER BY "+sort+" LIMIT ? OFFSET ?",params+[limit,offset])
            self.respond(200,{"items":[self.app.serialize_lead(row) for row in rows],"total":total,"limit":limit,"offset":offset})
            return
        if path == "/api/leads" and method == "POST":
            user = self.write_permission(db)
            data = self.app.validate_lead(self.body())
            duplicate = self.app.find_duplicate(db,data)
            if duplicate:
                raise ApiError(409,f"Duplicate contact exists as lead {duplicate['id']}")
            lead_id = self.app.insert_lead(db,data)
            self.app.audit(db,user["id"],"create","lead",lead_id)
            db.commit()
            self.respond(201,self.app.serialize_lead(db.execute("SELECT * FROM leads WHERE id=?",(lead_id,)).fetchone()))
            return
        match = re.fullmatch(r"/api/leads/(\d+)(?:/(notes|tasks))?",path)
        if match:
            lead_id, child = int(match[1]), match[2]
            row = db.execute("SELECT * FROM leads WHERE id=?",(lead_id,)).fetchone()
            if not row:
                raise ApiError(404,"Lead not found")
            if child:
                self.lead_child(db,user,lead_id,child,method)
                return
            if method == "GET":
                data = self.app.serialize_lead(row)
                data["notes"] = [dict(n) for n in db.execute("SELECT n.*,u.name AS author_name FROM notes n LEFT JOIN users u ON n.author_id=u.id WHERE n.lead_id=? ORDER BY n.id DESC",(lead_id,))]
                data["tasks"] = [dict(t) for t in db.execute("SELECT * FROM tasks WHERE lead_id=? ORDER BY id DESC",(lead_id,))]
                self.respond(200,data)
                return
            if method == "PATCH":
                user = self.write_permission(db)
                updates = self.app.validate_lead(self.body(),partial=True)
                if "metadata" in updates:
                    previous = json.loads(row["metadata"])
                    previous.update(json.loads(updates["metadata"]))
                    if len(json_text(previous)) > 100000:
                        raise ApiError(400,"Combined metadata exceeds 100,000 characters")
                    updates["metadata"] = json_text(previous)
                merged = dict(row)
                merged.update(updates)
                if not (merged["company"] or merged["name"]):
                    raise ApiError(400,"Provide a company or contact name")
                updates["dedup_key"] = dedup_key(merged)
                updates["updated_at"] = utcnow()
                db.execute("UPDATE leads SET "+",".join(k+"=?" for k in updates)+" WHERE id=?",list(updates.values())+[lead_id])
                self.app.audit(db,user["id"],"update","lead",lead_id,{"fields":list(updates)})
                db.commit()
                self.respond(200,self.app.serialize_lead(db.execute("SELECT * FROM leads WHERE id=?",(lead_id,)).fetchone()))
                return
            if method == "DELETE":
                user, _ = self.auth(db,("admin",),mutation=True)
                db.execute("DELETE FROM leads WHERE id=?",(lead_id,))
                self.app.audit(db,user["id"],"delete","lead",lead_id,{"company":row["company"]})
                db.commit()
                self.respond(200,{"ok":True})
                return
        if path == "/api/import" and method == "POST":
            user = self.write_permission(db)
            payload = self.body()
            rows = payload.get("rows")
            if "csv" in payload:
                if not isinstance(payload["csv"],str):
                    raise ApiError(400,"csv must be text")
                rows = list(csv.DictReader(io.StringIO(payload["csv"].lstrip("\ufeff"))))
            report = self.app.import_rows(db,rows,user["id"])
            db.commit()
            self.respond(200,report)
            return
        if path in ("/api/export.csv", "/api/export.json") and method == "GET":
            where, params = self.lead_filter(query)
            items = [self.app.serialize_lead(row) for row in db.execute("SELECT * FROM leads"+where+" ORDER BY company COLLATE NOCASE",params)]
            self.app.audit(db,user["id"],"export","leads",detail={"records":len(items),"format":path.rsplit(".",1)[-1]})
            db.commit()
            if path.endswith("json"):
                self.respond(200,{"items":items,"total":len(items),"exported_at":utcnow()},extra_headers={"Content-Disposition":"attachment; filename=capitalforge-lenders.json"})
            else:
                columns = ("id",) + LEAD_FIELDS + ("created_at","updated_at")
                buffer = io.StringIO(newline="")
                writer = csv.writer(buffer)
                writer.writerow(columns)
                for item in items:
                    writer.writerow([safe_csv_cell(json_text(item.get(k)) if isinstance(item.get(k),(list,dict)) else item.get(k)) for k in columns])
                self.respond(200,buffer.getvalue().encode("utf-8-sig"),"text/csv; charset=utf-8",{"Content-Disposition":"attachment; filename=capitalforge-lenders.csv"})
            return
        if path == "/api/stats" and method == "GET":
            counts = db.execute("SELECT COUNT(*) AS total,SUM(email<>'') AS with_email,SUM(phone<>'') AS with_phone,SUM(email<>'' AND phone<>'') AS contact_complete,SUM(do_not_contact) AS suppressed,SUM(capital_verification='documented' AND cash_capacity>=500000) AS capital_documented_minimum FROM leads").fetchone()
            data = {k:counts[k] or 0 for k in counts.keys()}
            candidates = db.execute("SELECT collateral_requirement FROM leads WHERE fit IN ('potential','strong') AND do_not_contact=0")
            data["potentially_suitable"] = sum(1 for row in candidates if self.collateral_may_fit(row[0]))
            confirmed = db.execute("SELECT collateral_requirement FROM leads WHERE fit='strong' AND do_not_contact=0 AND capital_verification='documented' AND cash_capacity>=500000")
            data["confirmed_suitable"] = sum(1 for row in confirmed if self.collateral_may_fit(row[0]))
            for column in ("stage","fit","capital_verification","verification_status"):
                data["by_"+column] = {r[0]:r[1] for r in db.execute("SELECT "+column+",COUNT(*) FROM leads GROUP BY "+column)}
            data["open_tasks"] = db.execute("SELECT COUNT(*) FROM tasks WHERE status='open'").fetchone()[0]
            data["overdue_tasks"] = db.execute("SELECT COUNT(*) FROM tasks WHERE status='open' AND due_date<>'' AND due_date<?",(utcnow()[:10],)).fetchone()[0]
            data["sources"] = db.execute("SELECT COUNT(DISTINCT source_url) FROM leads WHERE source_url<>''").fetchone()[0]
            data["by_state"] = {r[0]:r[1] for r in db.execute("SELECT state,COUNT(*) FROM leads GROUP BY state ORDER BY COUNT(*) DESC")}
            data["roles"] = list(ROLES)
            self.respond(200,data)
            return
        if path == "/api/deal":
            deal = json.loads(db.execute("SELECT value FROM settings WHERE key='deal'").fetchone()[0])
            if method == "GET":
                self.respond(200,{**deal, **CONTRACT_ECONOMICS})
                return
            if method == "PATCH":
                user, _ = self.auth(db,("admin",),mutation=True)
                payload = self.body()
                if not isinstance(payload, dict):
                    raise ApiError(400, "A JSON object is required")
                if any(key in payload for key in CONTRACT_ECONOMICS):
                    raise ApiError(400, "Contract source inputs and calculated underwriting base are read-only")
                for key in DEFAULT_DEAL:
                    if key in payload:
                        if key in DEAL_NUM_FIELDS:
                            if payload[key] in (None, "") and key in OPTIONAL_DEAL_NUM_FIELDS:
                                deal[key] = None
                                continue
                            try:
                                value = float(payload[key])
                            except (TypeError,ValueError):
                                raise ApiError(400,f"{key} must be numeric")
                            if not 0 <= value <= 1e15:
                                raise ApiError(400,f"Invalid {key}")
                            deal[key] = value
                        else:
                            deal[key] = str(payload[key])[:20000]
                if deal["raise_min"] > deal["raise_max"] or deal["equity_percent"] > 100:
                    raise ApiError(400,"Inconsistent deal ranges")
                for lower, upper in (("target_months_min", "target_months_max"),
                    ("estimated_initial_fees_min", "estimated_initial_fees"),
                    ("estimated_initial_fees", "estimated_initial_fees_max"),
                    ("estimated_initial_fees_min", "estimated_initial_fees_max")):
                    if deal.get(lower) is not None and deal.get(upper) is not None and deal[lower] > deal[upper]:
                        raise ApiError(400,"Inconsistent deal ranges")
                db.execute("UPDATE settings SET value=? WHERE key='deal'",(json_text(deal),))
                self.app.audit(db,user["id"],"update","deal",detail={"fields":list(payload)})
                db.commit()
                self.respond(200,{**deal, **CONTRACT_ECONOMICS})
                return
        if path == "/api/tasks":
            if method == "GET":
                where, params = [], []
                for key in ("status","lead_id","assigned_to"):
                    if query.get(key,[""])[0]:
                        where.append("t."+key+"=?")
                        params.append(query[key][0])
                clause = " WHERE "+" AND ".join(where) if where else ""
                limit, offset = self.pagination(query,100)
                total = db.execute("SELECT COUNT(*) FROM tasks t"+clause,params).fetchone()[0]
                rows = db.execute("SELECT t.*,l.company AS company,l.name AS contact_name,u.name AS assignee_name FROM tasks t LEFT JOIN leads l ON t.lead_id=l.id LEFT JOIN users u ON t.assigned_to=u.id"+clause+" ORDER BY t.status,t.due_date,t.id DESC LIMIT ? OFFSET ?",params+[limit,offset])
                self.respond(200,{"items":[dict(r) for r in rows],"total":total})
                return
            if method == "POST":
                user = self.write_permission(db)
                self.create_task(db,user,self.body())
                return
        match = re.fullmatch(r"/api/tasks/(\d+)",path)
        if match and method in ("PATCH","DELETE"):
            user = self.write_permission(db)
            task_id = int(match[1])
            if not db.execute("SELECT 1 FROM tasks WHERE id=?",(task_id,)).fetchone():
                raise ApiError(404,"Task not found")
            if method == "DELETE":
                db.execute("DELETE FROM tasks WHERE id=?",(task_id,))
                self.app.audit(db,user["id"],"delete","task",task_id)
                db.commit()
                self.respond(200,{"ok":True})
                return
            data = self.validate_task(self.body(),partial=True)
            data["updated_at"] = utcnow()
            db.execute("UPDATE tasks SET "+",".join(k+"=?" for k in data)+" WHERE id=?",list(data.values())+[task_id])
            self.app.audit(db,user["id"],"update","task",task_id,{"fields":list(data)})
            db.commit()
            self.respond(200,dict(db.execute("SELECT * FROM tasks WHERE id=?",(task_id,)).fetchone()))
            return
        if path == "/api/users" or re.fullmatch(r"/api/users/\d+",path):
            self.users(db,user,path,method)
            return
        if path == "/api/audit" and method == "GET":
            self.auth(db,("admin",))
            limit, offset = self.pagination(query,100)
            rows = db.execute("SELECT a.*,u.name AS actor_name FROM audit a LEFT JOIN users u ON a.actor_id=u.id ORDER BY a.id DESC LIMIT ? OFFSET ?",(limit,offset))
            items=[]
            for row in rows:
                item=dict(row); item["detail"]=json.loads(item["detail"]); items.append(item)
            self.respond(200,{"items":items,"total":db.execute("SELECT COUNT(*) FROM audit").fetchone()[0]})
            return
        if path == "/api/backup" and method == "POST":
            user, _ = self.auth(db,("admin",),mutation=True)
            filename = "capitalforge-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")+"-"+secrets.token_hex(3)+".sqlite3"
            destination = self.app.backup_dir / filename
            with sqlite3.connect(str(destination)) as backup_db:
                db.backup(backup_db)
                backup_db.execute("PRAGMA journal_mode=DELETE")
                # Downloaded snapshots do not carry live session tokens or rate-limit history.
                backup_db.execute("DELETE FROM sessions")
                backup_db.execute("DELETE FROM auth_failures")
            destination.chmod(0o600)
            self.app.audit(db,user["id"],"backup","database",detail={"filename":filename})
            db.commit()
            self.respond(201,{"filename":filename,"created_at":utcnow(),"download_url":"/api/backups/"+filename})
            return
        match = re.fullmatch(r"/api/backups/(capitalforge-[a-zA-Z0-9-]+\.sqlite3)",path)
        if match and method == "GET":
            self.auth(db,("admin",))
            file_path = self.app.backup_dir / match[1]
            if not file_path.is_file():
                raise ApiError(404,"Backup not found")
            self.respond(200,file_path.read_bytes(),"application/vnd.sqlite3",{"Content-Disposition":f"attachment; filename={match[1]}"})
            return
        raise ApiError(404,"Unknown endpoint or method")

    def validate_user(self, payload):
        name = str(payload.get("name","")).strip()[:200]
        email = email_normalize(payload.get("email"))
        password = str(payload.get("password",""))
        if not name or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+",email):
            raise ApiError(400,"Provide a name and valid email address")
        if len(password) < 12 or len(password) > 1024:
            raise ApiError(400,"Password must contain 12 to 1,024 characters")
        return name,email,password

    @staticmethod
    def collateral_may_fit(value):
        text = str(value or "").lower()
        if not text or any(term in text for term in ("unsecured", "not secured", "no property", "non-property", "equity", "receivable", "contract")):
            return True
        return not any(term in text for term in ("property", "mortgage", "real estate collateral", "first lien", "lien on"))

    def users(self, db, user, path, method):
        if method == "GET" and path == "/api/users":
            # Analysts may see names and roles to assign work; email exposed only to admin.
            rows = [self.app.public_user(r) for r in db.execute("SELECT * FROM users ORDER BY name")]
            if user["role"] != "admin":
                for row in rows: row.pop("email",None)
            self.respond(200,{"items":rows,"total":len(rows)})
            return
        user, _ = self.auth(db,("admin",),mutation=True)
        payload = self.body()
        if path == "/api/users" and method == "POST":
            name,email,password = self.validate_user(payload)
            role = payload.get("role","analyst")
            if role not in ROLES:
                raise ApiError(400,"Invalid user role")
            now=utcnow()
            cur=db.execute("INSERT INTO users(name,email,password_hash,role,created_at,updated_at) VALUES(?,?,?,?,?,?)",(name,email,password_hash(password),role,now,now))
            self.app.audit(db,user["id"],"create","user",cur.lastrowid,{"role":role})
            db.commit()
            self.respond(201,self.app.public_user(db.execute("SELECT * FROM users WHERE id=?",(cur.lastrowid,)).fetchone()))
            return
        match=re.fullmatch(r"/api/users/(\d+)",path)
        if match and method=="PATCH":
            db.execute("BEGIN IMMEDIATE")
            target_id=int(match[1]); target=db.execute("SELECT * FROM users WHERE id=?",(target_id,)).fetchone()
            if not target: raise ApiError(404,"User not found")
            updates={}
            if "name" in payload:
                updates["name"]=str(payload["name"]).strip()[:200]
                if not updates["name"]: raise ApiError(400,"Name cannot be empty")
            if "role" in payload:
                if payload["role"] not in ROLES: raise ApiError(400,"Invalid user role")
                updates["role"]=payload["role"]
            if "active" in payload: updates["active"]=int(payload["active"] is True or str(payload["active"]).lower() in ("1","true","yes"))
            if "password" in payload:
                password=str(payload["password"])
                if not 12<=len(password)<=1024: raise ApiError(400,"Password must contain 12 to 1,024 characters")
                updates["password_hash"]=password_hash(password)
            if target["role"]=="admin" and target["active"] and (updates.get("role","admin")!="admin" or updates.get("active",1)==0):
                active_admins=db.execute("SELECT COUNT(*) FROM users WHERE role='admin' AND active=1").fetchone()[0]
                if active_admins<=1: raise ApiError(400,"At least one active administrator is required")
            updates["updated_at"]=utcnow()
            db.execute("UPDATE users SET "+",".join(k+"=?" for k in updates)+" WHERE id=?",list(updates.values())+[target_id])
            if any(k in updates for k in ("password_hash","active","role")):
                db.execute("DELETE FROM sessions WHERE user_id=?",(target_id,))
            self.app.audit(db,user["id"],"update","user",target_id,{"fields":[k for k in updates if k!="password_hash"],"password_changed":"password_hash" in updates})
            db.commit()
            self.respond(200,self.app.public_user(db.execute("SELECT * FROM users WHERE id=?",(target_id,)).fetchone()))
            return
        raise ApiError(404,"Unknown user endpoint")

    def lead_child(self, db, user, lead_id, child, method):
        if child=="notes":
            if method=="GET":
                rows=[dict(r) for r in db.execute("SELECT n.*,u.name AS author_name FROM notes n LEFT JOIN users u ON n.author_id=u.id WHERE lead_id=? ORDER BY n.id DESC",(lead_id,))]
                self.respond(200,{"items":rows,"total":len(rows)})
                return
            if method=="POST":
                user=self.write_permission(db)
                body=str(self.body().get("body","")).strip()
                if not body or len(body)>20000: raise ApiError(400,"Note must contain 1 to 20,000 characters")
                cur=db.execute("INSERT INTO notes(lead_id,body,author_id,created_at) VALUES(?,?,?,?)",(lead_id,body,user["id"],utcnow()))
                self.app.audit(db,user["id"],"create","note",cur.lastrowid,{"lead_id":lead_id})
                db.commit()
                self.respond(201,dict(db.execute("SELECT n.*,u.name AS author_name FROM notes n LEFT JOIN users u ON n.author_id=u.id WHERE n.id=?",(cur.lastrowid,)).fetchone()))
                return
        if child=="tasks":
            if method=="GET":
                rows=[dict(r) for r in db.execute("SELECT * FROM tasks WHERE lead_id=? ORDER BY id DESC",(lead_id,))]
                self.respond(200,{"items":rows,"total":len(rows)})
                return
            if method=="POST":
                user=self.write_permission(db)
                payload=self.body(); payload["lead_id"]=lead_id
                self.create_task(db,user,payload)
                return
        raise ApiError(404,"Unknown lead endpoint")

    def validate_task(self,payload,partial=False):
        data={}
        if "title" in payload:
            data["title"]=str(payload["title"]).strip()[:500]
            if not data["title"]: raise ApiError(400,"Task title is required")
        elif not partial: raise ApiError(400,"Task title is required")
        if "status" in payload:
            if payload["status"] not in ("open","done","cancelled"): raise ApiError(400,"Invalid task status")
            data["status"]=payload["status"]
        if "due_date" in payload:
            date=str(payload["due_date"] or "")
            if date:
                try: datetime.strptime(date,"%Y-%m-%d")
                except ValueError: raise ApiError(400,"due_date must be YYYY-MM-DD")
            data["due_date"]=date
        for key in ("lead_id","assigned_to"):
            if key in payload:
                try: data[key]=int(payload[key]) if payload[key] not in (None,"") else None
                except (ValueError,TypeError): raise ApiError(400,f"{key} must be an ID")
        return data

    def create_task(self,db,user,payload):
        data=self.validate_task(payload)
        data.update(created_by=user["id"],created_at=utcnow(),updated_at=utcnow())
        cur=db.execute("INSERT INTO tasks("+",".join(data)+") VALUES("+",".join("?" for _ in data)+")",list(data.values()))
        self.app.audit(db,user["id"],"create","task",cur.lastrowid,{"lead_id":data.get("lead_id")})
        db.commit()
        self.respond(201,dict(db.execute("SELECT * FROM tasks WHERE id=?",(cur.lastrowid,)).fetchone()))

    def static(self,path):
        relative="index.html" if path in ("/","/index.html") else "app.html" if path in ("/app","/app/","/login") else path.lstrip("/")
        if relative.startswith("static/"): relative=relative[7:]
        base=(ROOT/"static").resolve()
        target=(base/relative).resolve()
        if not target.is_relative_to(base) or not target.is_file() or target.suffix.lower() not in (".html",".css",".js",".svg",".png",".jpg",".ico",".woff",".woff2"):
            raise ApiError(404,"Not found")
        mime=mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        if target.suffix in (".html",".css",".js",".svg"): mime+="; charset=utf-8"
        self.respond(200,target.read_bytes(),mime)


class CRMServer(ThreadingHTTPServer):
    """Bound concurrent worker threads; an HTTPS reverse proxy adds edge limits."""
    daemon_threads=True
    request_queue_size=64

    def __init__(self,*args,**kwargs):
        self._workers=threading.BoundedSemaphore(64)
        super().__init__(*args,**kwargs)

    def process_request(self,request,client_address):
        if not self._workers.acquire(blocking=False):
            try:
                request.settimeout(1)
                request.sendall(b"HTTP/1.1 503 Service Unavailable\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
            except OSError:
                pass
            self.shutdown_request(request)
            return
        try:
            super().process_request(request,client_address)
        except Exception:
            self._workers.release()
            raise

    def process_request_thread(self,request,client_address):
        try:
            super().process_request_thread(request,client_address)
        finally:
            self._workers.release()


def create_server(app,host="127.0.0.1",port=8787):
    server_class=CRMServer
    if ":" in host:
        class IPv6CRMServer(CRMServer):
            address_family=socket.AF_INET6
        server_class=IPv6CRMServer
    server=server_class((host,port),Handler)
    server.daemon_threads=True
    server.app=app
    return server


def main():
    parser=argparse.ArgumentParser(description="CapitalForge by 101XVC local CRM")
    parser.add_argument("--host",default=os.environ.get("CAPITALFORGE_HOST","127.0.0.1"))
    parser.add_argument("--port",type=int,default=int(os.environ.get("CAPITALFORGE_PORT","8787")))
    parser.add_argument("--data-dir",default=os.environ.get("CAPITALFORGE_DATA_DIR",str(ROOT/"runtime")))
    parser.add_argument("--seed-file",default=str(ROOT/"data"/"data_lenders.jsonl"))
    parser.add_argument("--equity-seed-file",default=str(ROOT/"data"/"equity_directory.jsonl"),help="Optional equity investor research seed; use an empty path to skip")
    parser.add_argument("--trial-seed-file",default=str(ROOT/"data"/"trial_capital_directory.jsonl"),help="Optional $100K-$500K trial funding research seed; use an empty path to skip")
    parser.add_argument("--investor-seed-file",default=str(ROOT/"data"/"investor2500_directory.jsonl"),help="Optional prospect campaign research seed; use an empty path to skip")
    parser.add_argument("--open-browser",action="store_true",help="Open the local portal after startup")
    args=parser.parse_args()
    allowed=[h.strip().lower() for h in os.environ.get("CAPITALFORGE_ALLOWED_HOSTS","localhost,127.0.0.1,::1").split(",") if h.strip()]
    app=App(args.data_dir,allowed,os.environ.get("CAPITALFORGE_SECURE_COOKIES")=="1",os.environ.get("CAPITALFORGE_BOOTSTRAP_TOKEN"))
    report=app.seed(args.seed_file)
    for optional_seed in (args.equity_seed_file, args.trial_seed_file, args.investor_seed_file):
        if optional_seed:
            optional_report=app.seed(optional_seed)
            for key in ("inserted", "merged", "invalid"):
                report[key]+=optional_report[key]
    server=create_server(app,args.host,args.port)
    print(f"CapitalForge by 101XVC\nOpen http://{args.host}:{args.port}/app\nData: {app.data_dir}\nSeed import: {report['inserted']} added, {report['merged']} merged, {report['invalid']} invalid",flush=True)
    if args.host not in ("127.0.0.1","localhost","::1"):
        print("Network binding enabled. Configure allowed hosts and use a TLS reverse proxy; initialize the administrator locally first.",flush=True)
    if args.open_browser:
        import webbrowser
        local_host = "127.0.0.1" if args.host in ("0.0.0.0","::") else args.host
        if ":" in local_host: local_host = "[" + local_host + "]"
        opener = threading.Timer(1,lambda: webbrowser.open(f"http://{local_host}:{args.port}/app"))
        opener.daemon = True
        opener.start()
    try: server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt: pass
    finally: server.server_close()


if __name__=="__main__":
    main()
