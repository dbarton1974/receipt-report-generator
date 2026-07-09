"""Sends the report PDF (and failure notices) over SMTP from the same account."""

from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from pathlib import Path


def _connect(smtp_host: str, smtp_port: int, security: str) -> smtplib.SMTP:
    """Opens an SMTP connection using SSL or STARTTLS depending on `security`."""
    context = ssl.create_default_context()
    if security.lower() == "starttls":
        smtp = smtplib.SMTP(smtp_host, smtp_port, timeout=30)
        smtp.ehlo()
        smtp.starttls(context=context)
        smtp.ehlo()
        return smtp
    return smtplib.SMTP_SSL(smtp_host, smtp_port, context=context, timeout=30)


def _base_message(sender: str, recipient: str, subject: str, body: str) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=sender.split("@")[-1])
    msg.set_content(body)
    return msg


def send_report(
    smtp_host: str, smtp_port: int, security: str,
    username: str, password: str, sender: str, recipient: str,
    subject: str, body: str, pdf_path: Path,
) -> bytes:
    """Sends an email with the PDF attached. Returns the message bytes (for a Sent copy)."""
    msg = _base_message(sender, recipient, subject, body)
    msg.add_attachment(
        pdf_path.read_bytes(), maintype="application", subtype="pdf", filename=pdf_path.name
    )
    with _connect(smtp_host, smtp_port, security) as smtp:
        smtp.login(username, password)
        smtp.send_message(msg)
    return msg.as_bytes()


def send_notification(
    smtp_host: str, smtp_port: int, security: str,
    username: str, password: str, sender: str, recipient: str,
    subject: str, body: str,
) -> None:
    """Sends a plain-text email with no attachment (e.g. a failure notice)."""
    msg = _base_message(sender, recipient, subject, body)
    with _connect(smtp_host, smtp_port, security) as smtp:
        smtp.login(username, password)
        smtp.send_message(msg)
