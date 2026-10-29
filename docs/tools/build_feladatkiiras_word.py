"""Build the assignment DOCX and export that same Word layout to PDF."""

from copy import deepcopy
from pathlib import Path
import shutil
import subprocess

from docx import Document
from docx.shared import Cm, Pt
from docx.text.paragraph import Paragraph
from word_flatopc import flatopc_to_docx


def replace(paragraph, text):
    exemplar = next((run for run in paragraph.runs if run.text.strip()), None)
    properties = deepcopy(exemplar._r.rPr) if exemplar is not None and exemplar._r.rPr is not None else None
    paragraph.clear()
    run = paragraph.add_run(text)
    if properties is not None:
        run._r.insert(0, properties)


def build_documents(root, metadata, introduction, tasks):
    docs = root / 'docs'
    generated = docs / 'generated'
    doc = Document(generated / 'PitWall-Insights-feladatkiiras-konzulensi-sablon.docx')
    p = list(doc.paragraphs)
    if len(p) != 22 or not p[16].text.startswith('Tanszéki konzulens:'):
        raise ValueError('Unexpected Word template structure')
    if len(introduction) != 3 or not tasks:
        raise ValueError('Expected introduction, technology rationale and goals')

    # Rebuild the body using the supplied Word file's paragraph formatting.
    # Section settings, institutional header/footer and their images survive.
    body = doc._element.body
    for child in list(body):
        if child is not body.sectPr:
            body.remove(child)

    def add(template_index, text):
        element = deepcopy(p[template_index]._p)
        body.insert(len(body) - 1, element)
        paragraph = Paragraph(element, doc._body)
        replace(paragraph, text)
        if template_index in (7, 8, 9, 16, 18, 19, 20, 21):
            for run in paragraph.runs:
                run.font.name = 'Times New Roman'
                run.font.size = Pt(11)
        return paragraph

    add(0, 'SZAKDOLGOZAT FELADAT')
    add(1, metadata['student'])
    add(2, 'Mérnökinformatikus hallgató részére (BSc) – ' + metadata['neptun'])
    title = add(5, metadata['title_hu'])
    title.paragraph_format.space_before = Pt(9)
    title.paragraph_format.space_after = Pt(9)
    for paragraph_text in introduction:
        paragraph = add(7, paragraph_text)
        paragraph.paragraph_format.space_after = Pt(4)
    add(8, metadata['task_heading'])
    for task in tasks:
        paragraph = add(9, '•\t' + task)
        paragraph.paragraph_format.left_indent = Cm(0.5)
        paragraph.paragraph_format.first_line_indent = Cm(-0.5)
        paragraph.paragraph_format.tab_stops.add_tab_stop(Cm(0.5))
        paragraph.paragraph_format.space_after = Pt(2)

    consultant = add(16, '')
    consultant.paragraph_format.space_before = Pt(6)
    consultant.add_run('Tanszéki konzulens:').bold = True
    consultant.add_run('\t' + metadata['supervisor'])
    for run in consultant.runs:
        run.font.name = 'Times New Roman'
        run.font.size = Pt(11)
    date = add(18, metadata['date'])
    date.paragraph_format.space_before = Pt(6)
    date.paragraph_format.space_after = Pt(6)
    add(19, metadata['head']).paragraph_format.keep_with_next = True
    add(20, 'egyetemi tanár').paragraph_format.keep_with_next = True
    add(21, 'tanszékvezető')

    staged_docx = generated / 'feladatkiiras-current-build.docx'
    export_snapshot = generated / 'feladatkiiras-exported-word.xml'
    target_docx = docs / 'PitWall-Insights-feladatkiiras-tervezet.docx'
    target_pdf = docs / 'PitWall-Insights-feladatkiiras.pdf'
    doc.save(staged_docx)
    subprocess.run([
        'powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
        str(Path(__file__).with_name('export_feladatkiiras.ps1')),
        '-InputDocx', str(staged_docx), '-TargetDocx', str(target_docx),
        '-OutputPdf', str(target_pdf), '-SnapshotXml', str(export_snapshot),
    ], check=True)
    flatopc_to_docx(export_snapshot, docs / 'PitWall-Insights-feladatkiiras-szerkesztheto.docx')
    shutil.copyfile(target_pdf, docs / 'PitWall-Insights-feladatkiiras-tervezet.pdf')

    text = 'MAGYAR CÍM\n' + metadata['title_hu'] + '\n\nANGOL CÍM\n' + metadata['title_en']
    text += f"\n\nNÉV: {metadata['student']}\nNEPTUN-KÓD: {metadata['neptun']}\nKÉPZÉS: Mérnökinformatikus BSc\n"
    text += 'TANSZÉK: Automatizálási és Alkalmazott Informatikai Tanszék\n'
    text += f"KONZULENS: {metadata['supervisor']}\n"
    text += '\nFELADATKIÍRÁS SZÖVEGE\n\n' + '\n\n'.join(introduction)
    text += '\n\n' + metadata['task_heading'] + '\n\n'
    text += '\n\n'.join(f'{i}. {task}' for i, task in enumerate(tasks, 1))
    (docs / 'PitWall-Insights-feladatkiiras-szoveg.txt').write_text(text + '\n', encoding='utf-8')
    print(target_docx)
    print(target_pdf)
