"""Configuration, loaded from environment variables (12-factor / metadata-driven).

A named preset from providers.json can be selected with MAIL_PROVIDER, which fills in
IMAP/SMTP host, port and security. Any explicit host/port/security env var overrides it.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # python-dotenv is optional; in CI the vars are set directly.
    def load_dotenv(*args, **kwargs):  # type: ignore[misc]
        return False

from .providers import get_provider


@dataclass(frozen=True)
class Config:
    # IMAP
    imap_host: str
    imap_port: int
    imap_user: str
    imap_password: str
    # SMTP
    smtp_host: str
    smtp_port: int
    smtp_security: str  # "ssl" or "starttls"
    # What to collect
    receipt_sender: str
    inbox_folder: str
    processed_folder: str
    # Report
    output_dir: Path
    recipient_name: str
    report_title: str
    purpose: str        # empty string => no "Purpose" column
    currency: str
    description_match: str  # optional regex to extract a description; empty => first line
    # Delivery / alerts
    archive_recipient: str  # empty => don't email the report
    notify_recipient: str   # empty => defaults to imap_user


def _require(name: str, value: str) -> str:
    if not value:
        raise SystemExit(
            f"Configuration error: {name} is missing. "
            f"Copy .env.example to .env and fill in the values."
        )
    return value


def load_config() -> Config:
    load_dotenv()

    # Resolve provider preset (if any) for host/port/security defaults.
    provider_key = os.getenv("MAIL_PROVIDER", "").strip()
    preset = get_provider(provider_key) if provider_key else None
    if provider_key and preset is None:
        raise SystemExit(
            f"Unknown MAIL_PROVIDER '{provider_key}'. See providers.json for valid keys, "
            f"or set IMAP_HOST/SMTP_HOST explicitly instead."
        )

    def _host_default(env_name: str, preset_value: str | None) -> str:
        return os.getenv(env_name, "").strip() or (preset_value or "")

    imap_host = _host_default("IMAP_HOST", preset.imap_host if preset else None)
    smtp_host = _host_default("SMTP_HOST", preset.smtp_host if preset else None)

    imap_port = int(os.getenv("IMAP_PORT", str(preset.imap_port if preset else 993)))
    smtp_port = int(os.getenv("SMTP_PORT", str(preset.smtp_port if preset else 465)))
    smtp_security = (
        os.getenv("SMTP_SECURITY", "").strip().lower()
        or (preset.smtp_security if preset else "ssl")
    )

    recipient_name = os.getenv("RECIPIENT_NAME", "Me")
    report_title = os.getenv("REPORT_TITLE", "Expense report for {name}").replace(
        "{name}", recipient_name
    )

    return Config(
        imap_host=_require("IMAP_HOST (or MAIL_PROVIDER)", imap_host),
        imap_port=imap_port,
        imap_user=_require("IMAP_USER", os.getenv("IMAP_USER", "").strip()),
        imap_password=_require("IMAP_PASSWORD", os.getenv("IMAP_PASSWORD", "").strip()),
        smtp_host=smtp_host or imap_host,
        smtp_port=smtp_port,
        smtp_security=smtp_security,
        receipt_sender=_require("RECEIPT_SENDER", os.getenv("RECEIPT_SENDER", "").strip()),
        inbox_folder=os.getenv("INBOX_FOLDER", "INBOX"),
        processed_folder=os.getenv("PROCESSED_FOLDER", "Processed/Receipts"),
        output_dir=Path(os.getenv("OUTPUT_DIR", "./output")).expanduser(),
        recipient_name=recipient_name,
        report_title=report_title,
        purpose=os.getenv("PURPOSE", "").strip(),
        currency=os.getenv("CURRENCY", "kr"),
        description_match=os.getenv("DESCRIPTION_MATCH", "").strip(),
        archive_recipient=os.getenv("ARCHIVE_RECIPIENT", "").strip(),
        notify_recipient=os.getenv("NOTIFY_RECIPIENT", "").strip(),
    )
