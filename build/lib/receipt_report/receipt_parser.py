"""Parses a receipt PDF: extracts amount, date and a short description.

The patterns are deliberately broad and multilingual so they work across many receipt
layouts. Amounts are matched in both '1,234.50' and '1 234,50' styles. On a miss the
raw text is returned so patterns can be tuned; set DESCRIPTION_MATCH to a custom regex
if the first text line is not a good description for your receipts.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber

# Keywords that usually sit next to the total on a receipt (lowercase, multilingual).
_AMOUNT_KEYWORDS = (
    "total",
    "totalt",
    "grand total",
    "amount due",
    "amount",
    "sum",
    "summa",
    "att betala",
    "to pay",
    "belopp",
    "balance",
)

# A monetary amount in either '1,234.50' / '1234.50' or '1 234,50' / '1234,50' style.
_AMOUNT_RE = re.compile(r"\d{1,3}(?:[ .,]\d{3})*[.,]\d{2}\b")

# Month names for date parsing (English + Swedish).
_MONTHS = {
    "january": 1, "februari": 2, "february": 2, "januari": 1, "march": 3, "mars": 3,
    "april": 4, "may": 5, "maj": 5, "june": 6, "juni": 6, "july": 7, "juli": 7,
    "august": 8, "augusti": 8, "september": 9, "october": 10, "oktober": 10,
    "november": 11, "december": 12,
}


@dataclass
class ParsedReceipt:
    amount: float | None
    date: dt.date | None
    description: str
    warnings: list[str] = field(default_factory=list)
    raw_text: str = ""


def _to_float(raw: str) -> float | None:
    """Parses an amount string in either English or European style to a float."""
    s = raw.strip().replace(" ", "").replace(" ", "")
    if "," in s and "." in s:
        # The last separator is the decimal one.
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        # Comma is the decimal separator (European style).
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _extract_amount(text: str) -> float | None:
    """Finds the total. Prefers lines with a keyword, otherwise the largest amount."""
    keyword_amounts: list[float] = []
    all_amounts: list[float] = []

    for line in text.splitlines():
        lowered = line.lower()
        line_amounts = [
            v for m in _AMOUNT_RE.findall(line) if (v := _to_float(m)) is not None
        ]
        all_amounts.extend(line_amounts)
        if any(kw in lowered for kw in _AMOUNT_KEYWORDS):
            keyword_amounts.extend(line_amounts)

    if keyword_amounts:
        return max(keyword_amounts)
    if all_amounts:
        return max(all_amounts)
    return None


def _extract_date(text: str) -> dt.date | None:
    """Finds a date in the PDF text: ISO, dotted/slashed, or month-name formats."""
    m = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", text)
    if m:
        try:
            return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass

    m = re.search(r"\b(\d{2})[./](\d{2})[./](\d{4})\b", text)
    if m:
        try:
            return dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            pass

    m = re.search(r"\b(\d{1,2})\s+([A-Za-zÀ-ÿ]+)\s+(\d{4})\b", text)
    if m and m.group(2).lower() in _MONTHS:
        try:
            return dt.date(int(m.group(3)), _MONTHS[m.group(2).lower()], int(m.group(1)))
        except ValueError:
            pass

    return None


def _extract_description(text: str, description_match: str) -> str:
    """Picks a short description. Uses DESCRIPTION_MATCH regex if provided."""
    if description_match:
        m = re.search(description_match, text, re.IGNORECASE)
        if m:
            grabbed = (m.group(1) if m.groups() else m.group(0)).strip()
            if grabbed:
                return grabbed[:80]

    for line in text.splitlines():
        stripped = line.strip()
        if len(stripped) >= 3 and re.search(r"[A-Za-zÀ-ÿ]", stripped):
            return stripped[:80]
    return ""


def parse_receipt(pdf_path: Path, description_match: str = "") -> ParsedReceipt:
    """Reads a receipt PDF and returns parsed fields plus any warnings."""
    warnings: list[str] = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    except Exception as exc:  # noqa: BLE001 - keep going even on a broken PDF
        warnings.append(f"Could not read PDF ({pdf_path.name}): {exc}")
        return ParsedReceipt(amount=None, date=None, description="", warnings=warnings)

    amount = _extract_amount(text)
    if amount is None:
        warnings.append(f"No amount found in {pdf_path.name}.")

    date = _extract_date(text)
    if date is None:
        warnings.append(f"No date found in {pdf_path.name} (using the email date).")

    description = _extract_description(text, description_match)

    return ParsedReceipt(
        amount=amount, date=date, description=description, warnings=warnings, raw_text=text
    )
