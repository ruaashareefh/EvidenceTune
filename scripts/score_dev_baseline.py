
"""Score the 20-example EvidenceTune development baseline."""

from pathlib import Path

from scripts.score_smoke import (
    load_jsonl,
    validate_reviews,
    score_predictions,
    print_results,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]

PREDICTIONS_PATH = (
    PROJECT_ROOT / "reports/baseline/dev_20_predictions.jsonl"
)

REVIEWS_PATH = (
    PROJECT_ROOT / "reports/baseline/dev_20_reviews.jsonl"
)


def main() -> None:
    """Score saved development predictions against reviewed labels."""

    # 1. Load predictions and reviews.
    predictions = load_jsonl(PREDICTIONS_PATH)
    reviews = load_jsonl(REVIEWS_PATH)

    # 2. Validate the expected dataset size.
    if len(predictions) != 20:
        raise ValueError(
            f"Expected 20 predictions, found {len(predictions)}"
        )

    # 3. Match records and validate labels.
    reviews_by_id = validate_reviews(
        predictions,
        reviews,
    )

    print(f"Loaded {len(predictions)} predictions")
    print(f"Validated {len(reviews)} review records")

    # 4. Calculate metrics.
    results = score_predictions(
        predictions,
        reviews_by_id,
    )

    # 5. Display results.
    print_results(results, len(predictions))


if __name__ == "__main__":
    main()
