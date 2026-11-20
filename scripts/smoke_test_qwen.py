
"""Smoke test Qwen3-1.7B on five EvidenceTune examples."""

import json
from pathlib import Path

from src.inference.qwen import (
    MODEL_NAME,
    generate_answer,
    load_qwen,
)


# =========================================================
# 1. CONFIGURATION
# =========================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATASET_PATH = (
    PROJECT_ROOT / "data/eval/curated_v4/squad_dev.jsonl"
)

OUTPUT_PATH = (
    PROJECT_ROOT
    / "reports/baseline/smoke_5_refactor_predictions.jsonl"
)

MAX_NEW_TOKENS = 128


# =========================================================
# 2. LOAD EVALUATION EXAMPLES
# =========================================================

def load_examples() -> list[dict]:
    """Select 3 answerable and 2 unanswerable examples."""

    examples = []
    answerable_count = 0
    unanswerable_count = 0

    with DATASET_PATH.open("r", encoding="utf-8") as file:
        for line in file:
            example = json.loads(line)

            if example["answerable"] and answerable_count < 3:
                examples.append(example)
                answerable_count += 1

            elif not example["answerable"] and unanswerable_count < 2:
                examples.append(example)
                unanswerable_count += 1

            if answerable_count == 3 and unanswerable_count == 2:
                break

    if answerable_count != 3 or unanswerable_count != 2:
        raise ValueError(
            "Could not find 3 answerable and "
            "2 unanswerable examples."
        )

    return examples


# =========================================================
# 3. RUN INFERENCE
# =========================================================

def main() -> None:
    """Run Qwen inference and save five predictions."""

    # Prevent overwriting existing predictions.
    if OUTPUT_PATH.exists():
        raise FileExistsError(
            f"Output already exists: {OUTPUT_PATH}\n"
            "Use a new output filename to preserve previous results."
        )

    # Step 1: Load five curated examples.
    examples = load_examples()

    # Step 2: Load the tokenizer and model once.
    print(f"Loading {MODEL_NAME}...")

    tokenizer, model = load_qwen()

    predictions = []

    # Step 3: Run inference on each example.
    for index, example in enumerate(examples, start=1):

        print("\n" + "=" * 70)
        print(f"EXAMPLE {index}/{len(examples)}")
        print("=" * 70)

        print("\nEXAMPLE ID:")
        print(example["id"])

        print("\nCONTEXT:")
        print(example["context"])

        print("\nQUESTION:")
        print(example["question"])

        # Step 4: Generate the response using reusable inference.
        response = generate_answer(
            model=model,
            tokenizer=tokenizer,
            context=example["context"],
            question=example["question"],
            max_new_tokens=MAX_NEW_TOKENS,
        )

        # Step 5: Display model output.
        print("\nQWEN RESPONSE:")
        print(response)

        print("\nREFERENCE ANSWER:")
        print(example["answer"])

        print("\nANSWERABLE:")
        print(example["answerable"])

        # Step 6: Store prediction and metadata.
        predictions.append({
            "example_id": example["id"],
            "context": example["context"],
            "question": example["question"],
            "reference_answer": example["answer"],
            "gold_answerable": example["answerable"],
            "prediction": response,
            "model": MODEL_NAME,
            "enable_thinking": False,
            "do_sample": False,
            "max_new_tokens": MAX_NEW_TOKENS,
        })

    # Step 7: Save predictions after all five examples.
    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT_PATH.open("x", encoding="utf-8") as file:
        for record in predictions:
            file.write(
                json.dumps(record, ensure_ascii=False) + "\n"
            )

    print("\n" + "=" * 70)
    print("INFERENCE COMPLETE")
    print("=" * 70)

    print(f"Examples processed: {len(predictions)}")
    print(f"Predictions saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
