"""Approved selection must be authorized, reproducible, and non-destructive."""

import json

import pytest

from src.data import assemble_curated as assembly, candidate_pool as pool, build_eval
from test_candidate_pool import case, build, review, save, snapshot


@pytest.fixture
def ready(case, tmp_path):
    pm = build(case)
    case['pool_dir'] = case['pools_root'] / 'pool_001'
    case['selected'] = pm['candidate_ids'][0]
    case['output'] = tmp_path / 'assembled'
    return case


def approve(c, **overrides):
    return review(c['pool_dir'], c['selected'], event_type='decision', actor_role='project_owner',
                  reviewer='owner', approval_reference='Explicit synthetic test approval', **overrides)


def run(c, **overrides):
    return assembly.assemble_curated(**{
        'eval_root': c['eval_root'], 'pool_dir': c['pool_dir'],
        'output_dir': c['output'], 'candidate_id': c['selected'], **overrides,
    })


def verify(c):
    return assembly.verify_assembly(eval_root=c['eval_root'], pool_dir=c['pool_dir'], output_dir=c['output'])


def test_deterministic_assembly_preserves_inputs_order_and_test(ready, tmp_path, monkeypatch):
    c = ready
    event = approve(c)
    inputs = snapshot(c['eval_root'])
    pool_before = snapshot(c['pool_dir'])
    def no_sampling(*a, **k):
        pytest.fail('Assembly must not load source data or sample')
    monkeypatch.setattr(pool, 'load_dataset', no_sampling)
    monkeypatch.setattr(build_eval, 'load_dataset', no_sampling)
    first = run(c)
    second_path = tmp_path / 'repeat'
    assert run(c, output_dir=second_path) == first
    assert snapshot(c['output']) == snapshot(second_path)
    assert snapshot(c['eval_root']) == inputs
    assert snapshot(c['pool_dir']) == pool_before
    parent = build_eval.read_jsonl(c['eval_root'] / c['parent_name'] / 'squad_dev.jsonl')
    rows = build_eval.read_jsonl(c['output'] / 'squad_dev.jsonl')
    retained = [r for r in parent if r.id in c['config']['approved_retained_ids']]
    assert rows[:-1] == retained
    assert rows[-1] == next(r for r in pool.verify_pool(c['pool_dir'])[1] if r.id == c['selected'])
    assert (c['output'] / 'squad_test.jsonl').read_bytes() == (c['eval_root'] / 'squad_test.jsonl').read_bytes()
    assert first['curation']['approval_event_sha256'] == event['event_sha256']
    assert first['curation']['excluded_ids'] == sorted(c['config']['excluded_ids'])
    assert first['curation']['status'] == 'approved_candidate_assembly'
    assert verify(c) == first
    # An additional review cannot rewrite this assembly's archived evidence.
    review(c['pool_dir'], pool.verify_pool(c['pool_dir'])[0]['candidate_ids'][1])
    assert verify(c) == first


@pytest.mark.parametrize('state', ['empty', 'ai_only', 'rejected', 'deferred', 'revoked', 'other_candidate'])
def test_selection_requires_current_owner_acceptance(ready, state):
    c = ready
    if state == 'ai_only':
        review(c['pool_dir'], c['selected'])
    elif state in {'rejected', 'deferred'}:
        approve(c, disposition='reject' if state == 'rejected' else 'defer')
    elif state == 'revoked':
        event = approve(c)
        approve(c, disposition='reject', supersedes=event['event_sha256'])
        review(c['pool_dir'], c['selected'])  # AI acceptance cannot override rejection.
    elif state == 'other_candidate':
        cid = pool.verify_pool(c['pool_dir'])[0]['candidate_ids'][1]
        review(c['pool_dir'], cid, event_type='decision', actor_role='project_owner',
               approval_reference='Other candidate approved')
    with pytest.raises(ValueError, match='latest project-owner acceptance'):
        run(c)
    assert not c['output'].exists()


def test_unknown_selection(ready):
    approve(ready)
    with pytest.raises(ValueError, match='not in the pool'):
        run(ready, candidate_id='squad_v2:unknown')
    assert not ready['output'].exists()


@pytest.mark.parametrize('target', ['parent_dev', 'parent_test', 'parent_manifest', 'pool', 'approval', 'reviews'])
def test_corrupt_inputs_rejected_without_output(ready, target):
    c = ready
    approve(c)
    paths = {
        'parent_dev': c['eval_root'] / c['parent_name'] / 'squad_dev.jsonl',
        'parent_test': c['eval_root'] / c['parent_name'] / 'squad_test.jsonl',
        'parent_manifest': c['eval_root'] / c['parent_name'] / 'squad_manifest.json',
        'pool': c['pool_dir'] / 'candidates.jsonl',
        'approval': c['pool_dir'] / 'approval_snapshot.json',
        'reviews': c['pool_dir'] / 'reviews.jsonl',
    }
    p = paths[target]
    if target == 'reviews':
        p.write_text(p.read_text().replace('Explicit synthetic', 'Tampered synthetic'))
    else:
        p.write_bytes(p.read_bytes() + b'\n')
    with pytest.raises(ValueError):
        run(c)
    assert not c['output'].exists()


@pytest.mark.parametrize('mutation', ['missing_exclusion', 'unknown_exclusion', 'retained_order', 'unapproved'])
def test_invalid_snapshot_even_with_updated_checksum(ready, mutation):
    c = ready
    p = c['pool_dir'] / 'approval_snapshot.json'
    cfg = json.loads(p.read_text())
    if mutation == 'missing_exclusion':
        del cfg['excluded_ids'][next(iter(cfg['excluded_ids']))]
    elif mutation == 'unknown_exclusion':
        cfg['excluded_ids']['squad_v2:unknown'] = 'Unknown'
    elif mutation == 'retained_order':
        cfg['approved_retained_ids'].reverse()
    else:
        cfg['review_status'] = 'pending'
    save(p, cfg)
    mp = c['pool_dir'] / 'manifest.json'
    m = json.loads(mp.read_text())
    m['approval_snapshot_sha256'] = build_eval.sha256_file(p)
    save(mp, m)
    approve(c)
    with pytest.raises(ValueError):
        run(c)
    assert not c['output'].exists()


@pytest.mark.parametrize('target', ['output', 'baseline', 'parent', 'pool'])
def test_no_overwrite(ready, target):
    c = ready
    approve(c)
    if target == 'output':
        run(c)
        directory = c['output']
    else:
        directory = {'baseline': c['eval_root'],
                     'parent': c['eval_root'] / c['parent_name'], 'pool': c['pool_dir']}[target]
    before = snapshot(directory)
    with pytest.raises(FileExistsError):
        run(c, output_dir=directory)
    assert snapshot(directory) == before


@pytest.mark.parametrize('file', ['squad_dev.jsonl', 'squad_test.jsonl', 'squad_manifest.json',
                                  'approval_reviews.jsonl', 'approval_snapshot.json', 'pool_manifest.json'])
def test_verifier_detects_output_corruption(ready, file):
    c = ready
    approve(c)
    run(c)
    p = c['output'] / file
    p.write_bytes(p.read_bytes() + b'\n')
    with pytest.raises(ValueError):
        verify(c)


def test_assembled_version_is_valid_historical_parent(ready):
    c = ready
    approve(c)
    output = c['eval_root'] / 'curated_v3'
    m = run(c, output_dir=output)
    _, _, _, rows, excluded, history = pool.verified_history(c['eval_root'], 'curated_v3')
    assert len(rows) == 4
    assert excluded == set(c['config']['excluded_ids'])
    assert 'curated_v3' in history
    assert assembly.verify_assembly(eval_root=c['eval_root'], pool_dir=c['pool_dir'], output_dir=output) == m
