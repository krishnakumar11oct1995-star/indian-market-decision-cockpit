import os
import pandas as pd
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

def generate_pdf_dossier(df: pd.DataFrame, output_path: str = "Market_Dossier.pdf") -> str:
    """
    Generates a publication-grade institutional PDF report for Indian market screening results.
    """
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#1E293B'),
        spaceAfter=6
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#64748B'),
        spaceAfter=14
    )
    
    section_style = ParagraphStyle(
        'SectionHeader',
        parent=styles['Heading2'],
        fontSize=13,
        leading=17,
        textColor=colors.HexColor('#0F172A'),
        spaceBefore=12,
        spaceAfter=6
    )
    
    cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#1E293B')
    )
    
    cell_header = ParagraphStyle(
        'TableHead',
        parent=styles['Normal'],
        fontSize=8,
        leading=10,
        fontName="Helvetica-Bold",
        textColor=colors.white
    )
    
    thesis_style = ParagraphStyle(
        'ThesisText',
        parent=styles['Normal'],
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor('#0F766E')
    )
    
    risk_style = ParagraphStyle(
        'RiskText',
        parent=styles['Normal'],
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor('#B91C1C')
    )
    
    elements = []
    
    # Title & Metadata
    elements.append(Paragraph("INDIAN EQUITIES DECISION SUPPORT & SCREENING COCKPIT", title_style))
    date_str = datetime.now().strftime("%d-%b-%Y %I:%M %p IST")
    elements.append(Paragraph(f"Institutional Research & Quantitative Risk Dossier | Generated: {date_str}", subtitle_style))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#0F766E'), spaceAfter=12))
    
    # Executive Summary Table
    elements.append(Paragraph("1. Executive Screening Summary", section_style))
    
    headers = ["Ticker", "CMP (₹)", "Signal", "Conviction", "Stop Loss (₹)", "Target Base (₹)", "R:R"]
    table_data = [[Paragraph(h, cell_header) for h in headers]]
    
    top_stocks = df.head(10)
    for _, row in top_stocks.iterrows():
        sig = str(row['Signal'])
        table_data.append([
            Paragraph(f"<b>{row['Ticker']}</b>", cell_style),
            Paragraph(f"₹{row['CMP']:,.1f}", cell_style),
            Paragraph(sig, cell_style),
            Paragraph(f"{row['Conviction_Score']}/100", cell_style),
            Paragraph(f"₹{row['Stop_Loss']:,.1f}", cell_style),
            Paragraph(f"₹{row['Target_Base']:,.1f}", cell_style),
            Paragraph(f"{row['Risk_Reward']:.2f}x", cell_style)
        ])
        
    t = Table(table_data, colWidths=[90, 65, 75, 65, 75, 85, 55])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0F172A')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#F8FAFC'), colors.white]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 14))
    
    # Section 2: Detailed Tactical Audits
    elements.append(Paragraph("2. Tactical Intelligence & Risk Audits (Top Candidates)", section_style))
    
    for idx, (_, row) in enumerate(top_stocks.head(5).iterrows()):
        card_data = [
            [
                Paragraph(f"<b>#{idx+1} {row['Ticker']} ({row['Sector']})</b>", cell_header),
                Paragraph(f"Signal: <b>{row['Signal']}</b> | Conviction: <b>{row['Conviction_Score']}/100</b>", cell_header)
            ],
            [
                Paragraph(f"<b>Technical Trend:</b> {row['Supertrend']} | <b>RSI:</b> {row['RSI_14']} | <b>EMA:</b> {row['EMA_Alignment']}", cell_style),
                Paragraph(f"<b>Options PCR:</b> {row['Option_PCR']} | <b>Max Pain:</b> ₹{row['Max_Pain']} | <b>OI:</b> {row['OI_Dynamics']}", cell_style)
            ],
            [
                Paragraph(f"<b>Trade Setup:</b> Entry CMP: ₹{row['CMP']:.1f} | Stop Loss: ₹{row['Stop_Loss']:.1f} | Target: ₹{row['Target_Base']:.1f} | Sizing: {row['Position_Size']} shares", cell_style),
                Paragraph(f"<b>Risk:Reward:</b> {row['Risk_Reward']:.2f} : 1", cell_style)
            ],
            [
                Paragraph(f"<b>Execution Thesis:</b> {row['Thesis']}", thesis_style),
                Paragraph(f"<b>Adversarial Risk:</b> {row['Adversarial_Risk']}", risk_style)
            ]
        ]
        
        card = Table(card_data, colWidths=[270, 240])
        card.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E293B')),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F8FAFC')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(card)
        elements.append(Spacer(1, 10))
        
    # Disclaimer
    elements.append(Spacer(1, 10))
    disclaimer_text = (
        "<b>DISCLAIMER:</b> This report is generated by an automated quantitative decision support tool for educational "
        "and analytical research purposes only. It does not constitute investment advice or a financial recommendation "
        "under SEBI regulations. Trading in equities and derivatives involves substantial risk of loss."
    )
    elements.append(Paragraph(disclaimer_text, subtitle_style))
    
    doc.build(elements)
    return output_path
