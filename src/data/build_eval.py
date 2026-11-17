
"""Build reproducible SQuAD evaluation subsets for EvidenceTune."""

import argparse
import hashlib
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

from datasets import load_dataset

from src.data.adapters.squad_v2 import adapt_squad_example


DATASET_NAME = "rajpurkar/squad_v2"
SOURCE_SPLIT = "validation"
CATEGORIES = ("answerable", "unanswerable")


def group_by_article(dataset):
    """Group records to prevent article-level leakage."""
    groups = defaultdict(list)

    for record in dataset:
        groups[record["title"]].append(record)

    return groups


def sample_split(groups, start_index, per_category, rng):
    """
    Select balanced examples from distinct source groups.

    Each article contributes at most one example per category.
    Returns selected records and the next unused group index.
    """
    remaining = {category: per_category for category in CATEGORIES}
    selected = []
    index = start_index

    while any(remaining.values()) and index < len(groups):
        article_records = groups[index]
        index += 1

        # Stable ordering before randomized selection
        article_records = sorted(
            article_records, key=lambda row: row["id"]
        )

        for category in CATEGORIES:
            if remaining[category] == 0:
                continue

            candidates = [
                row for row in article_records
                if (
                    "answerable"
                    if row["answers"]["text"]
                    else "unanswerable"
                ) == category
            ]

            if not candidates:
                continue

            selected.append(rng.choice(candidates))
            remaining[category] -= 1

    if any(remaining.values()):
        raise ValueError(
            f"Insufficient examples for requested split: {remaining}"
        )

    return selected, index


def validate_splits(dev, test):
    """Check identifiers and source isolation."""
    all_records = dev + test
    ids = [record.id for record in all_records]

    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate example IDs detected")

    dev_sources = {record.source_id for record in dev}
    test_sources = {record.source_id for record in test}

    if dev_sources & test_sources:
        raise ValueError("Source leakage between splits")

    # Exact duplicate contexts are also disallowed across splits.
    if (
        {record.context for record in dev}
        & {record.context for record in test}
    ):
        raise ValueError("Duplicate contexts across splits")


def write_jsonl(path, records):
    """Write deterministic JSONL and return its SHA-256 checksum."""
    lines = [
        json.dumps(
            record.model_dump(),
            ensure_ascii=False,
            sort_keys=True,
        )
        for record in records
    ]

    contents = "\n".join(lines) + "\n"
    path.write_text(contents, encoding="utf-8")

    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def build_dataset(
    output_dir: Path,
    seed: int = 42,
    per_category: int = 10,
    revision: str | None = None,
    overwrite: bool = False,
):
    """Build source-disjoint development and test subsets."""
    if per_category < 1:
        raise ValueError("per_category must be positive")

    output_dir = Path(output_dir)
    paths = {
        "dev": output_dir / "squad_dev.jsonl",
        "test": output_dir / "squad_test.jsonl",
        "manifest": output_dir / "squad_manifest.json",
    }

    if not overwrite:
        existing = [str(p) for p in paths.values() if p.exists()]
        if existing:
            raise FileExistsError(
                f"Outputs already exist: {existing}. "
                "Use --overwrite to regenerate intentionally."
            )

    rng = random.Random(seed)

    dataset = load_dataset(
        DATASET_NAME,
        split=SOURCE_SPLIT,
        revision=revision,
    )

    groups = group_by_article(dataset)

    # Sorting before shuffling makes the ordering reproducible.
    articles = sorted(groups)
    rng.shuffle(articles)

    ordered_groups = [groups[article] for article in articles]

    dev_raw, next_index = sample_split(
        ordered_groups, 0, per_category, rng
    )

    test_raw, _ = sample_split(
        ordered_groups, next_index, per_category, rng
    )

    # Apply the tested adapter and Pydantic validation.
    dev = [adapt_squad_example(row) for row in dev_raw]
    test = [adapt_squad_example(row) for row in test_raw]

    validate_splits(dev, test)

    output_dir.mkdir(parents=True, exist_ok=True)

    dev_hash = write_jsonl(paths["dev"], dev)
    test_hash = write_jsonl(paths["test"], test)

    manifest = {
        "dataset": DATASET_NAME,
        "source_split": SOURCE_SPLIT,
        "source_revision": revision or "UNPINNED",
        "seed": seed,
        "per_category_per_split": per_category,
        "grouping_strategy": "article_title",
        "splits": {
            "dev": {
                "count": len(dev),
                "categories": dict(Counter(r.category for r in dev)),
                "sha256": dev_hash,
            },
            "test": {
                "count": len(test),
                "categories": dict(Counter(r.category for r in test)),
                "sha256": test_hash,
            },
        },
    }

    paths["manifest"].write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(f"Development examples: {len(dev)}")
    print(f"Test examples: {len(test)}")
    print(f"Manifest: {paths['manifest']}")

    return manifest


def main():
    parser = argparse.ArgumentParser(
        description="Build EvidenceTune SQuAD evaluation subsets"
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/eval"),
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--per-category", type=int, default=10)
    parser.add_argument(
        "--revision",
        type=str,
        default=None,
        help="Optional pinned Hugging Face dataset commit revision",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Explicitly permit replacing existing outputs",
    )

    args = parser.parse_args()

    build_dataset(
        output_dir=args.output_dir,
        seed=args.seed,
        per_category=args.per_category,
        revision=args.revision,
        overwrite=args.overwrite,
    )


if __name__ == "__main__":
    main()
