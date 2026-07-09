"""IMAP client: fetches receipt emails, downloads PDF attachments, moves processed mail."""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field
from pathlib import Path

from imap_tools import AND, MailBox


@dataclass
class FetchedPdf:
    """A downloaded PDF attachment linked to its email."""

    uid: str
    email_date: dt.datetime
    subject: str
    sender: str
    filename: str
    path: Path


@dataclass
class FetchResult:
    pdfs: list[FetchedPdf] = field(default_factory=list)
    # UIDs of emails that contained at least one PDF (to mark as processed).
    processed_uids: set[str] = field(default_factory=set)
    emails_without_pdf: int = 0


def _safe_filename(name: str) -> str:
    name = name or "receipt.pdf"
    name = name.replace("/", "_").replace("\\", "_")
    name = re.sub(r"[^\w.\- ]", "_", name)
    return name.strip() or "receipt.pdf"


class MailClient:
    def __init__(self, host: str, port: int, user: str, password: str):
        self._host = host
        self._port = port
        self._user = user
        self._password = password
        self._box: MailBox | None = None

    def __enter__(self) -> "MailClient":
        self._box = MailBox(self._host, self._port).login(self._user, self._password)
        return self

    def __exit__(self, *exc) -> None:
        if self._box is not None:
            self._box.logout()
            self._box = None

    @property
    def box(self) -> MailBox:
        if self._box is None:
            raise RuntimeError("MailClient used outside of a 'with' context.")
        return self._box

    def fetch_receipts(
        self, inbox_folder: str, sender: str, work_dir: Path
    ) -> FetchResult:
        """Fetches all emails from `sender` in the inbox and downloads PDF attachments."""
        self.box.folder.set(inbox_folder)
        work_dir.mkdir(parents=True, exist_ok=True)

        result = FetchResult()
        for msg in self.box.fetch(AND(from_=sender), mark_seen=False):
            pdf_atts = [
                att
                for att in msg.attachments
                if (att.filename or "").lower().endswith(".pdf")
                or att.content_type == "application/pdf"
            ]
            if not pdf_atts:
                result.emails_without_pdf += 1
                continue

            result.processed_uids.add(msg.uid)
            for i, att in enumerate(pdf_atts):
                filename = _safe_filename(att.filename or f"receipt_{msg.uid}_{i}.pdf")
                # Prefix with UID to avoid collisions between emails sharing a filename.
                path = work_dir / f"{msg.uid}_{i}_{filename}"
                path.write_bytes(att.payload)
                result.pdfs.append(
                    FetchedPdf(
                        uid=msg.uid,
                        email_date=msg.date,
                        subject=msg.subject or "",
                        sender=msg.from_ or "",
                        filename=filename,
                        path=path,
                    )
                )
        return result

    def _server_delimiter(self) -> str:
        """Reads the server's folder hierarchy delimiter (e.g. '.' or '/')."""
        for f in self.box.folder.list():
            if f.delim:
                return f.delim
        return "/"

    def move_processed(self, inbox_folder: str, processed_folder: str, uids: set[str]) -> str:
        """Moves the given emails into the processed folder (created if needed).

        The folder is written with '/' as separator in config; it is translated to the
        server's own delimiter, so 'Processed/Receipts' works even on servers that use
        '.' and forbid '/' in mailbox names. Returns the actual folder name used.
        """
        if not uids:
            return ""

        delim = self._server_delimiter()
        target = processed_folder.replace("/", delim)

        existing = {f.name for f in self.box.folder.list()}
        if target not in existing:
            parts = target.split(delim)
            for i in range(1, len(parts) + 1):
                sub = delim.join(parts[:i])
                if sub not in existing:
                    self.box.folder.create(sub)
                    existing.add(sub)

        self.box.folder.set(inbox_folder)
        self.box.move(list(uids), target)
        return target

    def _sent_folder(self) -> str:
        """Finds the Sent folder (special-use \\Sent), with sensible fallbacks."""
        folders = self.box.folder.list()
        for f in folders:
            if "\\Sent" in f.flags:
                return f.name
        names = {f.name for f in folders}
        for candidate in ("Sent", "Sent Items", "Sent Mail", "Skickat"):
            if candidate in names:
                return candidate
        return "Sent"

    def save_to_sent(self, raw_message: bytes) -> str:
        """Appends a copy of a sent message to the Sent folder (marked read)."""
        folder = self._sent_folder()
        self.box.append(raw_message, folder, flag_set=["\\Seen"])
        return folder
