# Operations and data protection

CapitalForge is a Python-standard-library HTTP application with SQLite. It runs without external service accounts, network APIs, JavaScript build tooling or package installs. Python 3.10 or later is required. The contact seed is loaded from `data/data_lenders.jsonl` at startup; real workflow data lives separately under `runtime/` by default.

## Local operation

Run `python3 app.py`, then open `http://127.0.0.1:8787/app`. Create the administrator locally before permitting network access. The default bind is loopback only. The public landing page is `/`; contact data requires login. There are no preset passwords or sample lender identities inserted by the backend.

The administrator, analyst and viewer roles are enforced at API endpoints. Browser controls alone are not the authority. Use separate accounts for team members and a viewer role for access that does not require editing. All stored password values are salted PBKDF2 hashes, not recoverable plaintext passwords. Session tokens are also stored as hashes; CSRF values are distinct. Do not put real account credentials into source code, shared archives or screenshots.

## Website deployment

Deploy the same application behind an HTTPS reverse proxy. Keep its HTTP port private to the proxy/network; add the actual public hostname to `CAPITALFORGE_ALLOWED_HOSTS` and enable `CAPITALFORGE_SECURE_COOKIES=1`. The proxy must preserve the original Host header. Origins must match that Host exactly for writes. The backend deliberately ignores forwarded client-IP headers, so spoofed forwarding headers cannot bypass bootstrap protections or throttle rules. If multiple users share a proxy connection address, their failed-login limit is shared. Apply edge rate limits and timeouts at the proxy for a larger public deployment.

| Setting | Default / effect |
|---|---|
| `CAPITALFORGE_HOST` | `127.0.0.1`; use private/container `0.0.0.0` behind a protected reverse proxy |
| `CAPITALFORGE_PORT` | `8787` |
| `CAPITALFORGE_DATA_DIR` | `<project>/runtime`; use persistent storage on a host/container |
| `CAPITALFORGE_ALLOWED_HOSTS` | `localhost,127.0.0.1,::1`; comma-separated hostnames without scheme or port |
| `CAPITALFORGE_SECURE_COOKIES` | Set to `1` under HTTPS; never enable for ordinary local HTTP |
| `CAPITALFORGE_BOOTSTRAP_TOKEN` | Optional secret for intentionally authorized remote first-admin setup; initialize locally instead where practical |

CLI overrides are `--host`, `--port`, `--data-dir` and `--seed-file`. Bootstrap is one-time and race-safe. Requests to a public hostname cannot bootstrap merely because a local reverse proxy forwarded them. Standard startup does not trust or fetch any URL from contact data.

Use one application process per SQLite database. SQLite WAL mode handles concurrent short requests; write-heavy or large multi-tenant deployments should be migrated to a dedicated application stack/database. The server bounds concurrent request threads to 64, bodies to 20 MB and read timeouts to 20 seconds. The reference setup is an internal CRM, with no identity federation, MFA, email-based reset, fine-grained team partitioning or encryption-at-rest built in. Host-level disk encryption and backup access controls remain the operator's responsibility.

## Backups and recovery

Create a snapshot from the administrator settings page. Snapshots use SQLite's online backup operation, including the active WAL data, then remove live sessions. Store snapshots separately from the server and protect them like the live database. They contain password hashes, public contact records and internal notes. They are not served from the static directory and require administrator authentication to download.

To restore: stop the application, preserve the existing runtime directory, copy the chosen snapshot to `<data-dir>/capitalforge.sqlite3`, remove obsolete `capitalforge.sqlite3-wal` and `capitalforge.sqlite3-shm` files only after confirming the app is stopped, then restart. Sign in again; restored snapshots contain no active sessions. Startup merges the source seed with existing records while preserving suppression and reviewed workflow states. If you need an exact snapshot restore with no new seed records, start with `--seed-file` pointing to a nonexistent file.

For forgotten passwords, run `python3 scripts/reset_password.py --email owner@example.com --data-dir /path/to/runtime` on the trusted local host. It prompts for a new password, invalidates that user's sessions and audits the reset. It cannot create a user or guess an email. Someone with OS-level write access to the database can change accounts; protect that OS account and its storage.

## Research hygiene

Public business email availability does not prove interest, current cash availability or agreement to an equity/unsecured transaction. Keep source dates and provenance, mark missing fields explicitly, and distinguish organization types from confirmed lender fit. Fund assets, lender origination volume or an SEC registration cannot by themselves establish deployable $500,000 cash for this offer. Suppression is maintained across duplicate imports; use it for recipients who should not be contacted. CSV exports neutralize leading spreadsheet formula text.

The application provides no automatic communications, no guarantee calculations and no automatic claim of executed financing. The supplied return and contract economics remain estimates/proposals until evidence supports stronger statements.

## Verification

Run `python3 -m unittest discover -s tests -v`. The integration suite starts ephemeral loopback HTTP servers and temporary databases. It verifies bootstrap locking, real password hashing, session expiry/revocation, CSRF/origin/Host protections, role enforcement, last-administrator protection, imported provenance/deduplication/suppression, search and counts, notes/tasks, exports, consistent sanitized snapshots, validation and sign-in throttling.
