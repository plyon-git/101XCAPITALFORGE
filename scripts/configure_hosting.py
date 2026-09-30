#!/usr/bin/env python3
"""Create conventional HTTPS hosting configuration without hardcoded credentials."""
import argparse
import os
import re
import secrets
from pathlib import Path

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--domain',required=True)
    args=p.parse_args()
    domain=args.domain.lower().strip()
    if not re.fullmatch(r'(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}',domain):
        raise SystemExit('Supply a hostname such as crm.yourdomain.com without a URL scheme or path.')
    root=Path(__file__).resolve().parents[1]
    target=root/'.env'
    if target.exists():
        raise SystemExit('.env already exists. Keep its original bootstrap token or edit it deliberately.')
    token=secrets.token_urlsafe(32)
    fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as f:
        f.write(f'CAPITALFORGE_DOMAIN={domain}\nCAPITALFORGE_BOOTSTRAP_TOKEN={token}\n')
    print(f'Created hosting configuration for https://{domain}')
    print('Start with: docker compose up -d --build')
    print('Use this token only when creating the first administrator in the portal:')
    print(token)
    print('After account setup, remove the token from .env and restart: docker compose up -d')

if __name__=='__main__':main()
