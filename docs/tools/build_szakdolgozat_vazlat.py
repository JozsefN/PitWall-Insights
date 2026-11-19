"""Create a headings-only Word outline from the editable Markdown outline."""

from pathlib import Path
import re

from docx import Document
from docx.shared import Cm, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn


DOCS = Path(__file__).resolve().parents[1]
SOURCE = DOCS / 'PitWall-Insights-szakdolgozat-vazlat.md'
TARGET = SOURCE.with_suffix('.docx')


def main():
    lines = [line for line in SOURCE.read_text(encoding='utf-8').splitlines() if line.strip()]
    headings = []
    for line in lines:
        match = re.fullmatch(r'(#{1,4}) (.+)', line)
        if not match:
            raise ValueError(f'The outline must contain headings only: {line}')
        headings.append((len(match[1]), match[2]))

    document = Document()
    section = document.sections[0]
    section.page_width = Cm(21)
    section.page_height = Cm(29.7)
    section.top_margin = section.bottom_margin = Cm(2)
    section.left_margin = section.right_margin = Cm(2.5)
    for style_name, size in [('Normal', 11), ('Title', 17), ('Heading 1', 13), ('Heading 2', 11), ('Heading 3', 11)]:
        style = document.styles[style_name]
        style.font.name = 'Times New Roman'
        style.font.size = Pt(size)
        style.font.color.rgb = RGBColor(0, 0, 0)
        style.paragraph_format.line_spacing = 1
        style.paragraph_format.page_break_before = False
    document.styles['Title'].paragraph_format.space_after = Pt(12)
    for level, before, after, indent in [(1, 9, 3, 0), (2, 3, 1, 0.5), (3, 1, 0, 1)]:
        style = document.styles[f'Heading {level}']
        style.paragraph_format.space_before = Pt(before)
        style.paragraph_format.space_after = Pt(after)
        style.paragraph_format.left_indent = Cm(indent)
        style.font.bold = level != 3
    document.core_properties.title = headings[0][1]
    document.core_properties.author = 'Novák József Pál'
    document.core_properties.subject = 'Szakdolgozati fejezetvázlat'
    for index, (level, text) in enumerate(headings):
        paragraph = document.add_paragraph(text, 'Title' if level == 1 else f'Heading {level - 1}')
        paragraph.paragraph_format.keep_with_next = index + 1 < len(headings) and headings[index + 1][0] > level
        for run in paragraph.runs:
            properties = run._r.get_or_add_rPr()
            language = OxmlElement('w:lang')
            language.set(qn('w:val'), 'en-US' if text == 'Abstract' else 'hu-HU')
            properties.append(language)
    document.save(TARGET)

    # Verify the exported outline has the exact same headings and hierarchy.
    exported = Document(TARGET)
    assert [p.text for p in exported.paragraphs] == [text for _, text in headings]
    for paragraph, (level, _) in zip(exported.paragraphs, headings):
        assert paragraph.style.name == ('Title' if level == 1 else f'Heading {level - 1}')
    chapter_numbers = [int(re.match(r'(\d+)\.', text)[1]) for level, text in headings if level == 2 and re.match(r'\d+\.', text)]
    assert chapter_numbers == list(range(1, len(chapter_numbers) + 1))
    in_appendix = False
    for level, text in headings:
        if level == 2:
            in_appendix = text == 'Függelékek'
        if level == 4:
            pattern = r'[A-Z]\.\d+\.' if in_appendix else r'\d+\.\d+\.\d+\.'
            assert re.match(pattern, text), text
    print(TARGET)
    print(f'Validated: {len(headings) - 1} headings, {len(chapter_numbers)} numbered chapters; no body paragraphs; Markdown and Word match.')


if __name__ == '__main__':
    main()
