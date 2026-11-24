"""M2C approved classifications and read-only summary contract."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ERRORS = ROOT / 'reports/error_analysis/dev_20_errors.jsonl'
PREDICTIONS = ROOT / 'reports/baseline/dev_20_predictions.jsonl'
GOLD = ROOT / 'data/eval/curated_v4/squad_dev.jsonl'
APPROVED = {
    '5a66797c846392001a1e1c49': ('unsupported_inference', None),
    '5ad031ef77cf76001a686df6': ('entity_mismatch', 'unsupported_inference'),
    '5a5808ef770dc0001aeeff67': ('unsupported_definition', 'unsupported_inference'),
    '5ad0206677cf76001a686afd': ('scope_overgeneralization', 'unsupported_inference'),
    '5a23565482b03a001a4aa78f': ('scope_overgeneralization', 'unsupported_inference'),
    '5a550e6f134fea001a0e1880': ('unsupported_definition', 'unsupported_inference'),
    '5a581597770dc0001aeeffe4': ('annotation_disagreement', None),
    '5a2358cc82b03a001a4aa797': ('abstention_format_failure', None),
    '5acf9d3477cf76001a685516': ('false_premise_acceptance', 'unsupported_inference'),
}
COUNTS = {
    'unsupported_inference': 1, 'entity_mismatch': 1,
    'unsupported_definition': 2, 'scope_overgeneralization': 2,
    'false_premise_acceptance': 1, 'abstention_format_failure': 1,
    'annotation_disagreement': 1, 'no_identified_failure': 11,
}
# Frozen M2B inputs, captured before M2C writes. These are not regenerated.
INPUT_HASHES = {
    'data/eval/curated_v4/squad_dev.jsonl': 'a2b5fc8aa23cf6ca2738f482b993bf4c6626bed5f6adc5dd03461bfe4edb99b5',
    'reports/baseline/dev_20_predictions.jsonl': '05226110ead008ec23c8f540e0ad10a2f3d88f731309576797d25e84cdaf7c73',
    'reports/baseline/dev_20_reviews.jsonl': '6b9c60bbb4bb83412425346a7f43ad06242c9b9f5e647484bc8ff3c5a41216ca',
    'src/evaluation/metrics.py': '88c76dede90cb95aa35d20aded31ba9763fe4a9e901e996fa8f7ddee40b6b087',
}


def read(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_exact_approved_classifications_and_complete_id_coverage():
    from scripts.summarize_error_analysis import load_annotations
    records = load_annotations(ERRORS, PREDICTIONS)
    predictions = read(PREDICTIONS)
    assert len(records) == len(predictions) == 20
    ids = [r['example_id'] for r in records]
    assert len(set(ids)) == 20
    assert ids == [p['example_id'] for p in predictions]
    assert set(ids) == {r['id'] for r in read(GOLD)}
    for record in records:
        expected = APPROVED.get(record['example_id'].removeprefix('squad_v2:'),
                                ('no_identified_failure', None))
        assert (record['primary_failure'], record['secondary_failure']) == expected
        assert record['explanation'].strip()


def test_summary_counts_do_not_double_count_secondary_labels():
    from scripts.summarize_error_analysis import load_annotations, summarize
    summary = summarize(load_annotations(ERRORS, PREDICTIONS))
    assert summary == {
        'total': 20, 'primary_counts': COUNTS,
        'unsupported_answer_failures': 7, 'abstention_format_failures': 1,
        'annotation_disagreements': 1, 'no_identified_failure': 11,
    }
    assert sum(summary['primary_counts'].values()) == 20


def test_gold_and_prediction_alignment_is_preserved():
    gold = {r['id']: r for r in read(GOLD)}
    for p in read(PREDICTIONS):
        r = gold[p['example_id']]
        assert p['gold_answerable'] == r['answerable']
        assert p['reference_answer'] == r['answer']
        assert p['question'] == r['question']
        assert p['context'] == r['context']
    assert gold['squad_v2:5a581597770dc0001aeeffe4']['answerable'] is False


@pytest.mark.parametrize('name,expected', INPUT_HASHES.items())
def test_historical_inputs_match_frozen_m2b_hashes(name, expected):
    assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected


@pytest.fixture
def tiny_files(tmp_path):
    predictions = tmp_path / 'predictions.jsonl'
    annotations = tmp_path / 'errors.jsonl'
    predictions.write_text(json.dumps({'example_id': 'a', 'gold_answerable': False,
                                       'prediction': 'Preserve this original output'}) + '\n')
    row = {'example_id': 'a', 'primary_failure': 'unsupported_definition',
           'secondary_failure': 'unsupported_inference', 'explanation': 'Definition not supplied.'}
    annotations.write_text(json.dumps(row) + '\n')
    return predictions, annotations, row


@pytest.mark.parametrize('fault', [
    'duplicate', 'missing', 'unknown_id', 'primary', 'secondary', 'empty_explanation',
    'nonstring_explanation', 'missing_field', 'extra_field', 'secondary_without_primary',
    'secondary_same_as_primary', 'duplicate_predictions', 'invalid_prediction_id',
    'invalid_json', 'not_object', 'empty_predictions',
])
def test_invalid_annotations_fail_clearly(tiny_files, fault):
    from scripts.summarize_error_analysis import load_annotations
    predictions, annotations, row = tiny_files
    if fault == 'duplicate':
        annotations.write_text((json.dumps(row) + '\n') * 2)
    elif fault == 'missing':
        annotations.write_text('')
    elif fault == 'duplicate_predictions':
        predictions.write_text(predictions.read_text() * 2)
    elif fault == 'invalid_prediction_id':
        predictions.write_text('{"example_id": null}\n')
    elif fault == 'empty_predictions':
        predictions.write_text('')
    elif fault == 'invalid_json':
        annotations.write_text('{broken}\n')
    elif fault == 'not_object':
        annotations.write_text('[]\n')
    else:
        if fault == 'unknown_id': row['example_id'] = 'unknown'
        elif fault == 'primary': row['primary_failure'] = 'hallucination'
        elif fault == 'secondary': row['secondary_failure'] = 'invalid'
        elif fault == 'empty_explanation': row['explanation'] = ' '
        elif fault == 'nonstring_explanation': row['explanation'] = 123
        elif fault == 'missing_field': del row['secondary_failure']
        elif fault == 'extra_field': row['gold_answerable'] = True
        elif fault == 'secondary_without_primary': row['primary_failure'] = 'no_identified_failure'
        elif fault == 'secondary_same_as_primary': row['secondary_failure'] = row['primary_failure']
        annotations.write_text(json.dumps(row) + '\n')
    with pytest.raises(ValueError):
        load_annotations(annotations, predictions)


def test_cli_custom_paths_is_read_only_and_reusable(tiny_files, tmp_path):
    predictions, annotations, _ = tiny_files
    originals = {p: p.read_bytes() for p in (predictions, annotations)}
    result = subprocess.run([sys.executable, str(ROOT / 'scripts/summarize_error_analysis.py'),
                             '--annotations', str(annotations), '--predictions', str(predictions)],
                            cwd=tmp_path, text=True, capture_output=True, check=True)
    assert 'Total examples analyzed: 1' in result.stdout
    assert 'Unsupported-answer failures: 1' in result.stdout
    assert 'unsupported_inference: 0' in result.stdout
    assert all(p.read_bytes() == contents for p, contents in originals.items())


def test_cli_default_summary_preserves_original_inputs():
    paths = [ROOT / p for p in INPUT_HASHES]
    before = {p: p.read_bytes() for p in paths}
    result = subprocess.run([sys.executable, '-m', 'scripts.summarize_error_analysis'],
                            cwd=ROOT, text=True, capture_output=True, check=True)
    for line in ['Total examples analyzed: 20', 'Unsupported-answer failures: 7',
                 'Abstention-format failures: 1', 'Annotation disagreements: 1',
                 'Examples with no identified failure: 11']:
        assert line in result.stdout
    assert all(p.read_bytes() == contents for p, contents in before.items())


def test_cli_invalid_input_returns_failure(tiny_files):
    predictions, annotations, _ = tiny_files
    annotations.write_text('')
    result = subprocess.run([sys.executable, str(ROOT / 'scripts/summarize_error_analysis.py'),
                             '--annotations', str(annotations), '--predictions', str(predictions)],
                            text=True, capture_output=True)
    assert result.returncode != 0
    assert 'error:' in result.stderr
    assert 'Total examples analyzed' not in result.stdout
