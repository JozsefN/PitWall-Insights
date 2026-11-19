"""Build the source-checked thesis draft as Word, native PDF and inline HTML."""

import base64
import argparse
from html import escape
import json
from pathlib import Path
import re
import subprocess

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from PIL import Image

from thesis_template import create_document, UNNUMBERED


DOCS = Path(__file__).resolve().parents[1]
SOURCE = DOCS / 'PitWall-Insights-szakdolgozat-munkavaltozat.md'
STEM = SOURCE.stem
WORK = DOCS / 'generated/szakdolgozat-forrasok'


def parse(text):
    lines = text.splitlines()
    blocks = []
    position = 0
    while position < len(lines):
        line = lines[position].strip()
        if not line:
            position += 1
            continue
        if line.startswith('|'):
            table = []
            while position < len(lines) and lines[position].strip().startswith('|'):
                cells = [x.strip() for x in lines[position].strip().strip('|').split('|')]
                if not all(re.fullmatch(r':?-+:?', cell) for cell in cells):
                    table.append(cells)
                position += 1
            blocks.append(('table', table))
            continue
        heading = re.fullmatch(r'(#{1,4}) (.+)', line)
        picture = re.fullmatch(r'!\[(.+)\]\((.+)\)', line)
        if heading:
            blocks.append(('heading', (len(heading[1]), heading[2])))
        elif picture:
            blocks.append(('image', (picture[1], picture[2])))
        else:
            paragraph = [line]
            while position + 1 < len(lines) and lines[position + 1].strip() and not lines[position + 1].startswith(('#', '|', '![')):
                position += 1
                paragraph.append(lines[position].strip())
            blocks.append(('paragraph', ' '.join(paragraph)))
        position += 1
    return blocks


def field(paragraph, instruction, placeholder=''):
    begin = OxmlElement('w:fldChar')
    begin.set(qn('w:fldCharType'), 'begin')
    paragraph.add_run()._r.append(begin)
    code = OxmlElement('w:instrText')
    code.set(qn('xml:space'), 'preserve')
    code.text = instruction
    paragraph.add_run()._r.append(code)
    separator = OxmlElement('w:fldChar')
    separator.set(qn('w:fldCharType'), 'separate')
    paragraph.add_run()._r.append(separator)
    if placeholder:
        paragraph.add_run(placeholder)
    end = OxmlElement('w:fldChar')
    end.set(qn('w:fldCharType'), 'end')
    paragraph.add_run()._r.append(end)


def note(text):
    return text.startswith(('[Kidolgozandó:', '[Kiegészítendő:', '[Pontosítandó:', '[Kitöltendő ', '[Tervezett rész.'))


def main(update_outline=False):
    WORK.mkdir(parents=True, exist_ok=True)
    source = SOURCE.read_text(encoding='utf-8')
    assert not any(c in source for c in '\u2013\u2014\u2015'), 'Unexpected long dash'
    assert not re.search(r'^#{5,}', source, re.M), 'Only three numbered heading levels are supported'
    blocks = parse(source)
    title = blocks[0][1][1]
    first_chapter = next(i for i, block in enumerate(blocks) if block[0] == 'heading' and block[1][0] == 2)
    headings = [value for kind, value in blocks if kind == 'heading']
    outline = '# ' + title + '\n\n'
    outline += '\n\n'.join('## ' + text for text in ['Feladatkiírás', 'Címoldal', 'Tartalomjegyzék', 'Hallgatói nyilatkozat'])
    outline += '\n\n' + '\n\n'.join('#' * level + ' ' + text for level, text in headings[1:]) + '\n'
    (DOCS / 'PitWall-Insights-szakdolgozat-vazlat.md').write_text(outline, encoding='utf-8')

    def add_toc(document):
        field(document.add_paragraph(), ' TOC \\o "1-2" \\h \\z ', 'Tartalomjegyzék')
    document = create_document(title, add_toc)

    html_body = [f'<header><h1>{escape(title)}</h1>']
    for kind, value in blocks[1:first_chapter]:
        if kind == 'paragraph':
            html_body.append(f'<p>{escape(value)}</p>')
    html_body.append('</header><nav><h2>Tartalomjegyzék</h2><ul>')
    for i, (level, text) in enumerate(headings[1:]):
        if level <= 3:
            html_body.append(f'<li class="depth-{level}"><a href="#h{i}">{escape(text)}</a></li>')
    html_body.append('</ul></nav>')
    heading_index = 0
    figure_count = 0
    chapter = '0'
    chapter_figures = {}
    for kind, value in blocks[first_chapter:]:
        if kind == 'heading':
            level, text = value
            if level == 2 and not re.match(r'\d+\.', text):
                style = UNNUMBERED
            else:
                style = f'Heading {level - 1}'
            paragraph = document.add_paragraph(text, style)
            if level == 2:
                paragraph.paragraph_format.page_break_before = heading_index != 0
                if re.match(r'\d+\.', text):
                    chapter = text.split('.')[0]
                elif text == 'Függelékek':
                    chapter = 'F'
            html_body.append(f'<h{level} id="h{heading_index}">{escape(text)}</h{level}>')
            heading_index += 1
        elif kind == 'paragraph':
            paragraph = document.add_paragraph(value)
            if note(value):
                for run in paragraph.runs:
                    run.font.italic = True
                    run.font.size = Pt(10)
                    run.font.color.rgb = RGBColor(95, 95, 95)
            else:
                paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            html_body.append(f'<p class="{"note" if note(value) else "body"}">{escape(value)}</p>')
        elif kind == 'image':
            caption, relative = value
            path = DOCS / relative
            assert path.exists(), f'Missing figure: {path}'
            figure_count += 1
            chapter_figures[chapter] = chapter_figures.get(chapter, 0) + 1
            figure_number = f'{chapter}.{chapter_figures[chapter]}'
            with Image.open(path) as picture:
                width_cm = min(15, 15 * picture.width / picture.height)
            shape = document.add_picture(str(path), width=Cm(width_cm))
            shape._inline.docPr.set('descr', caption)
            figure_paragraph = document.paragraphs[-1]
            figure_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            figure_paragraph.paragraph_format.first_line_indent = Cm(0)
            figure_paragraph.paragraph_format.left_indent = Cm(0)
            figure_paragraph.paragraph_format.right_indent = Cm(0)
            figure_paragraph.paragraph_format.keep_with_next = True
            caption_paragraph = document.add_paragraph(f'{figure_number}. ábra. {caption}', 'Caption')
            caption_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            caption_paragraph.paragraph_format.first_line_indent = Cm(0)
            image = base64.b64encode(path.read_bytes()).decode('ascii')
            html_body.append(f'<figure><img src="data:image/png;base64,{image}" alt="{escape(caption)}"><figcaption>{figure_number}. ábra. {escape(caption)}</figcaption></figure>')
        elif kind == 'table':
            table = document.add_table(rows=1, cols=len(value[0]))
            if 'Table Grid' in document.styles:
                table.style = 'Table Grid'
            repeat = OxmlElement('w:tblHeader')
            table.rows[0]._tr.get_or_add_trPr().append(repeat)
            for i, cells in enumerate(value):
                row = table.rows[0] if i == 0 else table.add_row()
                row._tr.get_or_add_trPr().append(OxmlElement('w:cantSplit'))
                for cell, text in zip(row.cells, cells):
                    cell.text = text
                    for paragraph in cell.paragraphs:
                        paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
                        paragraph.paragraph_format.first_line_indent = Cm(0)
                        paragraph.paragraph_format.line_spacing = 1.1
                        paragraph.paragraph_format.space_after = Pt(4)
                        for run in paragraph.runs:
                            run.font.size = Pt(10)
                            run.bold = i == 0
            html_body.append('<table>')
            for i, row in enumerate(value):
                tag = 'th' if i == 0 else 'td'
                html_body.append('<tr>' + ''.join(f'<{tag}>{escape(cell)}</{tag}>' for cell in row) + '</tr>')
            html_body.append('</table>')

    for paragraph in document.paragraphs:
        for run in paragraph.runs:
            language = OxmlElement('w:lang')
            language.set(qn('w:val'), 'hu-HU')
            run._r.get_or_add_rPr().append(language)
    staged = WORK / 'szakdolgozat-export.docx'
    document.save(staged)
    css = '''@page{size:A4;margin:25mm 25mm 25mm 35mm}body{font:12pt/1.5 "Times New Roman",serif;color:#151515;max-width:150mm;margin:25px auto}header{text-align:center;padding:20mm 0;break-after:page}header p{font-size:11pt}h1{font-size:23pt}h2{font-size:18pt;break-after:avoid}h3{font-size:16pt;break-after:avoid}p{text-align:justify}header p{text-align:center}.note{font-size:10.5pt;color:#666;font-style:italic}table{width:100%;border-collapse:collapse;font-size:10.5pt}th,td{border:1px solid #aaa;padding:6px;vertical-align:top}figure{margin:16px 0;break-inside:avoid}img{width:100%;height:auto}figcaption{font-size:10pt}nav{break-after:page}nav ul{list-style:none;padding-left:0}nav li{font-size:10.5pt}.depth-3{padding-left:16px}a{color:inherit}'''
    css += 'h4{font-size:14pt;break-after:avoid}.depth-4{padding-left:32px}figure{text-align:center}figure img{max-height:150mm;object-fit:contain}'
    html = '<!doctype html><html lang="hu"><meta charset="utf-8"><title>' + escape(title) + '</title><style>' + css + '</style><body>' + '\n'.join(html_body) + '</body></html>'
    SOURCE.with_suffix('.html').write_text(html, encoding='utf-8')
    subprocess.run([
        'powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
        str(Path(__file__).with_name('export_feladatkiiras.ps1')),
        '-InputDocx', str(staged), '-TargetDocx', str(SOURCE.with_suffix('.docx')),
        '-OutputPdf', str(SOURCE.with_suffix('.pdf')),
        '-SnapshotXml', str(WORK / 'szakdolgozat-word.xml'), '-UpdateContents',
    ], check=True)
    if update_outline:
        subprocess.run(['python', '-X', 'utf8', str(Path(__file__).with_name('build_szakdolgozat_vazlat.py'))], check=True)
    chapters = sum(level == 2 and bool(re.match(r'\d+\.', text)) for level, text in headings)
    print(json.dumps({'paragraph_words': len(source.split()), 'figures': figure_count, 'chapters': chapters, 'word': str(SOURCE.with_suffix('.docx')), 'pdf': str(SOURCE.with_suffix('.pdf'))}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--update-outline', action='store_true', help='Also regenerate the separate outline document')
    main(update_outline=parser.parse_args().update_outline)
