"""Tests-first contract for the pinned Lavi et al. development release."""
import copy
import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PREFIX = ('Given the following passage and question, answer the question.\n'
          ' First make sure if it can be answered by the passage.\n'
          '         If it cannot be answered based on the passage, reply "unanswerable" \n'
          '         Passage: ')
SEP = ' \n         Question: '
SUFFIX = ' \n         Answer: '
SENTINEL = 'The answer is not found in the document.'
SOURCE = 'data/abstain_aware_prompt/squad/answerable_val.json'


def source_row(context='Passage with\ninternal spacing.', question='What is given?', answer='Passage'):
    return {'instruction': PREFIX + context + SEP + question + SUFFIX,
            'gt_answer': answer, 'category': None}


def test_extraction_exact_reference_and_input_preservation():
    from src.data.adapters.lavi import adapt_record
    row = source_row(answer='  Passage  ')
    before = copy.deepcopy(row)
    result = adapt_record(row, SOURCE, 0)
    assert result.context == 'Passage with\ninternal spacing.'
    assert result.question == 'What is given?'
    assert result.answer == '  Passage  '
    assert result.answerable and result.category == 'answerable'
    assert result.model_dump() == adapt_record(row, SOURCE, 0).model_dump()
    assert row == before
    assert PREFIX not in result.context and 'Answer:' not in result.context
    assert result.source_id.startswith('lavi2026:passage_sha256:')


def test_unanswerable_and_position_ids_preserve_duplicate_records():
    from src.data.adapters.lavi import adapt_record
    row = source_row(answer=SENTINEL)
    path = SOURCE.replace('answerable_val', 'unanswerable_val')
    a, b = [adapt_record(row, path, i) for i in [0, 1]]
    assert a.id != b.id and a.source_id == b.source_id
    assert a.answer == SENTINEL and not a.answerable
    assert a.category == 'unanswerable'


@pytest.mark.parametrize('fault', ['prefix', 'suffix', 'separator', 'ambiguous', 'empty_context',
                                   'empty_question', 'missing_instruction', 'missing_answer',
                                   'answer_type', 'empty_answer', 'label', 'path', 'index'])
def test_unreliable_parse_or_label_is_rejected(fault):
    from src.data.adapters.lavi import adapt_record
    row, path, index = source_row(), SOURCE, 0
    if fault == 'prefix': row['instruction'] = 'Other prompt ' + row['instruction']
    elif fault == 'suffix': row['instruction'] += 'generated answer'
    elif fault == 'separator': row['instruction'] = row['instruction'].replace(SEP, '\nQuestion:')
    elif fault == 'ambiguous': row['instruction'] = row['instruction'].replace(SEP, SEP + 'nested' + SEP)
    elif fault == 'empty_context': row = source_row(context=' ')
    elif fault == 'empty_question': row = source_row(question=' ')
    elif fault == 'missing_instruction': del row['instruction']
    elif fault == 'missing_answer': del row['gt_answer']
    elif fault == 'answer_type': row['gt_answer'] = ['Passage']
    elif fault == 'empty_answer': row['gt_answer'] = ''
    elif fault == 'label': row['gt_answer'] = SENTINEL
    elif fault == 'path': path = SOURCE.replace('_val', '_test')
    else: index = -1
    with pytest.raises(ValueError): adapt_record(row, path, index)


def test_false_label_requires_exact_source_sentinel():
    from src.data.adapters.lavi import adapt_record
    with pytest.raises(ValueError, match='gt_answer'):
        adapt_record(source_row(), SOURCE.replace('answerable_val', 'unanswerable_val'), 0)


def test_overlap_audit_detects_normalized_matches_and_conflicting_labels():
    from src.data.adapters.lavi import adapt_record
    from src.data.import_lavi import audit_collections
    a = adapt_record(source_row(context='A\nB', question='Question?'), SOURCE, 0)
    b = adapt_record(source_row(context='a b', question=' QUESTION? ', answer=SENTINEL),
                     SOURCE.replace('answerable_val', 'unanswerable_val'), 0)
    duplicate = a.model_copy(update={'id': 'duplicate'})
    audit = audit_collections({'import_a': [a, duplicate], 'heldout': [b]})
    assert audit['exact_record']['within']['import_a']['extra_records'] == 1
    match = audit['normalized_context_question']['across'][0]
    assert (match['left'], match['right']) == ('heldout', 'import_a')
    assert (match['left_records'], match['right_records']) == (1, 2)
    assert audit['normalized_context']['across'][0]['right_records'] == 2
    assert len(audit['label_conflicts']) == 1
    assert audit['exact_context_question']['across'] == []


@pytest.fixture
def ingestion_case(tmp_path, monkeypatch):
    from src.data import import_lavi as ingest
    from src.data.build_eval import build_dataset
    source_dir = tmp_path / 'sources'
    specs = {}
    for dataset in ['squad', 'repliqa']:
        for category in ['answerable', 'unanswerable']:
            path = f'data/abstain_aware_prompt/{dataset}/{category}_val.json'
            rows = [source_row(context=f'{dataset} {category} {i}',
                               answer='reference' if category == 'answerable' else SENTINEL)
                    for i in range(2)]
            raw = json.dumps(rows).encode()
            p = source_dir / path
            p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(raw)
            specs[path] = {'sha256': hashlib.sha256(raw).hexdigest(), 'git_blob_sha1':
                           hashlib.sha1(f'blob {len(raw)}\0'.encode()+raw).hexdigest(), 'count': 2}
    monkeypatch.setattr(ingest, 'SOURCE_FILES', specs)
    # Build a tiny verified existing benchmark, without loading the network.
    from src.data import build_eval
    raw_rows = [{'id': f'{i}_{j}', 'title': str(i), 'context': f'Existing {i}',
                 'question': 'Question?', 'answers': {'text': ['Existing'] if j == 0 else [], 'answer_start': [0] if j == 0 else []}}
                for i in range(4) for j in range(2)]
    monkeypatch.setattr(build_eval, 'load_dataset', lambda *a, **k: raw_rows)
    existing = tmp_path / 'existing'
    build_dataset(existing, per_category=1, revision='a'*40)
    return source_dir, existing, tmp_path / 'output'


def test_ingestion_determinism_provenance_and_no_modification(ingestion_case, tmp_path):
    from src.data.import_lavi import ingest, verify
    source, existing, out = ingestion_case
    before = {p: p.read_bytes() for p in existing.iterdir()}
    first = ingest(source, out, existing)
    second = ingest(source, tmp_path / 'repeat', existing)
    assert first == second
    for p in out.iterdir(): assert p.read_bytes() == (tmp_path / 'repeat' / p.name).read_bytes()
    assert all(p.read_bytes() == data for p, data in before.items())
    assert verify(source, out, existing) == first
    assert first['datasets']['squad']['count'] == 4
    assert first['datasets']['squad']['categories'] == {'answerable': 2, 'unanswerable': 2}
    assert len(first['source_files']) == 4
    provenance = [json.loads(l) for l in (out/'source_records.jsonl').read_text().splitlines()]
    assert len(provenance) == 8 and provenance[0]['extra_fields'] == {'category': None}
    with pytest.raises(FileExistsError): ingest(source, out, existing)


@pytest.mark.parametrize('fault', ['checksum', 'count', 'existing', 'output'])
def test_corrupt_source_or_output_fails(ingestion_case, fault, monkeypatch):
    from src.data import import_lavi as mod
    source, existing, out = ingestion_case
    if fault == 'output':
        mod.ingest(source, out, existing)
        p = out/'squad_dev.jsonl'; p.write_bytes(p.read_bytes()+b'\n')
        with pytest.raises(ValueError): mod.verify(source, out, existing)
        return
    if fault == 'checksum':
        p = source/SOURCE; p.write_bytes(p.read_bytes()+b'\n')
    elif fault == 'count': mod.SOURCE_FILES[SOURCE]['count'] = 99
    else:
        p = existing/'squad_test.jsonl'; p.write_bytes(p.read_bytes()+b'\n')
    with pytest.raises(ValueError): mod.ingest(source, out, existing)
    assert not out.exists()


def test_real_import_counts_schema_unique_ids_and_hashes():
    from scripts.validate_dataset import validate_dataset
    from src.data.import_lavi import SOURCE_FILES, SOURCE_REVISION
    root = ROOT/'data/eval/external/lavi2026_v1'
    m = json.loads((root/'manifest.json').read_text())
    assert m['source_revision'] == SOURCE_REVISION
    all_ids = []
    for dataset in ['squad', 'repliqa']:
        records = validate_dataset(str(root/f'{dataset}_dev.jsonl'))
        assert len(records) == 800
        assert sum(r.answerable for r in records) == 400
        all_ids.extend(r.id for r in records)
    assert len(set(all_ids)) == 1600
    for filename, sha in m['output_sha256'].items():
        assert hashlib.sha256((root/filename).read_bytes()).hexdigest() == sha
    for path, spec in SOURCE_FILES.items():
        assert m['source_files'][path]['sha256'] == spec['sha256']
        assert m['source_files'][path]['count'] == 400


def test_ingestion_reports_duplicates_without_dropping_them(ingestion_case):
    from src.data import import_lavi as mod
    source, existing, out = ingestion_case
    path = source/SOURCE
    rows = json.loads(path.read_text())
    rows[1] = rows[0]
    raw = json.dumps(rows).encode()
    path.write_bytes(raw)
    mod.SOURCE_FILES[SOURCE].update(
        sha256=hashlib.sha256(raw).hexdigest(),
        git_blob_sha1=hashlib.sha1(f'blob {len(raw)}\0'.encode()+raw).hexdigest())
    manifest = mod.ingest(source, out, existing)
    assert manifest['datasets']['squad']['count'] == 4
    audit = json.loads((out/'overlap_audit.json').read_text())
    assert audit['exact_record']['within']['squad/answerable_val']['extra_records'] == 1
    records = [json.loads(line) for line in (out/'squad_dev.jsonl').read_text().splitlines()]
    assert records[0]['context'] == records[1]['context']
    assert records[0]['id'] != records[1]['id']


def test_normalization_handles_unicode_but_keeps_punctuation():
    from src.data.import_lavi import normalize
    assert normalize('ＦＯＯ\u00a0Bar\n') == normalize('foo bar')
    assert normalize('foo?') != normalize('foo')


def test_download_only_locked_files_and_reject_bad_cache(ingestion_case, monkeypatch):
    from types import SimpleNamespace
    from src.data import import_lavi as mod
    source, _, out = ingestion_case
    calls = []

    def fetch(args, **kwargs):
        calls.append(args[-1])
        path = next(p for p in mod.SOURCE_FILES if mod.source_url(p) == args[-1])
        return SimpleNamespace(stdout=(source/path).read_bytes())

    monkeypatch.setattr(mod.subprocess, 'run', fetch)
    mod.download_sources(out)
    assert calls == [mod.source_url(p) for p in mod.SOURCE_FILES]
    mod.download_sources(out)
    assert len(calls) == 4  # Valid cached files are reused.
    (out/SOURCE).write_bytes(b'corrupt')
    with pytest.raises(ValueError, match='checksum'):
        mod.download_sources(out)
    assert (out/SOURCE).read_bytes() == b'corrupt'  # Never silently replace a bad cache.
