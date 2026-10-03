# Use CapitalForge by 101XVC

CapitalForge runs on your computer. Install Python 3.11 or newer; no additional Python packages, API keys, paid services, or build step are required. Your records are saved in a local SQLite database.

## 1. Download and start on Windows

1. Open [101XCAPITALFORGE on GitHub](https://github.com/plyon-git/101XCAPITALFORGE).
2. If the October 2 trial-funding update is still awaiting merge, select branch **codex/trial-capital-sourcing-20261002** first. Click **Code**, then **Download ZIP**. In File Explorer, right-click the downloaded ZIP and choose **Extract All**.
3. Open the extracted project folder. Confirm it contains `app.py`, `start-windows.bat`, `static`, and `data`. Run the application from this extracted folder, not from inside the ZIP.
4. Install **Python 3.11 or newer** from [python.org](https://www.python.org/downloads/). Enable the installer option to add Python to PATH when offered.
5. Double-click **start-windows.bat**. Keep its terminal window open while using the CRM.
6. The launcher opens your browser automatically. If it does not, open [http://127.0.0.1:8787/app](http://127.0.0.1:8787/app).

If double-clicking does not work, open Terminal in the extracted project folder and run:

```powershell
py -3 app.py --open-browser
```

If `py` is unavailable but `python --version` reports Python 3.11 or newer, run:

```powershell
python app.py --open-browser
```

If port 8787 is already in use, run `py -3 app.py --port 8788 --open-browser` and open `http://127.0.0.1:8788/app`.

## 2. Start on macOS or Linux

Extract the ZIP and install Python 3.11 or newer first.

| Computer | Start from the project folder | Portal |
| --- | --- | --- |
| macOS | Double-click `start-mac.command`, or run `python3 app.py --open-browser` in Terminal | `http://127.0.0.1:8787/app` |
| Linux | Run `sh start-linux.sh`, then open the portal manually | `http://127.0.0.1:8787/app` |

If macOS blocks the launcher or reports a permission error, use the Terminal command above. Keep the terminal open. Use `python3 app.py --port 8788` if port 8787 is occupied.

## 3. Create the first account

1. At **Create your workspace**, enter **Your name**, **Email address**, and a **Password** of at least 12 characters.
2. Leave **Bootstrap token (for remote setup)** empty when starting on your own computer through `127.0.0.1`.
3. Click **Create administrator account**. There is no default username or password.
4. For additional accounts, open **Administration**, choose **Team members**, then **+ Add team member**.

Administrators manage the workspace and accounts. Analysts can edit records, research, and tasks. Viewers can read and export. Separate accounts on a shared installation use the same server and database; starting a separate copy on another computer creates a separate workspace.

## 4. Find the $100K to $500K sourcing cohort

1. Click **Lender directory** in the left sidebar.
2. In the search box, enter exactly:

   ```text
   trial-100k-500k-2026-10-02
   ```

3. The targeted cohort is loaded automatically at startup. It appears alongside the existing directory; no manual import is needed for the bundled cohort.
4. Choose **Not suppressed** in the suppression filter before selecting prospects for outreach.
5. Leave **All capacity evidence** selected initially. **Documented $500K+** only returns records with documented cash of at least $500,000; it excludes smaller tickets and research prospects whose availability remains unconfirmed.
6. Use **All financing fits** for the full cohort, or select **Potential fit** or **Strong fit** individually. Use **Phone + email** only when you need both contact fields; otherwise it hides sources with a useful application form or one contact channel.
7. Click a relationship row to open its record. Use the bottom page arrows to browse further results.

The search also supports company, contact, email, phone, state, financier type, and tags. Clear the cohort text to search the broader existing directory. Filters persist while moving between views, so clear any old stage or fit filters if results are unexpectedly missing.

For the broader list of 2,500 potential capital prospects, search `investor-2500-2026-10-02` instead. Read **Prospect campaign review** in each record. It includes property investors and home-buying operators alongside private-capital and financing sources; the narrower trial cohort remains separately searchable. See [the campaign guide](INVESTOR_2500.md) for selection, counts and portable files.

## 5. Review and work a prospect

1. In the open record, read **Trial funding review**, **Capacity & financing fit**, **Source evidence**, and **Original research context**. Open the recorded sources to check the program and contact route.
2. Confirm the actual check size, eligibility of operating or marketing expenses, treatment of contingent assignment fees, underwriting requirements, guarantees, timing, and funding decision maker.
3. Under **Relationship controls**, change **Pipeline stage** and **Financing fit** as you review the prospect. These changes save immediately.
4. Under **Relationship notes**, type the conversation or research result into **Add a note**, then click **Save note**.
5. Click **+ Add follow-up**, enter **Task title**, **Due date**, and **Status**, then click **Create task**. This task is linked to the open relationship.
6. Click **Edit full record** to add **Assigned owner**, check range, evidence, source dates, or updated contact details. Click **Save relationship** to save that form.
7. Check **Do not contact this relationship** when outreach should be suppressed. This disables its email and call links and survives duplicate imports.

The pipeline stages are **New**, **Reviewing**, **Qualified**, **Contacted**, **Due diligence**, **Terms**, **Closed**, and **Passed**. Open **Relationship pipeline** to review stage groups; change a record's stage inside its relationship drawer. Open **Tasks & follow-ups** to see linked and general tasks, filter their status, or mark them **Completed** or **Cancelled**.

A published financing range establishes a program size, not cash available to your company. Keep **Capacity evidence level** at **Unverified** until direct evidence supports a stronger status. Record the particular offered amount rather than assigning every source a $500,000 capacity. Clicking an email or phone link opens your email or calling application; CapitalForge does not send messages itself.

## 6. Add, import, and export records

**Add one relationship:** click **+ Add relationship** in the top-right corner, fill in the supported fields, then click **Save relationship**. At least a company or contact name is required.

**Import a file:**

1. Create a backup first using the instructions below.
2. Open **Lender directory**, then click **Import records**.
3. Choose a CSV, JSON, or JSONL file, then click **Import records** in the dialog. Files may be up to 100 MB. CSV requires a header row. JSON accepts an array or an `items` / `rows` array.
4. Read the import result for added, merged, and invalid records. Existing matching records are merged while preserving workflow, ownership, verified research, and suppression.

Leave unavailable fields blank. Do not fill cash capacity from fund assets or program maximums. If a batch import stops partway through, completed batches remain saved; check the result before retrying.

**Export the shortlist:** keep your cohort search and desired filters active, click **Export**, then **Download filtered CSV**. This exports all matching records across pages, not just the currently displayed page.

**Export all relationships:** click **Export**, then **Download full JSON**. JSON exports ignore directory filters. The **Export directory** button on **Overview** exports the full directory as CSV.

Directory exports are for portable relationship data. Use a database backup to preserve the complete workspace, including accounts, relationship notes, and tasks.

## 7. Update the deal workspace

Open **Deal workspace**, then **Edit mandate** as an administrator. Enter the current raise, financing alternatives, estimated fees, timing, follow-on conditions, and **Internal diligence notes**, then click **Save mandate**.

Store private agreement details in your local workspace. The public repository and downloadable project should contain application code and public prospect research. Review the mandate when reusing an existing database because saved deal inputs are retained across software updates.

## 8. Back up, stop, restart, and update

**Back up:** open **Administration**, choose **Account & workspace**, then click **Create & download backup**. Save the downloaded database outside the project folder. The app also saves snapshots under `runtime/backups/`. Backups include accounts, records, notes, tasks, and workspace settings; active login sessions are removed.

**Stop:** click the terminal window and press **Ctrl+C**. Closing the browser alone does not stop the server.

**Restart:** run the same launcher from the same project folder. Open the portal and sign in using your existing account. Records persist in `runtime/capitalforge.sqlite3`; restarting does not clear your work.

**Move computers:** stop the server, copy the complete project including the whole `runtime` folder, install Python on the new computer, then run the appropriate launcher. Keep the database private.

**Update a ZIP installation:** back up and stop the server first. Extract the new project into a new folder, copy the complete `runtime` folder from the previous installation into it, then start the new copy. Do not run both copies against the same database at once. Bundled source updates merge into existing records without resetting reviewed workflow states or suppression.

**Update a Git installation:** back up and stop first, then run `git pull --ff-only` from the repository folder and restart. The ignored `runtime` folder stays in place.

For backup restoration or forgotten-password recovery, see [Operations and data protection](BACKEND_SECURITY.md). For hosting the same application under your own domain, see [HOSTING.md](../HOSTING.md).
