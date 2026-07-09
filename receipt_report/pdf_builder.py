"""Builds the final PDF: a cover sheet summary plus an indexed appendix of receipts."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


@dataclass
class ReceiptEntry:
    index: int
    date: dt.date | None
    description: str
    amount: float | None
    pdf_path: Path


def format_amount(value: float | None, currency: str) -> str:
    if value is None:
        return "—"
    return f"{value:,.2f} {currency}".strip()


def _format_date(date: dt.date | None) -> str:
    return date.isoformat() if date else "—"


def build_cover_pdf(
    report_title: str,
    recipient_name: str,
    generated_date: dt.date,
    entries: list[ReceiptEntry],
    currency: str,
    purpose: str = "",
) -> bytes:
    """Creates the cover sheet with a title, date and summary table."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=25 * mm, bottomMargin=20 * mm, leftMargin=20 * mm, rightMargin=20 * mm,
        title=report_title, author=recipient_name,
    )
    styles = getSampleStyleSheet()
    story = [
        Paragraph(report_title, styles["Title"]),
        Spacer(1, 6 * mm),
        Paragraph(f"Date: {generated_date.isoformat()}", styles["Normal"]),
        Spacer(1, 8 * mm),
    ]

    show_purpose = bool(purpose)
    header = ["#", "Date", "Description"]
    if show_purpose:
        header.append("Purpose")
    header.append(f"Amount ({currency})")
    data: list[list] = [header]

    total = 0.0
    for e in entries:
        row = [str(e.index), _format_date(e.date), e.description or "Receipt"]
        if show_purpose:
            row.append(purpose)
        row.append(format_amount(e.amount, currency))
        data.append(row)
        if e.amount is not None:
            total += e.amount

    # Total row: label in the second-to-last column, value in the last column.
    n_cols = len(header)
    total_row = [""] * n_cols
    total_row[-2] = "Total"
    total_row[-1] = format_amount(total, currency)
    data.append(total_row)

    if show_purpose:
        col_widths = [12 * mm, 24 * mm, 48 * mm, 40 * mm, 30 * mm]
    else:
        col_widths = [14 * mm, 28 * mm, 80 * mm, 32 * mm]

    amount_col = n_cols - 1
    table = Table(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f4e79")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ALIGN", (0, 0), (0, -1), "CENTER"),
            ("ALIGN", (amount_col, 0), (amount_col, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#f0f4f8")]),
            ("LINEBELOW", (0, 0), (-1, 0), 0.75, colors.HexColor("#1f4e79")),
            ("LINEABOVE", (0, -1), (-1, -1), 0.75, colors.HexColor("#1f4e79")),
            ("FONTNAME", (amount_col - 1, -1), (-1, -1), "Helvetica-Bold"),
            ("ALIGN", (amount_col - 1, -1), (amount_col - 1, -1), "RIGHT"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ])
    )
    story.append(table)
    story.append(Spacer(1, 8 * mm))
    story.append(
        Paragraph(
            f"{len(entries)} receipt(s). Each appears as an appendix with the matching index below.",
            styles["Italic"],
        )
    )

    doc.build(story)
    return buffer.getvalue()


def _stamp_page(page, label: str):
    """Stamps 'Appendix N' at the top-right of a page."""
    width = float(page.mediabox.width)
    height = float(page.mediabox.height)
    packet = BytesIO()
    c = canvas.Canvas(packet, pagesize=(width, height))
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(colors.HexColor("#1f4e79"))
    c.drawRightString(width - 15, height - 22, label)
    c.save()
    packet.seek(0)
    page.merge_page(PdfReader(packet).pages[0])
    return page


def build_final_pdf(
    report_title: str,
    recipient_name: str,
    generated_date: dt.date,
    entries: list[ReceiptEntry],
    output_path: Path,
    currency: str,
    purpose: str = "",
) -> Path:
    """Assembles cover sheet + all stamped receipts into one PDF with bookmarks."""
    writer = PdfWriter()

    cover = build_cover_pdf(
        report_title, recipient_name, generated_date, entries, currency, purpose
    )
    for page in PdfReader(BytesIO(cover)).pages:
        writer.add_page(page)
    writer.add_outline_item("Cover – summary", 0)

    for entry in entries:
        start = len(writer.pages)
        label = f"Appendix {entry.index}"
        try:
            for page in PdfReader(str(entry.pdf_path)).pages:
                writer.add_page(_stamp_page(page, label))
        except Exception as exc:  # noqa: BLE001
            writer.add_blank_page(width=A4[0], height=A4[1])
            print(f"  ! Could not embed {entry.pdf_path.name}: {exc}")
        writer.add_outline_item(f"{label} – {entry.description or 'Receipt'}", start)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        writer.write(f)
    return output_path
