"""
PDF Report Generation Service.

Generates PDF reports for analytics data using reportlab with native charts.
"""

import io
from datetime import datetime
from typing import Optional, List

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.graphics.shapes import Drawing, String
from reportlab.graphics.charts.barcharts import HorizontalBarChart
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.charts.piecharts import Pie


# Color palette matching the frontend
CHART_COLORS = [
    colors.HexColor("#3b82f6"),  # Blue
    colors.HexColor("#22c55e"),  # Green
    colors.HexColor("#f59e0b"),  # Amber
    colors.HexColor("#a855f7"),  # Purple
    colors.HexColor("#06b6d4"),  # Cyan
    colors.HexColor("#ef4444"),  # Red
    colors.HexColor("#ec4899"),  # Pink
    colors.HexColor("#8b5cf6"),  # Violet
]


def _create_bar_chart(
    data: List[dict], label_key: str, value_key: str, title: str, color: colors.Color
) -> Drawing:
    """Create a horizontal bar chart."""
    if not data:
        return None

    drawing = Drawing(450, 150)

    # Extract data
    labels = [
        item.get(label_key, "Unknown")[:20] for item in data[:8]
    ]  # Limit to 8, truncate labels
    values = [item.get(value_key, 0) for item in data[:8]]

    if not values or max(values) == 0:
        return None

    chart = HorizontalBarChart()
    chart.x = 100
    chart.y = 20
    chart.height = 110
    chart.width = 320
    chart.data = [values]
    chart.categoryAxis.categoryNames = labels
    chart.categoryAxis.labels.fontSize = 9
    chart.categoryAxis.labels.dx = -5
    chart.valueAxis.valueMin = 0
    chart.valueAxis.valueMax = max(values) * 1.1
    chart.valueAxis.labels.fontSize = 9
    chart.bars[0].fillColor = color
    chart.barWidth = 12
    chart.groupSpacing = 8

    drawing.add(chart)

    # Add title
    drawing.add(
        String(
            225, 140, title, fontSize=11, fontName="Helvetica-Bold", textAnchor="middle"
        )
    )

    return drawing


def _create_line_chart(data: List[dict], title: str) -> Drawing:
    """Create a line chart for trend data."""
    if not data or len(data) < 2:
        return None

    drawing = Drawing(450, 160)

    # Extract data (last 14 points max)
    display_data = data[-14:] if len(data) > 14 else data
    dates = [item.get("date", "")[-5:] for item in display_data]  # MM-DD format
    values = [item.get("count", 0) for item in display_data]

    if not values or max(values) == 0:
        return None

    chart = HorizontalLineChart()
    chart.x = 50
    chart.y = 30
    chart.height = 100
    chart.width = 380
    chart.data = [values]
    chart.categoryAxis.categoryNames = dates
    chart.categoryAxis.labels.fontSize = 8
    chart.categoryAxis.labels.angle = 45
    chart.valueAxis.valueMin = 0
    chart.valueAxis.valueMax = max(values) * 1.2
    chart.valueAxis.labels.fontSize = 9
    chart.lines[0].strokeColor = colors.HexColor("#3b82f6")
    chart.lines[0].strokeWidth = 2

    drawing.add(chart)

    # Add title
    drawing.add(
        String(
            225, 145, title, fontSize=11, fontName="Helvetica-Bold", textAnchor="middle"
        )
    )

    return drawing


def _create_pie_chart(
    data: List[dict], label_key: str, value_key: str, title: str
) -> Drawing:
    """Create a pie chart."""
    if not data:
        return None

    drawing = Drawing(450, 180)

    # Extract data (top 6)
    display_data = data[:6]
    labels = [item.get(label_key, "Unknown")[:15] for item in display_data]
    values = [item.get(value_key, 0) for item in display_data]

    total = sum(values)
    if total == 0:
        return None

    pie = Pie()
    pie.x = 150
    pie.y = 20
    pie.width = 120
    pie.height = 120
    pie.data = values
    pie.labels = [f"{label} ({value})" for label, value in zip(labels, values)]
    pie.slices.strokeWidth = 0.5
    pie.slices.strokeColor = colors.white

    for i, _ in enumerate(values):
        pie.slices[i].fillColor = CHART_COLORS[i % len(CHART_COLORS)]

    pie.sideLabels = True
    pie.simpleLabels = False
    pie.slices.labelRadius = 1.2
    pie.slices.fontSize = 9

    drawing.add(pie)

    # Add title
    drawing.add(
        String(
            225, 165, title, fontSize=11, fontName="Helvetica-Bold", textAnchor="middle"
        )
    )

    return drawing


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
    Generate a PDF analytics report with charts.

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
        rightMargin=50,
        leftMargin=50,
        topMargin=50,
        bottomMargin=50,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Heading1"],
        fontSize=22,
        spaceAfter=15,
        textColor=colors.HexColor("#1e293b"),
    )
    heading_style = ParagraphStyle(
        "CustomHeading",
        parent=styles["Heading2"],
        fontSize=14,
        spaceAfter=10,
        spaceBefore=15,
        textColor=colors.HexColor("#334155"),
    )
    subheading_style = ParagraphStyle(
        "SubHeading",
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.HexColor("#64748b"),
        spaceAfter=10,
    )
    normal_style = styles["Normal"]

    elements = []

    # Title
    elements.append(Paragraph(f"{org_name} Analytics Report", title_style))

    # Date info
    generated_at = datetime.utcnow().strftime("%B %d, %Y at %H:%M UTC")
    period_text = f"Period: {date_range}" if date_range else "Period: All Time"
    elements.append(
        Paragraph(f"{period_text} | Generated: {generated_at}", subheading_style)
    )
    elements.append(Spacer(1, 10))

    # =========================================================================
    # Summary Stats - Key Metrics in a horizontal layout
    # =========================================================================
    elements.append(Paragraph("Key Metrics", heading_style))

    summary_data = [
        [
            f"Total Cases\n{summary.get('total_cases', 0)}",
            f"New This Period\n{summary.get('new_this_period', 0)}",
            f"Qualified Rate\n{summary.get('qualified_rate', 0):.1f}%",
            f"Pending Tasks\n{summary.get('pending_tasks', 0)}",
            f"Overdue Tasks\n{summary.get('overdue_tasks', 0)}",
        ]
    ]

    summary_table = Table(
        summary_data,
        colWidths=[1.8 * inch, 1.8 * inch, 1.6 * inch, 1.4 * inch, 1.4 * inch],
    )
    summary_table.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 11),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#e2e8f0")),
                ("INNERGRID", (0, 0), (-1, -1), 1, colors.HexColor("#e2e8f0")),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ]
        )
    )
    elements.append(summary_table)
    elements.append(Spacer(1, 15))

    # =========================================================================
    # Cases by Status - Bar Chart + Table
    # =========================================================================
    if cases_by_status:
        elements.append(Paragraph("Cases by Status", heading_style))

        # Bar chart
        status_chart = _create_bar_chart(
            cases_by_status,
            "status",
            "count",
            "Distribution by Pipeline Stage",
            colors.HexColor("#22c55e"),
        )
        if status_chart:
            elements.append(status_chart)
            elements.append(Spacer(1, 10))

        # Compact table
        status_data = [["Status", "Count", "% of Total"]]
        total = sum(item.get("count", 0) for item in cases_by_status)
        for item in cases_by_status:
            count = item.get("count", 0)
            pct = (count / total * 100) if total > 0 else 0
            status_data.append(
                [item.get("status", "Unknown"), str(count), f"{pct:.1f}%"]
            )

        status_table = Table(
            status_data, colWidths=[2.5 * inch, 1.2 * inch, 1.2 * inch]
        )
        status_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#22c55e")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 10),
                    ("FONTSIZE", (0, 1), (-1, -1), 9),
                    ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [colors.white, colors.HexColor("#f0fdf4")],
                    ),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        elements.append(status_table)
        elements.append(Spacer(1, 15))

    # =========================================================================
    # Cases Trend - Line Chart
    # =========================================================================
    if trend_data and len(trend_data) >= 2:
        elements.append(Paragraph("Cases Trend", heading_style))

        trend_chart = _create_line_chart(trend_data, "New Cases Over Time")
        if trend_chart:
            elements.append(trend_chart)
            elements.append(Spacer(1, 15))

    # =========================================================================
    # Team Performance - Pie Chart for Assignees
    # =========================================================================
    if cases_by_assignee:
        elements.append(Paragraph("Team Performance", heading_style))

        # Pie chart
        assignee_chart = _create_pie_chart(
            cases_by_assignee, "display_name", "count", "Cases by Team Member"
        )
        if assignee_chart:
            elements.append(assignee_chart)
            elements.append(Spacer(1, 10))

        # Compact table (top 5)
        assignee_data = [["Team Member", "Cases"]]
        for item in cases_by_assignee[:5]:
            name = item.get("display_name") or item.get("owner_name") or "Unassigned"
            assignee_data.append([name, str(item.get("count", 0))])

        assignee_table = Table(assignee_data, colWidths=[3 * inch, 1.2 * inch])
        assignee_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#a855f7")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 10),
                    ("FONTSIZE", (0, 1), (-1, -1), 9),
                    ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [colors.white, colors.HexColor("#faf5ff")],
                    ),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        elements.append(assignee_table)
        elements.append(Spacer(1, 15))

    # =========================================================================
    # Meta Performance
    # =========================================================================
    if meta_performance and meta_performance.get("leads_received", 0) > 0:
        elements.append(Paragraph("Meta Lead Ads Performance", heading_style))

        leads_received = meta_performance.get("leads_received", 0)
        leads_qualified = meta_performance.get("leads_qualified", 0)
        leads_converted = meta_performance.get("leads_converted", 0)

        # Funnel visualization as nested bars
        meta_data = [
            [
                f"Leads Received\n{leads_received}",
                f"Qualified\n{leads_qualified} ({meta_performance.get('qualification_rate', 0):.1f}%)",
                f"Converted\n{leads_converted} ({meta_performance.get('conversion_rate', 0):.1f}%)",
            ]
        ]

        meta_table = Table(meta_data, colWidths=[2.4 * inch, 2.4 * inch, 2.4 * inch])
        meta_table.setStyle(
            TableStyle(
                [
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 11),
                    ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#3b82f6")),
                    ("BACKGROUND", (1, 0), (1, 0), colors.HexColor("#f59e0b")),
                    ("BACKGROUND", (2, 0), (2, 0), colors.HexColor("#22c55e")),
                    ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
                    ("TOPPADDING", (0, 0), (-1, -1), 15),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 15),
                ]
            )
        )
        elements.append(meta_table)

        avg_hours = meta_performance.get("avg_time_to_convert_hours")
        if avg_hours:
            days = avg_hours / 24
            elements.append(Spacer(1, 8))
            elements.append(
                Paragraph(f"Average Time to Convert: {days:.1f} days", subheading_style)
            )

        elements.append(Spacer(1, 15))

    # =========================================================================
    # Footer
    # =========================================================================
    elements.append(Spacer(1, 20))
    footer_style = ParagraphStyle(
        "Footer",
        parent=normal_style,
        fontSize=8,
        textColor=colors.gray,
        alignment=1,  # Center
    )
    elements.append(
        Paragraph(
            "This report was automatically generated by the CRM system.", footer_style
        )
    )

    doc.build(elements)
    return buffer.getvalue()
