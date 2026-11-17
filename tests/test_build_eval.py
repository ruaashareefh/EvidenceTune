
"""Tests for EvidenceTune evaluation dataset generation and curation."""

import hashlib
import json
from collections import Counter

import pytest

from src.data import build_eval
from src.data.schema import EvidenceExample


PINNED_REVISION = "a" * 40


# ---------------------------------------------------------
# Fixtures
# ---------------------------------------------------------

@pytest.fixture
def mock_squad_dataset(monkeypatch):
    """Create SQuAD-like records without network access."""
    records = []

    # Enough articles for original splits AND replacements.
    for i in range(48):
        title = f"Article_{i}"
        context = f"Project {i} was launched in {2000 + i}."

        records.append({
            "id": f"q_{i}_answerable",
            "title": title,
            "context": context,
            "question": f"When was Project {i} launched?",
            "answers": {
                "text": [str(2000 + i)],
                "answer_start": [len(context) - 5],
            },
        })

        records.append({
            "id": f"q_{i}_unanswerable",
            "title": title,
            "context": context,
            "question": f"Who launched Project {i}?",
            "answers": {
                "text": [],
                "answer_start": [],
            },
        })

    def fake_load_dataset(name, split, revision=None):
        assert name == "rajpurkar/squad_v2"
        assert split == "validation"
        return records

    monkeypatch.setattr(
        build_eval,
        "load_dataset",
        fake_load_dataset,
    )

    return records


@pytest.fixture
def curation_case(mock_squad_dataset, tmp_path):
    """Create a verified baseline and approved exclusion config."""
    baseline_dir = tmp_path / "baseline"
    output_dir = tmp_path / "curated"
    exclusions_path = tmp_path / "exclusions.json"

    build_eval.build_dataset(
        output_dir=baseline_dir,
        seed=42,
        per_category=10,
        revision=PINNED_REVISION,
    )

    dev = read_jsonl(baseline_dir / "squad_dev.jsonl")
    test = read_jsonl(baseline_dir / "squad_test.jsonl")

    answerable = [
        record for record in dev
        if record["category"] == "answerable"
    ]

    unanswerable = [
        record for record in dev
        if record["category"] == "unanswerable"
    ]

    # Mirror the actual audit:
    # 2 answerable + 8 unanswerable exclusions.
    excluded_records = answerable[:2] + unanswerable[:8]

    excluded_ids = {
        record["id"] for record in excluded_records
    }

    challenge_ids = [
        record["id"] for record in unanswerable[:3]
    ]

    config = {
        "version": "1.0",
        "dataset": "rajpurkar/squad_v2",
        "source_revision": PINNED_REVISION,
        "guideline_version": "0.2",
        "review_status": "project_owner_approved",
        "independent_double_review": False,
        "excluded_ids": {
            record_id: "Synthetic test exclusion"
            for record_id in sorted(excluded_ids)
        },
        "false_premise_challenge_candidates": challenge_ids,
    }

    exclusions_path.write_text(
        json.dumps(config, indent=2),
        encoding="utf-8",
    )

    return {
        "baseline_dir": baseline_dir,
        "output_dir": output_dir,
        "exclusions_path": exclusions_path,
        "excluded_ids": excluded_ids,
        "original_dev": dev,
        "original_test": test,
        "config": config,
    }


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def read_jsonl(path):
    """Read generated evaluation records."""
    return [
        json.loads(line)
        for line in path.read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]


def make_record(record_id, source_id, context="Some evidence."):
    """Create a valid EvidenceExample."""
    return EvidenceExample(
        id=record_id,
        source_id=source_id,
        context=context,
        question="What is the answer?",
        answer="An answer.",
        answerable=True,
        category="answerable",
    )


def sha256(path):
    """Calculate a file's SHA-256 checksum."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_curation(case, **overrides):
    """Build a curated dataset using the test fixture."""
    options = {
        "output_dir": case["output_dir"],
        "baseline_dir": case["baseline_dir"],
        "exclusions_path": case["exclusions_path"],
        "seed": 42,
        "per_category": 10,
        "revision": PINNED_REVISION,
    }

    options.update(overrides)

    return build_eval.build_curated_dataset(**options)


def save_exclusion_config(case, config):
    """Write a modified exclusion configuration."""
    case["exclusions_path"].write_text(
        json.dumps(config, indent=2),
        encoding="utf-8",
    )


@pytest.fixture
def successive_case(curation_case, tmp_path):
    """Mirror v1 -> v2: ten old exclusions, six new ones, 14 survivors."""
    case = curation_case
    parent_dir = tmp_path / "curated_v1"
    parent_manifest = run_curation(case, output_dir=parent_dir)
    parent_dev = read_jsonl(parent_dir / "squad_dev.jsonl")
    replacement_ids = set(parent_manifest["curation"]["replacement_ids"])
    newly_excluded = {
        record["id"] for record in parent_dev
        if record["id"] in replacement_ids
        and record["category"] == "unanswerable"
    }
    newly_excluded = set(sorted(newly_excluded)[:6])
    approved = [r["id"] for r in parent_dev if r["id"] not in newly_excluded]
    config = {
        **case["config"],
        "version": "2.0",
        "parent_version": "curated_v1",
        "excluded_ids": {
            **case["config"]["excluded_ids"],
            **{record_id: "Synthetic second-round exclusion"
               for record_id in sorted(newly_excluded)},
        },
        "approved_retained_ids": approved,
    }
    result = {
        **case,
        "parent_dir": parent_dir,
        "parent_dev": parent_dev,
        "parent_manifest": parent_manifest,
        "output_dir": tmp_path / "curated_v2",
        "exclusions_path": tmp_path / "exclusions_v2.json",
        "config": config,
        "newly_excluded_ids": newly_excluded,
    }
    save_exclusion_config(result, config)
    assert len(newly_excluded) == 6
    assert len(approved) == 14
    # Exercise the real v1 legacy format, which has no excluded_ids field.
    assert "excluded_ids" not in parent_manifest["curation"]
    return result


def run_successive(case, **overrides):
    options = {
        "output_dir": case["output_dir"],
        "baseline_dir": case["baseline_dir"],
        "parent_dir": case["parent_dir"],
        "exclusions_path": case["exclusions_path"],
        "seed": 42,
        "per_category": 10,
        "revision": PINNED_REVISION,
    }
    options.update(overrides)
    return build_eval.build_successive_curated_dataset(**options)


def artifact_bytes(directory):
    """Snapshot all benchmark artifacts, including manifest formatting."""
    return {
        name: (directory / name).read_bytes()
        for name in ("squad_dev.jsonl", "squad_test.jsonl", "squad_manifest.json")
    }


# =========================================================
# PART 1: ORIGINAL DATASET BUILDER
# =========================================================

def test_balanced_dataset(mock_squad_dataset, tmp_path):
    """Both splits contain 10 examples per category."""
    build_eval.build_dataset(
        output_dir=tmp_path,
        seed=42,
        per_category=10,
        revision="test-revision",
    )

    for name in ("dev", "test"):
        records = read_jsonl(
            tmp_path / f"squad_{name}.jsonl"
        )

        counts = Counter(
            record["category"] for record in records
        )

        assert len(records) == 20
        assert counts["answerable"] == 10
        assert counts["unanswerable"] == 10


def test_source_disjoint_splits(mock_squad_dataset, tmp_path):
    """Development and test splits cannot share sources."""
    build_eval.build_dataset(tmp_path, seed=42)

    dev = read_jsonl(tmp_path / "squad_dev.jsonl")
    test = read_jsonl(tmp_path / "squad_test.jsonl")

    dev_sources = {r["source_id"] for r in dev}
    test_sources = {r["source_id"] for r in test}

    assert dev_sources.isdisjoint(test_sources)

    all_ids = [r["id"] for r in dev + test]
    assert len(all_ids) == len(set(all_ids))


def test_reproducible_outputs(mock_squad_dataset, tmp_path):
    """Same seed and inputs produce identical files."""
    output_a = tmp_path / "run_a"
    output_b = tmp_path / "run_b"

    manifest_a = build_eval.build_dataset(
        output_a,
        seed=42,
        revision="test-revision",
    )

    manifest_b = build_eval.build_dataset(
        output_b,
        seed=42,
        revision="test-revision",
    )

    assert manifest_a == manifest_b

    for filename in (
        "squad_dev.jsonl",
        "squad_test.jsonl",
        "squad_manifest.json",
    ):
        assert (
            (output_a / filename).read_bytes()
            == (output_b / filename).read_bytes()
        )


def test_manifest_checksums(mock_squad_dataset, tmp_path):
    """Manifest checksums must match actual files."""
    manifest = build_eval.build_dataset(
        tmp_path,
        seed=42,
        revision="test-revision",
    )

    assert manifest["dataset"] == "rajpurkar/squad_v2"
    assert manifest["source_revision"] == "test-revision"
    assert manifest["seed"] == 42

    for name in ("dev", "test"):
        path = tmp_path / f"squad_{name}.jsonl"

        assert manifest["splits"][name]["sha256"] == sha256(path)
        assert manifest["splits"][name]["count"] == 20


# ---------------------------------------------------------
# Original data integrity tests
# ---------------------------------------------------------

def test_duplicate_ids_rejected():
    dev = [make_record("001", "source_a")]
    test = [make_record("001", "source_b")]

    with pytest.raises(ValueError, match="Duplicate example IDs"):
        build_eval.validate_splits(dev, test)


def test_source_leakage_rejected():
    dev = [make_record("001", "shared_source")]
    test = [make_record("002", "shared_source")]

    with pytest.raises(ValueError, match="Source leakage"):
        build_eval.validate_splits(dev, test)


def test_duplicate_contexts_rejected():
    dev = [make_record("001", "source_a", "Same context")]
    test = [make_record("002", "source_b", "Same context")]

    with pytest.raises(ValueError, match="Duplicate contexts"):
        build_eval.validate_splits(dev, test)


# ---------------------------------------------------------
# Original failure handling
# ---------------------------------------------------------

def test_existing_outputs_protected(mock_squad_dataset, tmp_path):
    build_eval.build_dataset(tmp_path)

    original = (
        tmp_path / "squad_dev.jsonl"
    ).read_bytes()

    with pytest.raises(FileExistsError):
        build_eval.build_dataset(tmp_path)

    assert (
        tmp_path / "squad_dev.jsonl"
    ).read_bytes() == original


def test_explicit_overwrite(mock_squad_dataset, tmp_path):
    build_eval.build_dataset(tmp_path, seed=42)

    manifest = build_eval.build_dataset(
        tmp_path,
        seed=123,
        overwrite=True,
    )

    assert manifest["seed"] == 123


@pytest.mark.parametrize("per_category", [0, -1])
def test_invalid_sample_size(
    mock_squad_dataset, tmp_path, per_category
):
    with pytest.raises(
        ValueError,
        match="per_category must be positive",
    ):
        build_eval.build_dataset(
            tmp_path,
            per_category=per_category,
        )


def test_insufficient_source_groups(
    mock_squad_dataset, monkeypatch, tmp_path
):
    small_dataset = mock_squad_dataset[:4]

    monkeypatch.setattr(
        build_eval,
        "load_dataset",
        lambda *args, **kwargs: small_dataset,
    )

    with pytest.raises(ValueError, match="Insufficient examples"):
        build_eval.build_dataset(
            tmp_path,
            per_category=3,
        )


# =========================================================
# PART 2: CURATED DATASET BUILDER
# =========================================================

def test_curated_retains_approved_examples(curation_case):
    """Every accepted development record remains unchanged."""
    case = curation_case

    manifest = run_curation(case)

    curated = read_jsonl(
        case["output_dir"] / "squad_dev.jsonl"
    )

    original = case["original_dev"]
    excluded = case["excluded_ids"]

    accepted = {
        record["id"]: record
        for record in original
        if record["id"] not in excluded
    }

    curated_by_id = {
        record["id"]: record
        for record in curated
    }

    assert len(accepted) == 10

    for record_id, original_record in accepted.items():
        assert record_id in curated_by_id
        assert curated_by_id[record_id] == original_record

    assert set(accepted).issubset(curated_by_id)

    assert manifest["curation"]["retained_dev_count"] == 10


def test_curated_exclusions_and_balance(curation_case):
    """Excluded IDs never reappear; category balance is restored."""
    case = curation_case

    manifest = run_curation(case)

    curated = read_jsonl(
        case["output_dir"] / "squad_dev.jsonl"
    )

    original_ids = {
        record["id"]
        for record in case["original_dev"]
    }

    curated_ids = {
        record["id"]
        for record in curated
    }

    excluded = case["excluded_ids"]

    assert curated_ids.isdisjoint(excluded)

    counts = Counter(
        record["category"] for record in curated
    )

    assert len(curated) == 20
    assert counts["answerable"] == 10
    assert counts["unanswerable"] == 10

    replacement_ids = curated_ids - original_ids

    assert len(replacement_ids) == 10
    assert len(curated_ids) == len(curated)

    assert set(
        manifest["curation"]["replacement_ids"]
    ) == replacement_ids

    assert manifest["curation"]["replacement_count"] == 10


def test_curated_preserves_heldout_test(curation_case):
    """Held-out test bytes and checksums remain unchanged."""
    case = curation_case

    baseline = case["baseline_dir"]
    curated = case["output_dir"]

    original_test_bytes = (
        baseline / "squad_test.jsonl"
    ).read_bytes()

    original_dev_bytes = (
        baseline / "squad_dev.jsonl"
    ).read_bytes()

    original_manifest_bytes = (
        baseline / "squad_manifest.json"
    ).read_bytes()

    manifest = run_curation(case)

    assert (
        curated / "squad_test.jsonl"
    ).read_bytes() == original_test_bytes

    assert (
        baseline / "squad_test.jsonl"
    ).read_bytes() == original_test_bytes

    assert (
        baseline / "squad_dev.jsonl"
    ).read_bytes() == original_dev_bytes

    assert (
        baseline / "squad_manifest.json"
    ).read_bytes() == original_manifest_bytes

    assert (
        manifest["splits"]["test"]["sha256"]
        == sha256(baseline / "squad_test.jsonl")
    )

    assert manifest["curation"]["test_preserved_byte_for_byte"]


def test_curated_source_isolation(curation_case):
    """Curated development sources must not overlap test sources."""
    case = curation_case

    run_curation(case)

    dev = read_jsonl(
        case["output_dir"] / "squad_dev.jsonl"
    )

    test = read_jsonl(
        case["output_dir"] / "squad_test.jsonl"
    )

    dev_sources = {
        record["source_id"] for record in dev
    }

    test_sources = {
        record["source_id"] for record in test
    }

    assert dev_sources.isdisjoint(test_sources)

    dev_contexts = {
        record["context"] for record in dev
    }

    test_contexts = {
        record["context"] for record in test
    }

    assert dev_contexts.isdisjoint(test_contexts)


def test_curated_reproducibility(curation_case, tmp_path):
    """Identical inputs generate identical curated artifacts."""
    case = curation_case

    output_a = tmp_path / "curated_a"
    output_b = tmp_path / "curated_b"

    manifest_a = run_curation(
        case,
        output_dir=output_a,
    )

    manifest_b = run_curation(
        case,
        output_dir=output_b,
    )

    assert manifest_a == manifest_b

    for filename in (
        "squad_dev.jsonl",
        "squad_test.jsonl",
        "squad_manifest.json",
    ):
        assert (
            (output_a / filename).read_bytes()
            == (output_b / filename).read_bytes()
        )


def test_curated_manifest_provenance(curation_case):
    """Manifest records all relevant curation provenance."""
    case = curation_case

    manifest = run_curation(case)

    curated = case["output_dir"]
    baseline = case["baseline_dir"]

    curation = manifest["curation"]

    assert manifest["source_revision"] == PINNED_REVISION

    assert curation["status"] == (
        "replacement_candidates_pending_review"
    )

    assert curation["guideline_version"] == "0.2"

    assert curation["excluded_count"] == 10
    assert curation["retained_dev_count"] == 10
    assert curation["replacement_count"] == 10

    assert curation["exclusion_file_sha256"] == sha256(
        case["exclusions_path"]
    )

    assert curation["baseline_manifest_sha256"] == sha256(
        baseline / "squad_manifest.json"
    )

    assert manifest["splits"]["dev"]["sha256"] == sha256(
        curated / "squad_dev.jsonl"
    )

    assert manifest["splits"]["test"]["sha256"] == sha256(
        curated / "squad_test.jsonl"
    )

    assert manifest["splits"]["dev"]["review_status"] == (
        "pending_replacement_audit"
    )


# ---------------------------------------------------------
# Curated output protection
# ---------------------------------------------------------

def test_curated_outputs_cannot_be_overwritten(curation_case):
    """Existing curated outputs cannot be silently replaced."""
    case = curation_case

    run_curation(case)

    original_bytes = (
        case["output_dir"] / "squad_dev.jsonl"
    ).read_bytes()

    with pytest.raises(FileExistsError):
        run_curation(case)

    assert (
        case["output_dir"] / "squad_dev.jsonl"
    ).read_bytes() == original_bytes


def test_curated_cannot_overwrite_baseline(curation_case):
    """Curated and baseline directories must differ."""
    case = curation_case

    with pytest.raises(
        ValueError,
        match="must differ from baseline",
    ):
        run_curation(
            case,
            output_dir=case["baseline_dir"],
        )


# ---------------------------------------------------------
# Baseline integrity checks
# ---------------------------------------------------------

@pytest.mark.parametrize("split", ["dev", "test"])
def test_corrupted_baseline_rejected(curation_case, split):
    """Reject baseline files whose checksums no longer match."""
    case = curation_case

    path = (
        case["baseline_dir"] / f"squad_{split}.jsonl"
    )

    path.write_bytes(
        path.read_bytes() + b"\n"
    )

    with pytest.raises(
        ValueError,
        match=f"Baseline {split} checksum mismatch",
    ):
        run_curation(case)

    assert not (
        case["output_dir"] / "squad_manifest.json"
    ).exists()


# ---------------------------------------------------------
# Exclusion configuration validation
# ---------------------------------------------------------

@pytest.mark.parametrize(
    "field,bad_value,error",
    [
        (
            "dataset",
            "wrong/dataset",
            "Exclusion dataset mismatch",
        ),
        (
            "source_revision",
            "b" * 40,
            "Exclusion source revision mismatch",
        ),
        (
            "review_status",
            "pending",
            "Exclusions are not project-owner approved",
        ),
        (
            "false_premise_challenge_candidates",
            ["squad_v2:unknown"],
            "Challenge candidates must be excluded records",
        ),
    ],
)
def test_invalid_exclusion_config_rejected(
    curation_case,
    field,
    bad_value,
    error,
):
    """Reject curation files with invalid provenance or status."""
    case = curation_case

    config = dict(case["config"])
    config[field] = bad_value

    save_exclusion_config(case, config)

    with pytest.raises(ValueError, match=error):
        run_curation(case)


def test_unknown_exclusion_id_rejected(curation_case):
    """Excluded IDs must belong to the baseline development set."""
    case = curation_case

    config = dict(case["config"])
    excluded = dict(config["excluded_ids"])

    excluded["squad_v2:nonexistent"] = "Invalid record"

    config["excluded_ids"] = excluded

    save_exclusion_config(case, config)

    with pytest.raises(
        ValueError,
        match="must belong to the baseline development set",
    ):
        run_curation(case)


def test_empty_exclusion_list_rejected(curation_case):
    """An empty exclusion configuration is not a curated build."""
    case = curation_case

    config = dict(case["config"])
    config["excluded_ids"] = {}
    config["false_premise_challenge_candidates"] = []

    save_exclusion_config(case, config)

    with pytest.raises(
        ValueError,
        match="Exclusion list is empty",
    ):
        run_curation(case)


def test_curated_category_target_mismatch_rejected(curation_case):
    """Curated category targets must match the baseline."""
    case = curation_case

    with pytest.raises(
        ValueError,
        match="category target must match the baseline",
    ):
        run_curation(
            case,
            per_category=9,
        )


def test_curated_revision_mismatch_rejected(curation_case):
    """Curated builds cannot silently change the source revision."""
    case = curation_case

    with pytest.raises(
        ValueError,
        match="Requested revision differs",
    ):
        run_curation(
            case,
            revision="b" * 40,
        )


# ---------------------------------------------------------
# Replacement availability
# ---------------------------------------------------------

def test_insufficient_replacements_rejected(
    curation_case,
    mock_squad_dataset,
    monkeypatch,
):
    """Fail when no eligible unused replacement records exist."""
    case = curation_case

    original_ids = {
        record["id"]
        for record in (
            case["original_dev"] + case["original_test"]
        )
    }

    # Restrict loader to records already in the baseline.
    # No unused candidates will be available.
    limited_records = [
        row for row in mock_squad_dataset
        if f"squad_v2:{row['id']}" in original_ids
    ]

    monkeypatch.setattr(
        build_eval,
        "load_dataset",
        lambda *args, **kwargs: limited_records,
    )

    with pytest.raises(
        ValueError,
        match="Insufficient eligible replacement examples",
    ):
        run_curation(case)

    assert not (
        case["output_dir"] / "squad_manifest.json"
    ).exists()


# =========================================================
# PART 3: SUCCESSIVE CURATION (curated_v1 -> curated_v2)
# =========================================================


def test_successive_preserves_approved_record_data(successive_case):
    case = successive_case
    manifest = run_successive(case)
    parent = {r["id"]: r for r in case["parent_dev"]}
    output = read_jsonl(case["output_dir"] / "squad_dev.jsonl")
    approved = case["config"]["approved_retained_ids"]
    assert [r["id"] for r in output[:14]] == approved
    for record in output[:14]:
        assert record == parent[record["id"]]
        # Compare deterministic record bytes, independent of file position.
        assert json.dumps(record, sort_keys=True).encode() == json.dumps(
            parent[record["id"]], sort_keys=True
        ).encode()
    # Approved replacements from v1 must survive, not just baseline records.
    assert len(set(approved) & set(
        case["parent_manifest"]["curation"]["replacement_ids"]
    )) == 4
    assert manifest["curation"]["retained_dev_ids"] == approved


def test_successive_cumulative_exclusions_and_balance(successive_case):
    case = successive_case
    manifest = run_successive(case)
    records = read_jsonl(case["output_dir"] / "squad_dev.jsonl")
    ids = {r["id"] for r in records}
    assert len(ids) == len(records) == 20
    assert ids.isdisjoint(case["config"]["excluded_ids"])
    assert Counter(r["category"] for r in records) == {
        "answerable": 10, "unanswerable": 10,
    }
    replacements = set(manifest["curation"]["replacement_ids"])
    assert len(replacements) == 6
    assert replacements == ids - set(case["config"]["approved_retained_ids"])
    assert {r["category"] for r in records if r["id"] in replacements} == {
        "unanswerable",
    }
    historical = case["original_dev"] + case["original_test"] + case["parent_dev"]
    assert replacements.isdisjoint(r["id"] for r in historical)


def test_successive_reproducible_outputs(successive_case, tmp_path):
    case = successive_case
    output_a, output_b = tmp_path / "run_a", tmp_path / "run_b"
    assert run_successive(case, output_dir=output_a) == run_successive(
        case, output_dir=output_b
    )
    assert artifact_bytes(output_a) == artifact_bytes(output_b)


def test_successive_preserves_test_and_input_artifacts(successive_case):
    case = successive_case
    baseline_before = artifact_bytes(case["baseline_dir"])
    parent_before = artifact_bytes(case["parent_dir"])
    config_before = case["exclusions_path"].read_bytes()
    manifest = run_successive(case)
    assert artifact_bytes(case["baseline_dir"]) == baseline_before
    assert artifact_bytes(case["parent_dir"]) == parent_before
    assert case["exclusions_path"].read_bytes() == config_before
    assert (case["output_dir"] / "squad_test.jsonl").read_bytes() == (
        baseline_before["squad_test.jsonl"]
    ) == parent_before["squad_test.jsonl"]
    assert manifest["splits"]["test"]["sha256"] == sha256(
        case["baseline_dir"] / "squad_test.jsonl"
    )
    assert manifest["curation"]["test_preserved_byte_for_byte"] is True


@pytest.mark.parametrize("split", ["dev", "test"])
def test_successive_corrupted_parent_data_rejected(successive_case, split):
    case = successive_case
    path = case["parent_dir"] / f"squad_{split}.jsonl"
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(ValueError, match=f"Baseline {split} checksum mismatch"):
        run_successive(case)
    assert not case["output_dir"].exists()


@pytest.mark.parametrize(
    "section,field,error",
    [
        ("dev", "sha256", "Baseline dev checksum mismatch"),
        ("test", "sha256", "Baseline test checksum mismatch"),
        ("curation", "baseline_manifest_sha256", "Parent baseline manifest checksum mismatch"),
        ("curation", "baseline_dev_sha256", "Parent baseline development checksum mismatch"),
        ("curation", "baseline_test_sha256", "Parent baseline test checksum mismatch"),
    ],
)
def test_successive_corrupted_parent_manifest_rejected(
    successive_case, section, field, error
):
    case = successive_case
    path = case["parent_dir"] / "squad_manifest.json"
    manifest = json.loads(path.read_text())
    target = manifest["curation"] if section == "curation" else manifest["splits"][section]
    target[field] = "0" * 64
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match=error):
        run_successive(case)
    assert not case["output_dir"].exists()


def test_successive_parent_test_must_match_original_even_with_updated_hash(successive_case):
    case = successive_case
    test_path = case["parent_dir"] / "squad_test.jsonl"
    test_path.write_bytes(test_path.read_bytes() + b"\n")
    manifest_path = case["parent_dir"] / "squad_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["splits"]["test"]["sha256"] = sha256(test_path)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="Parent held-out test differs from baseline"):
        run_successive(case)
    assert not case["output_dir"].exists()


@pytest.mark.parametrize("invalid", ["omitted_history", "unknown", "heldout", "no_new"])
def test_successive_invalid_exclusions_rejected(successive_case, invalid):
    case = successive_case
    config = case["config"]
    if invalid == "omitted_history":
        # Avoid the challenge-candidate guard so the cumulative guard is tested.
        old_id = next(iter(case["excluded_ids"] - set(
            config["false_premise_challenge_candidates"]
        )))
        del config["excluded_ids"][old_id]
        error = "Cumulative exclusions omit prior exclusions"
    elif invalid == "unknown":
        config["excluded_ids"]["squad_v2:unknown"] = "Unknown record"
        error = "Exclusions contain unknown historical IDs"
    elif invalid == "heldout":
        config["excluded_ids"][case["original_test"][0]["id"]] = "Test record"
        error = "Exclusion list contains held-out test IDs"
    else:
        for record_id in case["newly_excluded_ids"]:
            del config["excluded_ids"][record_id]
        error = "No newly excluded parent examples"
    save_exclusion_config(case, config)
    with pytest.raises(ValueError, match=error):
        run_successive(case)
    assert not case["output_dir"].exists()


@pytest.mark.parametrize(
    "invalid",
    ["missing", "null", "string", "non_string", "duplicate", "empty",
     "missing_survivor", "unknown", "excluded", "heldout"],
)
def test_successive_invalid_approved_retained_list_rejected(successive_case, invalid):
    case = successive_case
    config = case["config"]
    approved = config["approved_retained_ids"]
    error = "Approved retained IDs mismatch parent survivors"
    if invalid in {"missing", "null", "string", "non_string"}:
        error = "Successive curation requires approved_retained_ids list"
        if invalid == "missing":
            del config["approved_retained_ids"]
        else:
            config["approved_retained_ids"] = {
                "null": None, "string": approved[0], "non_string": [123],
            }[invalid]
    elif invalid == "duplicate":
        approved.append(approved[0])
        error = "Duplicate approved retained IDs"
    elif invalid == "empty":
        config["approved_retained_ids"] = []
    elif invalid == "missing_survivor":
        approved.pop()
    else:
        approved.append({
            "unknown": "squad_v2:unknown",
            "excluded": sorted(case["newly_excluded_ids"])[0],
            "heldout": case["original_test"][0]["id"],
        }[invalid])
    save_exclusion_config(case, config)
    with pytest.raises(ValueError, match=error):
        run_successive(case)
    assert not case["output_dir"].exists()


def test_successive_newly_rejected_ids_cannot_be_resampled(
    successive_case, mock_squad_dataset, monkeypatch
):
    case = successive_case
    # Give rejected IDs fresh sources/contexts so those filters cannot mask
    # a regression in historical-ID blocking. No valid candidates remain.
    rejected = [
        {**row, "title": f"Fresh_{row['id']}", "context": f"Fresh evidence {row['id']}"}
        for row in mock_squad_dataset
        if f"squad_v2:{row['id']}" in case["newly_excluded_ids"]
    ]
    assert len(rejected) == 6
    monkeypatch.setattr(build_eval, "load_dataset", lambda *a, **k: rejected)
    with pytest.raises(ValueError, match="Insufficient eligible replacement examples"):
        run_successive(case)
    assert not case["output_dir"].exists()


def test_successive_source_and_context_isolation(
    successive_case, mock_squad_dataset, monkeypatch
):
    case = successive_case
    test_ids = {r["id"] for r in case["original_test"]}
    test_rows = [row for row in mock_squad_dataset
                 if f"squad_v2:{row['id']}" in test_ids and not row["answers"]["text"]]
    # Fresh IDs and contexts on held-out articles must still be blocked.
    source_traps = [
        {**row, "id": f"source_trap_{i}", "context": f"New context {i}"}
        for i, row in enumerate(test_rows)
    ]
    # Fresh IDs and articles with held-out contexts must also be blocked.
    context_traps = [
        {**row, "id": f"context_trap_{i}", "title": f"New article {i}"}
        for i, row in enumerate(test_rows)
    ]
    traps = source_traps + context_traps
    monkeypatch.setattr(build_eval, "load_dataset", lambda *a, **k: traps)
    with pytest.raises(ValueError, match="Insufficient eligible replacement examples"):
        run_successive(case)
    assert not case["output_dir"].exists()

    monkeypatch.setattr(
        build_eval, "load_dataset", lambda *a, **k: traps + mock_squad_dataset
    )
    run_successive(case)
    dev = read_jsonl(case["output_dir"] / "squad_dev.jsonl")
    test = case["original_test"]
    for field in ("id", "source_id", "context"):
        assert {r[field] for r in dev}.isdisjoint(r[field] for r in test)
    assert {r["id"] for r in dev}.isdisjoint(f"squad_v2:{r['id']}" for r in traps)


@pytest.mark.parametrize("target", ["parent_dir", "baseline_dir", "existing_output"])
def test_successive_outputs_cannot_be_overwritten(successive_case, target):
    case = successive_case
    if target == "existing_output":
        # An existing first-round curated artifact at a different directory
        # must be protected by the output-file guard as well.
        run_curation(case, output_dir=case["output_dir"],
                     exclusions_path=case["exclusions_path"].parent / "exclusions.json")
        output_dir = case["output_dir"]
        error_type = FileExistsError
        message = "Outputs already exist"
    else:
        output_dir = case[target]
        error_type = ValueError
        message = "directories must differ"
    before = artifact_bytes(output_dir)
    with pytest.raises(error_type, match=message):
        run_successive(case, output_dir=output_dir)
    assert artifact_bytes(output_dir) == before


def test_successive_manifest_lineage_and_provenance(successive_case, monkeypatch):
    case = successive_case
    loader = build_eval.load_dataset
    calls = []

    def checked_loader(name, split, revision):
        calls.append((name, split, revision))
        return loader(name, split, revision)

    monkeypatch.setattr(build_eval, "load_dataset", checked_loader)
    manifest = run_successive(case)
    assert calls == [("rajpurkar/squad_v2", "validation", PINNED_REVISION)]
    assert manifest == json.loads((case["output_dir"] / "squad_manifest.json").read_text())
    assert manifest["source_revision"] == PINNED_REVISION
    assert manifest["seed"] == 42
    curation = manifest["curation"]
    assert curation["parent_version"] == "curated_v1"
    for field, directory, filename in [
        ("parent_manifest_sha256", "parent_dir", "squad_manifest.json"),
        ("parent_dev_sha256", "parent_dir", "squad_dev.jsonl"),
        ("baseline_manifest_sha256", "baseline_dir", "squad_manifest.json"),
        ("baseline_dev_sha256", "baseline_dir", "squad_dev.jsonl"),
        ("baseline_test_sha256", "baseline_dir", "squad_test.jsonl"),
    ]:
        assert curation[field] == sha256(case[directory] / filename)
    assert curation["exclusion_file_sha256"] == sha256(case["exclusions_path"])
    assert curation["excluded_ids"] == sorted(case["config"]["excluded_ids"])
    assert curation["excluded_count"] == 16
    assert curation["newly_excluded_ids"] == sorted(case["newly_excluded_ids"])
    assert curation["newly_excluded_count"] == 6
    assert curation["retained_dev_count"] == 14
    assert curation["replacement_count"] == 6
    assert curation["retained_dev_ids"] == case["config"]["approved_retained_ids"]
    assert curation["guideline_version"] == "0.2"
    assert curation["approval_status"] == "project_owner_approved"
    assert curation["independent_double_review"] is False
    assert curation["status"] == "replacement_candidates_pending_review"
    assert manifest["splits"]["dev"]["review_status"] == "pending_replacement_audit"
    for split in ("dev", "test"):
        assert manifest["splits"][split]["sha256"] == sha256(
            case["output_dir"] / f"squad_{split}.jsonl"
        )
