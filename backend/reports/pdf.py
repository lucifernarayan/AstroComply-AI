"""Small, bounded organization report PDFs with provenance and limitations."""
from html import escape
from io import BytesIO
import reportlab
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer


def render_pdf(title: str, sections: list[tuple[str, list[tuple[str, object]]]]) -> bytes:
    buffer = BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=22 * mm,
                                 rightMargin=22 * mm, topMargin=22 * mm, bottomMargin=22 * mm)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='AstroTitle', parent=styles['Title'],
                              fontName='Helvetica-Bold', fontSize=17, leading=21,
                              textColor=colors.HexColor('#0c3550'), alignment=TA_LEFT,
                              spaceAfter=12))
    styles.add(ParagraphStyle(name='AstroSection', parent=styles['Heading2'],
                              fontName='Helvetica-Bold', fontSize=11, leading=14,
                              textColor=colors.HexColor('#125b72'), spaceBefore=11, spaceAfter=5))
    styles.add(ParagraphStyle(name='AstroRow', parent=styles['BodyText'],
                              fontName='Helvetica', fontSize=9, leading=13, spaceAfter=4))
    story = [Paragraph(escape(title), styles['AstroTitle']),
             HRFlowable(width='100%', thickness=1, color=colors.HexColor('#2b93aa')),
             Spacer(1, 6 * mm)]
    for heading, rows in sections:
        story.append(Paragraph(escape(heading), styles['AstroSection']))
        for label, value in rows:
            printable = 'Unavailable' if value is None else str(value)
            story.append(Paragraph(f'<b>{escape(label)}:</b> {escape(printable)}', styles['AstroRow']))
    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(colors.HexColor('#657b86'))
        canvas.drawString(22 * mm, 14 * mm, f'AstroComply | ReportLab {reportlab.Version}')
        canvas.drawRightString(A4[0] - 22 * mm, 14 * mm, f'Page {doc.page}')
        canvas.restoreState()
    document.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
