import os
import io
import time
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch

from typing import Dict, Any

def generate_mom_pdf(mom_data: Dict[str, Any]) -> io.BytesIO:
    """
    Generates a PDF buffer using reportlab based on the strict MOM target schema.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40,
    )

    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'MainTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=15,
        textColor=colors.HexColor('#1a73e8'),
        alignment=1 # Center
    )
    
    heading2_style = ParagraphStyle(
        'Heading2',
        parent=styles['Heading2'],
        fontSize=14,
        spaceBefore=12,
        spaceAfter=8,
        textColor=colors.HexColor('#333333'),
        borderPadding=(0,0,2,0),
    )
    
    normal_style = styles['Normal']
    normal_style.fontSize = 11
    normal_style.leading = 14
    
    bullet_style = ParagraphStyle(
        'BulletStyle',
        parent=normal_style,
        leftIndent=20,
        bulletIndent=10,
        spaceAfter=4
    )

    elements = []

    # --- Title & Metadata ---
    elements.append(Paragraph("Minutes of Meeting", title_style))
    elements.append(Spacer(1, 10))
    
    # Grid for Title, Date, Duration, and Attendees
    title = mom_data.get("meeting_title", "Meeting Summary")
    date = mom_data.get("date", "")
    duration = mom_data.get("duration", "0s")
    attendees = mom_data.get("total_attendees", 0)
    
    meta_data = [
        [Paragraph("<b>Meeting Title:</b>", normal_style), Paragraph(title, normal_style)],
        [Paragraph("<b>Date:</b>", normal_style), Paragraph(date, normal_style)],
        [Paragraph("<b>Duration:</b>", normal_style), Paragraph(duration, normal_style)],
        [Paragraph("<b>Total Attendees:</b>", normal_style), Paragraph(str(attendees), normal_style)]
    ]
    
    t = Table(meta_data, colWidths=[1.5*inch, 4.5*inch])
    t.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 15))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.lightgrey, spaceBefore=0, spaceAfter=10))

    # --- Meeting Summary / Insights ---
    elements.append(Paragraph("Meeting Summary / Insights", heading2_style))
    elements.append(Paragraph(mom_data.get("summary", "No summary provided."), normal_style))
    elements.append(Spacer(1, 15))

    # --- Participants ---
    elements.append(Paragraph("Participants", heading2_style))
    participants = mom_data.get("participants", [])
    if participants:
        elements.append(Paragraph(", ".join(participants), normal_style))
    else:
        elements.append(Paragraph("No participants recorded.", normal_style))
    elements.append(Spacer(1, 15))

    # --- Agenda ---
    elements.append(Paragraph("Agenda", heading2_style))
    elements.append(Paragraph(mom_data.get("agenda", "No agenda recorded."), normal_style))
    elements.append(Spacer(1, 15))

    # --- Attendance Log ---
    elements.append(Paragraph("Attendance Log", heading2_style))
    attendance = mom_data.get("attendance_log", [])
    if attendance:
        attn_data = [["Name", "Join Time", "Leave Time", "Duration"]]
        for row in attendance:
            attn_data.append([
                row.get("name", "Unknown"), 
                row.get("join_time", ""), 
                row.get("leave_time", ""), 
                row.get("duration", "")
            ])
            
        t_attn = Table(attn_data, colWidths=[2.5*inch, 1*inch, 1*inch, 1.5*inch])
        t_attn.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f3f3f3')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.black),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 10),
            ('BOTTOMPADDING', (0,0), (-1,0), 10),
            ('INNERGRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
            ('BOX', (0,0), (-1,-1), 0.5, colors.lightgrey),
        ]))
        elements.append(t_attn)
    else:
        elements.append(Paragraph("No attendance events detected.", normal_style))
    elements.append(Spacer(1, 15))

    # --- Key Discussions ---
    elements.append(Paragraph("Key Discussions", heading2_style))
    discussions = mom_data.get("key_discussions", [])
    if discussions:
        for p in discussions:
            # Add bullet points
            elements.append(Paragraph(f"<bullet>&bull;</bullet>{p}", bullet_style))
    else:
        elements.append(Paragraph("No key discussions recorded.", normal_style))
    elements.append(Spacer(1, 15))

    # --- Decisions ---
    elements.append(Paragraph("Decisions", heading2_style))
    decisions = mom_data.get("decisions", [])
    if decisions:
        for p in decisions:
            elements.append(Paragraph(f"<bullet>&bull;</bullet>{p}", bullet_style))
    else:
        elements.append(Paragraph("No final decisions recorded.", normal_style))
    elements.append(Spacer(1, 15))

    # --- Action Items ---
    elements.append(Paragraph("Action Items", heading2_style))
    actions = mom_data.get("action_items", [])
    if actions:
        act_data = [["Task", "Owner", "Deadline", "Status"]]
        for a in actions:
            act_data.append([
                Paragraph(a.get("task", ""), normal_style),
                a.get("owner", "TBD"),
                a.get("deadline", "TBD"),
                a.get("status", "Pending")
            ])
            
        t_act = Table(act_data, colWidths=[3*inch, 1*inch, 1*inch, 1*inch])
        t_act.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f3f3f3')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.black),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 10),
            ('BOTTOMPADDING', (0,0), (-1,0), 10),
            ('INNERGRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
            ('BOX', (0,0), (-1,-1), 0.5, colors.lightgrey),
        ]))
        elements.append(t_act)
    else:
        elements.append(Paragraph("No action items recorded.", normal_style))
    elements.append(Spacer(1, 15))

    # --- Risks & Follow-ups ---
    elements.append(Paragraph("Risks & Follow-ups", heading2_style))
    risks = mom_data.get("risks_followups", [])
    if risks:
        for item in risks:
            if isinstance(item, str):
                elements.append(Paragraph(f"<bullet>&bull;</bullet>{item}", bullet_style))
            elif isinstance(item, dict) and 'message' in item:
                elements.append(Paragraph(f"<bullet>&bull;</bullet>{item['message']}", bullet_style))
    else:
        elements.append(Paragraph("No specific risks detected.", normal_style))
    elements.append(Spacer(1, 15))

    # --- Conclusion ---
    elements.append(Paragraph("Conclusion", heading2_style))
    elements.append(Paragraph(mom_data.get("conclusion", "Session concluded."), normal_style))
    elements.append(Spacer(1, 15))

    doc.build(elements)
    buffer.seek(0)
    return buffer
