#!/usr/bin/env python3
"""Local administrator password recovery; never accepts a password on the command line."""
import argparse
import getpass
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import App, email_normalize, password_hash, utcnow

def main():
    parser=argparse.ArgumentParser(description="Reset an existing CapitalForge user's password locally")
    parser.add_argument("--email",required=True)
    parser.add_argument("--data-dir",default=str(Path(__file__).resolve().parents[1]/"runtime"))
    args=parser.parse_args()
    database=Path(args.data_dir)/"capitalforge.sqlite3"
    if not database.is_file():
        raise SystemExit("No CRM database exists at this location")
    password=getpass.getpass("New password (at least 12 characters): ")
    if not 12<=len(password)<=1024:
        raise SystemExit("Password must contain 12 to 1,024 characters")
    if password!=getpass.getpass("Confirm new password: "):
        raise SystemExit("Passwords do not match")
    app=App(args.data_dir)
    with app.db() as db:
        user=db.execute("SELECT * FROM users WHERE email=?",(email_normalize(args.email),)).fetchone()
        if not user: raise SystemExit("No matching user exists")
        db.execute("UPDATE users SET password_hash=?,updated_at=? WHERE id=?",(password_hash(password),utcnow(),user["id"]))
        db.execute("DELETE FROM sessions WHERE user_id=?",(user["id"],))
        app.audit(db,None,"local_password_reset","user",user["id"])
    print("Password changed; all sessions for this user were invalidated")

if __name__=="__main__": main()
