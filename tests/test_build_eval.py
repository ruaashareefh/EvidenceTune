
"""Tests for the EvidenceTune evaluation dataset pipeline."""

import hashlib
import json
from collections import Counter

import pytest

from src.data import build_eval
from src.data.schema import EvidenceExample


# ---------------------------------------------------------
# Fixtures
# ---------------------------------------------------------

@pytest.fixture
def mock_squad_dataset(monkeypatch):
    """Create SQuAD-like records without network access."""
    records = []

    for i in range(24):
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


def read_jsonl(path):
    """Read generated evaluation records."""
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def make_record(record_id, source_id, context="Some evidence."):
    """Create a valid EvidenceExample for validation tests."""
    return EvidenceExample(
        id=record_id,
        source_id=source_id,
        context=context,
        question="What is the answer?",
        answer="An answer.",
        answerable=True,
        category="answerable",
    )


# ---------------------------------------------------------
# Dataset construction
# ---------------------------------------------------------

def test_balanced_dataset(mock_squad_dataset, tmp_path):
    """Both splits must contain 10 examples per category."""
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
    """Development and test splits must not share source IDs."""
    build_eval.build_dataset(tmp_path, seed=42)

    dev = read_jsonl(tmp_path / "squad_dev.jsonl")
    test = read_jsonl(tmp_path / "squad_test.jsonl")

    dev_sources = {r["source_id"] for r in dev}
    test_sources = {r["source_id"] for r in test}

    assert dev_sources.isdisjoint(test_sources)

    all_ids = [r["id"] for r in dev + test]
    assert len(all_ids) == len(set(all_ids))


def test_reproducible_outputs(mock_squad_dataset, tmp_path):
    """Same seed and inputs must produce identical files."""
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
    """Manifest checksums must match actual file contents."""
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

        actual_hash = hashlib.sha256(
            path.read_bytes()
        ).hexdigest()

        assert manifest["splits"][name]["sha256"] == actual_hash
        assert manifest["splits"][name]["count"] == 20


# ---------------------------------------------------------
# Data integrity
# ---------------------------------------------------------

def test_duplicate_ids_rejected():
    """Duplicate record IDs must raise an error."""
    dev = [make_record("001", "source_a")]
    test = [make_record("001", "source_b")]

    with pytest.raises(ValueError, match="Duplicate example IDs"):
        build_eval.validate_splits(dev, test)


def test_source_leakage_rejected():
    """Overlapping source IDs must raise an error."""
    dev = [make_record("001", "shared_source")]
    test = [make_record("002", "shared_source")]

    with pytest.raises(ValueError, match="Source leakage"):
        build_eval.validate_splits(dev, test)


def test_duplicate_contexts_rejected():
    """Identical contexts must not cross splits."""
    dev = [make_record("001", "source_a", "Same context")]
    test = [make_record("002", "source_b", "Same context")]

    with pytest.raises(ValueError, match="Duplicate contexts"):
        build_eval.validate_splits(dev, test)


# ---------------------------------------------------------
# Failure handling
# ---------------------------------------------------------

def test_existing_outputs_protected(mock_squad_dataset, tmp_path):
    """Existing evaluation files must not be overwritten."""
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
    """Overwrite must work when explicitly requested."""
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
    """Requested category counts must be positive."""
    with pytest.raises(
        ValueError, match="per_category must be positive"
    ):
        build_eval.build_dataset(
            tmp_path,
            per_category=per_category,
        )


def test_insufficient_source_groups(
    mock_squad_dataset, monkeypatch, tmp_path
):
    """Reject datasets without enough groups for both splits."""
    small_dataset = mock_squad_dataset[:4]

    monkeypatch.setattr(
        build_eval,
        "load_dataset",
        lambda *args, **kwargs: small_dataset,
    )

    with pytest.raises(
        ValueError, match="Insufficient examples"
    ):
        build_eval.build_dataset(
            tmp_path,
            per_category=3,
        )
