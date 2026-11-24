"""Validate and summarize error annotations without editing baseline artifacts."""

import argparse
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRIMARY_TAXONOMY = (
    'unsupported_inference', 'entity_mismatch', 'unsupported_definition',
    'scope_overgeneralization', 'false_premise_acceptance',
    'abstention_format_failure', 'annotation_disagreement', 'no_identified_failure',
)
UNSUPPORTED_ANSWER_FAILURES = frozenset(PRIMARY_TAXONOMY[:5])
SECONDARY_TAXONOMY = frozenset(PRIMARY_TAXONOMY[:-1])
FIELDS = {'example_id', 'primary_failure', 'secondary_failure', 'explanation'}


def read_jsonl(path):
    """Read JSON objects and report malformed input with a file/line reference."""
    records = []
    with Path(path).open(encoding='utf-8') as file:
        for number, line in enumerate(file, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f'{path}:{number}: invalid JSON') from exc
            if not isinstance(record, dict):
                raise ValueError(f'{path}:{number}: expected a JSON object')
            records.append(record)
    return records


def unique_ids(records, source):
    ids = set()
    for record in records:
        example_id = record.get('example_id')
        if not isinstance(example_id, str) or not example_id.strip():
            raise ValueError(f'{source}: invalid example_id')
        if example_id in ids:
            raise ValueError(f'{source}: duplicate ID {example_id}')
        ids.add(example_id)
    return ids


def load_annotations(annotations_path, predictions_path):
    """Require exactly one valid annotation per prediction; inputs are read-only.

    Sample size is determined by the supplied predictions so the same utility
    can summarize other runs. Repository regression tests pin this M2C run to
    20 records and its nine project-owner-approved classifications.
    """
    predictions = read_jsonl(predictions_path)
    records = read_jsonl(annotations_path)
    if not predictions:
        raise ValueError('Predictions are empty')
    prediction_ids = unique_ids(predictions, 'predictions')
    annotation_ids = unique_ids(records, 'annotations')
    if prediction_ids != annotation_ids:
        raise ValueError(
            f'Annotation IDs mismatch predictions: missing={sorted(prediction_ids - annotation_ids)}, '
            f'unknown={sorted(annotation_ids - prediction_ids)}'
        )
    for record in records:
        example_id = record['example_id']
        if set(record) != FIELDS:
            raise ValueError(f'{example_id}: expected fields {sorted(FIELDS)}')
        primary, secondary = record['primary_failure'], record['secondary_failure']
        if not isinstance(primary, str) or primary not in PRIMARY_TAXONOMY:
            raise ValueError(f'{example_id}: invalid primary classification')
        if secondary is not None:
            if not isinstance(secondary, str) or secondary not in SECONDARY_TAXONOMY:
                raise ValueError(f'{example_id}: invalid secondary classification')
            if primary == 'no_identified_failure' or secondary == primary:
                raise ValueError(f'{example_id}: inconsistent secondary classification')
        if not isinstance(record['explanation'], str) or not record['explanation'].strip():
            raise ValueError(f'{example_id}: explanation must be nonempty text')
    return records


def summarize(records):
    """Count validated primary labels once; secondary labels are descriptive only."""
    counts = Counter(record['primary_failure'] for record in records)
    return {
        'total': len(records),
        'primary_counts': {label: counts[label] for label in PRIMARY_TAXONOMY},
        'unsupported_answer_failures': sum(counts[label] for label in UNSUPPORTED_ANSWER_FAILURES),
        'abstention_format_failures': counts['abstention_format_failure'],
        'annotation_disagreements': counts['annotation_disagreement'],
        'no_identified_failure': counts['no_identified_failure'],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--annotations', type=Path,
                        default=ROOT / 'reports/error_analysis/dev_20_errors.jsonl')
    parser.add_argument('--predictions', type=Path,
                        default=ROOT / 'reports/baseline/dev_20_predictions.jsonl')
    args = parser.parse_args(argv)
    try:
        result = summarize(load_annotations(args.annotations, args.predictions))
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(f"Total examples analyzed: {result['total']}")
    print('Primary failure counts (secondary labels excluded):')
    for label, count in result['primary_counts'].items():
        print(f'  {label}: {count}')
    print(f"Unsupported-answer failures: {result['unsupported_answer_failures']}")
    print(f"Abstention-format failures: {result['abstention_format_failures']}")
    print(f"Annotation disagreements: {result['annotation_disagreements']}")
    print(f"Examples with no identified failure: {result['no_identified_failure']}")


if __name__ == '__main__':
    main()
