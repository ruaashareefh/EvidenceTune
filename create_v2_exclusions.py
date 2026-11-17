"""Create the project-owner-approved cumulative EvidenceTune v2 exclusions."""

import json
from collections import Counter
from pathlib import Path

original = Path('data/curation/squad_exclusions.json')
parent = Path('data/eval/curated_v1/squad_dev.jsonl')
output = Path('data/curation/squad_exclusions_v2.json')

new_exclusions = {
    'squad_v2:5ad277d3d7d075001a429549': 'Ambiguous spatial-spin correlation question; abstention target unreliable',
    'squad_v2:5a25f6a3c93d92001a400368': 'Ambiguous salary survey question',
    'squad_v2:5ad40358604f3c001a3ffd7e': 'False premise: three customaries rather than two',
    'squad_v2:5acf9a5277cf76001a685420': 'False premise: Woods Hole rather than Chicago campus',
    'squad_v2:5a550c52134fea001a0e1858': 'Potentially answerable connection-oriented transmission question',
    'squad_v2:5ad0301577cf76001a686db8': 'False premise: three forms rather than two',
}

challenge_candidates = {
    'squad_v2:5ad40358604f3c001a3ffd7e',
    'squad_v2:5acf9a5277cf76001a685420',
    'squad_v2:5ad0301577cf76001a686db8',
}

config = json.loads(original.read_text(encoding='utf-8'))
records = [
    json.loads(line)
    for line in parent.read_text(encoding='utf-8').splitlines()
    if line.strip()
]
parent_ids = {record['id'] for record in records}
assert len(records) == len(parent_ids) == 20
assert set(new_exclusions) <= parent_ids
assert set(new_exclusions).isdisjoint(config['excluded_ids'])
assert not output.exists(), f'Refusing to overwrite {output}'

approved_records = [record for record in records if record['id'] not in new_exclusions]
assert len(approved_records) == 14
assert Counter(record['category'] for record in approved_records) == {
    'answerable': 10,
    'unanswerable': 4,
}

config['version'] = '2.0'
config['guideline_version'] = '0.2'
config['review_status'] = 'project_owner_approved'
config['independent_double_review'] = False
config['parent_version'] = 'curated_v1'
config['excluded_ids'] = {**config['excluded_ids'], **new_exclusions}
config['approved_retained_ids'] = [record['id'] for record in approved_records]
config['false_premise_challenge_candidates'] = sorted(
    set(config.get('false_premise_challenge_candidates', [])) | challenge_candidates
)
assert len(config['excluded_ids']) == 16
assert len(config['approved_retained_ids']) == 14
assert len(config['false_premise_challenge_candidates']) == 6

output.write_text(json.dumps(config, indent=2, sort_keys=True) + '\n', encoding='utf-8')
print('Wrote:', output)
print('Cumulative exclusions:', len(config['excluded_ids']))
print('Approved retained IDs:', len(config['approved_retained_ids']))
print('False-premise candidates:', len(config['false_premise_challenge_candidates']))
