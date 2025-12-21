"""
PDF Report Generation Service.

Generates PDF reports for analytics data using reportlab.
"""
import io
from datetime import datetime
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie


def create_analytics_pdf(
    summary: dict,
    cases_by_status: list,
    cases_by_assignee: list,
    trend_data: list,
    meta_performance: Optional[dict] = None,
    org_name: str = "Organization",
    date_range: Optional[str] = None,
) -> bytes:
    """
    Generate a PDF analytics report.
    
    Args:
        summary: Analytics summary dict with total_cases, new_this_period, etc.
        cases_by_status: List of {status, count} dicts
        cases_by_assignee: List of {display_name, count} dicts
        trend_data: List of {date, count} dicts for trend chart
        meta_performance: Optional Meta leads performance dict
        org_name: Organization name for header
        date_range: Human-readable date range string
    
    Returns:
        PDF bytes
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=72
    )
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=20,
        textColor=colors.HexColor('#1e293b')
    )
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        spaceAfter=12,
        spaceBefore=20,
        textColor=colors.HexColor('#334155')
    )
    normal_style = styles['Normal']
    
    elements = []
    
    # Title
    elements.append(Paragraph(f"{org_name} Analytics Report", title_style))
    
    # Date info
    generated_at = datetime.utcnow().strftime("%B %d, %Y at %H:%M UTC")
    if date_range:
        elements.append(Paragraph(f"Period: {date_range}", normal_style))
    elements.append(Paragraph(f"Generated: {generated_at}", normal_style))
    elements.append(Spacer(1, 20))
    
    # Summary Stats Table
    elements.append(Paragraph("Summary", heading_style))
    
    summary_data = [
        ["Metric", "Value"],
        ["Total Cases", str(summary.get("total_cases", 0))],
        ["New This Period", str(summary.get("new_this_period", 0))],
        ["Qualified Rate", f"{summary.get('qualified_rate', 0):.1f}%"],
        ["Pending Tasks", str(summary.get("pending_tasks", 0))],
        ["Overdue Tasks", str(summary.get("overdue_tasks", 0))],
    ]
    
    summary_table = Table(summary_data, colWidths=[3*inch, 2*inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8fafc')),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
        ('FONTSIZE', (0, 1), (-1, -1), 11),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 20))
    
    # Cases by Status
    if cases_by_status:
        elements.append(Paragraph("Cases by Status", heading_style))
        
        status_data = [["Status", "Count"]]
        for item in cases_by_status:
            status_data.append([item.get("status", "Unknown"), str(item.get("count", 0))])
        
        status_table = Table(status_data, colWidths=[3*inch, 2*inch])
        status_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#22c55e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
            ('FONTSIZE', (0, 1), (-1, -1), 11),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0fdf4')]),
        ]))
        elements.append(status_table)
        elements.append(Spacer(1, 20))
    
    # Cases by Assignee (top 10)
    if cases_by_assignee:
        elements.append(Paragraph("Cases by Assignee", heading_style))
        
        assignee_data = [["Assignee", "Count"]]
        for item in cases_by_assignee[:10]:  # Top 10
            name = item.get("display_name") or item.get("owner_name") or "Unassigned"
            assignee_data.append([name, str(item.get("count", 0))])
        
        assignee_table = Table(assignee_data, colWidths=[3*inch, 2*inch])
        assignee_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#a855f7')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
            ('FONTSIZE', (0, 1), (-1, -1), 11),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#faf5ff')]),
        ]))
        elements.append(assignee_table)
        elements.append(Spacer(1, 20))
    
    # Meta Performance (if available)
    if meta_performance and meta_performance.get("leads_received", 0) > 0:
        elements.append(Paragraph("Meta Lead Ads Performance", heading_style))
        
        meta_data = [
            ["Metric", "Value"],
            ["Leads Received", str(meta_performance.get("leads_received", 0))],
            ["Leads Qualified", str(meta_performance.get("leads_qualified", 0))],
            ["Leads Converted", str(meta_performance.get("leads_converted", 0))],
            ["Qualification Rate", f"{meta_performance.get('qualification_rate', 0):.1f}%"],
            ["Conversion Rate", f"{meta_performance.get('conversion_rate', 0):.1f}%"],
        ]
        
        avg_hours = meta_performance.get("avg_time_to_convert_hours")
        if avg_hours:
            days = avg_hours / 24
            meta_data.append(["Avg Time to Convert", f"{days:.1f} days"])
        
        meta_table = Table(meta_data, colWidths=[3*inch, 2*inch])
        meta_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1877f2')),  # Facebook blue
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
            ('FONTSIZE', (0, 1), (-1, -1), 11),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#eff6ff')]),
        ]))
        elements.append(meta_table)
        elements.append(Spacer(1, 20))
    
    # Trend Data Table (last 7 points)
    if trend_data:
        elements.append(Paragraph("Recent Trend", heading_style))
        
        trend_display = trend_data[-7:] if len(trend_data) > 7 else trend_data
        trend_table_data = [["Date", "Cases"]]
        for item in trend_display:
            trend_table_data.append([item.get("date", ""), str(item.get("count", 0))])
        
        trend_table = Table(trend_table_data, colWidths=[3*inch, 2*inch])
        trend_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#06b6d4')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
            ('FONTSIZE', (0, 1), (-1, -1), 11),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#ecfeff')]),
        ]))
        elements.append(trend_table)
    
    # Footer
    elements.append(Spacer(1, 30))
    footer_style = ParagraphStyle(
        'Footer',
        parent=normal_style,
        fontSize=9,
        textColor=colors.gray
    )
    elements.append(Paragraph("This report was automatically generated by the CRM system.", footer_style))
    
    doc.build(elements)
    return buffer.getvalue()
