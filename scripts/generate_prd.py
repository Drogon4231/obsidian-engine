#!/usr/bin/env python3
"""Generate The Obsidian Archive — PRD v2.0 PDF."""

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.colors import HexColor, white
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether
)
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "The Obsidian Archive \u2014 PRD.pdf"

W, H = A4

# \u2500\u2500 Colour palette \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
NAVY        = HexColor("#1a2744")
NAVY_LIGHT  = HexColor("#2d3f6b")
ACCENT      = HexColor("#c8973a")
ACCENT2     = HexColor("#1d4ed8")
GREY_DARK   = HexColor("#374151")
GREY_MID    = HexColor("#6b7280")
GREY_LIGHT  = HexColor("#f3f4f6")
GREY_BORDER = HexColor("#e5e7eb")
GREY_LINE   = HexColor("#d1d5db")
TABLE_HEAD  = HexColor("#1a2744")
TABLE_ALT   = HexColor("#f8f9fa")
RED_SOFT    = HexColor("#dc2626")
GREEN_SOFT  = HexColor("#16a34a")
AMBER       = HexColor("#d97706")
CODE_BG     = HexColor("#f8f8f8")
COVER_BG    = HexColor("#1a2744")
PRIORITY_P0 = HexColor("#dc2626")
PRIORITY_P1 = HexColor("#d97706")
PRIORITY_P2 = HexColor("#2563eb")
PRIORITY_P3 = HexColor("#6b7280")

# \u2500\u2500 Styles \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
def S(name, **kw):
    return ParagraphStyle(name, **kw)

SC_TITLE  = S("sc_title",  fontName="Helvetica-Bold", fontSize=34, leading=42, textColor=white,              alignment=TA_LEFT, spaceAfter=10)
SC_SUB    = S("sc_sub",    fontName="Helvetica",      fontSize=14, leading=20, textColor=HexColor("#aab4c8"), alignment=TA_LEFT, spaceAfter=6)
SC_TAG    = S("sc_tag",    fontName="Helvetica",      fontSize=9,  leading=13, textColor=HexColor("#8899bb"), alignment=TA_LEFT, spaceAfter=4)
SC_LABEL  = S("sc_label",  fontName="Helvetica-Bold", fontSize=8,  leading=11, textColor=ACCENT,             alignment=TA_LEFT, spaceAfter=2)

SH1       = S("sh1",   fontName="Helvetica-Bold", fontSize=18, leading=24, textColor=NAVY,       spaceBefore=22, spaceAfter=8)
SH2       = S("sh2",   fontName="Helvetica-Bold", fontSize=13, leading=18, textColor=NAVY,       spaceBefore=16, spaceAfter=6)
SH3       = S("sh3",   fontName="Helvetica-Bold", fontSize=11, leading=15, textColor=NAVY_LIGHT, spaceBefore=10, spaceAfter=4)
SH4       = S("sh4",   fontName="Helvetica-Bold", fontSize=9,  leading=13, textColor=GREY_DARK,  spaceBefore=8,  spaceAfter=3)
SBODY     = S("sbody", fontName="Helvetica",      fontSize=9,  leading=14, textColor=GREY_DARK,  spaceAfter=5, alignment=TA_JUSTIFY)
SBODY_SM  = S("sbodysm", fontName="Helvetica",   fontSize=8,  leading=12, textColor=GREY_MID,   spaceAfter=4)
SBULLET   = S("sbullet",  fontName="Helvetica",  fontSize=9,  leading=13, textColor=GREY_DARK,  leftIndent=14, spaceAfter=3)
SBULLET2  = S("sbullet2", fontName="Helvetica",  fontSize=8,  leading=12, textColor=GREY_MID,   leftIndent=28, spaceAfter=2)
SCODE     = S("scode",    fontName="Courier",    fontSize=8,  leading=12, textColor=GREY_DARK,  backColor=CODE_BG, leftIndent=8, rightIndent=8, spaceAfter=6, spaceBefore=4, borderPadding=(5,5,5,5))
SLABEL    = S("slabel",   fontName="Helvetica-Bold", fontSize=8, leading=11, textColor=NAVY_LIGHT, spaceAfter=2, spaceBefore=6)
SCAPTION  = S("scaption", fontName="Helvetica",  fontSize=7,  leading=10, textColor=GREY_MID,   alignment=TA_CENTER, spaceAfter=4)
STOC      = S("stoc",     fontName="Helvetica",  fontSize=10, leading=18, textColor=GREY_DARK,  leftIndent=0)
STOC_SEC  = S("stoc_sec", fontName="Helvetica-Bold", fontSize=10, leading=18, textColor=NAVY)
STOC_SUB  = S("stoc_sub", fontName="Helvetica",  fontSize=9,  leading=16, textColor=GREY_MID,   leftIndent=18)

# \u2500\u2500 Helpers \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
def sp(h=6):   return Spacer(1, h)
def hr(t=0.5, c=GREY_LINE): return HRFlowable(width="100%", thickness=t, color=c, spaceAfter=8, spaceBefore=4)
def hr_accent(t=2): return HRFlowable(width="100%", thickness=t, color=ACCENT, spaceAfter=8, spaceBefore=2)

def h1(t): return Paragraph(t, SH1)
def h2(t): return Paragraph(t, SH2)
def h3(t): return Paragraph(t, SH3)
def h4(t): return Paragraph(t, SH4)
def body(t): return Paragraph(t, SBODY)
def bodysm(t): return Paragraph(t, SBODY_SM)
def lbl(t): return Paragraph(t, SLABEL)
def bullet(t): return Paragraph(f"<font color='#1a2744'>\u203a</font>  {t}", SBULLET)
def bullet2(t): return Paragraph(f"<font color='#c8973a'>\u2013</font>  {t}", SBULLET2)
def code(t):
    safe = t.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
    safe = safe.replace(" ", "&nbsp;").replace("\n","<br/>")
    return Paragraph(safe, SCODE)

def section_header(number, title):
    data = [[
        Paragraph(f'<font color="{ACCENT.hexval()}">{number}</font>',
                  S("sn", fontName="Helvetica-Bold", fontSize=28, leading=32, textColor=ACCENT)),
        Paragraph(title, S("st", fontName="Helvetica-Bold", fontSize=18, leading=22, textColor=NAVY)),
    ]]
    t = Table(data, colWidths=[36, 424])
    t.setStyle(TableStyle([
        ("VALIGN", (0,0),(-1,-1), "MIDDLE"),
        ("LEFTPADDING",  (0,0),(-1,-1), 0),
        ("RIGHTPADDING", (0,0),(-1,-1), 0),
        ("TOPPADDING",   (0,0),(-1,-1), 0),
        ("BOTTOMPADDING",(0,0),(-1,-1), 0),
    ]))
    return KeepTogether([sp(8), t,
                         HRFlowable(width="100%", thickness=2, color=ACCENT, spaceAfter=10, spaceBefore=4)])

def req_table(rows, col_widths=None):
    """Requirements table: ID | Requirement | Priority | Notes."""
    cw = col_widths or [50, 230, 60, 120]
    header = [
        Paragraph("<b>ID</b>",          S("th", fontName="Helvetica-Bold", fontSize=8, textColor=white)),
        Paragraph("<b>Requirement</b>", S("th", fontName="Helvetica-Bold", fontSize=8, textColor=white)),
        Paragraph("<b>Priority</b>",    S("th", fontName="Helvetica-Bold", fontSize=8, textColor=white)),
        Paragraph("<b>Notes</b>",       S("th", fontName="Helvetica-Bold", fontSize=8, textColor=white)),
    ]
    data = [header] + rows
    t = Table(data, colWidths=cw, repeatRows=1)
    style = [
        ("BACKGROUND",  (0,0), (-1,0), TABLE_HEAD),
        ("ROWBACKGROUNDS", (0,1),(-1,-1), [white, TABLE_ALT]),
        ("GRID",        (0,0), (-1,-1), 0.4, GREY_BORDER),
        ("TOPPADDING",  (0,0), (-1,-1), 5),
        ("BOTTOMPADDING",(0,0),(-1,-1), 5),
        ("LEFTPADDING", (0,0), (-1,-1), 6),
        ("RIGHTPADDING",(0,0), (-1,-1), 6),
        ("VALIGN",      (0,0), (-1,-1), "TOP"),
        ("FONTNAME",    (0,1), (-1,-1), "Helvetica"),
        ("FONTSIZE",    (0,1), (-1,-1), 8),
    ]
    t.setStyle(TableStyle(style))
    return t

def priority_badge(label, color):
    return Paragraph(
        f'<font color="{color.hexval()}"><b>{label}</b></font>',
        S("pb", fontName="Helvetica-Bold", fontSize=8, textColor=color)
    )

def p0(): return priority_badge("P0 \u2014 Critical", PRIORITY_P0)
def p1(): return priority_badge("P1 \u2014 High",     PRIORITY_P1)
def p2(): return priority_badge("P2 \u2014 Medium",   PRIORITY_P2)
def p3(): return priority_badge("P3 \u2014 Low",      PRIORITY_P3)

def metric_grid(items):
    rows = []
    for i in range(0, len(items), 2):
        row = [items[i]]
        row.append(items[i+1] if i+1 < len(items) else ("", ""))
        rows.append(row)
    cells = []
    for row in rows:
        cell_row = []
        for (metric, value) in row:
            inner = Table([[
                Paragraph(metric, S("mg", fontName="Helvetica",      fontSize=8,  leading=11, textColor=GREY_MID)),
                Paragraph(value,  S("mv", fontName="Helvetica-Bold", fontSize=14, leading=18, textColor=NAVY)),
            ]], colWidths=[160, 60])
            inner.setStyle(TableStyle([
                ("VALIGN",        (0,0),(-1,-1), "TOP"),
                ("LEFTPADDING",   (0,0),(-1,-1), 0),
                ("RIGHTPADDING",  (0,0),(-1,-1), 0),
                ("TOPPADDING",    (0,0),(-1,-1), 0),
                ("BOTTOMPADDING", (0,0),(-1,-1), 0),
            ]))
            cell = Table([[inner]], colWidths=[220])
            cell.setStyle(TableStyle([
                ("BOX",           (0,0),(-1,-1), 0.5, GREY_BORDER),
                ("BACKGROUND",    (0,0),(-1,-1), TABLE_ALT),
                ("LEFTPADDING",   (0,0),(-1,-1), 10),
                ("RIGHTPADDING",  (0,0),(-1,-1), 10),
                ("TOPPADDING",    (0,0),(-1,-1), 8),
                ("BOTTOMPADDING", (0,0),(-1,-1), 8),
            ]))
            cell_row.append(cell)
        cells.append(cell_row)
    grid = Table(cells, colWidths=[230, 230])
    grid.setStyle(TableStyle([
        ("LEFTPADDING",   (0,0),(-1,-1), 0),
        ("RIGHTPADDING",  (0,0),(-1,-1), 0),
        ("TOPPADDING",    (0,0),(-1,-1), 4),
        ("BOTTOMPADDING", (0,0),(-1,-1), 4),
    ]))
    return grid

def risk_row(rid, risk, impact, likelihood, mitigation, color):
    return [
        Paragraph(f"<b>{rid}</b>", S("rr", fontName="Helvetica-Bold", fontSize=8, textColor=color)),
        Paragraph(risk,        S("rb", fontName="Helvetica", fontSize=8, textColor=GREY_DARK)),
        Paragraph(f'<font color="{color.hexval()}"><b>{impact}</b></font>',
                  S("ri", fontName="Helvetica-Bold", fontSize=8)),
        Paragraph(likelihood,  S("rl", fontName="Helvetica", fontSize=8, textColor=GREY_MID)),
        Paragraph(mitigation,  S("rm", fontName="Helvetica", fontSize=8, textColor=GREY_DARK)),
    ]

def arch_flow(stages):
    cells = []
    for i, (name, color) in enumerate(stages):
        box = Table([[Paragraph(name, S("af", fontName="Helvetica-Bold", fontSize=7, leading=10,
                                        textColor=white, alignment=TA_CENTER))]],
                    colWidths=[54])
        box.setStyle(TableStyle([
            ("BACKGROUND",    (0,0),(-1,-1), color),
            ("TOPPADDING",    (0,0),(-1,-1), 6),
            ("BOTTOMPADDING", (0,0),(-1,-1), 6),
            ("LEFTPADDING",   (0,0),(-1,-1), 4),
            ("RIGHTPADDING",  (0,0),(-1,-1), 4),
        ]))
        cells.append(box)
        if i < len(stages) - 1:
            arrow = Paragraph("\u2192", S("arr", fontName="Helvetica-Bold", fontSize=10,
                                          textColor=GREY_MID, alignment=TA_CENTER))
            cells.append(arrow)

    col_widths = []
    for i in range(len(stages)):
        col_widths.append(54)
        if i < len(stages) - 1:
            col_widths.append(10)

    row = Table([cells], colWidths=col_widths)
    row.setStyle(TableStyle([
        ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
        ("LEFTPADDING",   (0,0),(-1,-1), 0),
        ("RIGHTPADDING",  (0,0),(-1,-1), 0),
        ("TOPPADDING",    (0,0),(-1,-1), 0),
        ("BOTTOMPADDING", (0,0),(-1,-1), 0),
    ]))
    return row

def data_table(headers, rows, col_widths=None, compact=False):
    pad = 4 if compact else 6
    n = len(headers)
    if col_widths is None:
        col_widths = [int(460/n)] * n
    hdr_cells = [Paragraph(f'<b>{h}</b>', S("th", fontName="Helvetica-Bold", fontSize=8, leading=11, textColor=white)) for h in headers]
    body_rows = []
    for row in rows:
        body_rows.append([Paragraph(str(c), S("td", fontName="Helvetica", fontSize=8, leading=12, textColor=GREY_DARK)) for c in row])
    data = [hdr_cells] + body_rows
    t = Table(data, colWidths=col_widths, repeatRows=1)
    cmd = [
        ("BACKGROUND",    (0,0), (-1,0), TABLE_HEAD),
        ("TEXTCOLOR",     (0,0), (-1,0), white),
        ("FONTNAME",      (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",      (0,0), (-1,0), 8),
        ("ROWBACKGROUNDS",(0,1), (-1,-1), [white, TABLE_ALT]),
        ("GRID",          (0,0), (-1,-1), 0.4, GREY_BORDER),
        ("TOPPADDING",    (0,0), (-1,-1), pad),
        ("BOTTOMPADDING", (0,0), (-1,-1), pad),
        ("LEFTPADDING",   (0,0), (-1,-1), 7),
        ("RIGHTPADDING",  (0,0), (-1,-1), 7),
        ("VALIGN",        (0,0), (-1,-1), "TOP"),
    ]
    t.setStyle(TableStyle(cmd))
    return t

def kv_table(rows, col_widths=None):
    if col_widths is None:
        col_widths = [130, 330]
    data = [[
        Paragraph(f'<b>{k}</b>', S("kk", fontName="Helvetica-Bold", fontSize=8, leading=12, textColor=NAVY)),
        Paragraph(v, S("kv", fontName="Helvetica", fontSize=8, leading=12, textColor=GREY_DARK))
    ] for k,v in rows]
    t = Table(data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ("ROWBACKGROUNDS",(0,0),(-1,-1),[white, GREY_LIGHT]),
        ("GRID",(0,0),(-1,-1),0.4, GREY_BORDER),
        ("TOPPADDING",(0,0),(-1,-1),5),
        ("BOTTOMPADDING",(0,0),(-1,-1),5),
        ("LEFTPADDING",(0,0),(-1,-1),8),
        ("VALIGN",(0,0),(-1,-1),"TOP"),
        ("LINEAFTER",(0,0),(0,-1),0.8,GREY_LINE),
    ]))
    return t

# \u2500\u2500 Page templates \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
def on_page(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(NAVY)
    canvas.rect(0, H - 28*mm, W, 28*mm, fill=1, stroke=0)
    canvas.setFillColor(ACCENT)
    canvas.rect(0, H - 29*mm, W, 1.5, fill=1, stroke=0)
    canvas.setFont("Helvetica-Bold", 8)
    canvas.setFillColor(white)
    canvas.drawString(20*mm, H - 18*mm, "THE OBSIDIAN ARCHIVE")
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(HexColor("#aab4c8"))
    canvas.drawRightString(W - 20*mm, H - 18*mm, "PRODUCT REQUIREMENTS DOCUMENT  \u00b7  CONFIDENTIAL")
    canvas.setFillColor(GREY_LIGHT)
    canvas.rect(0, 0, W, 14*mm, fill=1, stroke=0)
    canvas.setFillColor(GREY_LINE)
    canvas.rect(0, 14*mm, W, 0.5, fill=1, stroke=0)
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(GREY_MID)
    canvas.drawString(20*mm, 5*mm, "The Obsidian Archive  \u2014  PRD v2.0  \u00b7  March 2026")
    canvas.drawRightString(W - 20*mm, 5*mm, f"Page {doc.page}")
    canvas.restoreState()

def on_cover(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(COVER_BG)
    canvas.rect(0, 0, W, H, fill=1, stroke=0)
    canvas.setFillColor(ACCENT)
    canvas.rect(0, 0, 6*mm, H, fill=1, stroke=0)
    canvas.setFillColor(NAVY_LIGHT)
    canvas.rect(0, 0, W, 40*mm, fill=1, stroke=0)
    canvas.setFillColor(ACCENT)
    canvas.rect(0, 40*mm, W, 1.5, fill=1, stroke=0)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(HexColor("#8899bb"))
    canvas.drawString(20*mm, 14*mm, "CONFIDENTIAL  \u00b7  INTERNAL USE ONLY  \u00b7  The Obsidian Archive  \u00b7  2026")
    canvas.restoreState()

# \u2500\u2500 Cover page \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
def build_cover():
    elems = []
    elems.append(sp(30))
    elems.append(Paragraph("PRODUCT REQUIREMENTS DOCUMENT", SC_TAG))
    elems.append(sp(6))
    elems.append(Paragraph("The Obsidian Archive", SC_TITLE))
    elems.append(Paragraph("Autonomous AI-Powered Documentary Pipeline", SC_SUB))
    elems.append(sp(10))
    elems.append(HRFlowable(width="100%", thickness=1.5, color=ACCENT, spaceAfter=14))

    meta = [
        ["Document Version", "PRD v2.0"],
        ["Status",           "Production \u2014 Live on Railway"],
        ["Date",             "March 2026"],
        ["Owner",            "The Obsidian Archive"],
        ["Classification",   "Confidential \u00b7 Internal Use Only"],
    ]
    for k, v in meta:
        row = Table([[
            Paragraph(k, S("mk", fontName="Helvetica",      fontSize=9, textColor=HexColor("#8899bb"))),
            Paragraph(v, S("mv", fontName="Helvetica-Bold", fontSize=9, textColor=white)),
        ]], colWidths=[120, 300])
        row.setStyle(TableStyle([
            ("LEFTPADDING",   (0,0),(-1,-1), 0),
            ("RIGHTPADDING",  (0,0),(-1,-1), 0),
            ("TOPPADDING",    (0,0),(-1,-1), 3),
            ("BOTTOMPADDING", (0,0),(-1,-1), 3),
        ]))
        elems.append(row)

    elems.append(sp(28))
    elems.append(HRFlowable(width="100%", thickness=0.5, color=NAVY_LIGHT, spaceAfter=14))

    stats = [
        ("Agents",          "14"),
        ("AI Models",       "3"),
        ("External APIs",   "8"),
        ("Avg. Cycle Time", "~4 hrs"),
        ("Output",          "MP4 + YT"),
        ("Schedule",        "Weekly"),
    ]
    stat_cells = []
    for label, val in stats:
        cell = Table([[
            Paragraph(val,   S("sv", fontName="Helvetica-Bold", fontSize=22, leading=26, textColor=white, alignment=TA_CENTER)),
            Paragraph(label, S("sl", fontName="Helvetica",      fontSize=8,  leading=11, textColor=HexColor("#8899bb"), alignment=TA_CENTER)),
        ]], colWidths=[78])
        cell.setStyle(TableStyle([
            ("TOPPADDING",    (0,0),(-1,-1), 6),
            ("BOTTOMPADDING", (0,0),(-1,-1), 6),
            ("LEFTPADDING",   (0,0),(-1,-1), 0),
            ("RIGHTPADDING",  (0,0),(-1,-1), 0),
        ]))
        stat_cells.append(cell)

    stat_row = Table([stat_cells], colWidths=[78]*6)
    stat_row.setStyle(TableStyle([
        ("LINEAFTER",     (0,0), (4,0), 0.5, NAVY_LIGHT),
        ("LEFTPADDING",   (0,0),(-1,-1), 0),
        ("RIGHTPADDING",  (0,0),(-1,-1), 0),
        ("TOPPADDING",    (0,0),(-1,-1), 0),
        ("BOTTOMPADDING", (0,0),(-1,-1), 0),
    ]))
    elems.append(stat_row)
    elems.append(PageBreak())
    return elems

# \u2500\u2500 Table of Contents \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
def build_toc():
    elems = []
    elems.append(section_header("00", "Table of Contents"))
    sections = [
        ("01", "Executive Summary",                  ["1.1 Vision & Mission", "1.2 Problem Statement", "1.3 Proposed Solution", "1.4 KPIs & Success Criteria"]),
        ("02", "Product Overview",                   ["2.1 Product Description", "2.2 Operator Persona", "2.3 Core Value Propositions", "2.4 Out of Scope"]),
        ("03", "System Architecture",                ["3.1 Long-Form Pipeline (14 Stages)", "3.2 Short-Form Sub-Pipeline", "3.3 Component Overview", "3.4 State File Data Flow", "3.5 Infrastructure"]),
        ("04", "Closed-Loop Intelligence System",    ["4.1 Analytics Agent", "4.2 Channel Insights Hub", "4.3 Agent Injection", "4.4 DNA Confidence Scoring", "4.5 Era Performance Tracking"]),
        ("05", "Pipeline Monitoring & Quality",      ["5.1 Pipeline Doctor", "5.2 Pipeline Optimizer", "5.3 Quality Gates", "5.4 Telegram Alerting", "5.5 A/B Title Testing"]),
        ("06", "Functional Requirements",            ["6.1 Content Generation", "6.2 Media Production", "6.3 Rendering", "6.4 Distribution", "6.5 Intelligence", "6.6 Monitoring"]),
        ("07", "Agent Specifications",               ["7.1\u20137.14 All 14 Agents"]),
        ("08", "API & Integration Requirements",     ["8.1 Anthropic Claude", "8.2 ElevenLabs", "8.3 fal.ai Flux Pro", "8.4 Pexels", "8.5 YouTube Data API v3", "8.6 YouTube Analytics API v2", "8.7 Supabase", "8.8 Telegram Bot API"]),
        ("09", "Non-Functional Requirements",        ["9.1 Performance", "9.2 Reliability", "9.3 Security", "9.4 Scalability", "9.5 Observability"]),
        ("10", "Data Models",                        ["10.1 State File Schema", "10.2 channel_insights.json Schema", "10.3 Supabase Tables"]),
        ("11", "Error Handling & Resilience",        ["11.1 Pipeline Doctor Retry Matrix", "11.2 Quota Management", "11.3 Partial Recovery"]),
        ("12", "Operational Requirements",           ["12.1 Railway Deployment", "12.2 Scheduling", "12.3 Cost Model", "12.4 Monitoring"]),
        ("13", "Risks & Mitigations",                ["13.1 Risk Register"]),
        ("14", "Roadmap",                            ["14.1 V1 Current", "14.2 V2 Next", "14.3 V3 Vision"]),
    ]
    for num, title, subs in sections:
        elems.append(Paragraph(f"<b>{num}</b>  {title}", STOC_SEC))
        for sub in subs:
            elems.append(Paragraph(f"{sub}", STOC_SUB))
    elems.append(PageBreak())
    return elems

# \u2500\u2500 Section 01 \u2014 Executive Summary \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
def build_s01():
    elems = [section_header("01", "Executive Summary")]

    elems.append(h2("1.1  Vision & Mission"))
    elems.append(body(
        "The Obsidian Archive is a fully autonomous AI-powered YouTube documentary production "
        "pipeline. Its mission is to produce and publish high-quality, research-grade historical "
        "documentary videos on dark and suppressed history \u2014 every week, indefinitely \u2014 with zero "
        "human intervention. The system democratises professional documentary production by "
        "replacing the traditional multi-discipline production team with a single, self-improving "
        "14-stage AI pipeline that runs end-to-end on a weekly schedule hosted on Railway."
    ))
    elems.append(sp(4))

    elems.append(h2("1.2  Problem Statement"))
    elems.append(body(
        "Producing a single 10\u201315 minute documentary-style YouTube video requires 40+ hours of human "
        "labour across six distinct disciplines: historical research (8\u201310 hrs), script writing (6\u20138 hrs), "
        "voice recording and audio editing (4\u20136 hrs), video editing and motion graphics (10\u201315 hrs), "
        "SEO and metadata optimisation (2\u20133 hrs), and upload coordination (1\u20132 hrs). This cost is "
        "prohibitive for independent creators seeking to maintain a consistent publishing cadence. "
        "Existing AI tools address isolated sub-problems but require manual orchestration, "
        "brand governance, and technical integration to function as a coherent pipeline. "
        "No end-to-end automated system exists that maintains factual accuracy, brand identity, "
        "cinematic quality, and YouTube SEO best practices at scale \u2014 while continuously improving "
        "its own outputs using performance feedback."
    ))
    elems.append(sp(4))

    elems.append(h2("1.3  Proposed Solution"))
    elems.append(body(
        "A 14-agent sequential pipeline hosted on Railway that ingests a topic from a Supabase "
        "queue (discovered by a dedicated topic agent on Mondays), autonomously produces a fully "
        "rendered 1080p MP4 documentary with ElevenLabs v3 narration, fal.ai Flux Pro oil-painting "
        "visuals, Pexels B-roll footage, Kevin MacLeod background music, and Remotion-animated "
        "captions \u2014 then uploads the finished video to YouTube with complete SEO metadata, "
        "thumbnail, source citations, and real chapter markers. A closed-loop intelligence system "
        "runs daily, pulling YouTube Analytics data and feeding performance insights back into "
        "every agent\u2019s decision-making, enabling continuous self-improvement."
    ))
    elems.append(sp(4))

    elems.append(h2("1.4  KPIs & Success Criteria"))
    kpis = [
        ("End-to-end pipeline success rate",   "\u2265 95% of runs complete without manual intervention"),
        ("Average pipeline cycle time",         "< 5 hours from topic trigger to YouTube upload"),
        ("Video output resolution",             "1080p (1920\xd71080), 24 fps, H.264 MP4"),
        ("Script length compliance",            "1,400\u20132,200 words per video, enforced by quality gate"),
        ("Factual accuracy standard",           "\u2265 3 verified sources per scene, central twist verified"),
        ("Audio quality",                       "ElevenLabs v3 (George voice), no TTS artefacts"),
        ("SEO compliance",                      "Title \u2264 70 chars, \u2265 15 tags, chapters present, A/B title tested"),
        ("YouTube upload success rate",         "\u2265 99% (OAuth2 resumable upload, auto-token refresh)"),
        ("Weekly cadence compliance",           "1 video published per week, every week"),
        ("Intelligence system CTR impact",      "Measurable CTR growth as analytics data accumulates"),
        ("Per-video production cost",           "\u2264 $2.50 USD (Claude + ElevenLabs + fal.ai combined)"),
        ("Short-form pipeline success rate",    "\u2265 85% (non-blocking; failures do not kill long pipeline)"),
    ]
    data = [[
        Paragraph(k, S("kk", fontName="Helvetica-Bold", fontSize=8, textColor=NAVY)),
        Paragraph(v, S("kv", fontName="Helvetica",      fontSize=8, textColor=GREY_DARK)),
    ] for k, v in kpis]
    t = Table(data, colWidths=[210, 250])
    t.setStyle(TableStyle([
        ("ROWBACKGROUNDS",  (0,0),(-1,-1), [white, TABLE_ALT]),
        ("GRID",           (0,0),(-1,-1), 0.4, GREY_BORDER),
        ("TOPPADDING",     (0,0),(-1,-1), 5),
        ("BOTTOMPADDING",  (0,0),(-1,-1), 5),
        ("LEFTPADDING",    (0,0),(-1,-1), 8),
        ("RIGHTPADDING",   (0,0),(-1,-1), 8),
        ("VALIGN",         (0,0),(-1,-1), "TOP"),
    ]))
    elems.append(t)
    elems.append(PageBreak())
    return elems

# \u2500\u2500 Section 02 \u2014 Product Overview \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
def build_s02():
    elems = [section_header("02", "Product Overview")]

    elems.append(h2("2.1  Product Description"))
    elems.append(body(
        "The Obsidian Archive pipeline is a Python-based multi-agent system deployed as a single "
        "containerised Railway service. Each agent is a discrete Python module (00_topic_discovery.py "
        "through 11_youtube_uploader.py). Agents are orchestrated sequentially by run_pipeline.py, "
        "with all inter-stage state persisted to a JSON state file. The system uses three Claude "
        "models as its reasoning core (Opus 4.6 for heavy analysis, Sonnet 4.6 for creative/research "
        "agents, Haiku 4.5 for fast formatting tasks), with specialised external APIs for voice "
        "synthesis, image generation, footage retrieval, and YouTube distribution. A dedicated "
        "analytics agent runs daily to close the performance feedback loop."
    ))
    elems.append(sp(4))

    elems.append(h2("2.2  Operator Persona"))
    elems.append(body(
        "The primary operator is a solo content creator or small media team. The operator provides: "
        "(1) OAuth2 credentials for YouTube, (2) API keys for Anthropic, ElevenLabs, fal.ai, Pexels, "
        "Supabase, and Telegram, (3) an optional topic override via the webhook /trigger endpoint. "
        "The operator\u2019s ongoing role is limited to: reviewing weekly Telegram reports, rotating "
        "API credentials when required, and optionally updating dna_config.json to refine channel "
        "identity. No interaction is required during or between production runs."
    ))
    elems.append(sp(4))

    elems.append(h2("2.3  Core Value Propositions"))
    props = [
        ("Full Automation",
         "Zero human intervention required between topic selection and YouTube upload. The scheduler "
         "manages the entire weekly cadence; the pipeline handles every production step autonomously."),
        ("Brand Consistency",
         "A DNA config file (dna_config.json) enforces channel identity, narrative tone, forbidden "
         "topics, and style rules across every agent via dna_loader.py injection into system prompts."),
        ("Factual Integrity",
         "A dedicated fact verification agent (05_fact_verification_agent.py) cross-checks every "
         "claim against \u2265 3 independent sources. The central twist must be verifiable or the pipeline halts."),
        ("Cinematic Quality",
         "fal.ai Flux Pro oil-painting style AI imagery + Pexels licensed B-roll + ElevenLabs v3 "
         "George voice narration + Kevin MacLeod background music + Remotion animated captions."),
        ("SEO-Native Output",
         "Title (\u2264 70 chars), description, tags (\u2265 15), chapter markers, A/B title variant, and "
         "1280\xd7720 thumbnail are all generated by a dedicated SEO agent and applied at upload."),
        ("Self-Improving Intelligence Loop",
         "The analytics agent (12_analytics_agent.py) runs daily, fetches YouTube Analytics API v2 "
         "data, computes per-era performance stats, and writes channel_insights.json. All agents "
         "read this file at runtime to continuously improve topic selection, narrative structure, "
         "and SEO decisions as performance data accumulates."),
        ("Cost Efficiency",
         "Total per-video API cost is estimated at $1.75\u2013$2.50 USD (Claude ~$0.60, ElevenLabs ~$0.35, "
         "fal.ai ~$0.80, Pexels free tier). The short-form video runs in parallel at negligible added cost."),
    ]
    for title, desc in props:
        elems.append(KeepTogether([
            Paragraph(f"<b>{title}</b>", S("pt", fontName="Helvetica-Bold", fontSize=9, textColor=NAVY, spaceAfter=1, spaceBefore=8)),
            Paragraph(desc, SBODY),
        ]))

    elems.append(sp(4))
    elems.append(h2("2.4  Out of Scope"))
    oos = [
        "Multi-language or dubbed video output (V2 consideration)",
        "Multi-channel operation or multi-brand management (V2 consideration)",
        "Human review or approval gates between pipeline stages",
        "Real-time live streaming or live captioning",
        "Monetisation management or AdSense integration",
        "Automated comment moderation or community engagement",
        "Cross-platform publishing to TikTok, Instagram Reels, or X (V3 roadmap)",
        "Real-time analytics dashboards beyond the existing SSE webhook server",
        "Video licensing or rights management for sourced footage",
    ]
    for item in oos:
        elems.append(bullet(item))
    elems.append(PageBreak())
    return elems

# \u2500\u2500 Section 03 \u2014 System Architecture \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
def build_s03():
    elems = [section_header("03", "System Architecture")]

    elems.append(h2("3.1  Long-Form Pipeline (14 Stages)"))
    elems.append(body(
        "The pipeline consists of 14 sequential stages grouped into four phases: "
        "<b>Content</b> (stages 0\u20136), <b>Media Production</b> (stages 7\u201310), "
        "<b>Render</b> (stages 11\u201312), and <b>Distribution</b> (stage 13). "
        "Stage 0 runs on a separate Monday schedule to pre-populate the topic queue."
    ))
    elems.append(sp(8))

    phases = [
        ("PHASE 1 \u2014 CONTENT",   [("Topic\nDiscov.", NAVY), ("Research", NAVY), ("Original.", NAVY), ("Narrative", NAVY), ("Script", NAVY), ("Verify", NAVY), ("SEO", NAVY)]),
        ("PHASE 2 \u2014 MEDIA",     [("Scene\nBreakdn.", NAVY_LIGHT), ("Audio\nProd.", NAVY_LIGHT), ("Footage\nHunt", NAVY_LIGHT), ("Image\nGen.", NAVY_LIGHT)]),
        ("PHASE 3 \u2014 RENDER",    [("Remotion\nConvert.", HexColor("#374151")), ("Video\nRender", HexColor("#374151"))]),
        ("PHASE 4 \u2014 DISTRIBUTE",[("YouTube\nUpload", HexColor("#c8973a"))]),
    ]
    for label, stages in phases:
        elems.append(lbl(label))
        elems.append(arch_flow(stages))
        elems.append(sp(10))

    elems.append(h2("3.2  Short-Form Sub-Pipeline"))
    elems.append(body(
        "After Stage 2 (Originality) completes, a short-form sub-pipeline runs in parallel with "
        "the long pipeline. Failures in the short pipeline do not halt the long pipeline. The "
        "sub-pipeline uses the same topic and originality output to produce a vertical (9:16) "
        "short-form video optimised for YouTube Shorts."
    ))
    elems.append(sp(6))
    elems.append(arch_flow([
        ("Short\nScript", HexColor("#7c3aed")),
        ("Short\nStorybd.", HexColor("#7c3aed")),
        ("Short\nAudio", HexColor("#7c3aed")),
        ("Short\nImages", HexColor("#7c3aed")),
        ("Short\nConvert", HexColor("#7c3aed")),
        ("Short\nRender", HexColor("#7c3aed")),
        ("Short\nUpload", HexColor("#7c3aed")),
    ]))
    elems.append(sp(10))

    elems.append(h2("3.3  Component Overview"))
    comps = [
        ["run_pipeline.py",          "Master orchestrator. Executes all 14 stages sequentially. Manages state file, --from-stage N resume, error handling, short pipeline fork."],
        ["00_topic_discovery.py",    "Stage 0. Queries Supabase queue, scores topics using era performance from channel_insights.json, selects next topic."],
        ["01_research_agent.py",     "Stage 1. Claude Sonnet + web search. Produces structured fact sheet with 8+ primary sources."],
        ["02_originality_agent.py",  "Stage 2. Finds untold angle, checks against published_topics in Supabase to prevent duplication."],
        ["03_narrative_architect.py","Stage 3. Produces 4-act story blueprint, injected with retention data from channel_insights.json."],
        ["04_script_writer.py",      "Stage 4. Writes 1,400\u20132,200 word narration script. DNA-guided. Quality gate enforced."],
        ["05_fact_verification_agent.py", "Stage 5. Verifies every claim, \u22653 sources per scene. Halts pipeline if twist unverifiable."],
        ["06_seo_agent.py",          "Stage 6. Generates title, description, tags, chapter markers, A/B title variant using Haiku 4.5."],
        ["07_scene_breakdown_agent.py", "Stage 7. Breaks script into 12\u201320 scenes with B-roll search prompts."],
        ["08_audio_producer.py",     "Stage 8. ElevenLabs v3 TTS, chunked at 4,500 chars, word-level timestamps."],
        ["09_footage_hunter.py",     "Stage 9. Pexels video search per scene using B-roll prompts from Stage 7."],
        ["run_pipeline.py (S10)",    "Stage 10. fal.ai Flux Pro image generation. Oil-painting style, 16:9. One image per scene."],
        ["run_pipeline.py (S11)",    "Stage 11. Converts manifest + audio to video-data.json for Remotion renderer."],
        ["run_pipeline.py (S12)",    "Stage 12. Remotion headless render via Chrome. 1080p MP4 with captions + music."],
        ["11_youtube_uploader.py",   "Stage 13. OAuth2 resumable upload, thumbnail (scene 1 image, 1280\xd7720), sources comment, real chapter markers."],
        ["12_analytics_agent.py",    "Daily. Fetches YouTube Analytics API v2 data. Computes era stats. Calls Claude Sonnet for analysis. Writes channel_insights.json."],
        ["channel_insights.py",      "Read-only intelligence hub. Provides get_global_intelligence_block(), get_topic_discovery_intelligence(), get_seo_intelligence(), etc."],
        ["dna_loader.py",            "Loads dna_config.json channel DNA. Injects into every agent system prompt. Has dynamic channel_intelligence section."],
        ["pipeline_doctor.py",       "Error classifier + retry engine. Categorises errors by type, applies per-type retry strategies."],
        ["pipeline_optimizer.py",    "Post-run quality analyser using Claude Sonnet. Scores outputs A\u2013F. Saves to lessons_learned.json."],
        ["quality_gates.py",         "Gate functions for each stage. Checks script length, fact count, SEO compliance, audio duration, B-roll quality."],
        ["scheduler.py",             "Railway daemon. Manages all cron jobs: topic discovery, video production, analytics, A/B check, ElevenLabs credit check, Telegram report."],
        ["webhook_server.py",        "Flask server (port 8080). Real-time SSE dashboard, /trigger for manual runs, /status for pipeline state."],
        ["notify.py",                "Telegram Bot API. Notifications for upload complete, pipeline failures, weekly reports, ElevenLabs alerts, A/B swaps."],
        ["supabase_client.py",       "PostgreSQL via Supabase. Tables: topics, videos, analytics."],
    ]
    data = [[
        Paragraph(f"<font face='Courier'>{c}</font>", S("cc", fontName="Courier", fontSize=7, textColor=NAVY)),
        Paragraph(d, S("cd", fontName="Helvetica", fontSize=8, textColor=GREY_DARK)),
    ] for c, d in comps]
    t = Table(data, colWidths=[150, 310])
    t.setStyle(TableStyle([
        ("ROWBACKGROUNDS", (0,0),(-1,-1), [white, TABLE_ALT]),
        ("GRID",          (0,0),(-1,-1), 0.4, GREY_BORDER),
        ("TOPPADDING",    (0,0),(-1,-1), 4),
        ("BOTTOMPADDING", (0,0),(-1,-1), 4),
        ("LEFTPADDING",   (0,0),(-1,-1), 8),
        ("RIGHTPADDING",  (0,0),(-1,-1), 8),
        ("VALIGN",        (0,0),(-1,-1), "TOP"),
    ]))
    elems.append(t)
    elems.append(sp(8))

    elems.append(h2("3.4  State File Data Flow"))
    elems.append(body(
        "All inter-agent communication is mediated by a single JSON state file stored at "
        "<font face='Courier'>outputs/YYYYMMDD_HHMMSS_&lt;slug&gt;_state.json</font>. Each agent "
        "reads its upstream dependencies from the state file and appends its output under a keyed "
        "stage slot. This design ensures idempotency, full auditability, and pipeline resumability "
        "via the <font face='Courier'>--from-stage N</font> flag. If the pipeline fails at Stage 8, "
        "it can be resumed from Stage 8 without re-running the six prior stages."
    ))
    elems.append(sp(4))

    elems.append(h2("3.5  Infrastructure"))
    infra = [
        ("Hosting platform",      "Railway \u2014 containerised Python 3.11 service, auto-deployed from GitHub on push to main"),
        ("Container runtime",     "Python 3.11 + Node.js 20 + Chromium (for Remotion headless render)"),
        ("Container memory",      "\u2265 4 GB recommended; Remotion render requires \u2265 2 GB at concurrency=1"),
        ("Persistent storage",    "Railway persistent volume mounted at /app/outputs \u2014 survives redeployments"),
        ("Scheduler",             "Python schedule daemon (scheduler.py) running continuously in the Railway container"),
        ("HTTP server",           "Flask + Werkzeug (port 8080); provides SSE dashboard and webhook endpoint"),
        ("CI/CD",                 "GitHub \u2192 Railway auto-deploy on push to main branch; build time ~10 minutes"),
        ("Secrets management",    "Railway environment variables; YouTube OAuth token stored as YOUTUBE_TOKEN_JSON env var"),
        ("YouTube OAuth",         "Token restored from env var at startup; auto-refreshed using google-auth library"),
    ]
    t = kv_table(infra, [160, 300])
    elems.append(t)
    elems.append(PageBreak())
    return elems

# \u2500\u2500 Section 04 \u2014 Closed-Loop Intelligence System \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
def build_s04():
    elems = [section_header("04", "Closed-Loop Intelligence System")]

    elems.append(body(
        "The intelligence system is the primary differentiator of The Obsidian Archive pipeline. "
        "It converts raw YouTube performance data into structured guidance that every production "
        "agent consumes at runtime \u2014 creating a self-improving feedback loop where each video "
        "produced improves the quality decisions made in all future videos."
    ))
    elems.append(sp(6))

    elems.append(h2("4.1  Analytics Agent (12_analytics_agent.py)"))
    elems.append(body(
        "Runs daily at 06:00 UTC via the scheduler. Fetches YouTube Analytics API v2 data for "
        "all published videos: views, impressions, impressionClickThroughRate (CTR), "
        "averageViewPercentage (retention), and watch time. Classifies each video by historical "
        "era (Ancient, Medieval, Renaissance, Early Modern, Modern, Contemporary). Computes "
        "aggregate statistics per era and per video. Calls Claude Sonnet 4.6 for deep qualitative "
        "analysis of the performance patterns. Writes the complete results to "
        "<font face='Courier'>channel_insights.json</font> on the Railway persistent volume."
    ))
    elems.append(sp(4))

    elems.append(h2("4.2  Channel Insights Hub (channel_insights.py)"))
    elems.append(body(
        "A read-only Python module that acts as the intelligence interface between the analytics "
        "data and all production agents. Exposes six specialised getter functions, each returning "
        "a formatted string block suitable for injection into agent system prompts. When no analytics "
        "data exists (e.g., channel just launched), all functions return empty string gracefully."
    ))
    elems.append(sp(4))

    intel_fns = [
        ["get_global_intelligence_block()",    "Full performance overview injected into all agent system prompts. Includes top-performing eras, recent trend direction, and overall channel health signal."],
        ["get_topic_discovery_intelligence()", "Era performance rankings for the topic discovery agent. Guides ORACLE toward eras with highest historical CTR and retention."],
        ["get_seo_intelligence()",             "Title pattern analysis for the SEO agent. Identifies which title formats, lengths, and emotional hooks have driven highest CTR historically."],
        ["get_narrative_intelligence()",       "Retention data for the narrative architect. Identifies which 4-act structures and pacing patterns correlate with highest average view percentage."],
        ["get_script_intelligence()",          "Script-level insights for the script writer. Includes optimal word count ranges, scene count targets, and opening hook patterns that perform best."],
        ["get_dna_confidence_block()",         "Confidence score (0.0\u20131.0) for how much to weight analytics data vs. DNA defaults. Low when data is sparse; increases as more videos are published."],
    ]
    t = data_table(
        ["FUNCTION", "PURPOSE"],
        intel_fns,
        col_widths=[180, 280]
    )
    elems.append(t)
    elems.append(sp(8))

    elems.append(h2("4.3  Agent Injection via dna_loader.py"))
    elems.append(body(
        "The <font face='Courier'>dna_loader.py</font> module loads <font face='Courier'>dna_config.json</font> "
        "and appends a dynamic <font face='Courier'>channel_intelligence</font> section by calling "
        "<font face='Courier'>channel_insights.py</font> at load time. This injected block is included "
        "in the system prompt of every agent that calls <font face='Courier'>dna_loader.get_dna()</font>. "
        "The result is that all agents operate with both static brand guidelines and live performance "
        "intelligence in every inference call, without any manual prompt management."
    ))
    elems.append(sp(4))

    elems.append(h2("4.4  DNA Confidence Scoring"))
    elems.append(body(
        "The DNA confidence block provides a numeric confidence score that indicates how much weight "
        "agents should give to analytics-derived guidance versus the static DNA defaults. The score "
        "starts near 0.0 when the channel has no published videos, increases linearly to ~0.5 at "
        "10 published videos, and approaches 1.0 at 50+ videos with diverse era coverage. This "
        "prevents analytics noise from early underperforming videos from corrupting agent decisions. "
        "The formula accounts for: total video count, era diversity, recency of data, and variance "
        "in performance metrics."
    ))
    elems.append(sp(4))

    elems.append(h2("4.5  Era Performance Tracking"))
    elems.append(body(
        "Every published video is tagged with a historical era at upload time and stored in "
        "Supabase. The analytics agent aggregates CTR, retention, and view velocity by era. "
        "The topic discovery agent uses era rankings to score candidate topics: a topic from "
        "a high-performing era (e.g., Medieval) receives a higher score multiplier than one "
        "from a lower-performing era (e.g., Modern), all else being equal. Era performance "
        "data is refreshed daily and is visible in the Telegram weekly report."
    ))
    elems.append(sp(4))

    elems.append(body(
        "<b>Closed-Loop Summary:</b> YouTube Analytics API \u2192 12_analytics_agent.py \u2192 "
        "channel_insights.json \u2192 channel_insights.py getters \u2192 dna_loader.py injection \u2192 "
        "all agent system prompts \u2192 better topic selection, narrative structure, SEO decisions "
        "\u2192 higher-performing videos \u2192 more analytics data \u2192 improved guidance."
    ))
    elems.append(PageBreak())
    return elems

# \u2500\u2500 Section 05 \u2014 Pipeline Monitoring & Quality \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
def build_s05():
    elems = [section_header("05", "Pipeline Monitoring & Quality")]

    elems.append(h2("5.1  Pipeline Doctor (pipeline_doctor.py)"))
    elems.append(body(
        "The Pipeline Doctor is the error classification and retry engine. It intercepts all "
        "agent exceptions and classifies them into six error categories, then applies a "
        "per-category retry strategy. This prevents unnecessary failures from transient API "
        "errors while avoiding infinite retry loops on systemic issues."
    ))
    elems.append(sp(6))

    elems.append(data_table(
        ["ERROR TYPE", "EXAMPLES", "RETRY STRATEGY", "MAX ATTEMPTS"],
        [
            ["rate_limit",  "HTTP 429, RateLimitError",                   "Exponential backoff starting at 30s", "5"],
            ["timeout",     "ConnectionTimeout, ReadTimeout",              "Fixed 15s delay, then retry",         "3"],
            ["context",     "Context window exceeded, token limit",        "Reduce input size, retry with truncated context", "2"],
            ["quota",       "Daily quota exceeded, billing limit",         "Skip stage, alert via Telegram, halt pipeline", "1"],
            ["json",        "JSON parse error, malformed model response",  "Retry with stricter JSON prompt",     "3"],
            ["not_found",   "404, resource missing, asset unavailable",   "Use fallback asset, continue",        "2"],
        ],
        col_widths=[75, 130, 170, 85]
    ))
    elems.append(sp(8))

    elems.append(h2("5.2  Pipeline Optimizer (pipeline_optimizer.py)"))
    elems.append(body(
        "Runs automatically after every successful pipeline completion. Uses Claude Sonnet 4.6 "
        "to analyse the quality of all stage outputs. Assigns an A\u2013F grade to each stage "
        "and an overall pipeline grade. Identifies specific weaknesses (e.g., thin research, "
        "weak hook, low B-roll relevance) and produces actionable improvement notes. Results "
        "are saved to <font face='Courier'>lessons_learned.json</font>, which is read by the "
        "topic discovery and narrative agents on subsequent runs to avoid repeating identified weaknesses."
    ))
    elems.append(sp(4))

    elems.append(h2("5.3  Quality Gates (quality_gates.py)"))
    elems.append(body(
        "Discrete pass/fail checks executed by run_pipeline.py after each stage. A gate failure "
        "can either halt the pipeline (hard gate) or log a warning and continue (soft gate)."
    ))
    elems.append(sp(6))

    elems.append(data_table(
        ["STAGE", "GATE CHECK", "TYPE", "FAILURE ACTION"],
        [
            ["Stage 4 (Script)",       "Word count \u2265 1,400 and \u2264 2,200",              "Hard", "Halt pipeline, alert operator"],
            ["Stage 5 (Verify)",       "Central twist has \u2265 3 verified sources",       "Hard", "Halt pipeline, alert operator"],
            ["Stage 5 (Verify)",       "All scene claims have \u2265 1 source",             "Soft", "Log warning, continue"],
            ["Stage 6 (SEO)",          "Title \u2264 70 characters",                         "Hard", "Truncate and retry SEO agent"],
            ["Stage 6 (SEO)",          "\u2265 15 tags present",                              "Soft", "Log warning, continue"],
            ["Stage 8 (Audio)",        "Audio duration \u2265 300 seconds",                  "Soft", "Log warning, continue"],
            ["Stage 7 (Scenes)",       "B-roll prompts present for \u2265 80% of scenes",  "Soft", "Log warning, continue"],
            ["Stage 12 (Render)",      "Output MP4 file size \u2265 50 MB",                 "Soft", "Log warning, continue"],
        ],
        col_widths=[110, 165, 55, 130]
    ))
    elems.append(sp(8))

    elems.append(h2("5.4  Telegram Alerting (notify.py)"))
    elems.append(body(
        "Real-time operational notifications sent via the Telegram Bot API to the operator\u2019s "
        "configured chat. Notifications are sent for: upload complete (with video URL and "
        "stats), pipeline failure (stage, error type, retry count), weekly summary report "
        "(Monday 10:00 UTC \u2014 videos published, era performance, A/B test results), "
        "ElevenLabs credit alert (daily 07:30 UTC check, alert if credits below threshold), "
        "and A/B title swap notifications (after 48h if CTR < 4%)."
    ))
    elems.append(sp(4))

    elems.append(h2("5.5  A/B Title Testing"))
    elems.append(body(
        "The SEO agent generates two title variants for every video: Title A (the primary "
        "title, published at upload time) and Title B (the challenger, stored in the state "
        "file and Supabase). The scheduler runs a daily A/B check at 07:00 UTC. After 48 hours, "
        "if the video\u2019s CTR is below 4% (the threshold for a healthy YouTube thumbnail), "
        "the scheduler automatically swaps to Title B via the YouTube Data API v3 snippet update "
        "endpoint and notifies the operator via Telegram. The swap is recorded in Supabase "
        "and factored into analytics agent performance calculations."
    ))
    elems.append(PageBreak())
    return elems

# \u2500\u2500 Section 06 \u2014 Functional Requirements \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
def build_s06():
    elems = [section_header("06", "Functional Requirements")]

    elems.append(h2("6.1  Content Generation"))
    def rr(rid, req, pri, note):
        return [
            Paragraph(rid, S("ri", fontName="Helvetica-Bold", fontSize=8, textColor=NAVY)),
            Paragraph(req, S("rr", fontName="Helvetica",      fontSize=8, textColor=GREY_DARK)),
            pri,
            Paragraph(note, S("rn", fontName="Helvetica",     fontSize=8, textColor=GREY_MID)),
        ]

    elems.append(req_table([
        rr("CG-01", "System shall discover, score, and queue \u2265 15 topics per week via topic discovery agent", p0(), "Monday 08:00 UTC schedule"),
        rr("CG-02", "Research agent shall gather \u2265 8 primary sources per topic using Claude + web search", p0(), "Sources stored in state file"),
        rr("CG-03", "Originality agent shall verify topic angle is not duplicated in published_topics Supabase table", p0(), "Hard duplication block"),
        rr("CG-04", "Narrative architect shall produce a 4-act story blueprint with injected retention data", p1(), "channel_insights data injected"),
        rr("CG-05", "Script writer shall produce 1,400\u20132,200 words per video following DNA voice guidelines", p0(), "Hard quality gate enforced"),
        rr("CG-06", "Fact verification agent shall confirm \u2265 3 independent sources per scene", p0(), "Halt if twist unverifiable"),
        rr("CG-07", "SEO agent shall generate title \u2264 70 chars, \u2265 15 tags, chapter markers, and A/B variant", p0(), "Haiku 4.5 model"),
        rr("CG-08", "All agent system prompts shall include injected DNA + channel_insights block", p1(), "Via dna_loader.get_dna()"),
    ]))
    elems.append(sp(8))

    elems.append(h2("6.2  Media Production"))
    elems.append(req_table([
        rr("MP-01", "Scene breakdown shall produce 12\u201320 scenes with B-roll search prompts for each", p1(), "Feeds footage hunt + image gen"),
        rr("MP-02", "Audio producer shall generate narration using ElevenLabs v3 George voice (ID: JBFqnCBsd6RMkjVDRZzb)", p0(), "With word-level timestamps"),
        rr("MP-03", "Audio chunking shall split script at sentence boundaries with max 4,500 chars per chunk", p1(), "Prevents ElevenLabs token limit"),
        rr("MP-04", "Footage hunter shall query Pexels API for each scene using B-roll prompts", p1(), "Free tier acceptable"),
        rr("MP-05", "Image generator shall produce one fal.ai Flux Pro oil-painting image per scene", p0(), "16:9 for long-form, 9:16 for shorts"),
        rr("MP-06", "TTS format agent shall strip meta-text (stage directions, bracketed notes) before ElevenLabs submission", p1(), "Prevents artefacts in narration"),
    ]))
    elems.append(sp(8))

    elems.append(h2("6.3  Rendering"))
    elems.append(req_table([
        rr("RN-01", "Remotion conversion stage shall produce video-data.json with all scene timings synced to word timestamps", p0(), "Consumed by Remotion renderer"),
        rr("RN-02", "Video render shall produce 1920\xd71080px, 24 fps, H.264 MP4 via Remotion headless Chrome", p0(), "With animated captions + music"),
        rr("RN-03", "Background music shall be mixed by mood (dark/action/reverent/mysterious) from Kevin MacLeod library", p2(), "setup_music.py pre-loads tracks"),
        rr("RN-04", "Short-form render shall produce 1080\xd71920px vertical MP4 for YouTube Shorts", p1(), "Runs in parallel sub-pipeline"),
    ]))
    elems.append(sp(8))

    elems.append(h2("6.4  Distribution"))
    elems.append(req_table([
        rr("DI-01", "YouTube uploader shall use OAuth2 resumable upload with automatic token refresh", p0(), "Token from YOUTUBE_TOKEN_JSON env"),
        rr("DI-02", "Uploader shall set thumbnail to scene 1 AI image resized to 1280\xd7720 with dark overlay", p1(), "YouTube thumbnail API"),
        rr("DI-03", "Uploader shall post source citations as a pinned comment with all research URLs", p2(), "YouTube comment threads API"),
        rr("DI-04", "Uploader shall apply real chapter markers derived from script section timestamps", p1(), "In video description"),
        rr("DI-05", "After 48 hours, A/B title check shall swap to Title B if CTR < 4%", p1(), "Via scheduler daily 07:00 UTC"),
    ]))
    elems.append(sp(8))

    elems.append(h2("6.5  Intelligence"))
    elems.append(req_table([
        rr("IN-01", "Analytics agent shall fetch YouTube Analytics API v2 data daily for all published videos", p0(), "Daily 06:00 UTC"),
        rr("IN-02", "Analytics agent shall classify videos by era and compute per-era CTR, retention, view velocity", p1(), "Written to channel_insights.json"),
        rr("IN-03", "channel_insights.py shall provide specialised getter functions for each agent type", p1(), "Graceful empty-string on no data"),
        rr("IN-04", "DNA confidence score shall increase proportionally with published video count and era diversity", p2(), "Prevents noisy early data bias"),
        rr("IN-05", "Pipeline optimizer shall grade all stage outputs A\u2013F post-run and save to lessons_learned.json", p1(), "Consumed by future runs"),
    ]))
    elems.append(sp(8))

    elems.append(h2("6.6  Monitoring"))
    elems.append(req_table([
        rr("MO-01", "Pipeline Doctor shall classify all errors and apply per-type retry strategies", p0(), "6 error categories"),
        rr("MO-02", "Telegram notification shall be sent for upload complete, pipeline failure, and weekly report", p0(), "Real-time operator alerting"),
        rr("MO-03", "Webhook server shall provide real-time SSE dashboard and /trigger endpoint", p1(), "Flask, port 8080"),
        rr("MO-04", "Quality gates shall be evaluated after each stage; hard gate failures halt pipeline", p0(), "Soft gates log and continue"),
        rr("MO-05", "ElevenLabs credit balance shall be checked daily; alert sent if below operational threshold", p1(), "Daily 07:30 UTC check"),
    ]))
    elems.append(PageBreak())
    return elems

# \u2500\u2500 Section 07 \u2014 Agent Specifications \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
def build_s07():
    elems = [section_header("07", "Agent Specifications")]
    elems.append(body(
        "The following table specifies all 14 agents in the pipeline. Stage numbers follow the "
        "run_pipeline.py execution order. Model assignments reflect cost/quality trade-offs: "
        "Opus 4.6 for deep reasoning tasks, Sonnet 4.6 for research and creative tasks, "
        "Haiku 4.5 for fast formatting and classification tasks."
    ))
    elems.append(sp(8))

    elems.append(data_table(
        ["STAGE", "AGENT / FILE", "MODEL", "KEY INPUTS", "KEY OUTPUTS", "QUALITY GATE"],
        [
            ["0  (Mon)", "Topic Discovery\n00_topic_discovery.py",    "Sonnet 4.6",  "Supabase queue, channel_insights era scores",         "Scored topic, era tag, slug",              "None"],
            ["1",        "Research\n01_research_agent.py",            "Sonnet 4.6",  "Topic, DNA, channel_insights block",                   "Fact sheet: 8+ sources, timeline, figures","None"],
            ["2",        "Originality\n02_originality_agent.py",      "Sonnet 4.6",  "Fact sheet, published_topics from Supabase",           "Unique angle, twist potential, hook moment","Duplication block"],
            ["3",        "Narrative Architect\n03_narrative_architect.py", "Sonnet 4.6", "Angle, DNA, narrative_intelligence block",         "4-act blueprint with retention guidance",  "None"],
            ["4",        "Script Writer\n04_script_writer.py",        "Sonnet 4.6",  "Blueprint, DNA, script_intelligence block",            "1,400\u20132,200 word narration script",        "Word count (Hard)"],
            ["5",        "Fact Verification\n05_fact_verification_agent.py", "Sonnet 4.6", "Script, source list from Stage 1",             "Verified script, source map per scene",    "Twist sources (Hard)"],
            ["6",        "SEO\n06_seo_agent.py",                      "Haiku 4.5",   "Script, angle, seo_intelligence block",               "Title A+B, description, tags, chapters",   "Title length (Hard)"],
            ["7",        "Scene Breakdown\n07_scene_breakdown_agent.py", "Sonnet 4.6", "Verified script, DNA",                              "12\u201320 scenes with B-roll prompts",         "B-roll coverage (Soft)"],
            ["8",        "Audio Producer\n08_audio_producer.py",      "ElevenLabs v3","TTS-formatted script, voice ID George",              "narration.mp3, word-level timestamps",     "Duration \u2265 300s (Soft)"],
            ["9",        "Footage Hunter\n09_footage_hunter.py",      "Pexels API",  "B-roll prompts per scene from Stage 7",               "Scene footage manifest (video URLs)",      "None"],
            ["10",       "Image Generation\nrun_pipeline.py",         "fal.ai Flux Pro","Scene descriptions, oil-painting style prompt",   "1 image per scene (16:9 or 9:16)",         "None"],
            ["11",       "Remotion Conversion\nrun_pipeline.py",      "None",        "Scene manifest, word timestamps, audio duration",     "video-data.json for Remotion renderer",    "None"],
            ["12",       "Video Render\nrun_pipeline.py",             "Remotion+Chrome","video-data.json, narration.mp3, music track",    "1080p MP4 with captions + music",          "File size \u2265 50 MB (Soft)"],
            ["13",       "YouTube Upload\n11_youtube_uploader.py",    "YouTube API", "MP4, SEO metadata, thumbnail, chapters",             "Video ID, live YouTube URL",               "Upload success (Hard)"],
            ["Daily",    "Analytics\n12_analytics_agent.py",          "Sonnet 4.6",  "YouTube Analytics API v2 all published videos",       "channel_insights.json updated",            "None"],
        ],
        col_widths=[42, 110, 72, 110, 90, 36]
    ))
    elems.append(PageBreak())
    return elems

# \u2500\u2500 Section 08 \u2014 API & Integration Requirements \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
def build_s08():
    elems = [section_header("08", "API & Integration Requirements")]

    apis = [
        ("8.1  Anthropic Claude API", [
            ("Auth method",       "API key (ANTHROPIC_API_KEY env var)"),
            ("Models used",       "claude-opus-4-6 (heavy reasoning), claude-sonnet-4-6 (agents + optimizer), claude-haiku-4-5 (SEO, fast tasks)"),
            ("Rate limits",       "Tier-dependent; default 50 RPM / 100K TPM for Sonnet"),
            ("Quota failure",     "Pipeline Doctor classifies as quota error; halts pipeline; Telegram alert sent"),
            ("Retry strategy",    "Exponential backoff on 429; up to 5 attempts"),
            ("Context limit",     "claude-sonnet-4-6: 200K tokens. Script + research fit well within budget."),
        ]),
        ("8.2  ElevenLabs v3 TTS", [
            ("Auth method",       "API key (ELEVENLABS_API_KEY env var)"),
            ("Endpoint",          "with-timestamps endpoint; returns audio + word-level alignment data"),
            ("Voice",             "George (JBFqnCBsd6RMkjVDRZzb) \u2014 deep, authoritative documentary narrator"),
            ("Chunking strategy", "Script split at sentence boundaries, max 4,500 characters per chunk"),
            ("Credit consumption","~14,000 chars per video at $0.025/1K = ~$0.35/video"),
            ("Quota failure",     "Daily credit check at 07:30 UTC via scheduler; Telegram alert below threshold"),
        ]),
        ("8.3  fal.ai Flux Pro", [
            ("Auth method",       "API key (FAL_KEY env var)"),
            ("Model",             "fal-ai/flux-pro \u2014 photorealistic with oil-painting style modifier"),
            ("Dimensions",        "1344\xd7768 (16:9) for long-form; 768\xd71344 (9:16) for short-form"),
            ("Cost",              "~$0.05/image; 15 images per long-form = ~$0.75/video"),
            ("Failure behaviour", "Missing images substituted with solid colour placeholder; pipeline continues"),
        ]),
        ("8.4  Pexels Video API", [
            ("Auth method",       "API key (PEXELS_API_KEY env var)"),
            ("Usage",             "Per-scene B-roll search using scene description from Stage 7 output"),
            ("Quota",             "Free tier: 200 requests/hour, 20,000/month"),
            ("Failure behaviour", "Scene defaults to AI image if Pexels returns no results"),
        ]),
        ("8.5  YouTube Data API v3", [
            ("Auth method",       "OAuth2 (google-auth library); token stored as YOUTUBE_TOKEN_JSON env var, restored at startup"),
            ("Usage",             "Video upload (resumable), snippet update, thumbnail set, comment thread post, title A/B swap"),
            ("Quota",             "10,000 units/day; upload costs 1,600 units; well within limits at 1 video/week"),
            ("Failure behaviour", "Upload retry up to 3 times; Telegram alert on persistent failure"),
        ]),
        ("8.6  YouTube Analytics API v2", [
            ("Auth method",       "Same OAuth2 token as Data API v3"),
            ("Metrics fetched",   "views, impressions, impressionClickThroughRate, averageViewPercentage, estimatedMinutesWatched"),
            ("Dimension",         "Per-video breakdown; aggregated by era in analytics agent"),
            ("Quota",             "No hard daily quota for Analytics API; shared with Data API quota pool"),
        ]),
        ("8.7  Supabase (PostgreSQL)", [
            ("Auth method",       "Service role key (SUPABASE_KEY + SUPABASE_URL env vars)"),
            ("Tables",            "topics (queue + published history), videos (per-video metadata), analytics (raw performance data)"),
            ("Usage",             "Topic deduplication, video archive, analytics history storage"),
            ("Failure behaviour", "Pipeline continues with reduced deduplication protection if Supabase unavailable"),
        ]),
        ("8.8  Telegram Bot API", [
            ("Auth method",       "Bot token (TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID env vars)"),
            ("Usage",             "Operational alerting: upload complete, pipeline failure, weekly report, ElevenLabs alerts, A/B swaps"),
            ("Failure behaviour", "Notification failure is non-blocking; pipeline continues regardless"),
        ]),
    ]

    for title, rows in apis:
        elems.append(KeepTogether([h2(title), kv_table(rows, [130, 330]), sp(8)]))

    elems.append(PageBreak())
    return elems

# \u2500\u2500 Section 09 \u2014 Non-Functional Requirements \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
def build_s09():
    elems = [section_header("09", "Non-Functional Requirements")]

    elems.append(h2("9.1  Performance"))
    nfr_perf = [
        ("NFR-P01", "End-to-end pipeline cycle time shall not exceed 5 hours from trigger to YouTube upload", p0(), "Remotion render is dominant cost at ~35 min"),
        ("NFR-P02", "AI inference stages (1\u20137) shall complete within 45 minutes total", p1(), "~4\u20136 min per Claude agent"),
        ("NFR-P03", "ElevenLabs audio generation shall complete within 10 minutes for a 1,800-word script", p1(), "Chunked requests parallelised where possible"),
        ("NFR-P04", "fal.ai image generation shall complete within 15 minutes for 15 scenes", p1(), "Sequential API calls; async batching in V2"),
    ]
    elems.append(req_table(nfr_perf, [55, 225, 70, 110]))
    elems.append(sp(8))

    elems.append(h2("9.2  Reliability"))
    nfr_rel = [
        ("NFR-R01", "Pipeline success rate shall be \u2265 95% across all weekly runs", p0(), "Pipeline Doctor retry logic"),
        ("NFR-R02", "Failed pipeline shall be resumable from any stage without re-running prior stages", p0(), "--from-stage N flag"),
        ("NFR-R03", "API quota failures shall trigger Telegram alert and graceful halt, not crash", p0(), "Pipeline Doctor quota handler"),
        ("NFR-R04", "YouTube token expiry shall be handled automatically with no operator action required", p1(), "google-auth auto-refresh"),
        ("NFR-R05", "Short-form pipeline failure shall never halt the long-form pipeline", p0(), "Isolated try/except wrapper"),
    ]
    elems.append(req_table(nfr_rel, [55, 225, 70, 110]))
    elems.append(sp(8))

    elems.append(h2("9.3  Security"))
    nfr_sec = [
        ("NFR-S01", "All API credentials shall be stored as Railway environment variables, never in source code", p0(), "Includes YouTube OAuth token"),
        ("NFR-S02", "Supabase service role key shall not be exposed in any log output or state file", p0(), "Key masked in all log lines"),
        ("NFR-S03", "State files shall not contain raw API keys or credentials", p1(), "State contains only production artefacts"),
        ("NFR-S04", "Webhook /trigger endpoint shall not require authentication in V1", p2(), "Rate limiting recommended in V2"),
    ]
    elems.append(req_table(nfr_sec, [55, 225, 70, 110]))
    elems.append(sp(8))

    elems.append(h2("9.4  Scalability"))
    nfr_sca = [
        ("NFR-SC01", "Pipeline architecture shall support scaling to 5 videos/week without code changes", p2(), "Scheduler cron only change required"),
        ("NFR-SC02", "ElevenLabs credits shall be monitored; scaling requires credit tier upgrade", p1(), "Daily credit check in scheduler"),
        ("NFR-SC03", "Intelligence system shall maintain accuracy as video archive grows beyond 100 videos", p2(), "Era bucketing prevents overfitting"),
    ]
    elems.append(req_table(nfr_sca, [55, 225, 70, 110]))
    elems.append(sp(8))

    elems.append(h2("9.5  Observability"))
    nfr_obs = [
        ("NFR-O01", "Every stage shall write a timestamped log entry to stdout (captured by Railway logs)", p1(), "Structured logging format"),
        ("NFR-O02", "Pipeline state file shall serve as the full audit trail for every production run", p1(), "One state file per video"),
        ("NFR-O03", "Webhook SSE endpoint shall stream live pipeline status to any connected browser", p2(), "Flask /events SSE stream"),
        ("NFR-O04", "Pipeline Optimizer grade report shall be stored persistently in lessons_learned.json", p2(), "Feeds back into future runs"),
    ]
    elems.append(req_table(nfr_obs, [55, 225, 70, 110]))
    elems.append(PageBreak())
    return elems

# \u2500\u2500 Section 10 \u2014 Data Models \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
def build_s10():
    elems = [section_header("10", "Data Models")]

    elems.append(h2("10.1  State File Schema"))
    elems.append(body(
        "The state file is the single shared data store for a pipeline run. It is created by "
        "run_pipeline.py at Stage 0 and written to after every stage. All agents read from and "
        "write to this file. The file path follows the pattern: "
        "<font face='Courier'>outputs/YYYYMMDD_HHMMSS_&lt;slug&gt;_state.json</font>."
    ))
    elems.append(sp(4))
    elems.append(code(
        '{\n'
        '  "meta": {\n'
        '    "topic": "string",\n'
        '    "slug":  "string",\n'
        '    "era":   "Ancient|Medieval|Renaissance|Early Modern|Modern|Contemporary",\n'
        '    "created_at": "ISO-8601 timestamp",\n'
        '    "pipeline_version": "string"\n'
        '  },\n'
        '  "stage_0": { "topic_data": { ... } },\n'
        '  "stage_1": { "research": { "core_facts": [...], "key_figures": [...],\n'
        '                "timeline": [...], "primary_sources": [...] } },\n'
        '  "stage_2": { "angle": "string", "twist_potential": "string",\n'
        '               "hook_moment": "string", "central_figure": "string" },\n'
        '  "stage_3": { "blueprint": { "act_1": {...}, "act_2": {...},\n'
        '               "act_3": {...}, "act_4": {...} } },\n'
        '  "stage_4": { "script": "string (full narration text)" },\n'
        '  "stage_5": { "verified_script": "string", "source_map": { "scene_N": [...] } },\n'
        '  "stage_6": { "title_a": "string", "title_b": "string",\n'
        '               "description": "string", "tags": [...], "chapters": [...] },\n'
        '  "stage_7": { "scenes": [{ "number": N, "narration": "string",\n'
        '               "broll_prompt": "string", "duration_est": N }] },\n'
        '  "stage_8": { "audio_path": "string", "timestamps": { "words": [...] },\n'
        '               "duration_seconds": N },\n'
        '  "stage_9": { "footage": [{ "scene": N, "video_url": "string" }] },\n'
        '  "stage_10": { "images": [{ "scene": N, "image_path": "string" }] },\n'
        '  "stage_11": { "video_data_path": "string" },\n'
        '  "stage_12": { "render_path": "string", "file_size_mb": N },\n'
        '  "stage_13": { "youtube_id": "string", "youtube_url": "string",\n'
        '                "upload_timestamp": "ISO-8601" }\n'
        '}'
    ))
    elems.append(sp(8))

    elems.append(h2("10.2  channel_insights.json Schema"))
    elems.append(body(
        "Written by the analytics agent daily. Read by channel_insights.py at agent runtime. "
        "The file is stored on the Railway persistent volume at "
        "<font face='Courier'>/app/channel_insights.json</font>."
    ))
    elems.append(sp(4))
    elems.append(code(
        '{\n'
        '  "generated_at": "ISO-8601 timestamp",\n'
        '  "video_count": N,\n'
        '  "era_performance": {\n'
        '    "Ancient":      { "avg_ctr": 0.xx, "avg_retention": 0.xx, "video_count": N },\n'
        '    "Medieval":     { "avg_ctr": 0.xx, "avg_retention": 0.xx, "video_count": N },\n'
        '    "Renaissance":  { ... },\n'
        '    "Early Modern": { ... },\n'
        '    "Modern":       { ... },\n'
        '    "Contemporary": { ... }\n'
        '  },\n'
        '  "top_performing_eras": ["Medieval", "Ancient", ...],\n'
        '  "title_patterns": {\n'
        '    "high_ctr_formats": [...],\n'
        '    "optimal_length_range": [N, N],\n'
        '    "top_emotional_hooks": [...]\n'
        '  },\n'
        '  "narrative_insights": {\n'
        '    "optimal_word_count": [N, N],\n'
        '    "high_retention_structures": [...]\n'
        '  },\n'
        '  "dna_confidence_score": 0.xx,\n'
        '  "claude_analysis": "string (free-form qualitative analysis)"\n'
        '}'
    ))
    elems.append(sp(8))

    elems.append(h2("10.3  Supabase Tables"))
    elems.append(data_table(
        ["TABLE", "KEY COLUMNS", "PURPOSE"],
        [
            ["topics",    "id, topic, slug, era, score, status (queued/in_progress/published/skipped), created_at",
             "Topic queue and deduplication store. ORACLE writes; pipeline reads to select next topic."],
            ["videos",    "id, topic_id, youtube_id, title_a, title_b, era, published_at, ab_swapped",
             "Video archive. Used for originality checking, A/B tracking, and analytics enrichment."],
            ["analytics", "id, video_id, fetched_at, views, impressions, ctr, retention, watch_minutes",
             "Raw YouTube Analytics data per video per fetch. Analytics agent reads to compute insights."],
        ],
        col_widths=[70, 210, 180]
    ))
    elems.append(PageBreak())
    return elems

# \u2500\u2500 Section 11 \u2014 Error Handling & Resilience \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
def build_s11():
    elems = [section_header("11", "Error Handling & Resilience")]

    elems.append(h2("11.1  Pipeline Doctor Retry Matrix"))
    elems.append(body(
        "The Pipeline Doctor intercepts all unhandled exceptions from agent execution. It "
        "inspects the exception type, HTTP status code, and error message to classify the "
        "error. It then applies the appropriate retry strategy. If all retries are exhausted, "
        "the pipeline halts and sends a Telegram alert with the error classification, stage, "
        "and last exception message."
    ))
    elems.append(sp(6))
    elems.append(data_table(
        ["ERROR CLASS", "DETECTION SIGNALS", "STRATEGY", "MAX RETRIES", "ESCALATION"],
        [
            ["rate_limit",  "HTTP 429, RateLimitError, 'rate limit' in message",      "Exponential backoff: 30s, 60s, 120s, 240s, 480s", "5", "Telegram alert after 3 failures"],
            ["timeout",     "ConnectTimeout, ReadTimeout, asyncio.TimeoutError",       "Wait 15s, retry with same input",                  "3", "Telegram alert + halt"],
            ["context",     "'context window', 'token limit exceeded'",               "Truncate input by 20%, retry",                     "2", "Halt with input_too_large flag"],
            ["quota",       "HTTP 429 (billing), 'quota exceeded', 'insufficient credits'", "Log, alert via Telegram, halt pipeline immediately", "1", "Mandatory operator action"],
            ["json",        "JSONDecodeError, malformed JSON in model response",       "Retry with stricter JSON-only system prompt",      "3", "Fallback to plain text extraction"],
            ["not_found",   "HTTP 404, FileNotFoundError, 'resource not found'",      "Use fallback (placeholder image / silence clip)",  "2", "Log and continue if fallback available"],
        ],
        col_widths=[65, 130, 140, 55, 70]
    ))
    elems.append(sp(8))

    elems.append(h2("11.2  Quota Management"))
    elems.append(body(
        "API quotas are the primary systemic risk to pipeline reliability. The following "
        "controls are in place:"
    ))
    elems.append(sp(4))
    quota_items = [
        ("<b>Anthropic:</b> No hard daily quota for Sonnet/Haiku at standard tier. Token consumption monitored via API response headers. Context truncation prevents runaway usage."),
        ("<b>ElevenLabs:</b> Credit balance checked daily at 07:30 UTC. Telegram alert sent when balance drops below a configurable threshold. Script chunking ensures no single request exceeds API limits."),
        ("<b>fal.ai:</b> Per-call billing; no hard quota. Monthly spend monitored via fal.ai dashboard. Image count capped at 20 per pipeline run by quality_gates.py."),
        ("<b>YouTube Data API:</b> 10,000 units/day. Video upload costs 1,600 units; thumbnail set costs 50 units; comment post costs 50 units. Total per-video: ~1,700 units. Capacity: ~5 videos/day before quota hit."),
        ("<b>Pexels:</b> 200 requests/hour free tier. Scene count (12\u201320 per video) is well within limit. Scenes with no results fall back to AI images silently."),
        ("<b>Supabase:</b> Free tier supports current read/write volume. Connection pooling via supabase-py client prevents connection exhaustion."),
    ]
    for item in quota_items:
        elems.append(bullet(item))
    elems.append(sp(8))

    elems.append(h2("11.3  Partial Recovery via --from-stage"))
    elems.append(body(
        "Every stage writes its output to the shared state file before the next stage begins. "
        "If the pipeline fails at Stage N, all work from Stages 0 through N-1 is preserved. "
        "The operator can resume from the failed stage by running: "
        "<font face='Courier'>python run_pipeline.py --resume outputs/&lt;state_file&gt;.json</font> "
        "or force a specific stage with "
        "<font face='Courier'>--from-stage N</font>. "
        "This eliminates the need to re-run expensive AI stages (research, scripting, TTS) "
        "after transient failures in later stages (rendering, upload)."
    ))
    elems.append(PageBreak())
    return elems

# \u2500\u2500 Section 12 \u2014 Operational Requirements \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
def build_s12():
    elems = [section_header("12", "Operational Requirements")]

    elems.append(h2("12.1  Railway Deployment"))
    elems.append(body(
        "The system is deployed as a single Railway service from a GitHub repository with "
        "auto-deploy on push to main. The Dockerfile installs Python 3.11, Node.js 20, "
        "Chromium (for Remotion headless render), and all Python and Node dependencies. "
        "Build time is approximately 10 minutes due to Chromium installation. The service "
        "runs the scheduler.py daemon as the container entrypoint."
    ))
    elems.append(sp(4))
    elems.append(kv_table([
        ("Entrypoint",          "python scheduler.py"),
        ("Persistent volume",   "Mounted at /app/outputs. Stores state files, rendered MP4s, channel_insights.json, lessons_learned.json"),
        ("YouTube OAuth",       "Token JSON restored from YOUTUBE_TOKEN_JSON env var at startup into /app/token.json"),
        ("Health check",        "Flask webhook server on port 8080; Railway health check at /status endpoint"),
        ("Build command",       "Dockerfile: apt-get chromium, npm install in /app/remotion, pip install -r requirements.txt"),
        ("Auto-deploy",         "GitHub push to main branch triggers Railway rebuild and redeploy automatically"),
    ], [140, 320]))
    elems.append(sp(8))

    elems.append(h2("12.2  Scheduling"))
    elems.append(body("All times are UTC. The Python schedule library runs in scheduler.py with a 60-second polling loop."))
    elems.append(sp(6))
    elems.append(data_table(
        ["SCHEDULE", "JOB", "ACTION"],
        [
            ["Monday 08:00 UTC",    "Topic Discovery",       "Run 00_topic_discovery.py. Score and queue 15 topics in Supabase."],
            ["Tuesday 09:00 UTC",   "Video Production",      "Run run_pipeline.py. Execute all 14 stages. Publish to YouTube."],
            ["Daily 06:00 UTC",     "Analytics",             "Run 12_analytics_agent.py. Fetch YouTube Analytics. Update channel_insights.json."],
            ["Daily 07:00 UTC",     "A/B Title Check",       "Check CTR for all videos published 48+ hours ago. Swap to Title B if CTR < 4%."],
            ["Daily 07:30 UTC",     "ElevenLabs Credit Check","Fetch ElevenLabs account balance. Send Telegram alert if below threshold."],
            ["Monday 10:00 UTC",    "Weekly Telegram Report","Summarise: videos published, era performance, A/B results, cost estimate."],
        ],
        col_widths=[110, 110, 240]
    ))
    elems.append(sp(8))

    elems.append(h2("12.3  Cost Model"))
    elems.append(body("Per-video cost breakdown at current usage levels (1 video/week):"))
    elems.append(sp(6))
    elems.append(data_table(
        ["SERVICE", "USAGE", "UNIT COST", "PER VIDEO", "MONTHLY (4 VIDEOS)"],
        [
            ["Anthropic Claude (Sonnet \xd75)", "~300K tokens total across all agents", "$3/MTok in, $15/MTok out", "~$0.60", "~$2.40"],
            ["ElevenLabs v3",                  "~14,000 chars narration",              "$0.025/1K chars",          "~$0.35", "~$1.40"],
            ["fal.ai Flux Pro",                "15 images per video",                  "~$0.05/image",             "~$0.75", "~$3.00"],
            ["Pexels API",                     "12\u201320 footage searches",                "Free tier",                "$0.00",  "$0.00"],
            ["Railway hosting",                "Persistent container",                 "~$10\u201320/month",            "\u2014",      "$10\u201320"],
            ["Supabase",                       "Low volume reads/writes",              "Free tier",                "$0.00",  "$0.00"],
            ["TOTAL",                          "",                                    "",                         "~$1.70\u2013$2.50", "~$17\u201330"],
        ],
        col_widths=[120, 100, 80, 60, 100]
    ))
    elems.append(sp(8))

    elems.append(h2("12.4  Monitoring"))
    monitoring = [
        ("Primary monitoring",   "Telegram Bot notifications for all critical events (upload complete, failure, weekly report)"),
        ("Live dashboard",       "Webhook server SSE stream at http://&lt;railway-url&gt;:8080 shows real-time stage progress"),
        ("Pipeline logs",        "Full stdout captured by Railway logs; accessible via Railway dashboard"),
        ("State file audit",     "Every pipeline run\u2019s complete input/output chain preserved in the state file on persistent volume"),
        ("Quality grading",      "Pipeline Optimizer writes A\u2013F grade report to lessons_learned.json after every successful run"),
        ("Cost visibility",      "Weekly Telegram report includes estimated API cost breakdown for the week"),
    ]
    elems.append(kv_table(monitoring, [140, 320]))
    elems.append(PageBreak())
    return elems

# \u2500\u2500 Section 13 \u2014 Risks & Mitigations \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
def build_s13():
    elems = [section_header("13", "Risks & Mitigations")]

    elems.append(body(
        "The following risk register covers the primary operational, technical, and strategic "
        "risks to pipeline reliability, content quality, and channel viability. Risks are "
        "rated by impact (1\u20135) and likelihood (1\u20135), with combined score = impact \xd7 likelihood."
    ))
    elems.append(sp(8))

    risk_hdr = [
        Paragraph("<b>ID</b>",          S("th", fontName="Helvetica-Bold", fontSize=8, textColor=white)),
        Paragraph("<b>Risk</b>",         S("th", fontName="Helvetica-Bold", fontSize=8, textColor=white)),
        Paragraph("<b>Impact</b>",       S("th", fontName="Helvetica-Bold", fontSize=8, textColor=white)),
        Paragraph("<b>Likelihood</b>",   S("th", fontName="Helvetica-Bold", fontSize=8, textColor=white)),
        Paragraph("<b>Mitigation</b>",   S("th", fontName="Helvetica-Bold", fontSize=8, textColor=white)),
    ]
    risks = [
        risk_row("R-01", "Anthropic API outage during Tuesday production run halts pipeline entirely",
                 "HIGH", "Low", "Pipeline Doctor retry with backoff; manual --resume when service restored; Telegram alert", RED_SOFT),
        risk_row("R-02", "ElevenLabs credit exhaustion mid-pipeline produces video with no audio",
                 "HIGH", "Medium", "Daily credit check + alert; pre-run balance gate; automatic halt with clear error message", RED_SOFT),
        risk_row("R-03", "YouTube OAuth token expiry prevents upload after full production cycle completed",
                 "HIGH", "Low", "google-auth auto-refresh; token backed up in env var; upload retry with token regeneration", AMBER),
        risk_row("R-04", "Fact verification passes a historically inaccurate claim due to hallucinated sources",
                 "HIGH", "Medium", "Minimum 3-source verification requirement; Claude instructed to prefer primary sources; operator spot-check recommended", RED_SOFT),
        risk_row("R-05", "YouTube policy change or copyright claim on AI-generated or Pexels content",
                 "MEDIUM", "Low", "All stock footage from Pexels (licensed); AI images are original; channel monitored for policy violations", AMBER),
        risk_row("R-06", "Railway container memory exhaustion during Remotion headless Chrome render",
                 "MEDIUM", "Medium", "Remotion configured at concurrency=1; Railway service memory limit set to 4 GB; render timeout fallback", AMBER),
        risk_row("R-07", "Analytics feedback loop amplifies a local maximum, reducing topic diversity over time",
                 "MEDIUM", "Medium", "DNA confidence score caps analytics influence; diversity check in topic discovery agent; operator can reset insights file", AMBER),
        risk_row("R-08", "Pexels API free tier rate limit hit on weeks with multiple pipeline runs",
                 "LOW", "Medium", "AI images serve as B-roll fallback; 200 req/hour well above per-run usage at current cadence", GREEN_SOFT),
    ]
    t = Table([risk_hdr] + risks, colWidths=[35, 145, 55, 65, 160], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND",     (0,0), (-1,0), TABLE_HEAD),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [white, TABLE_ALT]),
        ("GRID",           (0,0), (-1,-1), 0.4, GREY_BORDER),
        ("TOPPADDING",     (0,0), (-1,-1), 5),
        ("BOTTOMPADDING",  (0,0), (-1,-1), 5),
        ("LEFTPADDING",    (0,0), (-1,-1), 6),
        ("RIGHTPADDING",   (0,0), (-1,-1), 6),
        ("VALIGN",         (0,0), (-1,-1), "TOP"),
        ("FONTSIZE",       (0,1), (-1,-1), 8),
    ]))
    elems.append(t)
    elems.append(PageBreak())
    return elems

# \u2500\u2500 Section 14 \u2014 Roadmap \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
def build_s14():
    elems = [section_header("14", "Roadmap")]

    elems.append(h2("14.1  V1 \u2014 Current (Live, March 2026)"))
    elems.append(body(
        "The current production system is fully operational on Railway. All 14 stages of the "
        "long-form pipeline are live, the short-form sub-pipeline runs in parallel, the "
        "closed-loop intelligence system refreshes daily, and the scheduler manages the "
        "complete weekly production cadence autonomously."
    ))
    elems.append(sp(4))
    v1_features = [
        "14-stage long-form documentary pipeline (Stage 0\u201313)",
        "Short-form vertical video sub-pipeline (7 stages, runs in parallel after Stage 2)",
        "Closed-loop analytics intelligence system (daily, 6 getter functions, DNA confidence scoring)",
        "Pipeline Doctor error classification + retry engine (6 error types)",
        "Pipeline Optimizer post-run quality grading (A\u2013F, lessons_learned.json)",
        "Quality gates at every critical stage (hard and soft gates)",
        "A/B title testing with automatic swap after 48h if CTR < 4%",
        "Telegram Bot notifications for all operational events",
        "Real-time SSE dashboard via Flask webhook server",
        "Full pipeline resumability via --from-stage N flag",
        "Railway persistent volume for output and intelligence file storage",
        "Weekly automated scheduling with 6 distinct cron jobs",
    ]
    for f in v1_features:
        elems.append(bullet(f))
    elems.append(sp(8))

    elems.append(h2("14.2  V2 \u2014 Next (Planned, H2 2026)"))
    elems.append(body(
        "V2 focuses on expanding distribution reach, improving intelligence fidelity, "
        "and reducing per-video cost through parallelisation and model routing optimisation."
    ))
    elems.append(sp(4))
    v2_features = [
        ("Cross-platform distribution",   "Automated publishing to TikTok, Instagram Reels, and X with format-adapted versions"),
        ("Multi-channel operation",        "Single pipeline deployment supports multiple YouTube channels with isolated DNA configs"),
        ("Real-time analytics dashboard", "Replace SSE stream with a persistent web dashboard showing per-video performance trends"),
        ("Parallel image generation",     "Batch fal.ai requests in parallel to reduce Stage 10 time from 15 min to < 3 min"),
        ("Script-to-chapters automation", "Fully automatic chapter generation from word timestamps without manual review"),
        ("Multi-language narration",       "ElevenLabs multilingual voice output for Spanish, French, German YouTube markets"),
        ("Thumbnail A/B testing",          "Test two thumbnail variants alongside title A/B testing for compound CTR optimisation"),
        ("Operator web UI",                "Replace Telegram-only operator interface with a lightweight web control panel"),
    ]
    v2_data = [[
        Paragraph(f"<b>{f}</b>", S("v2k", fontName="Helvetica-Bold", fontSize=8, textColor=NAVY)),
        Paragraph(d, S("v2v", fontName="Helvetica", fontSize=8, textColor=GREY_DARK)),
    ] for f, d in v2_features]
    t = Table(v2_data, colWidths=[160, 300])
    t.setStyle(TableStyle([
        ("ROWBACKGROUNDS", (0,0),(-1,-1), [white, TABLE_ALT]),
        ("GRID",          (0,0),(-1,-1), 0.4, GREY_BORDER),
        ("TOPPADDING",    (0,0),(-1,-1), 5),
        ("BOTTOMPADDING", (0,0),(-1,-1), 5),
        ("LEFTPADDING",   (0,0),(-1,-1), 8),
        ("VALIGN",        (0,0),(-1,-1), "TOP"),
    ]))
    elems.append(t)
    elems.append(sp(8))

    elems.append(h2("14.3  V3 \u2014 Vision (2027+)"))
    elems.append(body(
        "V3 represents a qualitative leap from a pipeline to a platform. The intelligence "
        "system evolves from passive observation to active production strategy. The system "
        "moves from scheduled batch production to an always-on, demand-driven model."
    ))
    elems.append(sp(4))
    v3_features = [
        "Autonomous channel strategy: system identifies emerging historical events and produces timely content without human topic input",
        "Proprietary voice model: fine-tuned ElevenLabs voice trained on The Obsidian Archive narration corpus for maximum brand consistency",
        "On-device Remotion cloud rendering: migrate from Railway Chrome to dedicated render farm for sub-10-minute video generation",
        "Generative thumbnail design: replace static scene 1 thumbnail with a purpose-designed generative thumbnail AI per video",
        "Viewer behaviour modelling: integrate YouTube audience retention graphs per-scene to identify and eliminate engagement drop-offs",
        "Automated monetisation strategy: A/B test card placement, end screens, and description link positioning for revenue optimisation",
        "Multi-modal research: add primary source document ingestion (OCR + PDF parsing) for deeper historical accuracy",
    ]
    for f in v3_features:
        elems.append(bullet(f))

    return elems

# \u2500\u2500 Build \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
def build():
    doc = SimpleDocTemplate(
        str(OUT),
        pagesize=A4,
        leftMargin=20*mm, rightMargin=20*mm,
        topMargin=32*mm,  bottomMargin=22*mm,
        title="The Obsidian Archive \u2014 PRD v2.0",
        author="The Obsidian Archive",
        subject="Autonomous AI Documentary Production Pipeline \u2014 Product Requirements Document",
    )

    story = []
    story += build_cover()
    story += build_toc()
    story += build_s01()
    story += build_s02()
    story += build_s03()
    story += build_s04()
    story += build_s05()
    story += build_s06()
    story += build_s07()
    story += build_s08()
    story += build_s09()
    story += build_s10()
    story += build_s11()
    story += build_s12()
    story += build_s13()
    story += build_s14()

    def first_page(canvas, doc):
        on_cover(canvas, doc)

    def later_pages(canvas, doc):
        on_page(canvas, doc)

    doc.build(story, onFirstPage=first_page, onLaterPages=later_pages)
    print(f"Generated: {OUT}")

if __name__ == "__main__":
    build()
