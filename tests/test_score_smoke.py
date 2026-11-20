
"""Unit tests for the EvidenceTune baseline scoring pipeline."""

import json

import pytest

from scripts import score_smoke


# =========================================================
# 1. TEST FIXTURES
# =========================================================

@pytest.fixture
def predictions():
    """Four synthetic predictions covering all AUCM outcomes."""
    return [
        {
            "example_id": "a1",
            "gold_answerable": True,
            "prediction": "force",
            "reference_answer": "force",
        },
        {
            "example_id": "u1",
            "gold_answerable": False,
            "prediction": "Catholicism.",
            "reference_answer": (
                "The provided context does not contain "
                "enough information to answer the question."
            ),
        },
        {
            "example_id": "a2",
            "gold_answerable": True,
            "prediction": "  abstain  ",
            "reference_answer": "wave speeds",
        },
        {
            "example_id": "u2",
            "gold_answerable": False,
            "prediction": "ABSTAIN",
            "reference_answer": (
                "The provided context does not contain "
                "enough information to answer the question."
            ),
        },
    ]


@pytest.fixture
def reviews():
    """Manual reviews corresponding to the four predictions."""
    return [
        {
            "example_id": "a1",
            "predicted_abstain": False,
            "answer_correct": True,
            "grounded": True,
        },
        {
            "example_id": "u1",
            "predicted_abstain": False,
            "answer_correct": False,
            "grounded": False,
        },
        {
            "example_id": "a2",
            "predicted_abstain": True,
            "answer_correct": False,
            "grounded": False,
        },
        {
            "example_id": "u2",
            "predicted_abstain": True,
            "answer_correct": False,
            "grounded": False,
        },
    ]


def write_jsonl(path, records):
    """Write test records to a temporary JSONL file."""
    with path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record) + "\n")


# =========================================================
# 2. JSONL LOADING
# =========================================================

def test_load_jsonl(tmp_path):
    """Load valid JSONL records."""
    path = tmp_path / "test.jsonl"

    records = [
        {"example_id": "a1"},
        {"example_id": "a2"},
    ]

    write_jsonl(path, records)

    result = score_smoke.load_jsonl(path)

    assert result == records
    assert len(result) == 2


def test_load_jsonl_skips_blank_lines(tmp_path):
    """Blank lines should be ignored."""
    path = tmp_path / "test.jsonl"

    path.write_text(
        '{"example_id": "a1"}\n'
        '\n'
        '{"example_id": "a2"}\n',
        encoding="utf-8",
    )

    result = score_smoke.load_jsonl(path)

    assert len(result) == 2


def test_load_jsonl_invalid_json(tmp_path):
    """Malformed JSON must raise ValueError."""
    path = tmp_path / "invalid.jsonl"

    path.write_text(
        '{"example_id": "a1"\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Invalid JSON"):
        score_smoke.load_jsonl(path)


def test_load_jsonl_rejects_non_objects(tmp_path):
    """Each JSONL record must be a JSON object."""
    path = tmp_path / "invalid.jsonl"

    path.write_text(
        '["a1", "a2"]\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Expected JSON object"):
        score_smoke.load_jsonl(path)


def test_load_jsonl_empty_file(tmp_path):
    """An empty file should return an empty list."""
    path = tmp_path / "empty.jsonl"
    path.write_text("", encoding="utf-8")

    assert score_smoke.load_jsonl(path) == []


# =========================================================
# 3. INDEXING BY EXAMPLE ID
# =========================================================

def test_index_by_id(predictions):
    """Records should be accessible by example ID."""
    indexed = score_smoke.index_by_id(predictions)

    assert len(indexed) == 4
    assert indexed["a1"]["prediction"] == "force"
    assert indexed["u2"]["prediction"] == "ABSTAIN"


def test_index_by_id_duplicate():
    """Duplicate example IDs must be rejected."""
    records = [
        {"example_id": "a1"},
        {"example_id": "a1"},
    ]

    with pytest.raises(ValueError, match="Duplicate example ID"):
        score_smoke.index_by_id(records)


# =========================================================
# 4. REVIEW VALIDATION
# =========================================================

def test_validate_reviews_valid(predictions, reviews):
    """Matching predictions and reviews should validate."""
    result = score_smoke.validate_reviews(
        predictions,
        reviews,
    )

    assert len(result) == 4
    assert result["a1"]["answer_correct"] is True


def test_validate_reviews_reordered(predictions, reviews):
    """Review order must not affect matching."""
    reversed_reviews = list(reversed(reviews))

    result = score_smoke.validate_reviews(
        predictions,
        reversed_reviews,
    )

    assert result["a1"]["answer_correct"] is True
    assert result["u1"]["answer_correct"] is False


def test_validate_reviews_missing(predictions, reviews):
    """Every prediction must have exactly one review."""
    incomplete_reviews = reviews[:-1]

    with pytest.raises(ValueError, match="Missing reviews"):
        score_smoke.validate_reviews(
            predictions,
            incomplete_reviews,
        )


def test_validate_reviews_extra(predictions, reviews):
    """Reviews without corresponding predictions are invalid."""
    extra_reviews = reviews + [
        {
            "example_id": "unknown",
            "predicted_abstain": False,
            "answer_correct": False,
            "grounded": False,
        }
    ]

    with pytest.raises(ValueError, match="Reviews without predictions"):
        score_smoke.validate_reviews(
            predictions,
            extra_reviews,
        )


def test_validate_reviews_duplicate_prediction(predictions, reviews):
    """Duplicate prediction IDs must be rejected."""
    duplicate_predictions = predictions + [predictions[0].copy()]

    with pytest.raises(ValueError, match="Duplicate example ID"):
        score_smoke.validate_reviews(
            duplicate_predictions,
            reviews,
        )


def test_validate_reviews_duplicate_review(predictions, reviews):
    """Duplicate manual reviews must be rejected."""
    duplicate_reviews = reviews + [reviews[0].copy()]

    with pytest.raises(ValueError, match="Duplicate example ID"):
        score_smoke.validate_reviews(
            predictions,
            duplicate_reviews,
        )


@pytest.mark.parametrize(
    "field",
    [
        "predicted_abstain",
        "answer_correct",
        "grounded",
    ],
)
def test_validate_reviews_rejects_non_boolean(
    predictions,
    reviews,
    field,
):
    """Review labels must be actual booleans."""
    invalid_reviews = [review.copy() for review in reviews]

    invalid_reviews[0][field] = "false"

    with pytest.raises(ValueError, match="must be a boolean"):
        score_smoke.validate_reviews(
            predictions,
            invalid_reviews,
        )


def test_validate_reviews_invalid_gold_answerable(
    predictions,
    reviews,
):
    """Ground-truth answerability must be boolean."""
    invalid_predictions = [
        prediction.copy()
        for prediction in predictions
    ]

    invalid_predictions[0]["gold_answerable"] = "True"

    with pytest.raises(ValueError, match="must be a boolean"):
        score_smoke.validate_reviews(
            invalid_predictions,
            reviews,
        )


def test_validate_reviews_abstention_mismatch(
    predictions,
    reviews,
):
    """Review labels must agree with explicit ABSTAIN detection."""
    invalid_reviews = [review.copy() for review in reviews]

    invalid_reviews[0]["predicted_abstain"] = True

    with pytest.raises(
        ValueError,
        match="Review abstention label",
    ):
        score_smoke.validate_reviews(
            predictions,
            invalid_reviews,
        )


def test_validate_reviews_abstain_case_insensitive(
    predictions,
    reviews,
):
    """ABSTAIN detection should ignore case and outer whitespace."""
    result = score_smoke.validate_reviews(
        predictions,
        reviews,
    )

    # Example a2 predicts "  abstain  "
    assert result["a2"]["predicted_abstain"] is True


# =========================================================
# 5. METRIC CALCULATIONS
# =========================================================

def test_score_predictions_aucm(predictions, reviews):
    """Verify AUCM counts and derived metrics."""
    reviews_by_id = score_smoke.validate_reviews(
        predictions,
        reviews,
    )

    result = score_smoke.score_predictions(
        predictions,
        reviews_by_id,
    )

    assert result["aucm_counts"] == {
        "TP": 1,
        "FP": 1,
        "FN": 1,
        "TN": 1,
    }

    assert result["aucm_precision"] == pytest.approx(0.5)
    assert result["aucm_recall"] == pytest.approx(0.5)
    assert result["aucm_f1"] == pytest.approx(0.5)


def test_score_predictions_abstention(predictions, reviews):
    """Verify abstention counts and derived metrics."""
    reviews_by_id = score_smoke.validate_reviews(
        predictions,
        reviews,
    )

    result = score_smoke.score_predictions(
        predictions,
        reviews_by_id,
    )

    assert result["abstention_counts"] == {
        "TP": 1,
        "FP": 1,
        "FN": 1,
        "TN": 1,
    }

    assert result["abstention_precision"] == pytest.approx(0.5)
    assert result["abstention_recall"] == pytest.approx(0.5)


def test_score_predictions_token_f1(predictions, reviews):
    """
    Token F1 should use answerable questions only.

    a1: Correct prediction -> F1 = 1
    a2: Incorrect abstention -> F1 = 0
    u1 and u2: Excluded from answer-quality scoring

    Mean = (1 + 0) / 2 = 0.5
    """
    reviews_by_id = score_smoke.validate_reviews(
        predictions,
        reviews,
    )

    result = score_smoke.score_predictions(
        predictions,
        reviews_by_id,
    )

    assert result["mean_answerable_token_f1"] == pytest.approx(0.5)


def test_score_predictions_independent_of_review_order(
    predictions,
    reviews,
):
    """Metrics should not depend on the order of manual reviews."""
    first = score_smoke.score_predictions(
        predictions,
        score_smoke.validate_reviews(predictions, reviews),
    )

    second = score_smoke.score_predictions(
        predictions,
        score_smoke.validate_reviews(
            predictions,
            list(reversed(reviews)),
        ),
    )

    assert first == second


def test_score_predictions_no_answerable_examples():
    """Token F1 should be 0 when no answerable questions exist."""
    predictions = [
        {
            "example_id": "u1",
            "gold_answerable": False,
            "prediction": "ABSTAIN",
            "reference_answer": "",
        }
    ]

    reviews = [
        {
            "example_id": "u1",
            "predicted_abstain": True,
            "answer_correct": False,
            "grounded": False,
        }
    ]

    reviews_by_id = score_smoke.validate_reviews(
        predictions,
        reviews,
    )

    result = score_smoke.score_predictions(
        predictions,
        reviews_by_id,
    )

    assert result["mean_answerable_token_f1"] == 0.0


# =========================================================
# 6. OUTPUT FORMATTING
# =========================================================

def test_print_results(predictions, reviews, capsys):
    """Summary output should include the important metrics."""
    reviews_by_id = score_smoke.validate_reviews(
        predictions,
        reviews,
    )

    results = score_smoke.score_predictions(
        predictions,
        reviews_by_id,
    )

    score_smoke.print_results(results, num_examples=4)

    output = capsys.readouterr().out

    assert "EVIDENCETUNE" in output
    assert "Examples evaluated: 4" in output
    assert "AUCM" in output
    assert "ABSTENTION" in output
    assert "Mean answerable token F1" in output


# =========================================================
# 7. END-TO-END SCORING
# =========================================================

def test_main_end_to_end(
    tmp_path,
    monkeypatch,
    capsys,
    predictions,
    reviews,
):
    """
    Test the complete pipeline using temporary files.

    No model loading or inference is required.
    """
    predictions_path = tmp_path / "predictions.jsonl"
    reviews_path = tmp_path / "reviews.jsonl"

    write_jsonl(predictions_path, predictions)
    write_jsonl(reviews_path, reviews)

    monkeypatch.setattr(
        score_smoke,
        "PREDICTIONS_PATH",
        predictions_path,
    )

    monkeypatch.setattr(
        score_smoke,
        "REVIEWS_PATH",
        reviews_path,
    )

    score_smoke.main()

    output = capsys.readouterr().out

    assert "Loaded 4 predictions" in output
    assert "Validated 4 manual reviews" in output
    assert "Examples evaluated: 4" in output
    assert "F1:" in output


def test_main_rejects_empty_predictions(
    tmp_path,
    monkeypatch,
):
    """The scorer must reject an empty prediction file."""
    predictions_path = tmp_path / "predictions.jsonl"
    reviews_path = tmp_path / "reviews.jsonl"

    write_jsonl(predictions_path, [])
    write_jsonl(reviews_path, [])

    monkeypatch.setattr(
        score_smoke,
        "PREDICTIONS_PATH",
        predictions_path,
    )

    monkeypatch.setattr(
        score_smoke,
        "REVIEWS_PATH",
        reviews_path,
    )

    with pytest.raises(ValueError, match="No predictions found"):
        score_smoke.main()
