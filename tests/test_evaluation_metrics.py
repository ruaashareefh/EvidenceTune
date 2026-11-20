
"""Tests for EvidenceTune evaluation metrics."""

import pytest

from src.evaluation.metrics import (
    aucm_counts,
    aucm_precision,
    aucm_recall,
    aucm_f1,
    abstention_counts,
    abstention_precision,
    abstention_recall,
    normalize_answer,
    token_f1,
)


# =========================================================
# 1. AUCM CONFUSION MATRIX
# =========================================================

def test_aucm_mixed_outcomes():
    """Verify all five possible model outcomes."""
    result = aucm_counts(
        gold_answerable=[True, True, True, False, False],
        predicted_abstain=[False, False, True, False, True],
        answer_correct=[True, False, False, False, False],
    )

    assert result == {
        "TP": 1,
        "FP": 2,
        "FN": 1,
        "TN": 1,
    }


def test_aucm_all_correct():
    """All correctly answered questions count as TP."""
    result = aucm_counts(
        gold_answerable=[True] * 5,
        predicted_abstain=[False] * 5,
        answer_correct=[True] * 5,
    )

    assert result == {
        "TP": 5,
        "FP": 0,
        "FN": 0,
        "TN": 0,
    }


def test_aucm_always_abstains():
    """Abstentions count as FN or TN based on answerability."""
    result = aucm_counts(
        gold_answerable=[True, True, True, False, False],
        predicted_abstain=[True] * 5,
        answer_correct=[False] * 5,
    )

    assert result == {
        "TP": 0,
        "FP": 0,
        "FN": 3,
        "TN": 2,
    }


def test_aucm_all_incorrect():
    """Incorrect attempts on answerable questions count as FP."""
    result = aucm_counts(
        gold_answerable=[True] * 5,
        predicted_abstain=[False] * 5,
        answer_correct=[False] * 5,
    )

    assert result == {
        "TP": 0,
        "FP": 5,
        "FN": 0,
        "TN": 0,
    }


def test_aucm_unanswerable_attempts():
    """Attempting unanswerable questions counts as FP."""
    result = aucm_counts(
        gold_answerable=[False] * 4,
        predicted_abstain=[False] * 4,
        answer_correct=[False] * 4,
    )

    assert result == {
        "TP": 0,
        "FP": 4,
        "FN": 0,
        "TN": 0,
    }


def test_aucm_ignores_correctness_for_abstentions():
    """Answer correctness must not affect abstained examples."""
    first = aucm_counts(
        gold_answerable=[True, False],
        predicted_abstain=[True, True],
        answer_correct=[True, True],
    )

    second = aucm_counts(
        gold_answerable=[True, False],
        predicted_abstain=[True, True],
        answer_correct=[False, False],
    )

    assert first == second
    assert first == {
        "TP": 0,
        "FP": 0,
        "FN": 1,
        "TN": 1,
    }


def test_aucm_mismatched_lengths():
    """Reject inputs with different lengths."""
    with pytest.raises(
        ValueError,
        match="Input lists must have equal lengths",
    ):
        aucm_counts(
            gold_answerable=[True, False, True],
            predicted_abstain=[False, True],
            answer_correct=[True, False, True],
        )


def test_aucm_empty_inputs():
    """Empty inputs should return zero counts."""
    result = aucm_counts([], [], [])

    assert result == {
        "TP": 0,
        "FP": 0,
        "FN": 0,
        "TN": 0,
    }


# =========================================================
# 2. AUCM PRECISION
# =========================================================

def test_aucm_precision():
    """Precision = TP / (TP + FP)."""
    counts = {
        "TP": 7,
        "FP": 3,
        "FN": 2,
        "TN": 8,
    }

    assert aucm_precision(counts) == pytest.approx(0.7)


def test_aucm_precision_perfect():
    """No false positives gives precision of 1."""
    counts = {
        "TP": 10,
        "FP": 0,
        "FN": 0,
        "TN": 10,
    }

    assert aucm_precision(counts) == 1.0


def test_aucm_precision_zero_denominator():
    """Avoid division by zero when TP + FP = 0."""
    counts = {
        "TP": 0,
        "FP": 0,
        "FN": 3,
        "TN": 2,
    }

    assert aucm_precision(counts) == 0.0


# =========================================================
# 3. AUCM RECALL
# =========================================================

def test_aucm_recall():
    """Recall = TP / (TP + FN)."""
    counts = {
        "TP": 7,
        "FP": 3,
        "FN": 2,
        "TN": 8,
    }

    assert aucm_recall(counts) == pytest.approx(7 / 9)


def test_aucm_recall_perfect():
    """No false negatives gives recall of 1."""
    counts = {
        "TP": 10,
        "FP": 0,
        "FN": 0,
        "TN": 10,
    }

    assert aucm_recall(counts) == 1.0


def test_aucm_recall_zero_denominator():
    """Avoid division by zero when TP + FN = 0."""
    counts = {
        "TP": 0,
        "FP": 2,
        "FN": 0,
        "TN": 3,
    }

    assert aucm_recall(counts) == 0.0


# =========================================================
# 4. AUCM F1
# =========================================================

def test_aucm_f1_normal():
    """F1 is the harmonic mean of precision and recall."""
    counts = {
        "TP": 7,
        "FP": 3,
        "FN": 2,
        "TN": 8,
    }

    assert aucm_f1(counts) == pytest.approx(14 / 19)


def test_aucm_f1_perfect():
    """Perfect precision and recall give F1 = 1."""
    counts = {
        "TP": 10,
        "FP": 0,
        "FN": 0,
        "TN": 10,
    }

    assert aucm_f1(counts) == 1.0


def test_aucm_f1_zero():
    """No correct answers gives F1 = 0."""
    counts = {
        "TP": 0,
        "FP": 5,
        "FN": 3,
        "TN": 2,
    }

    assert aucm_f1(counts) == 0.0


def test_aucm_f1_all_abstain():
    """A model that always abstains has AUCM F1 = 0."""
    counts = {
        "TP": 0,
        "FP": 0,
        "FN": 10,
        "TN": 10,
    }

    assert aucm_f1(counts) == 0.0


def test_aucm_f1_empty():
    """Empty counts should not cause division by zero."""
    counts = {
        "TP": 0,
        "FP": 0,
        "FN": 0,
        "TN": 0,
    }

    assert aucm_f1(counts) == 0.0


def test_aucm_f1_ignores_tn():
    """True negatives do not appear in the F1 formula."""
    counts_a = {
        "TP": 5,
        "FP": 2,
        "FN": 3,
        "TN": 0,
    }

    counts_b = {
        "TP": 5,
        "FP": 2,
        "FN": 3,
        "TN": 100,
    }

    assert aucm_f1(counts_a) == aucm_f1(counts_b)


# =========================================================
# 5. AUCM END-TO-END EVALUATION
# =========================================================

def test_aucm_end_to_end():
    """Check that counts, precision, recall, and F1 agree."""
    counts = aucm_counts(
        gold_answerable=[True, True, True, False, False],
        predicted_abstain=[False, False, True, False, True],
        answer_correct=[True, False, False, False, False],
    )

    assert counts == {
        "TP": 1,
        "FP": 2,
        "FN": 1,
        "TN": 1,
    }

    assert aucm_precision(counts) == pytest.approx(1 / 3)
    assert aucm_recall(counts) == pytest.approx(1 / 2)
    assert aucm_f1(counts) == pytest.approx(2 / 5)

    assert sum(counts.values()) == 5


def test_aucm_realistic_development_set():
    """
    Simulate a balanced 20-example development set.

    Answerable (10):
        7 correct, 2 incorrect, 1 abstained.

    Unanswerable (10):
        8 abstained, 2 answered incorrectly.
    """
    gold_answerable = [True] * 10 + [False] * 10

    predicted_abstain = (
        [False] * 9
        + [True]
        + [True] * 8
        + [False] * 2
    )

    answer_correct = (
        [True] * 7
        + [False] * 13
    )

    counts = aucm_counts(
        gold_answerable,
        predicted_abstain,
        answer_correct,
    )

    assert counts == {
        "TP": 7,
        "FP": 4,
        "FN": 1,
        "TN": 8,
    }

    assert sum(counts.values()) == 20

    assert aucm_precision(counts) == pytest.approx(7 / 11)
    assert aucm_recall(counts) == pytest.approx(7 / 8)
    assert aucm_f1(counts) == pytest.approx(14 / 19)


# =========================================================
# 6. ABSTENTION METRICS
# =========================================================

def test_abstention_metrics():
    """Test abstention counts, precision, and recall."""
    counts = abstention_counts(
        gold_answerable=[True, True, True, False, False],
        predicted_abstain=[False, False, True, True, False],
    )

    assert counts == {
        "TP": 1,
        "FP": 1,
        "FN": 1,
        "TN": 2,
    }

    assert abstention_precision(counts) == pytest.approx(0.5)
    assert abstention_recall(counts) == pytest.approx(0.5)

    assert sum(counts.values()) == 5


def test_abstention_always_abstains():
    """All unanswerable questions are TP; answerable ones are FP."""
    counts = abstention_counts(
        gold_answerable=[True, True, True, False, False],
        predicted_abstain=[True] * 5,
    )

    assert counts == {
        "TP": 2,
        "FP": 3,
        "FN": 0,
        "TN": 0,
    }

    assert abstention_precision(counts) == pytest.approx(2 / 5)
    assert abstention_recall(counts) == 1.0
    assert sum(counts.values()) == 5


def test_abstention_never_abstains():
    """All unanswerable questions are FN; answerable ones are TN."""
    counts = abstention_counts(
        gold_answerable=[True, True, True, False, False],
        predicted_abstain=[False] * 5,
    )

    assert counts == {
        "TP": 0,
        "FP": 0,
        "FN": 2,
        "TN": 3,
    }

    assert abstention_precision(counts) == 0.0
    assert abstention_recall(counts) == 0.0
    assert sum(counts.values()) == 5


def test_abstention_mismatched_lengths():
    """Reject input lists with different lengths."""
    with pytest.raises(
        ValueError,
        match="Input lists must have equal lengths",
    ):
        abstention_counts(
            gold_answerable=[True, False, True],
            predicted_abstain=[False, True],
        )


# =========================================================
# 7. ANSWER NORMALIZATION
# =========================================================

@pytest.mark.parametrize(
    "text, expected",
    [
        ("The Eiffel Tower.", ["eiffel", "tower"]),
        ("A red car!", ["red", "car"]),
        ("THE, BIG DOG", ["big", "dog"]),
        ("  The   quick   fox  ", ["quick", "fox"]),
    ],
)
def test_normalize_answer(text, expected):
    """Verify lowercase, punctuation, and article normalization."""
    assert normalize_answer(text) == expected


# =========================================================
# 8. TOKEN-LEVEL F1
# =========================================================

@pytest.mark.parametrize(
    "prediction, reference, expected",
    [
        # Exact match
        ("red car", "red car", 1.0),

        # Partial overlap
        ("red sports car", "red car", 0.8),

        # No overlapping tokens
        ("blue", "red", 0.0),

        # Articles and capitalization
        ("The Eiffel Tower", "eiffel tower", 1.0),

        # Repeated tokens
        ("cat dog dog", "cat cat dog", 2 / 3),

        # Prediction is empty
        ("", "red car", 0.0),

        # Both answers empty
        ("", "", 1.0),

        # Punctuation
        ("Paris!", "paris", 1.0),

        # Multiple normalization steps
        ("THE, BIG DOG", "big dog", 1.0),
    ],
)
def test_token_f1(prediction, reference, expected):
    """Verify token F1 across standard and edge cases."""
    assert token_f1(prediction, reference) == pytest.approx(expected)


def test_token_f1_repeated_tokens():
    """Repeated words should be counted by occurrence."""
    prediction = "cat cat"
    reference = "cat cat cat"

    # Two matching tokens, two predicted, three reference.
    expected = 2 * 2 / (2 + 3)

    assert token_f1(prediction, reference) == pytest.approx(expected)


def test_token_f1_articles_only():
    """Answers containing only articles normalize to empty."""
    assert token_f1("the", "an") == 1.0


def test_token_f1_symmetry():
    """Token F1 should be symmetric."""
    prediction = "red sports car"
    reference = "red car"

    assert token_f1(prediction, reference) == pytest.approx(
        token_f1(reference, prediction)
    )


def test_token_f1_range():
    """Token F1 must remain between 0 and 1."""
    examples = [
        ("red car", "red car"),
        ("red sports car", "red car"),
        ("blue", "red"),
        ("", ""),
        ("cat cat cat", "cat"),
    ]

    for prediction, reference in examples:
        score = token_f1(prediction, reference)

        assert 0.0 <= score <= 1.0
