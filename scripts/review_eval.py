
import argparse
import json
from pathlib import Path


def review_examples(path: Path, start: int, end: int):
    with path.open(encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]

    for i in range(start - 1, min(end, len(records))):
        record = records[i]

        print(f"\n{'=' * 60}")
        print(f"EXAMPLE {i + 1}")
        print(f"{'=' * 60}")
        print(f"ID: {record['id']}")
        print(f"Category: {record['category']}")
        print(f"\nCONTEXT:\n{record['context']}")
        print(f"\nQUESTION:\n{record['question']}")
        print(f"\nREFERENCE ANSWER:\n{record['answer']}")
        print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--end", type=int, default=5)
    args = parser.parse_args()

    review_examples(
        Path("data/eval/squad_dev.jsonl"),
        args.start,
        args.end,
    )
