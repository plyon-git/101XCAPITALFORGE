# Host CapitalForge under your own domain

The CRM runs without any ChatGPT hosting service. The package contains the same frontend and Python backend used locally. A static HTML host alone cannot run the authentication and database backend.

## Conventional server with Docker

1. Rent or use a Linux server with Docker Engine and the Docker Compose plugin installed. Copy this whole application folder to it.
2. Point a hostname such as `crm.yourdomain.com` to the server's public IP using your domain's DNS settings. Allow inbound TCP 80 and 443; Caddy handles certificates and redirects HTTP to HTTPS.
3. In the application folder, run:

   ```bash
   python3 scripts/configure_hosting.py --domain crm.yourdomain.com
   docker compose up -d --build
   ```

   The configuration helper creates a new `.env` with a random first-account setup token. It refuses to overwrite existing configuration.

4. Open `https://crm.yourdomain.com/app`, enter the setup token when creating the first administrator, and choose your own password.
5. Remove the setup token's value from `.env` after setup and run `docker compose up -d` again. The administrator account persists in the `crm_data` volume. The app container has no public port; Caddy is its public entry point.
6. Add team accounts in the administrator workspace. Viewers can read records; analysts can maintain the pipeline; administrators manage users, exports, and snapshots.

Use `docker compose logs --tail 100 app` to inspect startup and `docker compose ps` to check health. The first launch imports the directory before reporting ready; wait for that import to finish. A copied local `runtime/` is not automatically used by the Docker volume. For migration, use the CRM export/import workflow or intentionally place a stopped database into the named volume with the correct UID 10001 file ownership.

## Run without Docker

You can run `python3 app.py` with a process manager and Caddy or Nginx on a conventional VPS. Bind the Python server to loopback and reverse-proxy to it. Configure:

```text
CAPITALFORGE_HOST=127.0.0.1
CAPITALFORGE_PORT=8787
CAPITALFORGE_ALLOWED_HOSTS=crm.yourdomain.com,localhost,127.0.0.1
CAPITALFORGE_SECURE_COOKIES=1
CAPITALFORGE_DATA_DIR=/absolute/path/to/persistent/crm-data
```

Preserve the incoming `Host` header. Either create the first administrator through a local connection before public hosting, or set a newly generated `CAPITALFORGE_BOOTSTRAP_TOKEN` for remote setup and remove it afterward. The app rejects remote first-account setup without that token. Do not expose an unfinished setup portal with an empty or publicly known token.

## Persistence and recovery

The application uses a single SQLite database. Keep its data directory or Docker volume on persistent disk. Back up using the application's snapshot control. Protect snapshots as you would the CRM: they contain contact records, notes, and password hashes. Restored snapshots require users to sign in again.

Keep the hostname allowlist and secure-cookie option aligned with the actual HTTPS deployment. The public entry page contains no contact directory; authenticated APIs serve the working data. The package does not include a managed email service, domain, rented server, or outbound messaging provider.

## Validation status

The local application and its login/API workflows were tested during assembly. The Docker/Caddy files are supplied for a conventional deployment; a live public domain and certificate cannot be tested until you configure the actual DNS and server.
