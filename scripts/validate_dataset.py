
import json
from pathlib import Path
from pydantic import ValidationError
from src.data.schema import EvidenceExample

def validate_dataset(path: str):
    records = []
    seen_ids = set()

    with Path(path).open(encoding="utf-8") as f:
        for line_number, line in enumerate(f, 1):
            if not line.strip():
                continue

            try:
                record = EvidenceExample.model_validate_json(line)
            except ValidationError as e:
                raise ValueError(
                    f"Invalid record at line {line_number}"
                ) from e

            if record.id in seen_ids:
                raise ValueError(
                    f"Duplicate ID: {record.id}"
                )

            seen_ids.add(record.id)
            records.append(record)

    return records


if __name__ == "__main__":
    records = validate_dataset("data/raw/examples.jsonl")
    print(f"Validated {len(records)} examples")
