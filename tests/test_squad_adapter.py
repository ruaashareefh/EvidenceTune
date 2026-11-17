
import copy

import pytest
from pydantic import ValidationError

from src.data.adapters.squad_v2 import adapt_squad_example
from src.data.schema import EvidenceExample


@pytest.fixture
def squad_example():
    """A valid, answerable SQuAD 2.0 record."""
    return {
        "id": "abc123",
        "title": "Normans",
        "context": "Normandy is a region in France.",
        "question": "Where is Normandy located?",
        "answers": {
            "text": ["France", "France"],
            "answer_start": [24, 24],
        },
    }


def test_answerable_conversion(squad_example):
    """An answerable record should map correctly."""
    result = adapt_squad_example(squad_example)

    assert isinstance(result, EvidenceExample)
    assert result.id == "squad_v2:abc123"
    assert result.context == squad_example["context"]
    assert result.question == squad_example["question"]
    assert result.answer == "France"
    assert result.answerable is True
    assert result.category == "answerable"


@pytest.mark.parametrize(
    "answers",
    [
        [],
        ["", "   "],
    ],
)
def test_unanswerable_conversion(squad_example, answers):
    """Missing answers should produce an unanswerable record."""
    squad_example["answers"]["text"] = answers

    result = adapt_squad_example(squad_example)

    assert result.answerable is False
    assert result.category == "unanswerable"
    assert "does not contain enough information" in result.answer


def test_multiple_reference_answers(squad_example):
    """Use the first nonempty reference answer."""
    squad_example["answers"]["text"] = [
        "",
        "  France  ",
        "French Republic",
    ]

    result = adapt_squad_example(squad_example)

    assert result.answer == "France"


def test_same_article_source_id(squad_example):
    """Questions from the same article must share a source ID."""
    second_example = copy.deepcopy(squad_example)

    second_example["id"] = "xyz456"
    second_example["question"] = "What is Normandy?"

    result1 = adapt_squad_example(squad_example)
    result2 = adapt_squad_example(second_example)

    assert result1.source_id == result2.source_id
    assert result1.id != result2.id


def test_different_article_source_id(squad_example):
    """Different article titles should create different source IDs."""
    second_example = copy.deepcopy(squad_example)
    second_example["title"] = "Roman Empire"

    result1 = adapt_squad_example(squad_example)
    result2 = adapt_squad_example(second_example)

    assert result1.source_id != result2.source_id


def test_deterministic_conversion(squad_example):
    """Identical input must always produce identical output."""
    result1 = adapt_squad_example(squad_example)
    result2 = adapt_squad_example(squad_example)

    assert result1.model_dump() == result2.model_dump()


def test_input_not_modified(squad_example):
    """The adapter must not mutate the original dataset record."""
    original = copy.deepcopy(squad_example)

    adapt_squad_example(squad_example)

    assert squad_example == original


@pytest.mark.parametrize(
    "missing_field",
    ["id", "title", "context", "question", "answers"],
)
def test_missing_source_fields(squad_example, missing_field):
    """Missing required SQuAD fields should raise an error."""
    del squad_example[missing_field]

    with pytest.raises(KeyError):
        adapt_squad_example(squad_example)


@pytest.mark.parametrize("field", ["context", "question"])
def test_empty_required_fields(squad_example, field):
    """Empty required strings must fail Pydantic validation."""
    squad_example[field] = ""

    with pytest.raises(ValidationError):
        adapt_squad_example(squad_example)
