
"""Run Qwen3-1.7B on all 20 curated development examples."""

import json
from pathlib import Path

from src.inference.qwen import (
    MODEL_NAME,
    generate_answer,
    load_qwen,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATASET_PATH = (
    PROJECT_ROOT / "data/eval/curated_v4/squad_dev.jsonl"
)

OUTPUT_PATH = (
    PROJECT_ROOT / "reports/baseline/dev_20_predictions.jsonl"
)

MAX_NEW_TOKENS = 128


def load_examples() -> list[dict]:
    """Load and validate the 20 development examples."""

    with DATASET_PATH.open("r", encoding="utf-8") as file:
        examples = [
            json.loads(line)
            for line in file
            if line.strip()
        ]

    if len(examples) != 20:
        raise ValueError(
            f"Expected 20 examples, found {len(examples)}"
        )

    ids = [example["id"] for example in examples]

    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate example IDs found")

    answerable = sum(
        example["answerable"] is True
        for example in examples
    )

    unanswerable = sum(
        example["answerable"] is False
        for example in examples
    )

    if answerable != 10 or unanswerable != 10:
        raise ValueError(
            "Expected 10 answerable and 10 unanswerable examples"
        )

    return examples


def main() -> None:
    """Generate and save the complete development baseline."""

    if OUTPUT_PATH.exists():
        raise FileExistsError(
            f"Output already exists: {OUTPUT_PATH}"
        )

    examples = load_examples()

    print(f"Loaded {len(examples)} development examples")
    print(f"Loading {MODEL_NAME}...")

    # Load the model only once.
    tokenizer, model = load_qwen()

    predictions = []

    for index, example in enumerate(examples, start=1):
        print("\n" + "=" * 70)
        print(f"EXAMPLE {index}/{len(examples)}")
        print("=" * 70)

        print("\nCONTEXT:")
        print(example["context"])

        print("\nQUESTION:")
        print(example["question"])

        # Ground-truth labels are NOT passed to Qwen.
        response = generate_answer(
            model=model,
            tokenizer=tokenizer,
            context=example["context"],
            question=example["question"],
            max_new_tokens=MAX_NEW_TOKENS,
        )

        print("\nQWEN RESPONSE:")
        print(response)

        print("\nREFERENCE:")
        print(example["answer"])

        print("\nANSWERABLE:")
        print(example["answerable"])

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

    # Save results without overwriting an earlier experiment.
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
    print("DEVELOPMENT BASELINE COMPLETE")
    print("=" * 70)

    print(f"Total predictions: {len(predictions)}")
    print(f"Saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
