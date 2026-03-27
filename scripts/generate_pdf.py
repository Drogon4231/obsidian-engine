#!/usr/bin/env python3
"""Generate The Obsidian Archive \u2014 System Architecture & Operations Report v2.0."""

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.colors import HexColor, white
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether
)
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "The Obsidian Archive \u2014 System Documentation.pdf"

W, H = A4

# \u2500\u2500 Colour palette \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
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
CODE_BG     = HexColor("#f8f8f8")
CODE_BORDER = HexColor("#e2e5e8")
COVER_BG    = HexColor("#1a2744")
AMBER       = HexColor("#d97706")

# \u2500\u2500 Styles \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
def S(name, **kw):
    return ParagraphStyle(name, **kw)

SC_TITLE    = S("sc_title",    fontName="Helvetica-Bold",  fontSize=32, leading=40, textColor=white,    alignment=TA_LEFT,   spaceAfter=8)
SC_SUB      = S("sc_sub",      fontName="Helvetica",       fontSize=14, leading=20, textColor=HexColor("#aab4c8"), alignment=TA_LEFT, spaceAfter=6)
SC_TAG      = S("sc_tag",      fontName="Helvetica",       fontSize=9,  leading=13, textColor=HexColor("#8899bb"), alignment=TA_LEFT, spaceAfter=4)
SC_LABEL    = S("sc_label",    fontName="Helvetica-Bold",  fontSize=8,  leading=11, textColor=ACCENT,   alignment=TA_LEFT,   spaceAfter=2, spaceBefore=2)

SH1         = S("sh1",         fontName="Helvetica-Bold",  fontSize=18, leading=24, textColor=NAVY,      spaceBefore=22, spaceAfter=8)
SH2         = S("sh2",         fontName="Helvetica-Bold",  fontSize=13, leading=18, textColor=NAVY,      spaceBefore=16, spaceAfter=6)
SH3         = S("sh3",         fontName="Helvetica-Bold",  fontSize=11, leading=15, textColor=NAVY_LIGHT, spaceBefore=10, spaceAfter=4)
SH4         = S("sh4",         fontName="Helvetica-Bold",  fontSize=9,  leading=13, textColor=GREY_DARK,  spaceBefore=8,  spaceAfter=3)
SBODY       = S("sbody",       fontName="Helvetica",       fontSize=9,  leading=14, textColor=GREY_DARK, spaceAfter=5, alignment=TA_JUSTIFY)
SBODY_SM    = S("sbody_sm",    fontName="Helvetica",       fontSize=8,  leading=12, textColor=GREY_MID,  spaceAfter=4)
SBULLET     = S("sbullet",     fontName="Helvetica",       fontSize=9,  leading=13, textColor=GREY_DARK, leftIndent=14, spaceAfter=3)
SBULLET2    = S("sbullet2",    fontName="Helvetica",       fontSize=8,  leading=12, textColor=GREY_MID,  leftIndent=28, spaceAfter=2)
SCODE       = S("scode",       fontName="Courier",         fontSize=8,  leading=12, textColor=GREY_DARK, backColor=CODE_BG, leftIndent=8, rightIndent=8, spaceAfter=6, spaceBefore=4, borderPadding=(5,5,5,5))
SLABEL      = S("slabel",      fontName="Helvetica-Bold",  fontSize=8,  leading=11, textColor=NAVY_LIGHT, spaceAfter=2, spaceBefore=6)
SCAPTION    = S("scaption",    fontName="Helvetica",       fontSize=7,  leading=10, textColor=GREY_MID,  alignment=TA_CENTER, spaceAfter=4)
STOC        = S("stoc",        fontName="Helvetica",       fontSize=10, leading=18, textColor=GREY_DARK, leftIndent=0)
STOC_SEC    = S("stoc_sec",    fontName="Helvetica-Bold",  fontSize=10, leading=18, textColor=NAVY)
STOC_SUB    = S("stoc_sub",    fontName="Helvetica",       fontSize=9,  leading=16, textColor=GREY_MID,  leftIndent=18)

# \u2500\u2500 Helpers \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
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
    safe = safe.replace(" ","&nbsp;").replace("\n","<br/>")
    return Paragraph(safe, SCODE)

def section_header(number, title):
    """Large numbered section opener."""
    data = [[
        Paragraph(f'<font color="{ACCENT.hexval()}">{number}</font>', S("sn", fontName="Helvetica-Bold", fontSize=28, leading=32, textColor=ACCENT)),
        Paragraph(title, S("st", fontName="Helvetica-Bold", fontSize=18, leading=22, textColor=NAVY)),
    ]]
    t = Table(data, colWidths=[36, 424])
    t.setStyle(TableStyle([
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("TOPPADDING",(0,0),(-1,-1),8),
        ("BOTTOMPADDING",(0,0),(-1,-1),4),
        ("LEFTPADDING",(0,0),(-1,-1),0),
        ("LINEBELOW",(0,0),(-1,-1),1,GREY_LINE),
    ]))
    return KeepTogether([sp(8), t,
                         HRFlowable(width="100%", thickness=2, color=ACCENT, spaceAfter=10, spaceBefore=4)])

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
    """Key-value info table."""
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

def stage_block(num, name, filename, model, inputs, outputs, notes, color_hex):
    c = HexColor(color_hex)
    hdr = Table([[
        Paragraph(f'<font color="{color_hex}"><b>Stage {num}</b></font>',
                  S("sn", fontName="Helvetica-Bold", fontSize=10, leading=13, textColor=c)),
        Paragraph(f'<b>{name}</b>',
                  S("sname", fontName="Helvetica-Bold", fontSize=10, leading=13, textColor=NAVY)),
        Paragraph(f'<font face="Courier" size="7">{filename}</font>',
                  S("sfn", fontName="Courier", fontSize=7, leading=10, textColor=GREY_MID, alignment=TA_RIGHT)),
    ]], colWidths=[60, 240, 160])
    hdr.setStyle(TableStyle([
        ("BACKGROUND",     (0,0),(-1,-1), GREY_LIGHT),
        ("LINEBELOW",      (0,0),(-1,-1), 2, c),
        ("TOPPADDING",     (0,0),(-1,-1), 6),
        ("BOTTOMPADDING",  (0,0),(-1,-1), 6),
        ("LEFTPADDING",    (0,0),(-1,-1), 8),
        ("RIGHTPADDING",   (0,0),(-1,-1), 8),
        ("VALIGN",         (0,0),(-1,-1), "MIDDLE"),
    ]))
    detail_data = [
        [Paragraph("<b>Model</b>",   S("dl", fontName="Helvetica-Bold", fontSize=8, textColor=GREY_MID)),
         Paragraph(model,            S("dv", fontName="Helvetica",      fontSize=8, textColor=GREY_DARK))],
        [Paragraph("<b>Inputs</b>",  S("dl", fontName="Helvetica-Bold", fontSize=8, textColor=GREY_MID)),
         Paragraph(inputs,           S("dv", fontName="Helvetica",      fontSize=8, textColor=GREY_DARK))],
        [Paragraph("<b>Outputs</b>", S("dl", fontName="Helvetica-Bold", fontSize=8, textColor=GREY_MID)),
         Paragraph(outputs,          S("dv", fontName="Helvetica",      fontSize=8, textColor=GREY_DARK))],
        [Paragraph("<b>Notes</b>",   S("dl", fontName="Helvetica-Bold", fontSize=8, textColor=GREY_MID)),
         Paragraph(notes,            S("dv", fontName="Helvetica",      fontSize=8, textColor=GREY_DARK))],
    ]
    detail = Table(detail_data, colWidths=[55, 405])
    detail.setStyle(TableStyle([
        ("TOPPADDING",    (0,0),(-1,-1), 3),
        ("BOTTOMPADDING", (0,0),(-1,-1), 3),
        ("LEFTPADDING",   (0,0),(-1,-1), 8),
        ("RIGHTPADDING",  (0,0),(-1,-1), 0),
        ("VALIGN",        (0,0),(-1,-1), "TOP"),
        ("LINEBELOW",     (0,0),(-1,-1), 0.4, GREY_BORDER),
    ]))
    return KeepTogether([hdr, detail, sp(6)])

# \u2500\u2500 Page callbacks \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
def cover_page(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(COVER_BG)
    canvas.rect(0, 0, W, H, fill=1, stroke=0)
    canvas.setFillColor(ACCENT)
    canvas.rect(0, 0, 8, H, fill=1, stroke=0)
    canvas.setFillColor(NAVY_LIGHT)
    canvas.rect(0, 0, W, 40*mm, fill=1, stroke=0)
    canvas.setFillColor(ACCENT)
    canvas.rect(0, 40*mm, W, 1.5, fill=1, stroke=0)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(HexColor("#8899bb"))
    canvas.drawString(20*mm, 14*mm, "CONFIDENTIAL  \u00b7  INTERNAL USE ONLY  \u00b7  The Obsidian Archive  \u00b7  2026")
    canvas.restoreState()

def later_pages(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(NAVY)
    canvas.rect(0, H-14*mm, W, 14*mm, fill=1, stroke=0)
    canvas.setFillColor(ACCENT)
    canvas.rect(0, H-14*mm, W, 0.8, fill=1, stroke=0)
    canvas.setFont("Helvetica-Bold", 7)
    canvas.setFillColor(white)
    canvas.drawString(20*mm, H-9*mm, "THE OBSIDIAN ARCHIVE")
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(HexColor("#8899bb"))
    canvas.drawCentredString(W/2, H-9*mm, "SYSTEM ARCHITECTURE & OPERATIONS REPORT")
    canvas.drawRightString(W-20*mm, H-9*mm, "CONFIDENTIAL")
    canvas.setFillColor(GREY_LIGHT)
    canvas.rect(0, 0, W, 10*mm, fill=1, stroke=0)
    canvas.setFillColor(GREY_LINE)
    canvas.rect(0, 10*mm, W, 0.5, fill=1, stroke=0)
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(GREY_MID)
    canvas.drawCentredString(W/2, 3.5*mm, f"Page {doc.page}")
    canvas.drawString(20*mm, 3.5*mm, "The Obsidian Archive \u2014 Proprietary & Confidential")
    canvas.drawRightString(W-20*mm, 3.5*mm, "System Documentation v2.0 \u00b7 March 2026")
    canvas.restoreState()

# \u2500\u2500 Build \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
def build():
    doc = SimpleDocTemplate(
        str(OUT),
        pagesize=A4,
        leftMargin=20*mm, rightMargin=20*mm,
        topMargin=20*mm,  bottomMargin=18*mm,
        title="The Obsidian Archive \u2014 System Architecture & Operations Report v2.0",
        author="The Obsidian Archive",
        subject="Autonomous AI Documentary Production Pipeline \u2014 System Documentation",
    )

    story = []

    # \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
    # COVER PAGE
    # \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
    story += [
        sp(55),
        Paragraph("THE OBSIDIAN ARCHIVE",
                  S("cov_label", fontName="Helvetica-Bold", fontSize=9, leading=12,
                    textColor=ACCENT, alignment=TA_LEFT, spaceAfter=10, letterSpacing=3)),
        Paragraph("System Architecture\n& Operations Report",
                  S("cov_title", fontName="Helvetica-Bold", fontSize=30, leading=38,
                    textColor=white, alignment=TA_LEFT, spaceAfter=6)),
        Paragraph("Autonomous AI Documentary Production Pipeline",
                  S("cov_sub", fontName="Helvetica", fontSize=13, leading=19,
                    textColor=HexColor("#aab4c8"), alignment=TA_LEFT, spaceAfter=6)),
        Paragraph("Version 2.0  \u00b7  March 2026  \u00b7  Confidential",
                  S("cov_ver", fontName="Helvetica", fontSize=9, leading=13,
                    textColor=HexColor("#8899bb"), alignment=TA_LEFT, spaceAfter=30)),
        HRFlowable(width="40%", thickness=1, color=ACCENT, spaceAfter=24, spaceBefore=0),
        Table([
            [Paragraph("14", S("cv_n", fontName="Helvetica-Bold", fontSize=24, leading=28, textColor=ACCENT)),
             Paragraph("Pipeline Stages", S("cv_l", fontName="Helvetica", fontSize=9, leading=12, textColor=HexColor("#8899bb")))],
            [Paragraph("3", S("cv_n2", fontName="Helvetica-Bold", fontSize=24, leading=28, textColor=ACCENT)),
             Paragraph("Claude AI Models", S("cv_l2", fontName="Helvetica", fontSize=9, leading=12, textColor=HexColor("#8899bb")))],
            [Paragraph("8", S("cv_n3", fontName="Helvetica-Bold", fontSize=24, leading=28, textColor=ACCENT)),
             Paragraph("External APIs", S("cv_l3", fontName="Helvetica", fontSize=9, leading=12, textColor=HexColor("#8899bb")))],
            [Paragraph("0", S("cv_n4", fontName="Helvetica-Bold", fontSize=24, leading=28, textColor=ACCENT)),
             Paragraph("Human touchpoints", S("cv_l4", fontName="Helvetica", fontSize=9, leading=12, textColor=HexColor("#8899bb")))],
        ], colWidths=[50, 200]),
        sp(80),
        HRFlowable(width="100%", thickness=0.5, color=HexColor("#2d3f6b"), spaceAfter=12),
        Table([[
            Paragraph("CLASSIFICATION", S("cl_k", fontName="Helvetica-Bold", fontSize=7, leading=9, textColor=HexColor("#556688"))),
            Paragraph("Proprietary & Confidential", S("cl_v", fontName="Helvetica", fontSize=7, leading=9, textColor=HexColor("#8899bb"))),
            Paragraph("AUDIENCE", S("cl_k2", fontName="Helvetica-Bold", fontSize=7, leading=9, textColor=HexColor("#556688"))),
            Paragraph("Engineering & Operations", S("cl_v2", fontName="Helvetica", fontSize=7, leading=9, textColor=HexColor("#8899bb"))),
        ]], colWidths=[80, 130, 80, 170]),
        PageBreak(),
    ]

    # \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
    # TABLE OF CONTENTS
    # \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
    story += [
        section_header("", "Table of Contents"),
        sp(10),
    ]
    toc_entries = [
        ("01", "System Overview",                        False),
        ("",   "1.1  What it produces",                 True),
        ("",   "1.2  How it runs",                      True),
        ("",   "1.3  Key capabilities",                 True),
        ("02", "Pipeline Architecture",                 False),
        ("",   "2.1  Long-form pipeline stage walkthrough", True),
        ("",   "2.2  Short-form sub-pipeline",          True),
        ("",   "2.3  Stage dependency graph",           True),
        ("03", "Channel Intelligence System",           False),
        ("",   "3.1  Analytics agent deep-dive",        True),
        ("",   "3.2  channel_insights.py interface",    True),
        ("",   "3.3  Data flow into agent prompts",     True),
        ("",   "3.4  DNA confidence scoring model",     True),
        ("04", "Supporting Infrastructure",             False),
        ("",   "4.1  scheduler.py",                     True),
        ("",   "4.2  webhook_server.py",                True),
        ("",   "4.3  pipeline_doctor.py",               True),
        ("",   "4.4  pipeline_optimizer.py",            True),
        ("",   "4.5  quality_gates.py",                 True),
        ("05", "Data Architecture",                     False),
        ("",   "5.1  State file lifecycle",             True),
        ("",   "5.2  channel_insights.json schema",     True),
        ("",   "5.3  Supabase schema",                  True),
        ("",   "5.4  DNA config structure",             True),
        ("06", "API Integration Specifications",        False),
        ("",   "6.1\u20136.8  All 8 external APIs",         True),
        ("07", "Deployment & Infrastructure",           False),
        ("",   "7.1  Railway setup",                    True),
        ("",   "7.2  Dockerfile overview",              True),
        ("",   "7.3  Environment variables",            True),
        ("",   "7.4  YouTube OAuth flow",               True),
        ("08", "Operations Runbook",                    False),
        ("",   "8.1\u20138.8  Common operator procedures",   True),
        ("09", "Cost & Performance Model",              False),
        ("",   "9.1  Per-video cost breakdown",         True),
        ("",   "9.2  Pipeline timing by stage",         True),
        ("10", "Troubleshooting Guide",                 False),
        ("",   "10.1  Symptom \u2192 Cause \u2192 Resolution (15 scenarios)", True),
    ]
    for num, title, is_sub in toc_entries:
        if is_sub:
            story.append(Paragraph(f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{title}", STOC_SUB))
        else:
            prefix = f"<b><font color='#c8973a'>{num}&nbsp;&nbsp;</font></b>" if num else ""
            story.append(Paragraph(f"{prefix}<b>{title}</b>", STOC_SEC))
    story.append(PageBreak())

    # \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
    # 01. SYSTEM OVERVIEW
    # \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
    story += [
        section_header("01", "System Overview"),
        sp(8),
        body(
            "The Obsidian Archive is a fully autonomous AI-powered YouTube documentary production "
            "pipeline. The system ingests a topic about dark or suppressed history, produces a "
            "complete 10-minute 1080p documentary video with professional voiceover, AI-generated "
            "visuals, licensed B-roll footage, animated captions, and background music \u2014 then "
            "publishes it to YouTube with complete SEO metadata. The entire process runs without "
            "any human intervention, from topic selection through to the live published video."
        ),
        sp(6),
        kv_table([
            ("Channel identity",    "The Obsidian Archive \u2014 dark and suppressed history documentaries. Every story is real. Every fact is verified."),
            ("Production rate",     "1 long-form video per week (Tuesday 09:00 UTC). Short-form video runs in parallel on the same schedule."),
            ("Infrastructure",      "Single Railway container. Python 3.11 + Node.js 20 + Chromium. Persistent volume at /app/outputs."),
            ("AI models",           "Claude Opus 4.6 (heavy reasoning), Sonnet 4.6 (research, creative, analytics), Haiku 4.5 (SEO, fast classification)"),
            ("Voice",               "ElevenLabs v3 \u2014 George voice (JBFqnCBsd6RMkjVDRZzb). word-level timestamps. Chunked at 4,500 chars."),
            ("Images",              "fal.ai Flux Pro. Oil-painting style. 16:9 for long-form, 9:16 for short-form. One image per scene."),
            ("Video renderer",      "Remotion (React/TypeScript). Headless Chrome render. 1080p H.264 MP4. Animated word-level captions."),
            ("Self-improvement",    "Daily analytics loop: YouTube Analytics API v2 \u2192 channel_insights.json \u2192 all agent system prompts"),
            ("Total cycle time",    "~4 hours end-to-end (AI stages ~45 min, TTS ~10 min, images ~15 min, render ~35 min, upload ~5 min)"),
            ("Cost per video",      "~$1.75\u2013$2.50 USD (Claude ~$0.60, ElevenLabs ~$0.35, fal.ai ~$0.80, Pexels free, Railway shared)"),
            ("Human touchpoints",   "Zero. The operator\u2019s only ongoing role is credential rotation and optional DNA config updates."),
        ]),
        sp(10),
        h2("Container Structure"),
        code(
            "Railway Container  (Python 3.11 + Node.js 20 + Chromium)\n"
            "\u2502\n"
            "\u251c\u2500\u2500 scheduler.py              Daemon process. 60s poll loop. Manages all cron jobs.\n"
            "\u2502   \u251c\u2500\u2500 webhook_server.py      Flask server port 8080 (background thread)\n"
            "\u2502   \u251c\u2500\u2500 Monday 08:00          \u2192 00_topic_discovery.py\n"
            "\u2502   \u251c\u2500\u2500 Tuesday 09:00         \u2192 run_pipeline.py (Stages 0\u201313)\n"
            "\u2502   \u251c\u2500\u2500 Daily 06:00           \u2192 12_analytics_agent.py\n"
            "\u2502   \u251c\u2500\u2500 Daily 07:00           \u2192 A/B title check\n"
            "\u2502   \u251c\u2500\u2500 Daily 07:30           \u2192 ElevenLabs credit check\n"
            "\u2502   \u2514\u2500\u2500 Monday 10:00          \u2192 Weekly Telegram report\n"
            "\u2502\n"
            "\u251c\u2500\u2500 /app/outputs/             Railway persistent volume\n"
            "\u2502   \u251c\u2500\u2500 *_state.json           Per-run pipeline checkpoints\n"
            "\u2502   \u251c\u2500\u2500 *_FINAL_VIDEO.mp4      Rendered long-form video\n"
            "\u2502   \u251c\u2500\u2500 *_SHORT_FINAL.mp4      Rendered short-form video\n"
            "\u2502   \u251c\u2500\u2500 channel_insights.json  Daily-refreshed intelligence data\n"
            "\u2502   \u2514\u2500\u2500 lessons_learned.json   Pipeline Optimizer grade history\n"
            "\u2502\n"
            "\u2514\u2500\u2500 /app/remotion/            React/TypeScript Remotion project\n"
            "    \u251c\u2500\u2500 src/video-data.json     Scene + timing data (written at Stage 11)\n"
            "    \u2514\u2500\u2500 public/                 narration.mp3, scene images (read by Chrome)"
        ),
        PageBreak(),
    ]

    # \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
    # 02. PIPELINE ARCHITECTURE
    # \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
    story += [
        section_header("02", "Pipeline Architecture"),
        sp(8),
        body(
            "The pipeline is orchestrated by run_pipeline.py, which executes stages sequentially "
            "and writes each stage\u2019s output to the shared state file before advancing. All stage "
            "inputs are read from the state file; no agent has direct knowledge of another agent\u2019s "
            "code. This isolation enables safe resumption from any point and makes each stage "
            "independently testable."
        ),
        sp(6),
        h2("2.1  Long-Form Pipeline Stage Walkthrough"),
        sp(4),
    ]

    stages = [
        ("0", "Topic Discovery", "00_topic_discovery.py", "Claude Sonnet 4.6",
         "Supabase topics queue, channel_insights era performance scores",
         "Selected topic with era tag, score, and slug written to state file",
         "Runs on Monday 08:00 schedule, not inline with Tuesday production run. Pulls from "
         "pre-populated Supabase queue. Uses era performance rankings from channel_insights.json "
         "to score and select the highest-potential topic. Checks published_topics to prevent "
         "reuse. Writes topic to Supabase with status=in_progress.", "#7c3aed"),
        ("1", "Research", "01_research_agent.py", "Claude Sonnet 4.6 + web search",
         "Selected topic, DNA block (from dna_loader), channel_insights global intelligence",
         "Structured fact sheet: core_facts, key_figures, timeline, suppressed_details, primary_sources, contradictions, archival_gems",
         "Two-pass process: (1) Claude with web_search tool finds primary sources, exact dates, "
         "contemporary accounts, and contradictions in the mainstream narrative. (2) Structures "
         "findings into a typed JSON fact sheet with 8+ verified sources. This output is read by "
         "every downstream content agent.", "#0891b2"),
        ("2", "Originality", "02_originality_agent.py", "Claude Sonnet 4.6 + web search",
         "Fact sheet from Stage 1, published_topics from Supabase",
         "Unique angle, twist potential, hook moment, central figure, is_experiment flag",
         "Searches YouTube to map competitive landscape for the topic. Loads the complete "
         "Obsidian Archive video history from Supabase to prevent angle duplication. Identifies "
         "the gap \u2014 the angle missed by both YouTube competitors and our own archive. After Stage 2 "
         "completes, the short-form sub-pipeline forks and runs in parallel.", "#4f46e5"),
        ("3", "Narrative Architect", "03_narrative_architect.py", "Claude Sonnet 4.6",
         "Originality output, DNA block, narrative_intelligence block from channel_insights",
         "4-act story blueprint with scene count guidance, pacing notes, and twist placement",
         "Constructs the documentary\u2019s structural skeleton. Act 1: hook and context setup. "
         "Act 2: escalating discovery. Act 3: revelation build. Act 4: twist reveal and resolution. "
         "The narrative_intelligence block injects data about which 4-act structures have achieved "
         "the highest average view percentage on the channel.", "#059669"),
        ("4", "Script Writer", "04_script_writer.py", "Claude Sonnet 4.6",
         "4-act blueprint, DNA block with full voice guidelines, script_intelligence block",
         "1,400\u20132,200 word narration script. DNA-guided tone, sentence rhythm, forbidden phrases.",
         "Writes the full narration script following the 4-act blueprint. DNA block enforces "
         "brand voice rules: second-person address, short declarative sentences, no passive voice, "
         "no hedge words. script_intelligence block provides optimal word count range and opening "
         "hook patterns based on historical performance. Hard quality gate: < 1,400 words halts pipeline.", "#d97706"),
        ("5", "Fact Verification", "05_fact_verification_agent.py", "Claude Sonnet 4.6 + web search",
         "Script from Stage 4, primary_sources list from Stage 1",
         "Verified script (claims flagged), source_map (per-scene source list), verification_report",
         "Iterates through every factual claim in the script and verifies it against \u2265 1 source "
         "from the Stage 1 source list. The central twist must be verified against \u2265 3 independent "
         "sources \u2014 this is a hard gate; pipeline halts if the twist cannot be verified. "
         "tts_format_agent.py strips stage directions and meta-text before passing to Stage 8.", "#dc2626"),
        ("6", "SEO", "06_seo_agent.py", "Claude Haiku 4.5",
         "Verified script, originality angle, seo_intelligence block from channel_insights",
         "Title A (primary), Title B (A/B challenger), description, 15+ tags, chapter markers",
         "Uses the fastest model (Haiku 4.5) for this classification-heavy task. seo_intelligence "
         "block injects historical title patterns that have achieved highest CTR. Hard gate: "
         "title > 70 characters triggers a retry with a truncation constraint. Both titles are "
         "stored in Supabase; Title B is the automatic swap candidate after 48h.", "#6366f1"),
        ("7", "Scene Breakdown", "07_scene_breakdown_agent.py", "Claude Sonnet 4.6",
         "Verified script, DNA block",
         "12\u201320 scenes with: narration text, B-roll search prompt, estimated duration, visual notes",
         "Divides the script into individually renderable scenes. Each scene includes a B-roll "
         "search prompt written for the Pexels API \u2014 concrete, visual, atmospheric. Scene count "
         "determines how many images and footage clips are generated in Stages 9\u201310. "
         "Soft gate: B-roll prompts present for \u2265 80% of scenes.", "#0891b2"),
        ("8", "Audio Production", "08_audio_producer.py", "ElevenLabs v3 API",
         "TTS-formatted script (meta-text stripped), voice ID George (JBFqnCBsd6RMkjVDRZzb)",
         "narration.mp3, word-level timestamp JSON (word, start_time, end_time per word)",
         "Splits the script at sentence boundaries into chunks of max 4,500 characters. Calls "
         "ElevenLabs with-timestamps endpoint for each chunk. Concatenates audio chunks and "
         "merges timestamp arrays with adjusted offsets. Writes narration.mp3 to /app/outputs/media/ "
         "and copies to /app/remotion/public/ for Remotion access. Soft gate: duration < 300s.", "#059669"),
        ("9", "Footage Hunting", "09_footage_hunter.py", "Pexels Video API",
         "B-roll prompts per scene from Stage 7 output",
         "Scene footage manifest: per-scene list of Pexels video URLs, resolution, duration",
         "Queries Pexels Videos API for each scene\u2019s B-roll prompt. Selects the highest-resolution "
         "result that matches the scene duration estimate. Scenes with no Pexels results fall back "
         "to the AI-generated scene image. Pexels results are stored in the state file but "
         "are secondary to AI images in the Remotion video-data.json prioritisation.", "#d97706"),
        ("10", "Image Generation", "run_pipeline.py (internal)", "fal.ai Flux Pro",
         "Scene descriptions and visual notes from Stage 7, oil-painting style modifier",
         "One 16:9 AI image per scene (JPEG), stored at /app/outputs/media/scene_N.jpg",
         "Calls fal.ai Flux Pro API sequentially for each scene. Prompt constructed from scene "
         "visual notes + oil-painting style modifier + period-accurate lighting description. "
         "Images are copied to /app/remotion/public/ so Chromium can access them during render. "
         "Scene 1 image is used as the YouTube thumbnail (resized to 1280\u00d7720 with dark overlay).", "#7c3aed"),
        ("11", "Remotion Conversion", "run_pipeline.py (internal)", "None \u2014 local file I/O",
         "Scene manifest, word-level timestamps, audio duration, AI image paths",
         "video-data.json written to /app/remotion/src/ for the Remotion renderer",
         "Converts the pipeline\u2019s output format into the schema expected by the Remotion React "
         "components. Calculates per-scene start/end times from word timestamps. Maps scene images "
         "to timestamps. Writes background music mood based on topic era. The video-data.json is "
         "the complete specification that Remotion uses to render the final video.", "#374151"),
        ("12", "Video Render", "run_pipeline.py (internal)", "Remotion + headless Chrome",
         "video-data.json, narration.mp3, scene images in /app/remotion/public/",
         "1920\u00d71080px 1080p H.264 MP4 with animated word captions and background music",
         "Invokes Remotion CLI in headless mode (npx remotion render) with Chrome in the Railway "
         "container. concurrency=1 to stay within Railway memory limits. Render takes ~35 minutes "
         "for a 10-minute documentary. Background music mixed by mood (dark/action/reverent/mysterious) "
         "using Kevin MacLeod tracks pre-loaded by setup_music.py. Soft gate: file < 50 MB.", "#374151"),
        ("13", "YouTube Upload", "11_youtube_uploader.py", "YouTube Data API v3",
         "Rendered MP4, SEO metadata (title A, description, tags, chapters), scene 1 image for thumbnail",
         "YouTube video ID, live public YouTube URL, upload timestamp",
         "Uses google-auth OAuth2 resumable upload. Token loaded from YOUTUBE_TOKEN_JSON env var. "
         "After upload: sets thumbnail (scene 1 image resized to 1280\u00d7720), updates snippet "
         "(title A, description with chapters, tags), posts source citations as a pinned comment. "
         "Records video_id, title_a, title_b, era in Supabase. Sends Telegram notification.", "#c8973a"),
    ]

    for args in stages:
        story.append(stage_block(*args))

    story += [
        sp(8),
        h2("2.2  Short-Form Sub-Pipeline"),
        body(
            "After Stage 2 (Originality) completes, run_pipeline.py forks a parallel short-form "
            "production thread. The short pipeline uses the same topic, research, and originality "
            "output to produce a YouTube Shorts-compatible vertical video. Failures in the short "
            "pipeline are caught by an isolated try/except block and do not propagate to the long "
            "pipeline. The short pipeline consists of 7 stages:"
        ),
        sp(6),
        data_table(
            ["STAGE", "MODULE", "OUTPUT"],
            [
                ["Short Script",      "short_script_agent.py",      "60\u201390 second narration optimised for vertical format and hook-first structure"],
                ["Short Storyboard",  "short_storyboard_agent.py",  "4\u20136 scenes with 9:16 visual prompts and pacing designed for Shorts retention"],
                ["Short Audio",       "08_audio_producer.py",       "Short narration.mp3 with word timestamps via ElevenLabs v3 (same George voice)"],
                ["Short Images",      "run_pipeline.py (internal)", "fal.ai Flux Pro images at 768\u00d71344 (9:16 portrait orientation), one per scene"],
                ["Short Convert",     "run_pipeline.py (internal)", "Short video-data.json configured for vertical Remotion composition"],
                ["Short Render",      "run_pipeline.py (internal)", "1080\u00d71920px vertical MP4 via Remotion headless render"],
                ["Short Upload",      "11_youtube_uploader.py",     "YouTube Shorts upload with #Shorts tag in description, thumbnail, SEO metadata"],
            ],
            col_widths=[90, 130, 240]
        ),
        sp(8),
        h2("2.3  Stage Dependency Graph"),
        body("Each stage reads from the state file keys written by its upstream dependencies:"),
        sp(4),
        code(
            "Stage 0 (Topic Discovery)\n"
            "  \u2514\u2192 Stage 1 (Research)            reads: stage_0.topic_data\n"
            "      \u2514\u2192 Stage 2 (Originality)       reads: stage_1.research\n"
            "          \u2514\u2192 Stage 3 (Narrative)       reads: stage_1.research + stage_2.angle\n"
            "              \u2514\u2192 Stage 4 (Script)        reads: stage_3.blueprint + stage_1.research\n"
            "                  \u2514\u2192 Stage 5 (Verify)    reads: stage_4.script + stage_1.primary_sources\n"
            "                      \u2514\u2192 Stage 6 (SEO)   reads: stage_5.verified_script + stage_2.angle\n"
            "                          \u2514\u2192 Stage 7 (Scenes) reads: stage_5.verified_script\n"
            "                              \u2514\u2192 Stage 8 (Audio)   reads: stage_7.scenes[].narration\n"
            "                              \u2514\u2192 Stage 9 (Footage)  reads: stage_7.scenes[].broll_prompt\n"
            "                              \u2514\u2192 Stage 10 (Images)  reads: stage_7.scenes[].visual_notes\n"
            "                                  \u2514\u2192 Stage 11 (Convert) reads: stages 7,8,9,10\n"
            "                                      \u2514\u2192 Stage 12 (Render)  reads: stage_11.video_data_path\n"
            "                                          \u2514\u2192 Stage 13 (Upload) reads: stages 6,12"
        ),
        PageBreak(),
    ]

    # \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
    # 03. CHANNEL INTELLIGENCE SYSTEM
    # \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
    story += [
        section_header("03", "Channel Intelligence System"),
        sp(8),
        body(
            "The intelligence system is the feedback mechanism that makes The Obsidian Archive "
            "self-improving. Rather than producing identical content indefinitely, the system "
            "observes how each published video performs on YouTube, distils those observations "
            "into structured guidance, and injects that guidance into every future agent\u2019s "
            "decision-making. The loop closes completely: every video makes the next video smarter."
        ),
        sp(6),
        h2("3.1  Analytics Agent (12_analytics_agent.py)"),
        body(
            "The analytics agent is not part of the production pipeline. It runs independently "
            "on a daily schedule at 06:00 UTC. Its sole purpose is to observe, compute, and publish "
            "channel performance data."
        ),
        sp(4),
        lbl("PROCESS"),
        bullet("Authenticates with YouTube Analytics API v2 using the same OAuth2 token as the uploader"),
        bullet("Fetches the following metrics for all published videos: views, impressions, impressionClickThroughRate, averageViewPercentage, estimatedMinutesWatched"),
        bullet("Enriches each video record with its historical era tag stored in Supabase at upload time"),
        bullet("Computes aggregate statistics per era: average CTR, average retention, total view count, video count per era"),
        bullet("Identifies top-performing eras ranked by combined CTR + retention score"),
        bullet("Analyses title patterns of high-CTR videos: format type, character count, emotional hook category"),
        bullet("Calls Claude Sonnet 4.6 with the full performance dataset for qualitative analysis and actionable recommendations"),
        bullet("Writes the complete output to /app/channel_insights.json on the Railway persistent volume"),
        sp(8),
        h2("3.2  channel_insights.py Interface"),
        body(
            "channel_insights.py is a pure read module \u2014 it never writes, never calls any API, "
            "and never blocks. It reads /app/channel_insights.json on import and exposes six "
            "specialised getter functions, each returning a formatted string block sized and "
            "structured for its specific agent context window budget. When channel_insights.json "
            "does not exist (new deployment, file deleted), all getters return empty string."
        ),
        sp(6),
        data_table(
            ["FUNCTION", "CONSUMER AGENT", "CONTENT RETURNED"],
            [
                ["get_global_intelligence_block()",    "All agents (via dna_loader)",  "Full overview: top eras, trend direction, channel health, Claude qualitative analysis summary"],
                ["get_topic_discovery_intelligence()", "Stage 0 (Topic Discovery)",    "Era performance rankings with CTR/retention scores; recommended era mix for upcoming production"],
                ["get_seo_intelligence()",             "Stage 6 (SEO Agent)",          "High-CTR title formats, optimal length range, top emotional hooks, underperforming title patterns"],
                ["get_narrative_intelligence()",       "Stage 3 (Narrative Architect)", "Best-retention 4-act structures, optimal scene count range, pacing patterns by era"],
                ["get_script_intelligence()",          "Stage 4 (Script Writer)",       "Optimal word count range, high-retention opening hook formats, best-performing script elements"],
                ["get_dna_confidence_block()",         "dna_loader (all agents)",       "Numeric confidence score 0.0\u20131.0 indicating how much to weight analytics vs. DNA defaults"],
            ],
            col_widths=[155, 110, 195]
        ),
        sp(8),
        h2("3.3  Data Flow into Agent Prompts"),
        body(
            "The intelligence data reaches agents through dna_loader.py. When any agent calls "
            "<font face='Courier'>dna_loader.get_dna()</font>, the function: (1) loads the static "
            "brand DNA from dna_config.json, (2) calls the appropriate channel_insights.py getter "
            "for that agent type, (3) appends the intelligence block to the DNA string, "
            "(4) returns the combined string for inclusion in the agent\u2019s system prompt. "
            "This happens at runtime for every inference call, ensuring agents always have the "
            "most recently refreshed intelligence data."
        ),
        sp(8),
        h2("3.4  DNA Confidence Scoring Model"),
        body(
            "The confidence score prevents the system from over-correcting based on a small "
            "or noisy dataset. The formula accounts for: total published video count (primary "
            "factor), era diversity (number of distinct eras with \u2265 2 videos), recency weighting "
            "(videos published in the last 30 days weighted 2\u00d7), and performance variance "
            "(high variance = lower confidence). A score of 0.0 means agents ignore analytics "
            "entirely and rely purely on DNA defaults. A score of 1.0 means analytics data "
            "fully drives all intelligent decisions. The score is included in every agent\u2019s "
            "system prompt so each agent can calibrate its own reliance on the injected guidance."
        ),
        PageBreak(),
    ]

    # \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
    # 04. SUPPORTING INFRASTRUCTURE
    # \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
    story += [
        section_header("04", "Supporting Infrastructure"),
        sp(8),
        h2("4.1  scheduler.py"),
        body(
            "The scheduler is the container\u2019s process entrypoint. It runs a 60-second polling "
            "loop using the Python schedule library. It does not use Railway\u2019s native cron "
            "because Railway cron would require separate service deployments \u2014 the scheduler "
            "daemon keeps everything in one container."
        ),
        sp(4),
        kv_table([
            ("Monday 08:00 UTC",    "Topic discovery run \u2014 discovers and queues 15 topics for the week"),
            ("Tuesday 09:00 UTC",   "Full video production \u2014 runs run_pipeline.py (Stages 0\u201313 + short pipeline)"),
            ("Daily 06:00 UTC",     "Analytics run \u2014 fetches YouTube data, updates channel_insights.json"),
            ("Daily 07:00 UTC",     "A/B title check \u2014 swaps Title B for any video with CTR < 4% at 48h mark"),
            ("Daily 07:30 UTC",     "ElevenLabs credit check \u2014 Telegram alert if balance below threshold"),
            ("Monday 10:00 UTC",    "Weekly Telegram report \u2014 summary of production, performance, costs"),
        ], [140, 320]),
        sp(8),
        h2("4.2  webhook_server.py"),
        body(
            "A Flask application that runs in a background thread spawned by scheduler.py. "
            "Provides two key functions: real-time pipeline monitoring via Server-Sent Events (SSE), "
            "and a manual trigger endpoint for operator-initiated runs."
        ),
        sp(4),
        data_table(
            ["ENDPOINT", "METHOD", "PURPOSE"],
            [
                ["/",          "GET",  "HTML dashboard page with embedded SSE client showing live pipeline stage progress"],
                ["/events",    "GET",  "SSE stream \u2014 emits pipeline status events as each stage completes or fails"],
                ["/trigger",   "POST", "Manually triggers a pipeline run with optional topic override in JSON body"],
                ["/status",    "GET",  "Returns current pipeline state as JSON \u2014 used as Railway health check endpoint"],
                ["/analytics", "GET",  "Triggers a manual analytics run outside the daily schedule"],
            ],
            col_widths=[80, 55, 325]
        ),
        sp(8),
        h2("4.3  pipeline_doctor.py"),
        body(
            "The Pipeline Doctor wraps every stage execution in a retry harness. When an agent "
            "raises an exception, the Doctor: (1) classifies the error type by inspecting the "
            "exception class, HTTP status code, and error message string, (2) selects the "
            "appropriate retry strategy, (3) optionally modifies the stage input (e.g., truncating "
            "context for context overflow errors), (4) retries up to the configured maximum, "
            "(5) escalates to Telegram alert and pipeline halt if retries exhausted."
        ),
        sp(4),
        data_table(
            ["ERROR CLASS", "CLASSIFICATION LOGIC", "ACTION"],
            [
                ["rate_limit",  "HTTP 429 or 'rate limit' or RateLimitError",            "Exponential backoff: 30s \u2192 60s \u2192 120s \u2192 240s \u2192 480s. Max 5 retries."],
                ["timeout",     "ConnectTimeout, ReadTimeout, asyncio.TimeoutError",      "Wait 15s, retry same input. Max 3 retries."],
                ["context",     "'context window' or 'token limit' in message",          "Truncate input by 20% and retry. Max 2 retries."],
                ["quota",       "HTTP 429 (billing tier) or 'insufficient_quota'",       "Halt immediately. Send Telegram alert. Require operator action."],
                ["json",        "JSONDecodeError or model returned non-JSON",             "Retry with stricter 'respond in JSON only' system prompt. Max 3 retries."],
                ["not_found",   "HTTP 404 or FileNotFoundError or 'resource not found'", "Use fallback (placeholder image or silence). Log and continue."],
            ],
            col_widths=[65, 180, 215]
        ),
        sp(8),
        h2("4.4  pipeline_optimizer.py"),
        body(
            "Runs automatically after every successful pipeline completion. Reads the complete "
            "state file and passes all stage outputs to Claude Sonnet 4.6 for quality analysis. "
            "The model assigns an A\u2013F grade to: research depth, script quality, fact verification "
            "rigour, SEO effectiveness, scene breakdown quality, audio quality, and overall "
            "production quality. The grade report and improvement notes are appended to "
            "<font face='Courier'>lessons_learned.json</font>. On the next pipeline run, "
            "Stages 0, 3, and 4 read lessons_learned.json to avoid repeating identified weaknesses."
        ),
        sp(8),
        h2("4.5  quality_gates.py"),
        body(
            "Contains discrete gate functions called by run_pipeline.py after each critical stage. "
            "Gates are classified as hard (pipeline halts on failure) or soft (warning logged, "
            "pipeline continues). Gate functions return a GateResult dataclass with: passed (bool), "
            "gate_name (str), message (str), and is_hard (bool)."
        ),
        sp(4),
        data_table(
            ["GATE FUNCTION", "CHECK", "TYPE"],
            [
                ["check_script_length(script)",     "Word count between 1,400 and 2,200",              "Hard"],
                ["check_fact_sources(verify_out)",  "Central twist has \u2265 3 verified sources",          "Hard"],
                ["check_scene_claims(verify_out)",  "All scene claims have \u2265 1 source",               "Soft"],
                ["check_seo_title(seo_out)",        "Title A and Title B each \u2264 70 characters",       "Hard"],
                ["check_seo_tags(seo_out)",         "\u2265 15 tags present in SEO output",                "Soft"],
                ["check_audio_duration(audio_out)", "Audio duration \u2265 300 seconds",                   "Soft"],
                ["check_broll_coverage(scenes)",    "B-roll prompt present for \u2265 80% of scenes",     "Soft"],
                ["check_render_size(render_path)",  "Rendered MP4 file size \u2265 50 MB",                "Soft"],
            ],
            col_widths=[180, 190, 90]
        ),
        PageBreak(),
    ]

    # \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
    # 05. DATA ARCHITECTURE
    # \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
    story += [
        section_header("05", "Data Architecture"),
        sp(8),
        h2("5.1  State File Lifecycle"),
        body(
            "The state file is created at Stage 0 and serves as the complete record of a pipeline "
            "run. It lives in the Railway persistent volume, surviving container restarts and "
            "redeployments. One state file per video. File naming: "
            "<font face='Courier'>YYYYMMDD_HHMMSS_&lt;slug&gt;_state.json</font>. "
            "The file is human-readable JSON; any operator can inspect it to diagnose failures "
            "or verify stage outputs without database access."
        ),
        sp(4),
        code(
            "State file lifecycle:\n"
            "\n"
            "  Created:   run_pipeline.py writes meta block at Stage 0\n"
            "  Stage N:   Agent reads stage_N-1 keys, writes stage_N key\n"
            "  Failure:   State file preserved as-is; pipeline halts at failed stage\n"
            "  Resume:    --from-stage N reads state file, skips stages 0 through N-1\n"
            "  Complete:  Stage 13 writes youtube_id and youtube_url; file is final record\n"
            "  Retention: Files retained indefinitely on persistent volume (operator manages cleanup)"
        ),
        sp(8),
        h2("5.2  channel_insights.json Schema"),
        code(
            '{\n'
            '  "generated_at":        "ISO-8601 timestamp of last analytics run",\n'
            '  "video_count":         N,\n'
            '  "era_performance": {\n'
            '    "Ancient":      { "avg_ctr": 0.xx, "avg_retention": 0.xx, "video_count": N },\n'
            '    "Medieval":     { "avg_ctr": 0.xx, "avg_retention": 0.xx, "video_count": N },\n'
            '    "Renaissance":  { "avg_ctr": 0.xx, "avg_retention": 0.xx, "video_count": N },\n'
            '    "Early Modern": { "avg_ctr": 0.xx, "avg_retention": 0.xx, "video_count": N },\n'
            '    "Modern":       { "avg_ctr": 0.xx, "avg_retention": 0.xx, "video_count": N },\n'
            '    "Contemporary": { "avg_ctr": 0.xx, "avg_retention": 0.xx, "video_count": N }\n'
            '  },\n'
            '  "top_performing_eras": ["Medieval", "Ancient", ...],\n'
            '  "title_patterns": {\n'
            '    "high_ctr_formats":    ["The [Person] Who...", "How [Event] Was Hidden..."],\n'
            '    "optimal_length_range":[45, 65],\n'
            '    "top_emotional_hooks": ["suppressed", "hidden", "truth behind"]\n'
            '  },\n'
            '  "narrative_insights": {\n'
            '    "optimal_word_count":         [1600, 2000],\n'
            '    "high_retention_structures":  ["twist at 75%", "hook within first 30 words"]\n'
            '  },\n'
            '  "dna_confidence_score": 0.xx,\n'
            '  "claude_analysis":      "string \u2014 qualitative analysis from Sonnet 4.6"\n'
            '}'
        ),
        sp(8),
        h2("5.3  Supabase Schema"),
        data_table(
            ["TABLE", "COLUMN", "TYPE", "PURPOSE"],
            [
                ["topics",    "id, topic, slug, era",          "text, text, text, text",    "Topic identity and era classification"],
                ["topics",    "score, status",                  "float, enum",               "Discovery score and queue status (queued/in_progress/published/skipped)"],
                ["topics",    "created_at, produced_at",        "timestamp, timestamp",      "Queue insertion and production completion times"],
                ["videos",    "id, topic_id, youtube_id",       "uuid, fk, text",            "Video record linked to topic"],
                ["videos",    "title_a, title_b, ab_swapped",   "text, text, bool",          "A/B title test data; swapped flag set after automatic title swap"],
                ["videos",    "era, published_at",              "text, timestamp",           "Era tag for analytics grouping; YouTube publish time"],
                ["analytics", "id, video_id, fetched_at",       "uuid, fk, timestamp",       "Raw analytics record linked to video"],
                ["analytics", "views, impressions, ctr",        "int, int, float",           "Core YouTube Analytics metrics"],
                ["analytics", "retention, watch_minutes",       "float, int",                "Average view percentage and total watch time"],
            ],
            col_widths=[65, 135, 110, 150]
        ),
        sp(8),
        h2("5.4  DNA Config Structure (dna_config.json)"),
        body(
            "The DNA config is the static brand identity document. It is not modified by any "
            "agent \u2014 it is operator-managed. dna_loader.py reads it at runtime and appends "
            "the dynamic channel_intelligence block before returning to agents."
        ),
        sp(4),
        code(
            '{\n'
            '  "channel": {\n'
            '    "name":        "The Obsidian Archive",\n'
            '    "tagline":     "Uncover sinister, suppressed history. Every story is real.",\n'
            '    "niche":       "Dark history, hidden events, suppressed narratives"\n'
            '  },\n'
            '  "voice": {\n'
            '    "tone":        "cinematic, authoritative, second-person",\n'
            '    "sentence_style": "short declarative sentences",\n'
            '    "forbidden":   ["it is worth noting", "in conclusion", "as we can see"]\n'
            '  },\n'
            '  "content": {\n'
            '    "format":      "10-minute documentary, verified twist reveal ending",\n'
            '    "forbidden_topics": ["living persons without consent", "unverifiable claims"]\n'
            '  },\n'
            '  "quality": {\n'
            '    "min_sources_per_scene": 1,\n'
            '    "min_sources_for_twist": 3,\n'
            '    "target_word_count":     [1400, 2200]\n'
            '  },\n'
            '  "channel_intelligence": "(dynamically injected by dna_loader.py at runtime)"\n'
            '}'
        ),
        PageBreak(),
    ]

    # \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
    # 06. API INTEGRATION SPECIFICATIONS
    # \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
    story += [
        section_header("06", "API Integration Specifications"),
        sp(8),
    ]

    api_specs = [
        ("6.1  Anthropic Claude API", [
            ("Base URL",          "https://api.anthropic.com/v1/"),
            ("Auth method",       "X-API-Key header from ANTHROPIC_API_KEY env var"),
            ("Client library",    "anthropic Python SDK; wrapped in claude_client.py for JSON extraction and retry"),
            ("Models",            "claude-opus-4-6 (heavy reasoning tasks), claude-sonnet-4-6 (all production agents + optimizer), claude-haiku-4-5 (SEO + fast classification)"),
            ("Context limits",    "Sonnet 4.6: 200K tokens. Full research + script fits comfortably. Truncation at 80% capacity."),
            ("Retry on 429",      "Exponential backoff via Pipeline Doctor: 30s, 60s, 120s, 240s, 480s. Max 5 attempts."),
            ("JSON extraction",   "claude_client.py parses JSON from model response; retries with stricter prompt on JSONDecodeError"),
            ("Web search tool",   "Stages 1, 2, 5 use Claude\u2019s built-in web_search tool for live source retrieval"),
        ]),
        ("6.2  ElevenLabs v3 TTS", [
            ("Base URL",          "https://api.elevenlabs.io/v1/"),
            ("Auth method",       "xi-api-key header from ELEVENLABS_API_KEY env var"),
            ("Endpoint",          "/text-to-speech/{voice_id}/with-timestamps"),
            ("Voice ID",          "JBFqnCBsd6RMkjVDRZzb (George \u2014 deep, authoritative male narrator)"),
            ("Request format",    "JSON: text (string), model_id (eleven_v3), voice_settings (stability, similarity_boost)"),
            ("Response format",   "JSON: audio_base64 (string), alignment (word, start_time, end_time arrays)"),
            ("Chunking",          "tts_format_agent.py splits at sentence boundaries; max 4,500 chars per chunk"),
            ("Audio assembly",    "Base64 chunks decoded to bytes, concatenated, written as narration.mp3"),
            ("Timestamp merge",   "Per-chunk word timestamps offset by cumulative duration before merging"),
            ("Quota monitoring",  "GET /user/subscription fetched daily by scheduler at 07:30 UTC; alert if credits < threshold"),
        ]),
        ("6.3  fal.ai Flux Pro", [
            ("Auth method",       "FAL_KEY env var via fal-client Python SDK"),
            ("Model endpoint",    "fal-ai/flux-pro"),
            ("Long-form prompt",  "Scene visual notes + 'oil painting, dramatic lighting, [era]-period accurate, cinematic composition'"),
            ("Image size",        "1344\xd7768 pixels (16:9) for long-form; 768\xd71344 pixels (9:16) for short-form"),
            ("Requests",          "Sequential (one per scene). Async batching planned for V2."),
            ("Fallback",          "If fal.ai call fails, scene uses a solid NAVY colour placeholder. Pipeline continues."),
            ("Output",            "PNG download URL; file fetched and saved to /app/outputs/media/scene_N.jpg"),
            ("Thumbnail",         "Scene 1 image resized to 1280\xd7720 via Pillow with a semi-transparent dark overlay"),
        ]),
        ("6.4  Pexels Video API", [
            ("Base URL",          "https://api.pexels.com/videos/"),
            ("Auth method",       "Authorization header from PEXELS_API_KEY env var"),
            ("Endpoint",          "GET /videos/search?query={broll_prompt}&per_page=5&orientation=landscape"),
            ("Selection logic",   "Selects highest-resolution result with duration closest to scene estimated duration"),
            ("Quota",             "Free tier: 200 requests/hour, 20,000/month. Per-run usage: 12\u201320 requests."),
            ("Fallback",          "Scene defaults to AI-generated image if Pexels returns 0 results"),
            ("Output",            "Video download URL stored in state file; used as secondary source in video-data.json"),
        ]),
        ("6.5  YouTube Data API v3", [
            ("Auth method",       "OAuth2 via google-auth. Token JSON stored in YOUTUBE_TOKEN_JSON env var, restored to /app/token.json at startup"),
            ("Upload endpoint",   "POST /upload/youtube/v3/videos?uploadType=resumable"),
            ("Upload quota",      "1,600 units per upload. Daily quota: 10,000 units. Effective capacity: ~6 uploads/day."),
            ("Thumbnail",         "POST /youtube/v3/thumbnails/set \u2014 50 quota units. Requires PNG/JPEG \u2264 2 MB."),
            ("Snippet update",    "PUT /youtube/v3/videos with snippet part \u2014 costs 50 units. Used for title, description, tags."),
            ("Comment post",      "POST /youtube/v3/commentThreads \u2014 50 units. Posts source citations as pinned comment."),
            ("A/B swap",          "Scheduler calls PUT /youtube/v3/videos with Title B in snippet part after 48h if CTR < 4%"),
            ("Token refresh",     "google-auth auto-refreshes access token using stored refresh token. No operator action needed."),
        ]),
        ("6.6  YouTube Analytics API v2", [
            ("Base URL",          "https://youtubeanalytics.googleapis.com/v2/"),
            ("Auth method",       "Same OAuth2 token as Data API v3"),
            ("Endpoint",          "GET /reports?ids=channel==MINE&dimensions=video&metrics=views,impressions,..."),
            ("Metrics fetched",   "views, impressions, impressionClickThroughRate, averageViewPercentage, estimatedMinutesWatched"),
            ("Frequency",         "Daily at 06:00 UTC. Data has ~48h lag in YouTube\u2019s system for fresh videos."),
            ("Quota",             "No hard quota separate from Data API pool. Analytics queries use minimal units."),
        ]),
        ("6.7  Supabase (PostgreSQL)", [
            ("Auth method",       "SUPABASE_URL + SUPABASE_KEY (service role key) env vars via supabase-py client"),
            ("Connection",        "supabase-py manages connection pooling; no manual connection management needed"),
            ("Read pattern",      "SELECT at Stage 0 (topic queue), Stage 2 (published_topics for deduplication)"),
            ("Write pattern",     "INSERT/UPDATE at Stage 0 (topic status), Stage 13 (video record), daily analytics"),
            ("Failure handling",  "If Supabase unavailable: Stage 0 skips queue, Stage 2 skips deduplication check, continues"),
        ]),
        ("6.8  Telegram Bot API", [
            ("Auth method",       "TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID env vars"),
            ("Endpoint",          "POST https://api.telegram.org/bot{TOKEN}/sendMessage"),
            ("Message types",     "Upload complete (video URL + stats), pipeline failure (stage + error), weekly report, credit alert, A/B swap notice"),
            ("Failure handling",  "Telegram send failures are fully non-blocking. Wrapped in try/except; exception logged and swallowed."),
            ("Format",            "Plain text with Markdown formatting. Emoji used for visual priority signalling."),
        ]),
    ]

    for title, rows in api_specs:
        story.append(KeepTogether([h2(title), kv_table(rows, [120, 340]), sp(8)]))

    story.append(PageBreak())

    # \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
    # 07. DEPLOYMENT & INFRASTRUCTURE
    # \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
    story += [
        section_header("07", "Deployment & Infrastructure"),
        sp(8),
        h2("7.1  Railway Setup"),
        body(
            "The Obsidian Archive is deployed as a single Railway service. The service is linked "
            "to the GitHub repository and auto-deploys on every push to the main branch. "
            "A persistent volume is mounted at /app/outputs to retain state files, rendered "
            "videos, and intelligence data across deployments."
        ),
        sp(4),
        kv_table([
            ("Service type",       "Railway Worker (always-on container, no HTTP port requirement from Railway\u2019s perspective)"),
            ("Health check",       "Flask webhook server on port 8080; /status endpoint returns 200 if scheduler is running"),
            ("Restart policy",     "Railway restarts the container on crash automatically"),
            ("Persistent volume",  "/app/outputs \u2014 5 GB minimum recommended (each rendered video ~500 MB)"),
            ("Build time",         "~10 minutes (Chromium apt-get installation dominates build time)"),
            ("Deploy trigger",     "GitHub push to main branch. Railway detects Dockerfile change or code change."),
            ("Memory",             "4 GB recommended minimum. Remotion headless Chrome requires ~2 GB during render phase."),
            ("CPU",                "2 vCPU minimum. Render phase is CPU-bound. AI stages are I/O-bound."),
        ], [130, 330]),
        sp(8),
        h2("7.2  Dockerfile Overview"),
        code(
            "FROM python:3.11-slim\n"
            "\n"
            "# System dependencies\n"
            "RUN apt-get update && apt-get install -y \\\n"
            "    chromium chromium-driver \\\n"
            "    nodejs npm \\\n"
            "    ffmpeg \\\n"
            "    && rm -rf /var/lib/apt/lists/*\n"
            "\n"
            "# Python dependencies\n"
            "COPY requirements.txt .\n"
            "RUN pip install -r requirements.txt\n"
            "\n"
            "# Node/Remotion dependencies\n"
            "COPY remotion/ /app/remotion/\n"
            "WORKDIR /app/remotion\n"
            "RUN npm install\n"
            "\n"
            "# Application code\n"
            "WORKDIR /app\n"
            "COPY . /app/\n"
            "\n"
            "# Persistent volume mount point\n"
            "RUN mkdir -p /app/outputs\n"
            "\n"
            "CMD [\"python\", \"scheduler.py\"]"
        ),
        sp(8),
        h2("7.3  Environment Variables"),
        data_table(
            ["VARIABLE", "PURPOSE", "REQUIRED"],
            [
                ["ANTHROPIC_API_KEY",    "Anthropic Claude API authentication",              "Yes"],
                ["ELEVENLABS_API_KEY",   "ElevenLabs TTS API authentication",                "Yes"],
                ["FAL_KEY",              "fal.ai Flux Pro image generation authentication",   "Yes"],
                ["PEXELS_API_KEY",       "Pexels stock footage API authentication",           "Yes"],
                ["SUPABASE_URL",         "Supabase project URL",                             "Yes"],
                ["SUPABASE_KEY",         "Supabase service role key",                        "Yes"],
                ["YOUTUBE_TOKEN_JSON",   "Full YouTube OAuth2 token JSON (stringified)",      "Yes"],
                ["TELEGRAM_BOT_TOKEN",   "Telegram Bot API token",                           "Yes"],
                ["TELEGRAM_CHAT_ID",     "Telegram chat/channel ID for notifications",        "Yes"],
                ["ELEVENLABS_THRESHOLD", "Credit balance threshold for low-credit alert",    "No (default: 10,000)"],
            ],
            col_widths=[145, 230, 85]
        ),
        sp(8),
        h2("7.4  YouTube OAuth Flow"),
        body(
            "YouTube OAuth2 credentials cannot be automatically refreshed without a stored "
            "refresh token. The initial OAuth flow must be completed manually by the operator "
            "using the Google OAuth2 playground or a local script. Once completed, the resulting "
            "token JSON (containing access_token, refresh_token, token_uri, client_id, "
            "client_secret, scopes) is stringified and stored as the YOUTUBE_TOKEN_JSON "
            "Railway environment variable. At container startup, the scheduler restores this "
            "JSON to /app/token.json. The google-auth library automatically refreshes the "
            "access token when it expires, using the stored refresh token. The updated token "
            "is written back to /app/token.json but not back to the environment variable "
            "(environment variables are immutable at runtime on Railway)."
        ),
        PageBreak(),
    ]

    # \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
    # 08. OPERATIONS RUNBOOK
    # \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
    story += [
        section_header("08", "Operations Runbook"),
        sp(8),
    ]

    runbook = [
        ("8.1  Trigger a video manually",
         "Send a POST request to the webhook server:\n"
         "  curl -X POST https://<railway-url>:8080/trigger\n"
         "  -H 'Content-Type: application/json'\n"
         "  -d '{\"topic\": \"optional topic override\"}'",
         "If no topic is provided in the body, the pipeline pulls the top-scored topic from the Supabase queue."),
        ("8.2  Resume a failed pipeline",
         "SSH into the Railway container (via Railway CLI or shell) and run:\n"
         "  python run_pipeline.py --resume outputs/<state_file>.json\n"
         "Or force from a specific stage:\n"
         "  python run_pipeline.py --from-stage 8 --state outputs/<state_file>.json",
         "The pipeline will skip all stages before the specified stage and resume from there, using all prior outputs from the state file."),
        ("8.3  Check pipeline status",
         "Visit the webhook server dashboard:\n"
         "  https://<railway-url>:8080/\n"
         "Or query the status endpoint:\n"
         "  curl https://<railway-url>:8080/status",
         "The /status endpoint returns JSON with current stage, last completed stage, and any error messages."),
        ("8.4  Rotate an API key",
         "1. Generate new key in the relevant service dashboard.\n"
         "2. In Railway dashboard: Settings \u2192 Variables \u2192 update the relevant env var.\n"
         "3. Trigger a Railway redeploy (or wait for next auto-deploy).\n"
         "4. Verify the first scheduled run completes successfully.",
         "Never commit API keys to GitHub. All keys must live in Railway environment variables."),
        ("8.5  Update the DNA config",
         "1. Edit /app/dna_config.json directly on the Railway volume, or\n"
         "2. Edit locally and push to GitHub (triggers redeploy).\n"
         "3. Changes take effect on the next pipeline run (dna_loader reads file at runtime).",
         "The channel_intelligence section is dynamically injected by dna_loader.py and should NOT be edited in dna_config.json directly."),
        ("8.6  Run analytics manually",
         "Via webhook:\n"
         "  curl https://<railway-url>:8080/analytics\n"
         "Or directly in the container:\n"
         "  python 12_analytics_agent.py",
         "The analytics agent writes to /app/channel_insights.json. All subsequent agent runs will use the updated data."),
        ("8.7  Refresh YouTube OAuth token",
         "If the refresh token expires (rare; typically valid for 6 months):\n"
         "1. Run the local OAuth flow script to generate a new token JSON.\n"
         "2. Stringify the JSON: python -c \"import json; print(json.dumps(token_dict))\"\n"
         "3. Update YOUTUBE_TOKEN_JSON Railway env var with the stringified JSON.\n"
         "4. Trigger redeploy.",
         "The access token refreshes automatically. Only the refresh token requires manual renewal."),
        ("8.8  View pipeline logs",
         "In Railway dashboard: select service \u2192 Deployments \u2192 View Logs.\n"
         "Logs are streamed in real time during production runs.\n"
         "All stage start/end events are logged with timestamps.",
         "Logs are retained by Railway for the configured retention period (typically 7 days on the free tier)."),
    ]

    for title, procedure, notes in runbook:
        story.append(KeepTogether([
            h3(title),
            code(procedure),
            Paragraph(f"<i>{notes}</i>", S("rn", fontName="Helvetica", fontSize=8,
                                            leading=12, textColor=GREY_MID, spaceAfter=10)),
        ]))

    story.append(PageBreak())

    # \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
    # 09. COST & PERFORMANCE MODEL
    # \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
    story += [
        section_header("09", "Cost & Performance Model"),
        sp(8),
        h2("9.1  Per-Video Cost Breakdown"),
        data_table(
            ["SERVICE", "WHAT IS CONSUMED", "UNIT PRICE", "PER VIDEO COST", "NOTES"],
            [
                ["Claude Sonnet 4.6 \xd75", "~250K input + ~50K output tokens across 5 agents", "$3/MTok in, $15/MTok out", "~$0.60", "Haiku 4.5 for SEO adds < $0.02"],
                ["ElevenLabs v3",          "~14,000 characters narration (George voice)",      "$0.025 per 1K chars",       "~$0.35", "Chunked; with-timestamps endpoint"],
                ["fal.ai Flux Pro",        "15 AI images at 1344\xd7768 per video",            "~$0.05 per image",          "~$0.75", "Sequential calls; V2 will parallelise"],
                ["Pexels API",             "12\u201320 stock footage searches",                       "Free tier",                 "$0.00",  "No cost at current production rate"],
                ["Supabase",               "Low-volume reads/writes",                         "Free tier",                 "$0.00",  "Upgrade at > 500 MB database size"],
                ["Railway hosting",        "Always-on container (~730 hrs/month)",            "~$10\u201320/month flat",        "\u2014",      "Shared across all runs; not per-video"],
                ["TOTAL (API only)",       "",                                                "",                          "~$1.70\u2013$2.50", "Excluding Railway fixed cost"],
            ],
            col_widths=[115, 120, 90, 70, 65]
        ),
        sp(8),
        h2("9.2  Pipeline Timing by Stage"),
        body("Approximate stage durations for a standard 1,800-word documentary video:"),
        sp(6),
        data_table(
            ["STAGE", "TYPICAL DURATION", "BOTTLENECK", "OPTIMISATION OPPORTUNITY"],
            [
                ["Stage 0  (Topic)",       "1\u20132 min",    "Claude API latency",   "Pre-scored topics eliminate this from Tuesday\u2019s critical path"],
                ["Stage 1  (Research)",    "3\u20135 min",    "Web search calls",     "Parallel search queries (V2)"],
                ["Stage 2  (Originality)", "2\u20134 min",    "YouTube search calls", "Cache competitor analysis per topic"],
                ["Stage 3  (Narrative)",   "1\u20132 min",    "Claude inference",     "None \u2014 already fast"],
                ["Stage 4  (Script)",      "2\u20134 min",    "Claude inference",     "None \u2014 already fast"],
                ["Stage 5  (Verify)",      "4\u20136 min",    "Web search per claim", "Batch verification queries (V2)"],
                ["Stage 6  (SEO)",         "1 min",      "Haiku inference",      "Already using fastest model"],
                ["Stage 7  (Scenes)",      "1\u20132 min",    "Claude inference",     "None"],
                ["Stage 8  (Audio)",       "5\u201310 min",   "ElevenLabs API",       "Parallel chunk requests (V2)"],
                ["Stage 9  (Footage)",     "2\u20133 min",    "Pexels API calls",     "Parallel scene queries (V2)"],
                ["Stage 10 (Images)",      "10\u201315 min",  "fal.ai API",           "Parallel image generation (V2) \u2014 biggest gain"],
                ["Stage 11 (Convert)",     "< 1 min",    "File I/O",             "None"],
                ["Stage 12 (Render)",      "30\u201340 min",  "Chromium CPU render",  "Cloud render farm (V3); concurrency > 1 (needs more RAM)"],
                ["Stage 13 (Upload)",      "3\u20135 min",    "YouTube upload speed", "Resumable upload already optimal"],
                ["TOTAL",                  "~65\u201390 min", "Render dominates",     "V2 parallelisation reduces non-render time to < 20 min"],
            ],
            col_widths=[95, 70, 110, 185]
        ),
        PageBreak(),
    ]

    # \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
    # 10. TROUBLESHOOTING GUIDE
    # \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
    story += [
        section_header("10", "Troubleshooting Guide"),
        sp(8),
        body(
            "The following table covers the most common failure scenarios encountered in "
            "production operation. For each symptom, the likely root cause is identified "
            "alongside the recommended resolution steps."
        ),
        sp(8),
        data_table(
            ["SYMPTOM", "LIKELY CAUSE", "RESOLUTION"],
            [
                ["Pipeline halts at Stage 4 with 'script too short' error",
                 "Script writer returned < 1,400 words. Often caused by thin research output from Stage 1.",
                 "Check Stage 1 output in state file. If research is thin, resume from Stage 1 with a more specific topic framing. Alternatively, add word count constraint to Stage 4 prompt retry."],
                ["Stage 5 (Verify) halts with 'twist unverifiable'",
                 "The central twist from Stage 2 cannot be verified against 3 independent sources.",
                 "Resume from Stage 2 and select a different angle with a more verifiable twist. Review Stage 1 research to confirm the twist is supported by primary sources before proceeding."],
                ["ElevenLabs returns 401 Unauthorized",
                 "ELEVENLABS_API_KEY env var is missing, incorrect, or expired.",
                 "Verify ELEVENLABS_API_KEY in Railway environment variables. Regenerate key in ElevenLabs dashboard if needed. Redeploy to apply updated env var."],
                ["YouTube upload fails with 'invalid_grant'",
                 "YouTube OAuth refresh token has expired (typically after 6 months of inactivity).",
                 "Complete the OAuth flow again locally. Stringify the new token JSON and update YOUTUBE_TOKEN_JSON Railway env var. Redeploy."],
                ["Remotion render fails with 'out of memory'",
                 "Railway container running out of memory during Chromium render. Common if memory limit < 4 GB.",
                 "Scale up Railway service memory to 4 GB or above. Remotion render at concurrency=1 requires ~2 GB for Chrome alone."],
                ["Rendered video has no audio",
                 "narration.mp3 not copied to /app/remotion/public/ before render, or ElevenLabs produced empty audio.",
                 "Check Stage 8 output in state file for audio_path and duration_seconds. If duration is 0, ElevenLabs may have returned an empty response \u2014 check TTS format agent output for stripped-to-empty script."],
                ["Video renders with black image frames",
                 "Scene images not found in /app/remotion/public/ when Chrome executes the Remotion render.",
                 "Verify Stage 10 output in state file lists all image_paths. Check that the image copy step completed successfully. Manually copy images to /app/remotion/public/ and rerun from Stage 12."],
                ["SEO agent title exceeds 70 characters after retry",
                 "Hard constraint retry is producing titles that still exceed limit. Usually indicates a model instruction compliance issue.",
                 "Check Stage 6 output in state file. Manually truncate title_a and title_b in the state file JSON, then resume from Stage 7."],
                ["Topic discovery selects the same era every week",
                 "channel_insights.json showing very high confidence for one era, causing topic discovery to over-weight it.",
                 "Delete or reset channel_insights.json to force DNA-default behaviour. Consider manually adjusting the era score multipliers in the topic discovery system prompt temporarily."],
                ["Telegram notifications stopped arriving",
                 "TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID env var is incorrect, or bot was blocked.",
                 "Test the bot token: curl https://api.telegram.org/bot{TOKEN}/getMe. If bot is blocked, start a new conversation with the bot. Telegram failures are non-blocking and will not affect pipeline operation."],
                ["Analytics agent fails with 'insufficient permissions'",
                 "YouTube Analytics API requires the same OAuth token as Data API but with analytics scope granted.",
                 "Re-run OAuth flow ensuring https://www.googleapis.com/auth/yt-analytics.readonly scope is included. Update YOUTUBE_TOKEN_JSON env var with new token."],
                ["Pexels footage missing from final video (all AI images)",
                 "All Pexels searches returned no results for the scene B-roll prompts.",
                 "This is expected behaviour \u2014 AI images are the primary visual source. Review Stage 7 B-roll prompts to ensure they use concrete, searchable visual descriptions rather than abstract concepts."],
                ["Pipeline runs twice on Tuesday",
                 "scheduler.py restarted mid-run (container restart), triggering a second scheduled job.",
                 "Check Railway logs for container restart events. Pipeline Doctor prevents duplicate state file corruption. Check Supabase topic status; if the first run wrote published, the second run will select a new topic."],
                ["fal.ai images appear blurry or incorrect style",
                 "Style modifier not applied correctly, or Flux Pro model updated with changed behaviour.",
                 "Review Stage 10 image generation prompt in logs. Verify the oil-painting style modifier is present in the fal.ai API call. Consider strengthening the style modifier weight if the model has been updated."],
                ["channel_insights.json not being updated",
                 "Analytics agent failing silently, or Supabase missing analytics records to compute from.",
                 "Run the analytics agent manually: python 12_analytics_agent.py. Check Railway logs for error output. Verify at least one video is published and that the YouTube Analytics API is returning data (48h lag for new videos)."],
            ],
            col_widths=[130, 130, 200]
        ),
    ]

    doc.build(story, onFirstPage=cover_page, onLaterPages=later_pages)
    print(f"Generated: {OUT}")

if __name__ == "__main__":
    build()
