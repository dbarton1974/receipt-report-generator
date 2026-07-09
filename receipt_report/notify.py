"""Sends a failure notice by email when a scheduled run fails.

Called by the CI workflow in a step that only runs on failure (`if: failure()`).
Recipient is NOTIFY_RECIPIENT, falling back to IMAP_USER. An optional RUN_URL is
included so you can jump straight to the failed run.
"""

from __future__ import annotations

import datetime as dt
import os

from .config import load_config
from .mailer import send_notification


def main() -> int:
    config = load_config()
    recipient = config.notify_recipient or config.imap_user
    run_url = os.getenv("RUN_URL", "").strip()
    today = dt.date.today().isoformat()

    subject = f"⚠️ receipt-report run failed {today}"
    body = (
        f"The scheduled receipt-report run failed on {today}.\n\n"
        f"Check the log and re-run if needed.\n"
    )
    if run_url:
        body += f"\nRun log:\n{run_url}\n"

    send_notification(
        smtp_host=config.smtp_host, smtp_port=config.smtp_port, security=config.smtp_security,
        username=config.imap_user, password=config.imap_password,
        sender=config.imap_user, recipient=recipient, subject=subject, body=body,
    )
    print(f"Sent failure notice to {recipient}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
