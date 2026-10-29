"""Archive completed detector runs; never infer unreported scores."""

from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil


ROOT = Path(__file__).resolve().parents[2]
GENERATED = ROOT / 'docs/generated'
SOURCE = Path(os.environ['TEMP']) / 'pitwall-detector-check'
FINAL_VERSION = 'race-analysis-final-2026-10-08'


def normalize(text):
    return re.sub(r'\s+', '', text)


def archive(service, version):
    prefix = '' if service == 'aidetego' else service + '-'
    original = SOURCE / f'{prefix}{version}-result.json'
    result = json.loads(original.read_text(encoding='utf-8'))
    basename = f'feladatkiiras-{service}-{version}'
    shutil.copyfile(original, GENERATED / f'{basename}.json')
    shutil.copyfile(original.with_suffix('.png'), GENERATED / f'{basename}.png')
    entry = {
        'service': {'zerogpt': 'ZeroGPT', 'smodin': 'Smodin', 'aidetego': 'AIDetego'}[service],
        'version': version,
        'date': '2026-10-08',
        'input_characters': len(result['input']),
        'input_sha256': sha256(result['input'].encode('utf-8')).hexdigest(),
        'full_text_submitted': True,
        'screenshot': f'{basename}.png',
        'raw_result': f'{basename}.json',
    }
    if service in ('zerogpt', 'smodin'):
        response = next(
            r for r in result['responses']
            if '/detect/detectText' in r['url'] or '/ai-detection/v2/single' in r['url']
        )
        value = json.loads(response['body'])
        entry['http_status'] = response['status']
        if service == 'zerogpt':
            data = value['data']
            entry['ai_percentage'] = data['fakePercentage']
            entry['reported_words'] = data['textWords']
            entry['detected_language'] = data['detected_language']
            entry['full_text_verified'] = normalize(data['originalParagraph']) == normalize(result['input'])
            assert entry['full_text_verified'], 'ZeroGPT did not return the complete submitted text'
        else:
            score = re.search(r'MI által generált\s+(\d+(?:[.,]\d+)?)%', result['resultText'])
            assert score, 'Missing Smodin UI score'
            entry['ai_percentage'] = float(score[1].replace(',', '.'))
            entry['api_ai_percentage'] = value['completelyGeneratedProbability']
            entry['analyzed_characters'] = len(value['text'])
            entry['full_text_verified'] = normalize(value['text']) == normalize(result['input'])
            entry['note'] = 'The UI and API scores differ. The API returns analysis for a prefix only.'
    else:
        score = re.search(r'(\d+(?:\.\d+)?)%\s+AI Probability', result['resultText'])
        assert score, 'Missing AIDetego score'
        entry['ai_percentage'] = float(score[1])
        entry['detected_language'] = 'ES' if '🇪🇸 ES' in result['resultText'] else None
        entry['profile'] = result['profile']
        entry['note'] = 'Hungarian input was identified as Spanish (ES). UI-only result.'
    return entry


def main():
    audit_path = GENERATED / 'feladatkiiras-ai-meresek.json'
    audit = json.loads(audit_path.read_text(encoding='utf-8'))
    new_results = [
        archive(service, version)
        for version in ('race-analysis-2026-10-08', FINAL_VERSION)
        for service in ('zerogpt', 'smodin', 'aidetego')
    ]
    # Keep Windows CRLF newlines: the browser scanner reads the exact bytes.
    final_body = (ROOT / 'docs/PitWall-Insights-feladatkiiras-szoveg.txt').read_bytes().decode(
        'utf-8'
    ).split('FELADATKIÍRÁS SZÖVEGE', 1)[1].strip()
    body_hash = sha256(final_body.encode('utf-8')).hexdigest()
    for result in new_results:
        if result['version'] == FINAL_VERSION:
            assert result['input_sha256'] == body_hash, 'Scanned text differs from the final assignment'
    new_keys = {(r['service'], r['version']) for r in new_results}
    audit['results'] = [
        r for r in audit['results'] if (r['service'], r['version']) not in new_keys
    ] + new_results
    audit['historical_results_date'] = '2026-10-06'
    audit['date'] = '2026-10-08'
    audit['updated_date'] = '2026-10-08'
    audit['current_version'] = FINAL_VERSION
    audit['current_body_sha256'] = body_hash
    audit['last_scanned_body_sha256'] = body_hash
    audit['last_scanned_version'] = FINAL_VERSION
    audit['current_version_scan_status'] = 'tested'
    audit['current_version_note'] = 'All three final runs used the current assignment body. Only ZeroGPT returned a verified full-text analysis.'
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    for result in new_results:
        if result['version'] == FINAL_VERSION:
            print(result['service'], result['ai_percentage'])
    print('Final scanned text matches the current assignment source.')


if __name__ == '__main__':
    main()
