"""
Builds the examination scorecard PDF for ONE published result (PDR 5.7).
Pure function: no request, no response objects.
"""

import io
import os
from decimal import Decimal

from flask import current_app
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.services import student_queries, windows


def build_scorecard(student_id: int, booking_id: int) -> tuple[bytes, str] | None:
    detail = student_queries.result_detail(student_id, booking_id)
    if not detail:
        return None

    booking = detail.get("booking") or detail.get("_booking")
    exam = booking.examination

    font_name = "Helvetica"
    font_bold = "Helvetica-Bold"

    # Attempt to load vendored fonts
    font_dir = os.path.join(current_app.root_path, "static", "vendor", "fonts")
    sans_path = os.path.join(font_dir, "DejaVuSans.ttf")
    bold_path = os.path.join(font_dir, "DejaVuSans-Bold.ttf")

    if os.path.exists(sans_path) and os.path.exists(bold_path):
        try:
            pdfmetrics.registerFont(TTFont("DejaVu", sans_path))
            pdfmetrics.registerFont(TTFont("DejaVu-Bold", bold_path))
            font_name = "DejaVu"
            font_bold = "DejaVu-Bold"
        except Exception:  # noqa: S110
            pass

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=30,
        leftMargin=30,
        topMargin=30,
        bottomMargin=30,
        title=f"Scorecard - {exam.name}",
        author=current_app.config.get("INSTITUTION_NAME", "Examination Management Portal"),
        subject="Examination result",
        creator="EMP System",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ScorecardTitle",
        parent=styles["Heading1"],
        fontName=font_bold,
        fontSize=16,
        alignment=1,
        spaceAfter=20,
    )
    norm_style = ParagraphStyle("NormalCustom", parent=styles["Normal"], fontName=font_name)
    bold_style = ParagraphStyle("BoldCustom", parent=styles["Normal"], fontName=font_bold)

    elements = []

    inst_name = current_app.config.get("INSTITUTION_NAME", "Examination Management Portal")
    elements.append(Paragraph(f"{inst_name}<br/><b>Examination Scorecard</b>", title_style))

    # Details table
    student = booking.student
    tz = current_app.config.get("APP_TIMEZONE", "UTC")
    slot_start = windows.format_local(windows.to_local(booking.slot.start_at))

    details_data = [
        [
            Paragraph("<b>Student:</b>", norm_style),
            Paragraph(student.full_name, norm_style),
            Paragraph("<b>Course:</b>", norm_style),
            Paragraph(f"{exam.course.code} - {exam.course.name}", norm_style),
        ],
        [
            Paragraph("<b>Roll Number:</b>", norm_style),
            Paragraph(student.student_profile.roll_number or "-", norm_style),
            Paragraph("<b>Examination:</b>", norm_style),
            Paragraph(f"{exam.name} ({exam.exam_type})", norm_style),
        ],
        [
            Paragraph("<b>Programme:</b>", norm_style),
            Paragraph(student.student_profile.program or "-", norm_style),
            Paragraph("<b>Date & Time:</b>", norm_style),
            Paragraph(f"{slot_start} {tz}", norm_style),
        ],
        [
            Paragraph("<b>Booking ID:</b>", norm_style),
            Paragraph(str(booking.id), norm_style),
            Paragraph("<b>Examiner:</b>", norm_style),
            Paragraph(booking.slot.examiner.full_name, norm_style),
        ],
    ]

    dt_table = Table(details_data, colWidths=[80, 180, 80, 180])
    dt_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    elements.append(dt_table)
    elements.append(Spacer(1, 20))

    # Criteria Table
    c_data = [
        [
            Paragraph("<b>Criterion</b>", bold_style),
            Paragraph("<b>Weightage %</b>", bold_style),
            Paragraph("<b>Maximum</b>", bold_style),
            Paragraph("<b>Score</b>", bold_style),
            Paragraph("<b>Comment</b>", bold_style),
        ]
    ]

    criteria = detail.get("criteria")
    if criteria is None:
        criteria = []
        evaluation = detail.get("evaluation")
        if evaluation and evaluation.scores:
            for sc in evaluation.scores:
                criteria.append(
                    {
                        "name": sc.rubric.criterion_name,
                        "weightage": sc.rubric.weightage,
                        "max_score": sc.rubric.max_score,
                        "score": sc.score,
                        "comment": sc.comment,
                    }
                )
        elif "scores" in detail:
            for s in detail["scores"]:
                criteria.append(
                    {
                        "name": s.get("criterion") or s.get("name"),
                        "weightage": s.get("weightage", "-"),
                        "max_score": s.get("max_score"),
                        "score": s.get("score"),
                        "comment": s.get("comment"),
                    }
                )

    for crit in criteria:
        c_data.append(
            [
                Paragraph(crit["name"], norm_style),
                Paragraph(str(crit["weightage"]), norm_style),
                Paragraph(str(crit["max_score"]), norm_style),
                Paragraph(str(crit["score"]) if crit["score"] is not None else "-", norm_style),
                Paragraph(crit["comment"] or "-", norm_style),
            ]
        )

    c_table = Table(c_data, colWidths=[120, 70, 70, 70, 200], repeatRows=1)
    c_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("GRID", (0, 0), (-1, -1), 1, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.append(c_table)
    elements.append(Spacer(1, 15))

    # Totals
    maximum = detail.get("maximum") or detail.get("max_marks") or exam.max_marks
    total = detail.get("total")
    if maximum and float(maximum) > 0:
        total_pct = (Decimal(str(total)) / Decimal(str(maximum)) * 100).quantize(Decimal("0.1"))
    else:
        total_pct = Decimal("0.0")
    elements.append(
        Paragraph(
            f"<b>Total:</b> {total} of {maximum} &nbsp;&nbsp;&nbsp; <b>Percentage:</b> {total_pct} %",
            norm_style,
        )
    )
    elements.append(Spacer(1, 20))

    if detail["remarks"]:
        elements.append(Paragraph("<b>Feedback</b>", bold_style))
        elements.append(Paragraph(detail["remarks"].replace("\n", "<br/>"), norm_style))

    # Generate
    def on_page(canvas, _doc):
        canvas.saveState()
        canvas.setFont(font_name, 8)
        now_loc = windows.format_local(windows.to_local(windows.now_utc()))
        footer = f"Generated on {now_loc} - Reference EMP-{booking.id}-{exam.id} | Page {_doc.page}"
        canvas.drawCentredString(A4[0] / 2.0, 15, footer)
        canvas.restoreState()

    doc.build(elements, onFirstPage=on_page, onLaterPages=on_page)

    # File name slug
    import re

    slug = re.sub(r"[^a-zA-Z0-9]+", "-", exam.name).strip("-")[:40]
    filename = f"scorecard-{slug}-{booking.id}.pdf"

    return buffer.getvalue(), filename
