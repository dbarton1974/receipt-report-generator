"""CLI orchestration: fetch receipts, build the report PDF, mark and optionally email."""

from __future__ import annotations

import argparse
import datetime as dt
import sys

from .config import Config, load_config
from .mail_client import MailClient
from .mailer import send_report
from .pdf_builder import ReceiptEntry, build_final_pdf, format_amount
from .receipt_parser import parse_receipt


def _build_entries(config: Config) -> tuple[list[ReceiptEntry], set[str], list[str]]:
    """Fetches and parses receipts. Returns (entries, uids_to_move, warnings)."""
    warnings: list[str] = []
    work_dir = config.output_dir / "_work"

    with MailClient(
        config.imap_host, config.imap_port, config.imap_user, config.imap_password
    ) as mail:
        fetch = mail.fetch_receipts(config.inbox_folder, config.receipt_sender, work_dir)

    if fetch.emails_without_pdf:
        warnings.append(
            f"{fetch.emails_without_pdf} email(s) from {config.receipt_sender} had no PDF "
            f"attachment and were skipped."
        )

    parsed: list[tuple] = []  # (date, description, amount, pdf_path)
    for pdf in fetch.pdfs:
        result = parse_receipt(pdf.path, config.description_match)
        warnings.extend(result.warnings)
        date = result.date or pdf.email_date.date()
        description = result.description or pdf.subject or "Receipt"
        parsed.append((date, description, result.amount, pdf.path))

    parsed.sort(key=lambda r: r[0])
    entries = [
        ReceiptEntry(index=i, date=d, description=desc, amount=amt, pdf_path=path)
        for i, (d, desc, amt, path) in enumerate(parsed, start=1)
    ]
    return entries, fetch.processed_uids, warnings


def _send_report(config: Config, output_path, today) -> bytes:
    """Emails the report to the archive recipient. Returns the message bytes."""
    subject = f"Expense report {today.isoformat()}"
    body = (
        f"Hi,\n\nAttached is the expense report ({subject}) for {config.recipient_name}.\n"
        f"It contains a cover summary and all receipts as an appendix.\n\n"
        f"Best regards\n{config.recipient_name}"
    )
    raw = send_report(
        smtp_host=config.smtp_host, smtp_port=config.smtp_port, security=config.smtp_security,
        username=config.imap_user, password=config.imap_password,
        sender=config.imap_user, recipient=config.archive_recipient,
        subject=subject, body=body, pdf_path=output_path,
    )
    print(f"  Emailed the PDF to {config.archive_recipient} (subject: {subject})")
    return raw


def run(dry_run: bool = False, send_email: bool = True) -> int:
    config = load_config()
    entries, processed_uids, warnings = _build_entries(config)

    if not entries:
        print(f"No new receipts found in {config.inbox_folder} from {config.receipt_sender}.")
        for w in warnings:
            print(f"  ! {w}")
        return 0

    today = dt.date.today()
    output_path = config.output_dir / f"expense-report_{today.isoformat()}.pdf"
    build_final_pdf(
        config.report_title, config.recipient_name, today, entries,
        output_path, config.currency, config.purpose,
    )

    total = sum(e.amount for e in entries if e.amount is not None)
    print(f"* Created {output_path}")
    print(f"  Receipts: {len(entries)}")
    print(f"  Total: {format_amount(total, config.currency)}")

    if dry_run:
        print("  (dry-run: emails left in the inbox, nothing sent)")
    else:
        with MailClient(
            config.imap_host, config.imap_port, config.imap_user, config.imap_password
        ) as mail:
            folder = mail.move_processed(
                config.inbox_folder, config.processed_folder, processed_uids
            )
        print(f"  Moved {len(processed_uids)} email(s) to {folder or config.processed_folder}")

        if send_email and config.archive_recipient:
            raw = _send_report(config, output_path, today)
            with MailClient(
                config.imap_host, config.imap_port, config.imap_user, config.imap_password
            ) as mail:
                sent_folder = mail.save_to_sent(raw)
            print(f"  Saved a copy in {sent_folder}")
        elif send_email and not config.archive_recipient:
            print("  (ARCHIVE_RECIPIENT not set — report not emailed)")

    if warnings:
        print("\nWarnings (check these receipts manually):")
        for w in warnings:
            print(f"  ! {w}")

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="receipt-report",
        description="Collect emailed receipts into a single expense-report PDF.",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Build the PDF but leave emails in the inbox and send nothing (for testing).",
    )
    parser.add_argument(
        "--no-email", action="store_true",
        help="Run for real (move emails) but do not email the report.",
    )
    args = parser.parse_args(argv)
    return run(dry_run=args.dry_run, send_email=not args.no_email)


if __name__ == "__main__":
    sys.exit(main())
