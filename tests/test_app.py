"""Integration tests exercise authentication, access controls and actual CRM behavior."""
import csv
import http.client
import io
import json
import sqlite3
import tempfile
import threading
import time
import unittest
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import App, create_server, password_ok


class CRMTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.app=App(self.temp.name)
        self.server=create_server(self.app,port=0)
        self.port=self.server.server_port
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.cookie=""
        self.csrf=""

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(2)
        self.temp.cleanup()

    def request(self,method,path,data=None,csrf=True,headers=None,raw=False):
        connection=http.client.HTTPConnection("127.0.0.1",self.port,timeout=10)
        request_headers={"Cookie":self.cookie}
        if data is not None: request_headers["Content-Type"]="application/json"
        if csrf: request_headers["X-CSRF-Token"]=self.csrf
        request_headers.update(headers or {})
        connection.request(method,path,json.dumps(data) if data is not None else None,request_headers)
        response=connection.getresponse()
        body=response.read()
        cookie=response.getheader("Set-Cookie")
        if cookie: self.cookie=cookie.split(";",1)[0]
        response_headers=dict(response.getheaders())
        status=response.status
        connection.close()
        if raw: return status,body,response_headers
        result=json.loads(body)
        if result.get("csrf"): self.csrf=result["csrf"]
        return status,result

    def setup_admin(self):
        status,data=self.request("POST","/api/setup",{"name":"Owner","email":"owner@example.com","password":"a-strong-test-password"})
        self.assertEqual(status,201,data)
        return data

    def create_lead(self,**fields):
        data={"company":"Example Capital","name":"Public Team","email":"team@example.com","phone":"+1 303 555 0100","website":"https://example.com","source_url":"https://example.com/contact","verification_status":"source_observed"}
        data.update(fields)
        status,result=self.request("POST","/api/leads",data)
        self.assertEqual(status,201,result)
        return result

    def test_setup_auth_password_hash_and_bootstrap_lock(self):
        status,data=self.request("GET","/api/status")
        self.assertTrue(data["setup_required"])
        self.assertEqual(self.request("GET","/api/leads")[0],401)
        self.assertEqual(self.request("POST","/api/setup",{"name":"A","email":"a@b.com","password":"short"})[0],400)
        setup=self.setup_admin()
        with self.app.db() as db:
            encoded=db.execute("SELECT password_hash FROM users").fetchone()[0]
        self.assertNotIn("a-strong-test-password",encoded)
        self.assertTrue(password_ok("a-strong-test-password",encoded))
        self.assertEqual(setup["user"]["role"],"admin")
        self.assertEqual(self.request("POST","/api/setup",{"name":"B","email":"b@b.com","password":"another-long-password"})[0],409)
        self.assertEqual(self.request("POST","/api/logout",{})[0],200)
        self.assertEqual(self.request("GET","/api/leads")[0],401)
        self.assertEqual(self.request("POST","/api/login",{"email":"owner@example.com","password":"wrong"})[0],401)
        self.assertEqual(self.request("POST","/api/login",{"email":"OWNER@example.com","password":"a-strong-test-password"})[0],200)

    def test_csrf_host_origin_and_security_headers(self):
        self.setup_admin()
        self.assertEqual(self.request("POST","/api/leads",{"company":"X"},csrf=False)[0],403)
        self.assertEqual(self.request("POST","/api/leads",{"company":"X"},headers={"Origin":"https://malicious.example"})[0],403)
        self.assertEqual(self.request("GET","/api/status",headers={"Host":"malicious.example"})[0],403)
        status,body,headers=self.request("GET","/api/status",raw=True)
        self.assertEqual(status,200)
        self.assertEqual(headers["X-Frame-Options"],"DENY")
        self.assertIn("frame-ancestors 'none'",headers["Content-Security-Policy"])
        self.assertEqual(self.request("GET","/../../app.py")[0],404)

    def test_import_dedup_provenance_suppression_metadata(self):
        self.setup_admin()
        lead=self.create_lead(do_not_contact=True,stage="terms",fit="strong",cash_capacity=600000,capital_verification="documented",custom_evidence={"registered":True})
        status,result=self.request("POST","/api/import",{"rows":[
            {"company":"Example Capital","email":"team@example.com","phone":"wrong","do_not_contact":False,"stage":"new","fit":"poor","source_url":"https://example.com/about","source_title":"New source","tags":["SBIC"],"custom_evidence":{"different":True}},
            {"company":"Second Firm","email":"public@second.example","state":"TX","category":"contract financier"},
            {"email":"bad"}
        ]})
        self.assertEqual(status,200,result)
        self.assertEqual((result["inserted"],result["merged"],result["invalid"]),(1,1,1))
        updated=self.request("GET",f"/api/leads/{lead['id']}")[1]
        self.assertTrue(updated["do_not_contact"])
        self.assertEqual(updated["stage"],"terms")
        self.assertEqual(updated["fit"],"strong")
        self.assertEqual(updated["phone"],lead["phone"])
        self.assertEqual(updated["metadata"]["custom_evidence"],{"registered":True})
        status,metadata_updated=self.request("PATCH",f"/api/leads/{lead['id']}",{"additional_context":"Retain the original research"})
        self.assertEqual(status,200)
        self.assertEqual(metadata_updated["metadata"]["custom_evidence"],{"registered":True})
        self.assertEqual(metadata_updated["metadata"]["additional_context"],"Retain the original research")
        self.assertEqual(updated["sources"][0]["url"],"https://example.com/about")
        self.assertEqual(self.request("POST","/api/leads",{"company":"Duplicate","email":"team@example.com"})[0],409)

    def test_filters_counts_and_csv_formula_safety(self):
        self.setup_admin()
        self.create_lead(company="=HYPERLINK(\"evil\")",state="TX",fit="strong",capital_verification="documented",cash_capacity=500000,collateral_requirement="unsecured")
        self.create_lead(company="Mortgage Provider",email="other@mortgage.example",state="AZ",fit="potential",collateral_requirement="First lien on property",tags=["equity-500k-9.3"])
        status,filtered=self.request("GET","/api/leads?state=TX&contact_complete=1&capital_min=500000&capital_verification=documented")
        self.assertEqual(filtered["total"],1)
        cohort=self.request("GET","/api/leads?q=equity-500k-9.3")[1]
        self.assertEqual(cohort["total"],1)
        self.assertEqual(cohort["items"][0]["company"],"Mortgage Provider")
        stats=self.request("GET","/api/stats")[1]
        self.assertEqual(stats["total"],2)
        self.assertEqual(stats["contact_complete"],2)
        self.assertEqual(stats["capital_documented_minimum"],1)
        self.assertEqual(stats["confirmed_suitable"],1)
        self.assertEqual(stats["potentially_suitable"],1)
        first=self.request("GET","/api/leads?state=TX")[1]["items"][0]
        self.request("PATCH",f"/api/leads/{first['id']}",{"do_not_contact":True})
        self.assertEqual(self.request("GET","/api/stats")[1]["confirmed_suitable"],0)
        self.request("PATCH",f"/api/leads/{first['id']}",{"do_not_contact":False,"collateral_requirement":"Property first lien required"})
        self.assertEqual(self.request("GET","/api/stats")[1]["confirmed_suitable"],0)
        status,body,headers=self.request("GET","/api/export.csv?state=TX",raw=True)
        rows=list(csv.DictReader(io.StringIO(body.decode("utf-8-sig"))))
        self.assertTrue(rows[0]["company"].startswith("'="))
        self.assertIn("attachment",headers["Content-Disposition"])
        self.assertEqual(self.request("GET","/api/leads?q=%25")[1]["total"],0)

    def test_named_investor_import_preserves_people_and_company_routes(self):
        self.setup_admin()
        firm = {"company":"Shared Investment Firm", "website":"https://investors.example",
                "email":"info@investors.example", "phone":"212-555-0180"}
        status, company_route = self.request("POST","/api/leads",firm)
        self.assertEqual(status,201,company_route)
        named = [{**firm,"name":name,"metadata":{"record_kind":"named_investor"}}
                 for name in ("Alice Smith","Bob Jones")]
        status, result = self.request("POST","/api/import",{"rows":named})
        self.assertEqual(status,200,result)
        self.assertEqual((result["inserted"],result["merged"],result["invalid"]),(2,0,0))
        contacts = self.request("GET","/api/leads")[1]
        self.assertEqual(contacts["total"],3)
        self.assertEqual({row["name"] for row in contacts["items"]},{"","Alice Smith","Bob Jones"})
        alice = next(row for row in contacts["items"] if row["name"] == "Alice Smith")
        self.request("PATCH",f"/api/leads/{alice['id']}",{"stage":"terms"})
        repeated = {**named[0],"name":" ALICE SMITH ","website":"https://www.investors.example/team",
                    "email":"alice@investors.example","source_url":"https://investors.example/team/alice"}
        status, result = self.request("POST","/api/import",{"rows":[repeated]})
        self.assertEqual(status,200,result)
        self.assertEqual((result["inserted"],result["merged"],result["invalid"]),(0,1,0))
        self.assertEqual(self.request("GET","/api/leads")[1]["total"],3)
        updated = self.request("GET",f"/api/leads/{alice['id']}")[1]
        self.assertEqual(updated["stage"],"terms")
        self.assertEqual(updated["source_url"],repeated["source_url"])
        # Untagged imports retain the existing company-route behavior.
        result = self.request("POST","/api/import",{"rows":[firm]})[1]
        self.assertEqual((result["inserted"],result["merged"],result["invalid"]),(0,1,0))
        self.assertEqual(self.request("GET","/api/leads")[1]["total"],3)
        # A named opt-in without an actual name cannot silently become a firm row.
        invalid = self.request("POST","/api/import",{"rows":[{**firm,"metadata":{"record_kind":"named_investor"}}]})[1]
        self.assertEqual((invalid["inserted"],invalid["merged"],invalid["invalid"]),(0,0,1))

    def test_pipeline_notes_tasks_and_audit(self):
        self.setup_admin()
        lead=self.create_lead()
        lead_id=lead["id"]
        status,updated=self.request("PATCH",f"/api/leads/{lead_id}",{"stage":"due_diligence","fit_reason":"Needs unsecured appetite review"})
        self.assertEqual(updated["stage"],"due_diligence")
        self.assertEqual(self.request("POST",f"/api/leads/{lead_id}/notes",{"body":"Public business email confirmed on source"})[0],201)
        status,task=self.request("POST",f"/api/leads/{lead_id}/tasks",{"title":"Verify capital availability","due_date":"2030-01-02"})
        self.assertEqual(status,201)
        self.assertEqual(self.request("PATCH",f"/api/tasks/{task['id']}",{"status":"done"})[0],200)
        detail=self.request("GET",f"/api/leads/{lead_id}")[1]
        self.assertEqual(len(detail["notes"]),1)
        self.assertEqual(detail["tasks"][0]["status"],"done")
        self.assertEqual(self.request("GET","/api/tasks?status=done")[1]["total"],1)
        audit=self.request("GET","/api/audit")[1]["items"]
        self.assertTrue(any(item["entity_type"]=="note" for item in audit))
        self.assertNotIn("a-strong-test-password",json.dumps(audit))

    def test_roles_admin_protection_and_password_session_invalidation(self):
        self.setup_admin()
        admin_cookie,admin_csrf=self.cookie,self.csrf
        status,viewer=self.request("POST","/api/users",{"name":"Read Only","email":"viewer@example.com","password":"viewer-password-long","role":"viewer"})
        self.assertEqual(status,201)
        self.assertEqual(self.request("PATCH","/api/users/1",{"active":False})[0],400)
        self.request("POST","/api/logout",{})
        self.request("POST","/api/login",{"email":"viewer@example.com","password":"viewer-password-long"})
        self.assertEqual(self.request("GET","/api/leads")[0],200)
        self.assertEqual(self.request("POST","/api/leads",{"company":"No"})[0],403)
        self.assertEqual(self.request("GET","/api/audit")[0],403)
        self.assertEqual(self.request("POST","/api/backup",{})[0],403)
        self.assertNotIn("email",self.request("GET","/api/users")[1]["items"][0])
        viewer_cookie,viewer_csrf=self.cookie,self.csrf
        self.request("POST","/api/login",{"email":"owner@example.com","password":"a-strong-test-password"})
        self.assertEqual(self.request("PATCH",f"/api/users/{viewer['id']}",{"password":"changed-password-long"})[0],200)
        self.cookie,self.csrf=viewer_cookie,viewer_csrf
        self.assertEqual(self.request("GET","/api/leads")[0],401)

    def test_snapshot_download_has_no_live_sessions_and_can_restore(self):
        self.setup_admin(); lead=self.create_lead()
        status,result=self.request("POST","/api/backup",{})
        self.assertEqual(status,201,result)
        status,body,_=self.request("GET",result["download_url"],raw=True)
        self.assertEqual(status,200)
        restored=Path(self.temp.name)/"restored.sqlite3"
        restored.write_bytes(body)
        with sqlite3.connect(str(restored)) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM leads").fetchone()[0],1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0],0)
        self.request("DELETE",f"/api/leads/{lead['id']}")
        self.assertEqual(self.request("GET","/api/leads")[1]["total"],0)

    def test_invalid_data_nonfinite_dates_and_expired_sessions(self):
        self.setup_admin()
        self.assertEqual(self.request("POST","/api/leads",{"company":"Bad","cash_capacity":"NaN"})[0],400)
        self.assertEqual(self.request("POST","/api/leads",{"company":"Bad","website":"javascript:evil"})[0],400)
        self.assertEqual(self.request("POST","/api/tasks",{"title":"Bad date","due_date":"2030-02-31"})[0],400)
        self.assertEqual(self.request("PATCH","/api/deal",{"equity_percent":101})[0],400)
        self.assertEqual(self.request("PATCH","/api/deal",{"raise_min":600000,"raise_max":500000})[0],400)
        with self.app.db() as db: db.execute("UPDATE sessions SET expires_at=?",(time.time()-1,))
        self.assertEqual(self.request("GET","/api/leads")[0],401)

    def test_seed_idempotent_csv_import_and_rate_limit(self):
        path=Path(self.temp.name)/"seed.jsonl"
        path.write_text(json.dumps({"company":"Seed Example","phone":"555-0100","source_url":"https://example.com"})+"\n",encoding="utf-8")
        self.assertEqual(self.app.seed(path)["inserted"],1)
        self.assertEqual(self.app.seed(path)["merged"],1)
        self.setup_admin()
        status,result=self.request("POST","/api/import",{"csv":"company,email,phone\nCSV Example,info@csv.example,5550101\n"})
        self.assertEqual(result["inserted"],1)
        self.request("POST","/api/logout",{})
        with self.app.db() as db:
            db.executemany("INSERT INTO auth_failures(ip,occurred_at) VALUES(?,?)",[("127.0.0.1",time.time())]*15)
        self.assertEqual(self.request("POST","/api/login",{"email":"owner@example.com","password":"a-strong-test-password"})[0],429)

    def test_remote_hostname_bootstrap_is_blocked_even_through_local_proxy(self):
        self.app.allowed_hosts.add("crm.example.com")
        status,_=self.request("POST","/api/setup",{"name":"Admin","email":"admin@example.com","password":"a-password-long-enough"},headers={"Host":"crm.example.com"})
        self.assertEqual(status,403)

    def test_keepalive_consumes_logout_and_backup_request_bodies(self):
        self.setup_admin()
        self.create_lead()
        connection=http.client.HTTPConnection("127.0.0.1",self.port,timeout=10)
        headers={"Cookie":self.cookie,"X-CSRF-Token":self.csrf,"Content-Type":"application/json"}
        connection.request("POST","/api/backup","{}",headers)
        response=connection.getresponse()
        self.assertEqual(response.status,201)
        snapshot=json.loads(response.read())
        connection.request("GET",snapshot["download_url"],headers=headers)
        response=connection.getresponse()
        self.assertEqual(response.status,200)
        self.assertTrue(response.read().startswith(b"SQLite format 3"))
        connection.request("POST","/api/logout","{}",headers)
        response=connection.getresponse()
        self.assertEqual(response.status,200)
        response.read()
        connection.request("POST","/api/login",json.dumps({"email":"owner@example.com","password":"a-strong-test-password"}),{"Content-Type":"application/json"})
        response=connection.getresponse()
        self.assertEqual(response.status,200)
        self.assertEqual(json.loads(response.read())["user"]["role"],"admin")
        connection.close()


if __name__=="__main__": unittest.main()
