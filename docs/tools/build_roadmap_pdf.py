from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / 'docs' / 'PitWall-Insights-fejlesztesi-utemterv-2026.pdf'
pdfmetrics.registerFont(TTFont('Arial', 'C:/Windows/Fonts/arial.ttf'))
styles = {
    'heading': ParagraphStyle('WeekHu', fontName='Arial', fontSize=10, leading=13, spaceBefore=8, spaceAfter=4, keepWithNext=True),
    'body': ParagraphStyle('BodyHu', fontName='Arial', fontSize=10, leading=13, spaceAfter=5, alignment=TA_LEFT),
}
story = []


def add(text, style='body'):
    story.append(Paragraph(escape(text), styles[style]))


lines = OUTPUT.with_suffix('.txt').read_text(encoding='utf-8').splitlines()
for index, line in enumerate(lines):
    if not line.strip():
        continue
    if index < 2:
        continue
    elif line.startswith('# '):
        add(line[2:], 'heading')
    else:
        add(line)


doc = SimpleDocTemplate(str(OUTPUT), pagesize=(210 * mm, 297 * mm),
                        rightMargin=20 * mm, leftMargin=20 * mm,
                        topMargin=17 * mm, bottomMargin=20 * mm,
                        title='PitWall Insights – fejlesztési ütemterv',
                        author='PitWall Insights')
doc.build(story)
print(OUTPUT)
