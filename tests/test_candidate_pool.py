"""Regression coverage for pool generation and append-only review events."""

import json
from pathlib import Path

import pytest

from src.data import build_eval, candidate_pool as pool
from src.data.adapters.squad_v2 import adapt_squad_example

REVISION = "a" * 40


def raw(i, title=None, context=None, answerable=False):
    return {"id": str(i), "title": title or f"Article {i}",
            "context": context or f"Evidence {i}", "question": f"Question {i}?",
            "answers": {"text": ["Evidence"] if answerable else [], "answer_start": [0] if answerable else []}}


def save(path, value):
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def snapshot(directory):
    return {str(p.relative_to(directory)): p.read_bytes()
            for p in directory.rglob("*") if p.is_file()}


@pytest.fixture
def case(tmp_path, monkeypatch):
    rows = [raw(f"{i}_{category}", title=f"Article {i}", answerable=category == "a")
            for i in range(80) for category in ("a", "u")]
    calls = []

    def loader(name, split, revision):
        calls.append((name, split, revision))
        assert (name, split, revision) == (build_eval.DATASET_NAME, "validation", REVISION)
        return rows

    monkeypatch.setattr(build_eval, "load_dataset", loader)
    monkeypatch.setattr(pool, "load_dataset", loader)
    baseline = tmp_path / "eval"
    build_eval.build_dataset(baseline, per_category=2, revision=REVISION)
    dev = build_eval.read_jsonl(baseline / "squad_dev.jsonl")
    excluded = next(r.id for r in dev if not r.answerable)
    cfg = {"dataset": build_eval.DATASET_NAME, "source_revision": REVISION,
           "review_status": "project_owner_approved", "guideline_version": "0.2",
           "excluded_ids": {excluded: "Synthetic exclusion"}}
    approvals = tmp_path / "approvals.json"
    save(approvals, cfg)
    v1 = baseline / "curated_v1"
    m1 = build_eval.build_curated_dataset(v1, baseline, approvals, per_category=2)
    cfg["excluded_ids"][m1["curation"]["replacement_ids"][0]] = "Rejected v1"
    cfg["approved_retained_ids"] = [r.id for r in build_eval.read_jsonl(v1 / "squad_dev.jsonl")
                                     if r.id not in cfg["excluded_ids"]]
    save(approvals, cfg)
    v2 = baseline / "curated_v2"
    m2 = build_eval.build_successive_curated_dataset(v2, baseline, v1, approvals, per_category=2)
    cfg["excluded_ids"][m2["curation"]["replacement_ids"][0]] = "Rejected v2"
    cfg["approved_retained_ids"] = [r.id for r in build_eval.read_jsonl(v2 / "squad_dev.jsonl")
                                     if r.id not in cfg["excluded_ids"]]
    cfg["parent_version"] = "curated_v2"
    save(approvals, cfg)
    return dict(eval_root=baseline, pools_root=tmp_path / "pools", approvals_path=approvals,
                parent_name="curated_v2", rows=rows, config=cfg, calls=calls)


def build(case, name="pool_001", **overrides):
    options = {k: case[k] for k in ("eval_root", "pools_root", "approvals_path", "parent_name")}
    return pool.build_pool(**{**options, "pool_name": name, **overrides})


def test_determinism_row_order_and_provenance(case, tmp_path):
    before = snapshot(case["eval_root"])
    config_bytes = case["approvals_path"].read_bytes()
    first = build(case)
    case["rows"].reverse()
    other_root = tmp_path / "repeat_pools"
    second = build(case, pools_root=other_root)
    assert first == second
    assert snapshot(case["pools_root"] / "pool_001") == snapshot(other_root / "pool_001")
    assert snapshot(case["eval_root"]) == before
    assert case["approvals_path"].read_bytes() == config_bytes
    assert first["initial_review_status"] == "unreviewed"
    assert first["source_revision"] == REVISION
    assert first["policy"] == pool.POLICY
    assert first["parent_version"] == "curated_v2"
    assert set(first["history"]) == {"baseline", "curated_v1", "curated_v2"}
    assert first["approval_snapshot_sha256"] == build_eval.sha256_file(case["approvals_path"])
    assert (case["pools_root"] / "pool_001/reviews.jsonl").read_bytes() == b""
    assert case["calls"][-1] == (build_eval.DATASET_NAME, "validation", REVISION)


def test_history_prior_pools_and_diversity(case):
    first = build(case)
    before = snapshot(case["pools_root"] / "pool_001")
    second = build(case, "pool_002")
    assert set(first["candidate_ids"]).isdisjoint(second["candidate_ids"])
    assert snapshot(case["pools_root"] / "pool_001") == before
    assert second["previous_pools"]["pool_001"]["manifest_sha256"] == build_eval.sha256_file(
        case["pools_root"] / "pool_001/manifest.json")
    historical = []
    for file in case["eval_root"].rglob("*.jsonl"):
        historical.extend(build_eval.read_jsonl(file))
    _, rows = pool.verify_pool(case["pools_root"] / "pool_002")
    assert len(rows) == len({r.source_id for r in rows}) == len({r.context for r in rows}) == 10
    assert all(r.category == "unanswerable" for r in rows)
    assert {r.id for r in rows}.isdisjoint(r.id for r in historical)
    assert {r.id for r in rows}.isdisjoint(case["config"]["excluded_ids"])
    assert {r.context for r in rows}.isdisjoint(r.context for r in historical)
    test = build_eval.read_jsonl(case["eval_root"] / "squad_test.jsonl")
    assert {r.source_id for r in rows}.isdisjoint(r.source_id for r in test)


@pytest.mark.parametrize("barrier", ["historical_id", "pool_id", "exclusion", "test_source", "context", "answerable"])
def test_each_eligibility_barrier(barrier):
    row = raw("blocked")
    converted = adapt_squad_example(row)
    args = dict(blocked_ids=set(), blocked_contexts=set(), test_sources=set())
    if barrier in {"historical_id", "pool_id", "exclusion"}:
        args["blocked_ids"].add(converted.id)
    elif barrier == "test_source":
        args["test_sources"].add(converted.source_id)
    elif barrier == "context":
        args["blocked_contexts"].add(converted.context)
    else:
        row["answers"]["text"] = ["Evidence"]
    with pytest.raises(ValueError, match="Insufficient eligible articles"):
        pool.sample_pool([row], count=1, seed=42, **args)


def test_one_per_article_and_context_even_with_multiple_records():
    rows = [raw("a", title="Same"), raw("b", title="Same"),
            raw("c", title="Different", context="Evidence a"),
            raw("d", title="Independent")]
    selected = pool.sample_pool(rows, count=2, seed=42, blocked_ids=set(),
                                blocked_contexts=set(), test_sources=set())
    assert len({r.source_id for r in selected}) == len({r.context for r in selected}) == 2
    with pytest.raises(ValueError, match="Insufficient eligible articles"):
        pool.sample_pool(rows, count=4, seed=42, blocked_ids=set(),
                         blocked_contexts=set(), test_sources=set())


def test_cross_article_duplicate_context_is_blocked():
    rows = [raw("a", title="First", context="Shared"),
            raw("b", title="Second", context="Shared")]
    with pytest.raises(ValueError, match="Insufficient eligible articles"):
        pool.sample_pool(rows, count=2, seed=42, blocked_ids=set(),
                         blocked_contexts=set(), test_sources=set())


def test_duplicate_source_ids_rejected():
    with pytest.raises(ValueError, match="Duplicate source dataset IDs"):
        pool.sample_pool([raw(1), raw(1)], count=1, seed=42,
                         blocked_ids=set(), blocked_contexts=set(), test_sources=set())


def test_insufficient_candidates_leaves_no_output(case, monkeypatch):
    monkeypatch.setattr(pool, "load_dataset", lambda *a, **k: [])
    with pytest.raises(ValueError, match="Insufficient eligible articles"):
        build(case)
    assert not case["pools_root"].exists()


def test_no_overwrite(case):
    build(case)
    before = snapshot(case["pools_root"])
    with pytest.raises(FileExistsError):
        build(case)
    assert snapshot(case["pools_root"]) == before


@pytest.mark.parametrize("corrupt", ["parent_data", "parent_lineage", "prior_pool_data", "prior_pool_snapshot", "missing_pool_manifest"])
def test_corruption_rejected(case, corrupt):
    if corrupt.startswith("prior_pool") or corrupt == "missing_pool_manifest":
        build(case)
        directory = case["pools_root"] / "pool_001"
        if corrupt == "missing_pool_manifest":
            (directory / "manifest.json").unlink()
        else:
            filename = "candidates.jsonl" if corrupt == "prior_pool_data" else "approval_snapshot.json"
            p = directory / filename
            p.write_bytes(p.read_bytes() + b"\n")
    elif corrupt == "parent_data":
        p = case["eval_root"] / "curated_v2/squad_dev.jsonl"
        p.write_bytes(p.read_bytes() + b"\n")
    else:
        p = case["eval_root"] / "curated_v2/squad_manifest.json"
        m = json.loads(p.read_text())
        m["curation"]["parent_manifest_sha256"] = "0" * 64
        save(p, m)
    with pytest.raises((ValueError, FileNotFoundError)):
        build(case, "pool_002")
    assert not (case["pools_root"] / "pool_002").exists()


@pytest.mark.parametrize("invalid", ["revision", "approval", "omit_exclusion", "unknown_exclusion", "retained", "parent"])
def test_invalid_approval_snapshot_rejected(case, invalid):
    cfg = case["config"]
    if invalid == "revision":
        cfg["source_revision"] = "b" * 40
    elif invalid == "approval":
        cfg["review_status"] = "ai_recommended"
    elif invalid == "omit_exclusion":
        del cfg["excluded_ids"][next(iter(cfg["excluded_ids"]))]
    elif invalid == "unknown_exclusion":
        cfg["excluded_ids"]["squad_v2:unknown"] = "Invalid"
    elif invalid == "retained":
        cfg["approved_retained_ids"].pop()
    else:
        cfg["parent_version"] = "curated_v1"
    save(case["approvals_path"], cfg)
    with pytest.raises(ValueError):
        build(case)
    assert not case["pools_root"].exists()


def review(directory, candidate_id, **overrides):
    args = dict(candidate_id=candidate_id, event_type="recommendation", actor_role="ai_assisted",
                reviewer="assistant", disposition="accept", evidence="Evidence excerpt",
                rationale="Review rationale")
    return pool.append_review(directory, **{**args, **overrides})


def test_review_append_only_actor_roles_and_supersession(case):
    manifest = build(case)
    directory = case["pools_root"] / "pool_001"
    artifacts = {name: (directory / name).read_bytes()
                 for name in ("candidates.jsonl", "manifest.json", "approval_snapshot.json")}
    candidate_id = manifest["candidate_ids"][0]
    recommendation = review(directory, candidate_id)
    before = (directory / "reviews.jsonl").read_bytes()
    decision = review(directory, candidate_id, event_type="decision", actor_role="project_owner",
                      reviewer="owner", disposition="defer", approval_reference="Synthetic approval",
                      supersedes=recommendation["event_sha256"])
    assert (directory / "reviews.jsonl").read_bytes().startswith(before)
    assert recommendation["event_type"] == "recommendation"
    assert decision["event_type"] == "decision"
    assert decision["sequence"] == 2
    assert decision["previous_event_sha256"] == recommendation["event_sha256"]
    for name, original in artifacts.items():
        assert (directory / name).read_bytes() == original
    # Prior-pool review activity does not modify its immutable sampling provenance.
    build(case, "pool_002")


@pytest.mark.parametrize("bad", [
    {"event_type": "decision"},
    {"event_type": "decision", "actor_role": "project_owner"},
    {"approval_reference": "AI cannot approve"},
    {"candidate_id": "unknown"}, {"supersedes": "unknown"},
    {"rationale": ""}, {"disposition": "approved"},
])
def test_invalid_review_does_not_append(case, bad):
    manifest = build(case)
    directory = case["pools_root"] / "pool_001"
    args = {"candidate_id": manifest["candidate_ids"][0], **bad}
    with pytest.raises(ValueError):
        review(directory, **args)
    assert (directory / "reviews.jsonl").read_bytes() == b""


def test_review_tampering_detected(case):
    manifest = build(case)
    directory = case["pools_root"] / "pool_001"
    cid = manifest["candidate_ids"][0]
    review(directory, cid)
    log = directory / "reviews.jsonl"
    log.write_text(log.read_text().replace("Review rationale", "Modified rationale"))
    before = log.read_bytes()
    with pytest.raises(ValueError, match="Review log integrity"):
        review(directory, cid)
    assert log.read_bytes() == before
    with pytest.raises(ValueError, match="Review log integrity"):
        build(case, "pool_002")


def test_missing_review_log_is_not_silently_recreated(case):
    manifest = build(case)
    directory = case["pools_root"] / "pool_001"
    (directory / "reviews.jsonl").unlink()
    with pytest.raises(FileNotFoundError):
        review(directory, manifest["candidate_ids"][0])
    assert not (directory / "reviews.jsonl").exists()


@pytest.mark.parametrize("count", [0, -1])
def test_invalid_pool_count(case, count):
    with pytest.raises(ValueError, match="Pool count must be positive"):
        build(case, count=count)
    assert not case["pools_root"].exists()


def test_missing_historical_version_is_rejected(case):
    # A complete v2 artifact still references v1; it must not bypass ID blocking
    # when that historical version is absent from the discovered inventory.
    (case["eval_root"] / "curated_v1").rename(case["eval_root"] / "hidden_v1")
    with pytest.raises(ValueError, match="Unknown or invalid parent lineage"):
        build(case)
    assert not case["pools_root"].exists()


def test_policy_v1_known_order():
    # Pin a small policy vector: changing canonical encoding, hash inputs, or
    # ranking must require an intentional policy-version change.
    rows = [raw(i) for i in range(8)]
    selected = pool.sample_pool(rows, count=4, seed=42, blocked_ids=set(),
                                blocked_contexts=set(), test_sources=set())
    assert [r.id for r in selected] == [
        "squad_v2:3", "squad_v2:2", "squad_v2:7", "squad_v2:1",
    ]
