"""Use the supplied AUT Word template without changing the original file."""

from copy import deepcopy
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION_START
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from docx.text.paragraph import Paragraph
import pymupdf


DOCS = Path(__file__).resolve().parents[1]
TEMPLATE = next(DOCS.glob('DiplomatervSablon*.docx'))
WORK = DOCS / 'generated/szakdolgozat-forrasok'
UNNUMBERED = 'Fejezetcim számozás nélkül'


def field(paragraph, instruction):
    for kind in ('begin', 'instruction', 'end'):
        element = OxmlElement('w:instrText' if kind == 'instruction' else 'w:fldChar')
        if kind == 'instruction':
            element.set(qn('xml:space'), 'preserve')
            element.text = instruction
        else:
            element.set(qn('w:fldCharType'), kind)
        paragraph.add_run()._r.append(element)


def set_section(section, numbered):
    section.top_margin = section.bottom_margin = Cm(2.5)
    section.left_margin = section.right_margin = Cm(2.5)
    section.gutter = Cm(1)
    section.different_first_page_header_footer = False
    for item in [section.header, section.footer, section.first_page_header, section.first_page_footer, section.even_page_header, section.even_page_footer]:
        item.is_linked_to_previous = False
        for paragraph in item.paragraphs:
            paragraph.clear()
    if numbered:
        paragraph = section.footer.paragraphs[0]
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        field(paragraph, ' PAGE ')


def assignment_picture():
    pdf = pymupdf.open(DOCS / 'Forma1feladatkiiras.pdf')
    page = pdf[0]
    rectangles = [pymupdf.Rect(block[:4]) for block in page.get_text('blocks')]
    clip = rectangles[0]
    for rectangle in rectangles[1:]:
        clip |= rectangle
    clip = pymupdf.Rect(clip.x0 - 3, clip.y0 - 3, clip.x1 + 3, clip.y1 + 3) & page.rect
    output = WORK / 'feladatkiiras-beillesztve.png'
    page.get_pixmap(matrix=pymupdf.Matrix(2, 2), clip=clip).save(output)
    return output


def create_document(title, toc_callback):
    document = Document(TEMPLATE)
    saved = list(document.paragraphs)
    logo = deepcopy(saved[2]._p)
    for element in logo.xpath('.//w:br | .//w:lastRenderedPageBreak'):
        if element.tag == qn('w:lastRenderedPageBreak') or element.get(qn('w:type')) == 'page':
            element.getparent().remove(element)
    legal = [saved[93].text, saved[94].text]
    body = document._element.body
    for child in list(body):
        if child is not body.sectPr:
            body.remove(child)
    section = document.sections[0]
    set_section(section, numbered=False)
    for name, size in [('Heading 1', 18), ('Heading 2', 16), ('Heading 3', 14), (UNNUMBERED, 18)]:
        style = document.styles[name]
        # Explicit values prevent inherited/linked Word styles from changing
        # the appearance of headings that belong to the same outline level.
        style.font.name = 'Times New Roman'
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = RGBColor(0, 0, 0)
        style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
        style.paragraph_format.first_line_indent = Cm(0)
        style.paragraph_format.left_indent = Cm(0)
        style.paragraph_format.keep_with_next = True
        style.paragraph_format.line_spacing = 1
        style.paragraph_format.space_before = Pt(14)
        style.paragraph_format.space_after = Pt(6)
        if style.element.pPr is not None:
            for numbering in list(style.element.pPr.findall(qn('w:numPr'))):
                style.element.pPr.remove(numbering)
    normal = document.styles['Normal']
    normal.font.name = 'Times New Roman'
    normal.font.size = Pt(12)
    normal.paragraph_format.line_spacing = 1.5
    normal.paragraph_format.space_after = Pt(6)
    document.core_properties.title = title
    document.core_properties.author = 'Novák József Pál'
    document.core_properties.subject = 'Szakdolgozati munkaváltozat'

    paragraph = document.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.line_spacing = 1
    paragraph.paragraph_format.space_after = Pt(0)
    picture = assignment_picture()
    image_size = pymupdf.Pixmap(picture)
    width = min(15, 23.2 * image_size.width / image_size.height)
    paragraph.add_run().add_picture(str(picture), width=Cm(width))
    document.add_page_break()

    body.insert(len(body) - 1, logo)
    Paragraph(logo, document._body).paragraph_format.page_break_before = False
    document.add_paragraph('Budapesti Műszaki és Gazdaságtudományi Egyetem', 'Címlap egyetem')
    document.add_paragraph('Villamosmérnöki és Informatikai Kar', 'Címlap kar és tanszék')
    document.add_paragraph('Automatizálási és Alkalmazott Informatikai Tanszék', 'Címlap kar és tanszék')
    paragraph = document.add_paragraph('Novák József Pál', 'Címlap szerző')
    paragraph.paragraph_format.space_before = Pt(58)
    document.add_paragraph(title, 'Title')
    paragraph = document.add_paragraph('Szakdolgozati munkaváltozat.')
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph = document.add_paragraph('Konzulens')
    paragraph.paragraph_format.space_before = Pt(35)
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    document.add_paragraph('Albert István', 'Címlap szerző')
    paragraph = document.add_paragraph('Budapest, 2026')
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    document.add_page_break()

    paragraph = document.add_paragraph('Tartalomjegyzék', 'Fejezetcím tartalomjegyzék nélkül')
    paragraph.paragraph_format.page_break_before = False
    toc_callback(document)
    document.add_page_break()

    document.add_paragraph('Hallgatói nyilatkozat', 'Nyilatkozat cím')
    for text in legal:
        text = text.replace('Kővári Bence', 'Novák József Pál').replace('szakdolgozatot/ diplomatervet', 'szakdolgozatot')
        document.add_paragraph(text, 'Nyilatkozat szöveg')
    document.add_paragraph('Kelt: Budapest, ................................', 'Nyilatkozat keltezés')
    document.add_paragraph('........................................................', 'Nyilatkozat aláírás')
    document.add_paragraph('Novák József Pál', 'Nyilatkozat aláírás')
    paragraph = document.add_paragraph('[A nyilatkozat a munkaváltozatban kitöltetlen keltezéssel és aláírás nélkül szerepel.]')
    paragraph.runs[0].font.size = Pt(10)
    paragraph.runs[0].italic = True

    section = document.add_section(WD_SECTION_START.NEW_PAGE)
    set_section(section, numbered=True)
    return document


def append_mi_declaration(document):
    original = Document(TEMPLATE)
    for index in (324, 325):
        document.add_paragraph(original.paragraphs[index].text.replace('\uf0a8', '\u2610'))
    table = deepcopy(original.tables[0]._tbl)
    body = document._element.body
    body.insert(len(body) - 1, table)
    target = document.tables[-1]
    entries = {
        1: ('Codex (OpenAI)', 'Hivatalos dokumentációk és az írásmódról szóló kutatás előkeresése, ellenőrzése.'),
        3: ('Codex (OpenAI)', 'Dokumentum-előállító és ellenőrző segédprogramok. Az alkalmazáskód használata külön pontosítandó.'),
        5: ('Codex (OpenAI)', 'A dolgozat szerkezetére és a bemutatás sorrendjére vonatkozó javaslatok.'),
        7: ('Codex (OpenAI)', 'A fejezet- és alfejezetvázlat összeállítása és átdolgozása.'),
        9: ('Codex (OpenAI)', 'A munkaváltozat szövegének megfogalmazása és átdolgozása a saját kód, jegyzetek és mérések alapján.'),
    }
    for index in range(1, 18, 2):
        row = target.rows[index]
        if index in entries:
            row.cells[1].text, row.cells[2].text = entries[index]
        else:
            row.cells[1].text = 'A tényleges használat szerint kitöltendő.'
            row.cells[2].text = 'Pontosítandó.'
        row.cells[3].text = 'Kitöltendő'
        prompt = target.rows[index + 1]
        prompt.cells[1].text = 'A kapcsolódó feladatleírások rövid összefoglalása és a pontos modelladatok még kitöltendők.'
    target.rows[19].cells[4].text = 'Kitöltendő'
    for row in target.rows:
        properties = row._tr.get_or_add_trPr()
        properties.append(OxmlElement('w:cantSplit'))
        for cell in row.cells:
            for paragraph in cell.paragraphs:
                paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
                paragraph.paragraph_format.line_spacing = 1
                paragraph.paragraph_format.space_after = Pt(3)
                for run in paragraph.runs:
                    run.font.size = Pt(10)
    header = OxmlElement('w:tblHeader')
    target.rows[0]._tr.get_or_add_trPr().append(header)
    document.add_paragraph('[A felhasználási arányok és a teljes projekt eszközhasználata személyes ellenőrzés után véglegesíthetők. A táblázat nem tartalmaz kitalált százalékokat.]')
