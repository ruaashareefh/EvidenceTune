"""Pinned development-only ingestion and overlap audit; no inference or training."""

import argparse
import hashlib
import itertools
import json
import subprocess
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from src.data.adapters.lavi import SOURCE_REVISION, adapt_record
from src.data.build_eval import load_verified_baseline, sha256_file

REPOSITORY = 'https://github.com/MaorLavi/unanswerability-directions'
PAPER = 'https://aclanthology.org/2026.eacl-long.29/'
POLICY = 'lavi-abstain-aware-val-v1'
SOURCE_FILES = {
    'data/abstain_aware_prompt/squad/answerable_val.json': {
        'sha256': 'ca46680de3cfd54a0d8aac849a0ef6de9b29c6cecae4304b56660562f823ec5f',
        'git_blob_sha1': 'c2a715b08795aaba98537ba5f180c11e0bc63bda', 'count': 400},
    'data/abstain_aware_prompt/squad/unanswerable_val.json': {
        'sha256': '99365058dcbb202639208f73480e813c981158d3180192c4510be70f7371d6bd',
        'git_blob_sha1': '66bf609f195bafc04b293b16ac96afc4cc972556', 'count': 400},
    'data/abstain_aware_prompt/repliqa/answerable_val.json': {
        'sha256': '62a6a8fde99fe5055f54ae00d22e032807280c4b67150816ac3e8dc31e2121a9',
        'git_blob_sha1': '6b17140974cec507113e5e2f3cda1981926b194d', 'count': 400},
    'data/abstain_aware_prompt/repliqa/unanswerable_val.json': {
        'sha256': 'd5066d233747513de7a4483d74c9cb6ab79a83c12f76757c311996b71e5b2408',
        'git_blob_sha1': 'b43e8f92a82cabfa4eac5f61521376af4fa7abab', 'count': 400},
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode('utf-8')


def jsonl_bytes(rows):
    return ''.join(json.dumps(r, ensure_ascii=False, sort_keys=True) + '\n' for r in rows).encode('utf-8')


def normalize(text):
    """Conservative match key: NFKC, casefold, collapse all whitespace; no stemming."""
    return ' '.join(unicodedata.normalize('NFKC', text).casefold().split())


def audit_collections(collections):
    """Report all repeated keys without altering source rows; expose IDs, not test text."""
    keys = {
        'exact_record': lambda r: (r.context, r.question, r.answer, r.category),
        'exact_context_question': lambda r: (r.context, r.question),
        'normalized_context_question': lambda r: (normalize(r.context), normalize(r.question)),
        'exact_context': lambda r: (r.context,),
        'normalized_context': lambda r: (normalize(r.context),),
    }
    result = {}
    conflicts = []
    for metric, key_fn in keys.items():
        groups = defaultdict(list)
        for name, records in sorted(collections.items()):
            for record in records:
                groups[key_fn(record)].append((name, record))
        details, within, across = [], {}, {}
        for key, members in sorted(groups.items()):
            if len(members) < 2:
                continue
            by_collection = defaultdict(list)
            for name, row in members:
                by_collection[name].append(row.id)
            details.append({'match_sha256': sha(json_bytes(key)), 'members': dict(by_collection)})
            for name, ids in by_collection.items():
                if len(ids) > 1:
                    counts = within.setdefault(name, {'groups': 0, 'records': 0, 'extra_records': 0})
                    counts['groups'] += 1; counts['records'] += len(ids); counts['extra_records'] += len(ids)-1
            for left, right in itertools.combinations(sorted(by_collection), 2):
                counts = across.setdefault((left, right), {'left': left, 'right': right,
                    'matching_groups': 0, 'left_records': 0, 'right_records': 0, 'matching_pairs': 0})
                a, b = len(by_collection[left]), len(by_collection[right])
                counts['matching_groups'] += 1; counts['left_records'] += a; counts['right_records'] += b
                counts['matching_pairs'] += a*b
            if metric == 'normalized_context_question' and len({r.answerable for _, r in members}) > 1:
                conflicts.append({'match_sha256': sha(json_bytes(key)), 'records': [
                    {'collection': name, 'id': r.id, 'answerable': r.answerable} for name, r in members]})
        result[metric] = {'within': within, 'across': [across[k] for k in sorted(across)], 'groups': details}
    result['label_conflicts'] = conflicts
    result['normalization'] = 'Unicode NFKC + casefold + whitespace collapse; punctuation retained'
    result['scope'] = 'Four published val label partitions plus existing curated_v4 dev/test; no authors train/val2/test inspected'
    return result


def source_url(path):
    return f'https://raw.githubusercontent.com/MaorLavi/unanswerability-directions/{SOURCE_REVISION}/{path}'


def check_source(raw, spec, path):
    if sha(raw) != spec['sha256'] or hashlib.sha1(f'blob {len(raw)}\0'.encode()+raw).hexdigest() != spec['git_blob_sha1']:
        raise ValueError(f'Source checksum mismatch: {path}')


def download_sources(source_dir):
    """Fetch only four locked validation files; existing cache bytes must verify."""
    for path, spec in SOURCE_FILES.items():
        target = Path(source_dir)/path
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            result = subprocess.run(['curl', '--fail', '--location', '--max-time', '60',
                                     source_url(path)], check=True, capture_output=True)
            check_source(result.stdout, spec, path)
            with target.open('xb') as file: file.write(result.stdout)
        check_source(target.read_bytes(), spec, path)


def prepare(source_dir, existing_dir):
    source_dir, existing_dir = Path(source_dir), Path(existing_dir)
    _, dev, test = load_verified_baseline(existing_dir)
    existing_hashes = {name: sha256_file(existing_dir/name)
                       for name in ['squad_dev.jsonl', 'squad_test.jsonl', 'squad_manifest.json']}
    collections = {'evidencetune_dev': dev, 'evidencetune_test': test}
    datasets = defaultdict(list)
    source_metadata, provenance, issues = {}, [], []
    for path, spec in SOURCE_FILES.items():
        raw = (source_dir/path).read_bytes()
        check_source(raw, spec, path)
        rows = json.loads(raw)
        if not isinstance(rows, list) or len(rows) != spec['count']:
            raise ValueError(f'Unexpected source record count: {path}')
        dataset = Path(path).parent.name
        converted = [adapt_record(row, path, i) for i, row in enumerate(rows)]
        collections[f'{dataset}/{Path(path).stem}'] = converted
        datasets[dataset].extend(converted)
        source_metadata[path] = {**spec, 'url': source_url(path), 'bytes': len(raw),
            'published_split': 'val', 'label_partition': Path(path).stem.removesuffix('_val'),
            'field_sets': dict(Counter(','.join(sorted(row)) for row in rows))}
        for i, (row, converted_row) in enumerate(zip(rows, converted, strict=True)):
            provenance.append({'example_id': converted_row.id, 'source_file': path,
                'source_row_index': i, 'source_record_sha256': sha(json_bytes(row)),
                'extra_fields': {k: v for k, v in row.items() if k not in {'instruction', 'gt_answer'}}})
            if converted_row.answerable and normalize(converted_row.answer) not in normalize(converted_row.context):
                issues.append({'example_id': converted_row.id,
                               'issue': 'reference_not_normalized_substring',
                               'interpretation': 'screening flag only; paraphrased references may be valid'})
    all_ids = [r.id for rows in datasets.values() for r in rows]
    if len(all_ids) != len(set(all_ids)):
        raise ValueError('Duplicate generated example IDs')
    artifacts = {f'{dataset}_dev.jsonl': jsonl_bytes([r.model_dump() for r in rows]) for dataset, rows in datasets.items()}
    audit = audit_collections(collections)
    audit['annotation_screening'] = issues
    artifacts['overlap_audit.json'] = json_bytes(audit)
    artifacts['source_records.jsonl'] = jsonl_bytes(provenance)
    manifest = {
        'format_version': 1, 'adapter_policy': POLICY, 'source_repository': REPOSITORY,
        'source_revision': SOURCE_REVISION, 'paper': PAPER,
        'source_files': source_metadata, 'datasets': {
            dataset: {'count': len(rows), 'categories': dict(Counter(r.category for r in rows)),
                      'output': f'{dataset}_dev.jsonl', 'source_split': 'val',
                      'review_status': 'source_labels_preserved_not_manually_audited'}
            for dataset, rows in datasets.items()},
        'source_id_policy': 'SHA256 of exact extracted passage, not an article/document identifier',
        'example_id_policy': 'release SHA prefix + dataset + val + filename label + zero-based row index',
        'ordering': 'answerable_val source order followed by unanswerable_val source order, per dataset',
        'reference_policy': 'gt_answer preserved verbatim, including source unanswerable sentinel',
        'existing_benchmark': {'version': existing_dir.name, 'sha256': existing_hashes},
        'limitations': ['No original row IDs, article IDs, or document IDs in released rows',
                       'Shared passages detectable; full document-level isolation cannot be certified',
                       'Authors train/val2/test splits not retrieved; cross-split isolation against them unverified',
                       'No deduplication, filtering, relabeling, or split reassignment performed'],
        'output_sha256': {name: sha(data) for name, data in artifacts.items()},
    }
    artifacts['manifest.json'] = json_bytes(manifest)
    return manifest, artifacts


def ingest(source_dir, output_dir, existing_dir):
    output_dir = Path(output_dir)
    if output_dir.exists(): raise FileExistsError(f'Output already exists: {output_dir}')
    manifest, artifacts = prepare(source_dir, existing_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    for name, raw in artifacts.items():
        with (output_dir/name).open('xb') as file: file.write(raw)
    return manifest


def verify(source_dir, output_dir, existing_dir):
    manifest, artifacts = prepare(source_dir, existing_dir)
    for name, expected in artifacts.items():
        if (Path(output_dir)/name).read_bytes() != expected:
            raise ValueError(f'Imported artifact mismatch: {name}')
    return manifest


def main():
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, default=root/'data/eval/external/lavi2026_v1')
    parser.add_argument('--existing-dir', type=Path, default=root/'data/eval/curated_v4')
    parser.add_argument('--download', action='store_true')
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    if args.download: download_sources(args.source_dir)
    operation = verify if args.verify else ingest
    manifest = operation(args.source_dir, args.output_dir, args.existing_dir)
    for name, item in manifest['datasets'].items():
        print(f"{name}: {item['count']} records, {item['categories']}")
    print('Verified' if args.verify else 'Imported', args.output_dir)


if __name__ == '__main__':
    main()
