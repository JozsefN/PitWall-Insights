"""Validate traceability, heading typography and source/Word/PDF consistency."""

from datetime import date
from hashlib import sha256
from html import escape
import json
from pathlib import Path
import re
import sqlite3
import unicodedata

from docx import Document
from docx.oxml.ns import qn
import pymupdf

from build_thesis_draft import parse, note
from thesis_template import TEMPLATE, UNNUMBERED

DOCS = Path(__file__).resolve().parents[1]
SOURCE = DOCS / 'PitWall-Insights-szakdolgozat-munkavaltozat.md'
OUTPUT = DOCS / 'generated/szakdolgozat-forrasok'


def normalized(text):
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', text))


def section(text, start, end):
    return text.split(start, 1)[1].split(end, 1)[0]


def effective_font(style, attribute):
    styles_element = style.element.getparent()
    while style is not None:
        value = getattr(style.font, attribute)
        if value is not None:
            return value
        style = style.base_style
    if attribute == 'name':
        defaults = styles_element.xpath('./w:docDefaults/w:rPrDefault/w:rPr/w:rFonts')
        if defaults:
            return defaults[0].get(qn('w:ascii'))
    return None


def numbered_headings(blocks):
    headings, counters = [], {}
    for kind, value in blocks:
        if kind != 'heading':
            continue
        level, title = value
        match = re.match(r'(\d+(?:\.\d+)*)\. ', title)
        if not match:
            continue
        numbers = tuple(map(int, match[1].split('.')))
        assert len(numbers) <= 3 and len(numbers) == level - 1, title
        parent = numbers[:-1]
        assert numbers[-1] == counters.get(parent, 0) + 1, title
        if parent:
            assert parent in [row[2] for row in headings], f'Missing parent: {title}'
        counters[parent] = numbers[-1]
        headings.append((level, title, numbers))
    return headings


def main():
    text = SOURCE.read_text(encoding='utf-8')
    blocks = parse(text)
    numbered = numbered_headings(blocks)
    chapters = [row for row in numbered if len(row[2]) == 1]
    assert len(chapters) == 8
    assert not re.search(r'^#{5,}', text, re.M)
    pdf = pymupdf.open(SOURCE.with_suffix('.pdf'))
    pdf_text = '\n'.join(page.get_text() for page in pdf)
    body_text = '\n'.join(page.get_text(clip=pymupdf.Rect(0, 0, page.rect.width, page.rect.height - 60)) for page in pdf)
    pdf_normal = normalized(body_text)
    word = Document(SOURCE.with_suffix('.docx'))
    headings = [value[1] for kind, value in blocks if kind == 'heading'][1:]
    exported = [p for p in word.paragraphs if p.style.name.startswith('Heading') or p.style.name == UNNUMBERED]
    assert [p.text for p in exported] == headings
    for kind, value in blocks:
        if kind == 'paragraph':
            assert normalized(value) in pdf_normal, f'Paragraph differs or is missing: {value[:90]}'
        elif kind == 'heading':
            assert normalized(value[1]).casefold() in pdf_normal.casefold(), f'Heading differs: {value[1]}'
        elif kind == 'table':
            for row in value:
                for cell in row:
                    assert normalized(cell) in pdf_normal, f'Table cell differs: {cell}'
        elif kind == 'image':
            assert normalized(value[0]) in pdf_normal, f'Figure caption differs: {value[0]}'

    html = SOURCE.with_suffix('.html').read_text(encoding='utf-8')
    assert html.count('<figure>') == sum(kind == 'image' for kind, _ in blocks)
    for kind, value in blocks:
        if kind == 'paragraph':
            assert escape(value) in html, f'HTML paragraph differs: {value[:90]}'

    assert not any(char in text + pdf_text for char in '\u2013\u2014\u2015')
    forbidden = ['.qeax', 'generated', 'clean-diagrams', 'Generált mellékletek']
    assert all(value not in pdf_text for value in forbidden)
    assert not re.search(r'\[(?:Kidolgozandó|Kiegészítendő|Tervezett rész|Pontosítandó):', text)
    assert all(term not in pdf_text for term in ['Kővári Bence', 'Diplomaterv Útmutató', '4.8.5.'])
    main_images = sum(kind == 'image' for kind, _ in blocks)
    images = {item[0] for page in pdf for item in page.get_images()}
    assert len(word.inline_shapes) == main_images + 2
    assert len(images) == main_images + 2
    for page in pdf:
        assert page.get_text().strip() or page.get_images(), 'Unexpected empty PDF page'
    for item in word.sections:
        assert abs(item.left_margin.cm - 2.5) < 0.01
        assert abs(item.right_margin.cm - 2.5) < 0.01
        assert abs(item.gutter.cm - 1) < 0.01
    assert word.styles['Normal'].font.size.pt == 12
    assert word.styles['Normal'].paragraph_format.line_spacing == 1.5
    assert len(word.sections) == 2
    assert not word.sections[0].footer.paragraphs[0].text.strip()
    assert len(word.tables) == sum(kind == 'table' for kind, _ in blocks)

    font_sizes = {'Heading 1': 18, 'Heading 2': 16, 'Heading 3': 14, UNNUMBERED: 18}
    for name, size in font_sizes.items():
        assert effective_font(word.styles[name], 'size').pt == size, name
        assert effective_font(word.styles[name], 'name') == 'Times New Roman', name
    for paragraph in exported:
        assert paragraph._p.find('./' + qn('w:pPr') + '/' + qn('w:numPr')) is None, paragraph.text
        for run in paragraph.runs:
            assert run.font.size is None or run.font.size.pt == font_sizes[paragraph.style.name], paragraph.text

    # Check the rendered font too; style definitions alone miss direct overrides.
    rendered = []
    for page in pdf:
        chars, sizes = [], []
        for block in page.get_text('dict')['blocks']:
            for line in block.get('lines', []):
                for span in line['spans']:
                    for char in normalized(span['text']):
                        chars.append(char)
                        sizes.append(span['size'])
        rendered.append((''.join(chars), sizes))
    heading_pages = {}
    for paragraph in exported:
        needle, expected = normalized(paragraph.text), font_sizes[paragraph.style.name]
        found = False
        for page_number, (contents, sizes) in enumerate(rendered, start=1):
            for match in re.finditer(re.escape(needle), contents):
                observed = sizes[match.start():match.end()]
                if observed and all(abs(size - expected) < 0.1 for size in observed):
                    found = True
                    heading_pages[paragraph.text] = page_number
                    break
            if found:
                break
        assert found, f'PDF heading size differs: {paragraph.text}, expected {expected} pt'

    pages_before_appendix = heading_pages['Függelékek'] - 1
    assert pages_before_appendix <= 50, f'{pages_before_appendix} pages before the appendix'
    technology_heading = '2.3. A technológiaválasztás indokai'
    technology_end = '2.4. Közös időalap és adatminőség'
    technology = section(text, technology_heading, technology_end)
    assert len(technology.split()) >= 330
    assert heading_pages[technology_heading] < heading_pages[technology_end]
    main_figures = sum(kind == 'image' for kind, _ in parse(text.split('## Függelékek', 1)[0]))

    requirement_text = section(text, '## 3. Követelményspecifikáció', '## 4. Rendszerterv')
    evaluation = section(text, '## 6. Tesztelés és értékelés', '## 7. Fejlesztési tapasztalatok')
    for prefix, count in [('F', 12), ('NF', 7)]:
        for index in range(1, count + 1):
            key = f'{prefix}{index:02}'
            assert f'| {key} |' in requirement_text, key
            assert key in evaluation or any(int(a) <= index <= int(b) for a, b in re.findall(r'(?<![A-Z])' + prefix + r'(\d+)-' + prefix + r'(\d+)', evaluation)), f'Missing validation mapping: {key}'
    main_design = section(text, '## 4. Rendszerterv', '## 6. Tesztelés és értékelés')
    assert 'FastF1' not in main_design and 'hibrid' not in main_design.lower()
    assert all(value not in main_design for value in ('17,601 s', '18,714 s', '50,583 s', '93,687 s'))
    assert '4.8.' not in text
    assert 'hibrid-adatforras.png' not in text
    assert 'HybridSource' not in text and 'Isolated F1 worker' not in text
    assert all(term not in text for term in ['MultiViewer', 'F1 Insights powered by AWS', 'FastAPI service'])
    history = section(text, '## 7. Fejlesztési tapasztalatok', '## 8. Összefoglalás')
    assert all(term in history for term in ['FastF1', 'OpenF1', 'hibrid', 'Companion', '2023-2025'])
    assert '93,687' not in text.split('## Függelékek')[0]
    model_path = DOCS / 'generated/PitWall-Insights-thesis-structure.qeax'
    with sqlite3.connect(model_path.resolve().as_uri() + '?mode=ro', uri=True) as model:
        retired = model.execute('select Name from t_object where Name like ? or Name like ?', ('%FastF1%', '%Hybrid%')).fetchall()
        assert not retired, f'Retired provider still in current UML model: {retired}'
        diagram_names = [row[0] for row in model.execute('select Name from t_diagram')]
        assert set(diagram_names) == {'On-demand telemetry workflow', 'Application architecture', 'OpenF1 access components', 'Core race data model', 'Telemetry preparation services', 'Final OpenF1 data pipeline'}, diagram_names
        names = {row[0] for row in model.execute('select Name from t_object')}
        assert {'PitWall API', 'OpenF1Client', 'OpenF1ResponseCache', 'OpenF1RequestLimiter'} <= names
        assert 'FastAPI service' not in names
        dependencies = set(model.execute('select a.Name, b.Name from t_connector c join t_object a on a.Object_ID=c.Start_Object_ID join t_object b on b.Object_ID=c.End_Object_ID'))
        assert ('PitWall API', 'Data preparation worker') not in dependencies
        assert ('Data preparation worker', 'PostgreSQL data and jobs') in dependencies

    net_parts, active = [], False
    for kind, value in blocks:
        if kind == 'heading' and value[1].startswith('1. '):
            active = True
        if kind == 'heading' and value[1] == 'Irodalomjegyzék':
            break
        if active:
            if kind == 'heading':
                net_parts.append(value[1])
            elif kind == 'paragraph' and not note(value):
                net_parts.append(value)
            elif kind == 'table':
                net_parts.extend(' '.join(row) for row in value)
    net = '\n'.join(net_parts)
    assert 50000 <= len(net) < 105000, len(net)
    current_path = DOCS / 'testing/openf1-current-validation.json'
    model_validation_path = DOCS / 'testing/race-estimation-validation.json'
    model_validation = json.loads(model_validation_path.read_text(encoding='utf-8'))
    assert model_validation['definitions'] == 75 and model_validation['new_panels'] == 15
    assert model_validation['backend']['passed'] == 140 and model_validation['backend']['failed'] == 0
    assert model_validation['frontend']['tests_passed'] == 21
    assert model_validation['browser']['count'] == 6 and model_validation['browser']['browser_errors'] == []
    current = json.loads(current_path.read_text(encoding='utf-8'))
    assert current['provider'] == 'openf1' and current['account_or_subscription_used'] is False
    assert current['job_status'] == 'completed' and current['repeat_ensure_ready'] is True
    assert f"{current['startup_seconds']:.3f}".replace('.', ',') in evaluation
    assert f"{current['telemetry_rows']:,}".replace(',', ' ') in evaluation
    browser_path = DOCS / 'testing/openf1-browser/results.json'
    browser = json.loads(browser_path.read_text(encoding='utf-8'))
    assert browser['real_openf1_import_and_replay'] is True and browser['external_account_requests'] == 0
    assert f"{browser['replay_startup_seconds']:.3f}".replace('.', ',') in evaluation
    assert browser['count'] == len(browser['checks']) and browser['browser_errors'] == []
    switch_path = DOCS / 'testing/openf1-switch-validation.json'
    switch = json.loads(switch_path.read_text(encoding='utf-8'))
    assert f"{switch['three_driver_browser_replay_seconds']:.3f}".replace('.', ',') in evaluation
    architecture_path = DOCS / 'testing/openf1-architecture-data-validation.json'
    architecture = json.loads(architecture_path.read_text(encoding='utf-8'))
    assert architecture['provider'] == 'openf1' and architecture['account_or_subscription_used'] is False
    assert architecture['job_status'] == 'completed' and architecture['repeat_ensure_ready'] is True
    assert architecture['disposable_schema_removed'] is True and architecture['telemetry_rows'] == 233940
    assert f"{architecture['startup_seconds']:.3f}".replace('.', ',') in evaluation
    strategy_dir = DOCS / 'testing/replay-strategy'
    crossover_timing = json.loads((strategy_dir / 'weather-crossover-timing.json').read_text(encoding='utf-8'))
    for check in crossover_timing['outlap_checks']:
        assert f"{check['evidence_before_outlap_end_s']:.3f}".replace('.', ',') in evaluation
    for field in ('lead_to_reported_stop_s', 'margin_to_estimated_earliest_pit_entry_s'):
        assert f"{crossover_timing['melbourne_later_switch'][field]:.3f}".replace('.', ',') in evaluation
    pit_backtest = json.loads((strategy_dir / 'pit-sector-backtest.json').read_text(encoding='utf-8'))
    for category in ('sc', 'vsc'):
        for field in ('model_mae_s', 'green_baseline_mae_s', 'pooled_baseline_mae_s'):
            assert f'{pit_backtest[category][field]:.3f}'.replace('.', ',') in evaluation
    facts = {}
    cases = {
        'replay-readiness-final.json': {'drivers': 20, 'rows_written': 1206220, 'startup_seconds': 93.687, 'preparation_seconds': 87.843},
        'analytics-benchmark-2026-10-18.json': {'definitions': 137, 'metric_results': 2417, 'first_request_seconds': 5.547},
        'analytics-cache-benchmark-2026-10-18.json': {'cached_request_seconds': 0.031},
        'strategy-api-benchmark-miami-2025.json': {'definitions': 67, 'first_request_seconds': 0.329, 'cached_request_seconds': 0.031, 'scenario_coefficients_are_synthetic': True},
    }
    for filename, expected in cases.items():
        path = DOCS / 'testing' / filename
        data = json.loads(path.read_text(encoding='utf-8'))
        for key, value in expected.items():
            assert data[key] == value, f'Historical measurement differs: {filename}/{key}'
        facts[filename] = {'sha256': sha256(path.read_bytes()).hexdigest(), 'verified_values': expected}

    previews = []
    for needle, label in [('A rendszer fő komponensei.', 'rendszerterv'), ('A visszajátszás közös órája', 'ora'), ('Az imolai futam visszajátszása', 'visszajatszas'), ('A stratégiai modell adatútja.', 'strategia'), ('A Strategy call panel', 'javaslat'), ('Mérési helyzet', 'meresek'), ('A technológiaválasztás indokai', 'technologia')]:
        indices = [i for i, page in enumerate(pdf) if normalized(needle) in normalized(page.get_text())]
        assert indices, needle
        index = indices[-1]
        path = OUTPUT / f'ellenorzes-{label}.png'
        pdf[index].get_pixmap(matrix=pymupdf.Matrix(1.3, 1.3)).save(path)
        previews.append({'label': label, 'page': index + 1, 'path': str(path)})
    report = {
        'checked_at': date.today().isoformat(), 'pages': len(pdf), 'embedded_images': len(images),
        'pages_before_appendix': pages_before_appendix, 'remaining_pages_to_50': 50 - pages_before_appendix,
        'appendix_pages': len(pdf) - pages_before_appendix, 'main_figures': main_figures,
        'appendix_figures': main_images - main_figures, 'numbered_chapters': len(chapters), 'maximum_heading_depth': 3,
        'technology_section_pages': [heading_pages[technology_heading], heading_pages[technology_end]],
        'headings_reviewed': len(headings), 'heading_fonts_points': font_sizes,
        'heading_sizes_verified_in_word_and_pdf': True,
        'source_sha256': sha256(SOURCE.read_bytes()).hexdigest(),
        'source_word_pdf_content_matches': True,
        'source_html_content_matches': True,
        'figure_captions_checked': True,
        'internal_render_references_absent': True, 'editorial_placeholders_absent_from_body': True,
        'functional_requirements': 12, 'nonfunctional_requirements': 7,
        'requirement_validation_mapping_checked': True,
        'source_decision_history_confined_to_experiences': True,
        'historical_measurements_confined_to_appendix': True,
        'current_uml_has_no_fastf1_or_hybrid_elements': True,
        'uml_diagrams': diagram_names,
        'net_characters_with_spaces': len(net),
        'net_characters_without_spaces': len(re.sub(r'\s', '', net)),
        'rubric_minimum_characters': 50000, 'rubric_minimum_currently_met': True,
        'template': {'filename': TEMPLATE.name, 'sha256': sha256(TEMPLATE.read_bytes()).hexdigest(), 'font_points': 12, 'line_spacing': 1.5, 'gutter_cm': 1, 'unsigned_declarations': True},
        'benchmark_facts': facts, 'replay_crossover_timing': crossover_timing, 'pit_sector_backtest': pit_backtest,
        'current_openf1': {'source_sha256': sha256(current_path.read_bytes()).hexdigest(), 'browser_sha256': sha256(browser_path.read_bytes()).hexdigest(), 'telemetry_rows': current['telemetry_rows'], 'startup_seconds': current['startup_seconds'], 'browser_startup_seconds': browser['replay_startup_seconds'], 'earlier_browser_startup_seconds': switch['three_driver_browser_replay_seconds'], 'rerun_during_editorial_revision': False},
        'architecture_openf1_validation': {'source_sha256': sha256(architecture_path.read_bytes()).hexdigest(), 'telemetry_rows': architecture['telemetry_rows'], 'startup_seconds': architecture['startup_seconds'], 'rerun_after_transport_refactor': True},
        'product_checks': {'backend_unittest_discover': model_validation['backend'], 'frontend_tests': model_validation['frontend'], 'race_insights_browser': model_validation['browser'], 'layout_builder_regression': model_validation['layout_builder_regression'], 'evidence_sha256': sha256(model_validation_path.read_bytes()).hexdigest(), 'physical_calibration': model_validation['physical_calibration']},
        'previews': previews,
    }
    (OUTPUT / 'ellenorzes.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: report[key] for key in ['pages', 'pages_before_appendix', 'remaining_pages_to_50', 'appendix_pages', 'main_figures', 'appendix_figures', 'technology_section_pages', 'headings_reviewed', 'net_characters_with_spaces', 'heading_sizes_verified_in_word_and_pdf', 'source_word_pdf_content_matches']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
