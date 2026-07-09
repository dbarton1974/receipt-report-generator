# receipt-report-generator

Turn receipts that land in your inbox into a single, tidy **expense-report PDF** — a cover
sheet that summarises every receipt with a running total, followed by each original receipt
as an indexed appendix. Optionally emails the finished PDF onwards and files the processed
messages away so they are never counted twice.

Originally built to collect public-transport receipts for monthly bookkeeping, it is
**metadata-driven**: point it at any sender, any IMAP mailbox, and any currency.

## What it does

1. Connects to your mailbox over **IMAP**.
2. Finds every email from a configured **sender** that has a **PDF attachment**.
3. Reads the **amount** and **date** out of each receipt PDF.
4. Builds one PDF:
   - **Cover sheet** — a title, today's date, and a table of `# | Date | Description |
     (Purpose) | Amount`, ending in a **Total**.
   - **Appendix** — every original receipt, stamped `Appendix N` to match its table row,
     with PDF bookmarks.
5. **Moves** the processed emails to a folder so the next run only sees new receipts.
6. *(Optional)* **Emails** the PDF to an archive address and saves a copy in your Sent folder.
7. *(Optional, in CI)* **Emails you** if a scheduled run fails.

Because "what's already processed" is represented by *moving the emails out of the inbox*,
there is no database or local state to maintain — the mailbox is the single source of truth,
which is what makes running it in the cloud trivial.

## Requirements

- Python 3.10+
- An email account reachable over IMAP + SMTP (see [supported servers](#supported-mail-servers))

## Installation

```bash
git clone https://github.com/<you>/receipt-report-generator.git
cd receipt-report-generator
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # then edit .env
```

Or install it as a package to get the `receipt-report` command on your PATH:

```bash
pip install git+https://github.com/<you>/receipt-report-generator.git
# then, in a directory containing your .env:
receipt-report --dry-run
```

## Configuration

All configuration is via environment variables (read from `.env` locally, or injected by
your host in the cloud). The most important ones:

| Variable | Description |
| --- | --- |
| `MAIL_PROVIDER` | A preset from [`providers.json`](receipt_report/providers.json) (`gmail`, `outlook`, `icloud`, …). Fills in IMAP/SMTP host, port and security. |
| `IMAP_USER` / `IMAP_PASSWORD` | Mailbox login. Use an **app password** where the provider supports one. |
| `RECEIPT_SENDER` | Sender address of the receipts. A substring works (e.g. `sl.se`). |
| `PROCESSED_FOLDER` | Where processed emails are moved (default `Processed/Receipts`, created if missing). |
| `RECIPIENT_NAME` / `REPORT_TITLE` | Name and cover title (`{name}` is substituted). |
| `CURRENCY` | Label after each amount (default `kr`). |
| `PURPOSE` | Optional value for a "Purpose" column; empty hides the column. |
| `DESCRIPTION_MATCH` | Optional regex to extract a description from the receipt text. |
| `ARCHIVE_RECIPIENT` | If set, the report is emailed here on a real run. |
| `NOTIFY_RECIPIENT` | Where CI failure notices go (defaults to `IMAP_USER`). |

To use a server not in the presets, leave `MAIL_PROVIDER` empty and set `IMAP_HOST`,
`IMAP_PORT`, `SMTP_HOST`, `SMTP_PORT` and `SMTP_SECURITY` (`ssl` or `starttls`) directly.
See [`.env.example`](.env.example) for the full list.

## Supported mail servers

Presets live in [`providers.json`](receipt_report/providers.json) and are easy to extend.

| `MAIL_PROVIDER` | Service | IMAP | SMTP |
| --- | --- | --- | --- |
| `gmail` | Gmail / Google Workspace | imap.gmail.com:993 | smtp.gmail.com:465 (SSL) |
| `outlook` | Outlook.com / Hotmail | outlook.office365.com:993 | smtp-mail.outlook.com:587 (STARTTLS) |
| `office365` | Microsoft 365 (work/school) | outlook.office365.com:993 | smtp.office365.com:587 (STARTTLS) |
| `icloud` | iCloud Mail | imap.mail.me.com:993 | smtp.mail.me.com:587 (STARTTLS) |
| `yahoo` | Yahoo Mail | imap.mail.yahoo.com:993 | smtp.mail.yahoo.com:465 (SSL) |
| `fastmail` | Fastmail | imap.fastmail.com:993 | smtp.fastmail.com:465 (SSL) |
| `gmx` | GMX | imap.gmx.com:993 | mail.gmx.com:465 (SSL) |
| `zoho` | Zoho Mail | imap.zoho.com:993 | smtp.zoho.com:465 (SSL) |
| `opensrs` | OpenSRS / Tucows Hosted Email | imap.hostedemail.com:993 | smtp.hostedemail.com:465 (SSL) |

Any IMAP/SMTP server works via explicit host settings — the presets are just conveniences.

## Setting up your mail account

Most providers need two things:

1. **IMAP access enabled.** On by default for many; for some (Yahoo, GMX, Zoho) you toggle
   it in settings.
2. **An app password** if the account uses 2-factor authentication. The generator logs in
   with a plain username + password, so create a provider-specific *app password* and use it
   as `IMAP_PASSWORD`:
   - **Gmail:** Google Account → Security → App passwords (requires 2-Step Verification).
   - **iCloud:** appleid.apple.com → Sign-In and Security → App-Specific Passwords.
   - **Yahoo / Fastmail / Zoho:** Account security → generate an app password.
   - **OpenSRS/hosted email:** usually the normal mailbox password works.

> **Microsoft note:** Outlook.com and many Microsoft 365 tenants have disabled basic
> IMAP/SMTP auth. If password login is refused, an admin may need to allow it, or the account
> may require OAuth (not handled by this tool).

The same account is used both to **read** receipts and to **send** the report, so make sure
SMTP submission is allowed too. The per-provider notes in `providers.json` summarise this.

## Usage

Dry run (build the PDF; touch nothing in the mailbox):

```bash
python -m receipt_report.main --dry-run
```

Real run (build the PDF, move processed emails, and email the report if `ARCHIVE_RECIPIENT`
is set):

```bash
python -m receipt_report.main
```

Real run without emailing:

```bash
python -m receipt_report.main --no-email
```

Output lands in `output/expense-report_<YYYY-MM-DD>.pdf`.

## Run it in the cloud (GitHub Actions)

[`.github/workflows/monthly.yml`](.github/workflows/monthly.yml) runs the generator on the
**last day of each month** — no machine of your own needs to be on.

Set these in your repository (**Settings → Secrets and variables → Actions**):

**Secrets** (sensitive):

| Secret | Value |
| --- | --- |
| `IMAP_USER` | Your mailbox address |
| `IMAP_PASSWORD` | App password / mailbox password |
| `ARCHIVE_RECIPIENT` | *(optional)* where to email the report |

**Variables** (non-sensitive):

| Variable | Example |
| --- | --- |
| `MAIL_PROVIDER` | `gmail` |
| `RECEIPT_SENDER` | `receipts@vendor.com` |
| `RECIPIENT_NAME` | `Jane Doe` |
| `CURRENCY` | `kr` |
| `PURPOSE` | *(optional)* |

Then:

- **Test anytime:** Actions tab → *Monthly expense report* → **Run workflow**. A manual run
  skips the last-day guard and runs immediately.
- **Test the failure alert:** run the workflow with the **test_fail** input checked — it forces
  a failure and emails `NOTIFY_RECIPIENT` (or `IMAP_USER`).
- The generated PDF is also kept as a **run artifact** for 90 days.
- Scheduled workflows only run on the repository's default branch.

## Customising the parsing

Receipt layouts vary. The parser ([`receipt_parser.py`](receipt_report/receipt_parser.py)) is
built to be tuned:

- **Amounts** are matched in both `1,234.50` and `1 234,50` styles; lines containing keywords
  like *total*, *amount due*, *summa* are preferred, otherwise the largest amount wins.
- **Dates** are read as ISO, `dd.mm.yyyy`, or `12 June 2026` (English + Swedish month names),
  falling back to the email's date.
- **Descriptions** default to the first meaningful text line; set `DESCRIPTION_MATCH` to a
  regex to grab something specific (group 1 if present).

Receipts where an amount or date can't be read are still included and listed as warnings so
you can check them.

## Security

- Credentials live only in `.env` (git-ignored) or your host's secret store. Nothing sensitive
  is committed.
- The processed-email move happens **after** the PDF is written successfully, so an interrupted
  run never loses receipts.

## License

[MIT](LICENSE)
