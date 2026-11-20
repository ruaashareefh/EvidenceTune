
"""Score saved Qwen3-1.7B predictions using manual reviews."""

import json
from pathlib import Path

from src.evaluation.metrics import (
    aucm_counts,
    aucm_precision,
    aucm_recall,
    aucm_f1,
    abstention_counts,
    abstention_precision,
    abstention_recall,
    token_f1,
)


# =========================================================
# 1. FILE PATHS
# =========================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

PREDICTIONS_PATH = (
    PROJECT_ROOT / "reports/baseline/smoke_5_predictions.jsonl"
)

REVIEWS_PATH = (
    PROJECT_ROOT / "reports/baseline/smoke_5_reviews.jsonl"
)


# =========================================================
# 2. LOAD JSONL FILES
# =========================================================

def load_jsonl(path: Path) -> list[dict]:
    """Load a JSONL file into a list of dictionaries."""
    records = []

    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue

            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSON at {path}:{line_number}"
                ) from exc

            if not isinstance(record, dict):
                raise ValueError(
                    f"Expected JSON object at {path}:{line_number}"
                )

            records.append(record)

    return records


# =========================================================
# 3. MATCH PREDICTIONS WITH REVIEWS
# =========================================================

def index_by_id(records: list[dict]) -> dict[str, dict]:
    """Index records by example ID, rejecting duplicates."""
    indexed = {}

    for record in records:
        example_id = record["example_id"]

        if example_id in indexed:
            raise ValueError(
                f"Duplicate example ID: {example_id}"
            )

        indexed[example_id] = record

    return indexed


def validate_reviews(
    predictions: list[dict],
    reviews: list[dict],
) -> dict[str, dict]:
    """Check IDs, labels, and abstention consistency."""

    predictions_by_id = index_by_id(predictions)
    reviews_by_id = index_by_id(reviews)

    prediction_ids = set(predictions_by_id)
    review_ids = set(reviews_by_id)

    missing = prediction_ids - review_ids
    extra = review_ids - prediction_ids

    if missing:
        raise ValueError(
            f"Missing reviews for: {sorted(missing)}"
        )

    if extra:
        raise ValueError(
            f"Reviews without predictions: {sorted(extra)}"
        )

    for prediction in predictions:
        example_id = prediction["example_id"]
        review = reviews_by_id[example_id]

        for field in (
            "predicted_abstain",
            "answer_correct",
            "grounded",
        ):
            if type(review[field]) is not bool:
                raise ValueError(
                    f"{example_id}: {field} must be a boolean"
                )

        if type(prediction["gold_answerable"]) is not bool:
            raise ValueError(
                f"{example_id}: gold_answerable must be a boolean"
            )

        # EvidenceTune's explicit abstention convention:
        # The complete model response must be "ABSTAIN".
        detected_abstain = (
            prediction["prediction"].strip().upper()
            == "ABSTAIN"
        )

        if review["predicted_abstain"] != detected_abstain:
            raise ValueError(
                f"{example_id}: Review abstention label "
                "does not match the model response."
            )

    return reviews_by_id


# =========================================================
# 4. CALCULATE METRICS
# =========================================================

def score_predictions(
    predictions: list[dict],
    reviews_by_id: dict[str, dict],
) -> dict:
    """Calculate AUCM, abstention, and answer quality metrics."""

    gold_answerable = [
        prediction["gold_answerable"]
        for prediction in predictions
    ]

    predicted_abstain = [
        reviews_by_id[prediction["example_id"]]["predicted_abstain"]
        for prediction in predictions
    ]

    answer_correct = [
        reviews_by_id[prediction["example_id"]]["answer_correct"]
        for prediction in predictions
    ]

    # AUCM metrics
    aucm = aucm_counts(
        gold_answerable,
        predicted_abstain,
        answer_correct,
    )

    # Abstention metrics
    abstention = abstention_counts(
        gold_answerable,
        predicted_abstain,
    )

    # Token F1 on answerable examples only.
    # Unnecessary abstentions receive zero answer credit.
    token_scores = []

    for prediction, abstained in zip(
        predictions,
        predicted_abstain,
        strict=True,
    ):
        if not prediction["gold_answerable"]:
            continue

        if abstained:
            score = 0.0
        else:
            score = token_f1(
                prediction["prediction"],
                prediction["reference_answer"],
            )

        token_scores.append(score)

    mean_token_f1 = (
        sum(token_scores) / len(token_scores)
        if token_scores
        else 0.0
    )

    return {
        "aucm_counts": aucm,
        "aucm_precision": aucm_precision(aucm),
        "aucm_recall": aucm_recall(aucm),
        "aucm_f1": aucm_f1(aucm),
        "abstention_counts": abstention,
        "abstention_precision": abstention_precision(abstention),
        "abstention_recall": abstention_recall(abstention),
        "mean_answerable_token_f1": mean_token_f1,
    }


# =========================================================
# 5. PRINT RESULTS
# =========================================================

def print_results(results: dict, num_examples: int) -> None:
    """Display the evaluation summary."""

    print("\n" + "=" * 55)
    print("EVIDENCETUNE: QWEN BASELINE EVALUATION")
    print("=" * 55)

    print(f"\nExamples evaluated: {num_examples}")

    print("\nAUCM")
    print("Counts:", results["aucm_counts"])
    print(f"Precision: {results['aucm_precision']:.4f}")
    print(f"Recall:    {results['aucm_recall']:.4f}")
    print(f"F1:        {results['aucm_f1']:.4f}")

    print("\nABSTENTION")
    print("Counts:", results["abstention_counts"])
    print(f"Precision: {results['abstention_precision']:.4f}")
    print(f"Recall:    {results['abstention_recall']:.4f}")

    print("\nANSWER QUALITY")
    print(
        "Mean answerable token F1: "
        f"{results['mean_answerable_token_f1']:.4f}"
    )

    print("\n" + "=" * 55)


# =========================================================
# 6. MAIN
# =========================================================

def main():
    # Load saved files.
    predictions = load_jsonl(PREDICTIONS_PATH)
    reviews = load_jsonl(REVIEWS_PATH)

    if not predictions:
        raise ValueError("No predictions found")

    # Match predictions with manual reviews.
    reviews_by_id = validate_reviews(predictions, reviews)

    print(f"Loaded {len(predictions)} predictions")
    print(f"Validated {len(reviews)} manual reviews")

    # Calculate evaluation metrics.
    results = score_predictions(
        predictions,
        reviews_by_id,
    )

    # Display results.
    print_results(results, len(predictions))


if __name__ == "__main__":
    main()
