
from datasets import load_dataset

from src.data.adapters.squad_v2 import adapt_squad_example


def main():
    dataset = load_dataset(
        "rajpurkar/squad_v2",
        split="validation",
    )

    # Test one answerable example
    answerable = next(
        row for row in dataset
        if len(row["answers"]["text"]) > 0
    )

    # Test one unanswerable example
    unanswerable = next(
        row for row in dataset
        if len(row["answers"]["text"]) == 0
    )

    for row in [answerable, unanswerable]:
        converted = adapt_squad_example(row)

        print("\n--- Converted Example ---")
        print(converted.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
