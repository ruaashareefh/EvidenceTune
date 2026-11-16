import json

import pytest
from pydantic import ValidationError

from src.data.schema import EvidenceExample
from scripts.validate_dataset import validate_dataset


@pytest.fixture
def valid_example():
    return {
        "id": "001",
        "source_id": "doc_01",
        "context": "Orion Labs was founded in 2019.",
        "question": "When was Orion Labs founded?",
        "answer": "2019.",
        "answerable": True,
        "category": "answerable",
    }


def test_valid_example(valid_example):
    example = EvidenceExample(**valid_example)

    assert example.id == "001"
    assert example.category == "answerable"



def test_invalid_category(valid_example):
    valid_example["category"] = "unknown"

    with pytest.raises(ValidationError):
        EvidenceExample(**valid_example)


def test_inconsistent_labels(valid_example):
    valid_example["answerable"] = False
    valid_example["category"] = "answerable"

    with pytest.raises(
        ValidationError,
        match="answerable must match category"
    ):
        EvidenceExample(**valid_example)



@pytest.mark.parametrize(
    "field",
    ["id", "source_id", "context", "question", "answer"]
)
def test_empty_required_field(valid_example, field):
    valid_example[field] = ""

    with pytest.raises(ValidationError):
        EvidenceExample(**valid_example)


def test_duplicate_ids(valid_example, tmp_path):
    record1 = valid_example.copy()
    record2 = {
        **valid_example,
        "question": "Where was Orion Labs founded?"
    }

    file_path = tmp_path / "examples.jsonl"

    file_path.write_text(
        json.dumps(record1) + "\n" +
        json.dumps(record2) + "\n",
        encoding="utf-8"
    )

    with pytest.raises(ValueError, match="Duplicate ID"):
        validate_dataset(str(file_path))

def test_unexpected_field(valid_example):
    valid_example["unexpected_field"] = "hello"

    with pytest.raises(ValidationError):
        EvidenceExample(**valid_example)


def test_missing_required_field(valid_example):
    del valid_example["source_id"]

    with pytest.raises(ValidationError):
        EvidenceExample(**valid_example)


