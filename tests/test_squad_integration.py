import os

import pytest
from datasets import load_dataset

from src.data.adapters.squad_v2 import adapt_squad_example
from src.data.schema import EvidenceExample


# Explicit opt-in prevents unexpected dataset downloads
# during normal unit test runs.
pytestmark = pytest.mark.skipif(
    os.getenv("RUN_SQUAD_INTEGRATION") != "1",
    reason="Set RUN_SQUAD_INTEGRATION=1 to run integration tests",
)


@pytest.fixture(scope="module")
def squad_dataset():
    """Load the real SQuAD 2.0 validation split once."""
    return load_dataset(
        "rajpurkar/squad_v2",
        split="validation",
    )


@pytest.fixture(scope="module")
def sample_examples(squad_dataset):
    """Select 10 answerable and 10 unanswerable records."""
    answerable = []
    unanswerable = []

    for example in squad_dataset:
        if example["answers"]["text"]:
            if len(answerable) < 10:
                answerable.append(example)
        else:
            if len(unanswerable) < 10:
                unanswerable.append(example)

        if len(answerable) == 10 and len(unanswerable) == 10:
            break

    assert len(answerable) == 10
    assert len(unanswerable) == 10

    return answerable + unanswerable


def test_real_dataset_conversion(sample_examples):
    """Every sampled record should pass schema validation."""
    for example in sample_examples:
        result = adapt_squad_example(example)

        assert isinstance(result, EvidenceExample)
        assert result.id == f"squad_v2:{example['id']}"
        assert result.context == example["context"]
        assert result.question == example["question"]


def test_real_answerability_labels(sample_examples):
    """Converted labels must match SQuAD ground truth."""
    for example in sample_examples:
        result = adapt_squad_example(example)

        expected = bool(example["answers"]["text"])

        assert result.answerable is expected
        assert result.category == (
            "answerable" if expected else "unanswerable"
        )


def test_real_reference_answers(sample_examples):
    """Answerable records should preserve the first valid answer."""
    for example in sample_examples:
        if not example["answers"]["text"]:
            continue

        result = adapt_squad_example(example)

        expected_answer = next(
            answer.strip()
            for answer in example["answers"]["text"]
            if answer.strip()
        )

        assert result.answer == expected_answer


def test_real_unanswerable_responses(sample_examples):
    """Unanswerable records must receive an abstention."""
    for example in sample_examples:
        if example["answers"]["text"]:
            continue

        result = adapt_squad_example(example)

        assert result.answerable is False
        assert result.category == "unanswerable"
        assert result.answer.strip()


def test_real_source_grouping(squad_dataset):
    """Questions from one article must share a source ID."""
    first = squad_dataset[0]

    second = next(
        example
        for example in squad_dataset
        if (
            example["title"] == first["title"]
            and example["id"] != first["id"]
        )
    )

    result1 = adapt_squad_example(first)
    result2 = adapt_squad_example(second)

    assert result1.source_id == result2.source_id
    assert result1.id != result2.id


def test_real_conversion_determinism(squad_dataset):
    """Repeated conversions must produce identical records."""
    example = squad_dataset[0]

    result1 = adapt_squad_example(example)
    result2 = adapt_squad_example(example)

    assert result1.model_dump() == result2.model_dump()
