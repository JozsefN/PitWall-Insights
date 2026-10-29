"""Check the assignment export and render its current preview."""

from pathlib import Path
import re
import unicodedata

from docx import Document
import pymupdf

from build_feladatkiiras import (
    INTRO, TECHNOLOGY, GOAL, TASKS, TITLE_HU, STUDENT, NEPTUN, DATE, TASK_HEADING,
)


def normalize(text):
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', text))


def main():
    docs = Path(__file__).resolve().parents[1]
    pdf = pymupdf.open(docs / 'PitWall-Insights-feladatkiiras.pdf')
    assert len(pdf) == 1, 'The assignment must fit on one page'
    body = pdf[0].get_text()
    for text in [INTRO, TECHNOLOGY, GOAL, *TASKS, TITLE_HU, STUDENT, NEPTUN, DATE, TASK_HEADING]:
        assert normalize(text) in normalize(body), f'PDF text differs: {text[:60]}'
    doc = Document(docs / 'PitWall-Insights-feladatkiiras-tervezet.docx')
    mirror = Document(docs / 'PitWall-Insights-feladatkiiras-szerkesztheto.docx')
    assert [p.text for p in doc.paragraphs] == [p.text for p in mirror.paragraphs]
    assert [p.text for p in doc.paragraphs[4:7]] == [INTRO, TECHNOLOGY, GOAL]
    assert [p.text for p in doc.paragraphs[8:15]] == ['•\t' + task for task in TASKS]
    assert any('TANSZÉKVEZETŐ' in p.text for p in doc.sections[0].header.paragraphs)
    footer = ''.join(p.text for p in doc.sections[0].footer.paragraphs)
    assert 'Automatizálási és Alkalmazott Informatikai Tanszék' in footer
    assert (docs / 'PitWall-Insights-feladatkiiras.pdf').read_bytes() == (
        docs / 'PitWall-Insights-feladatkiiras-tervezet.pdf'
    ).read_bytes()
    assert all(term not in body for term in ['BKK', 'Válassz', 'készítek', 'chatbot'])
    pdf[0].get_pixmap(matrix=pymupdf.Matrix(1.6, 1.6)).save(
        docs / 'generated/feladatkiiras-preview.png'
    )
    print('Validated: one page; three introduction paragraphs; seven tasks; '
          'Word/PDF text, metadata, institutional header/footer and mirror files match.')


if __name__ == '__main__':
    main()
