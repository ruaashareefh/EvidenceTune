
"""Build reproducible SQuAD evaluation datasets for EvidenceTune."""

import argparse
import hashlib
import json
import random
import re
import shutil
from collections import Counter, defaultdict
from pathlib import Path

from datasets import load_dataset

from src.data.adapters.squad_v2 import adapt_squad_example
from src.data.schema import EvidenceExample


DATASET_NAME = "rajpurkar/squad_v2"
SOURCE_SPLIT = "validation"
CATEGORIES = ("answerable", "unanswerable")


# ---------------------------------------------------------
# Shared utilities
# ---------------------------------------------------------

def sha256_file(path: Path) -> str:
    """Calculate the SHA-256 checksum of a file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_jsonl(path: Path) -> list[EvidenceExample]:
    """Read and validate EvidenceExample records from JSONL."""
    with path.open(encoding="utf-8") as file:
        return [
            EvidenceExample.model_validate_json(line)
            for line in file
            if line.strip()
        ]


def write_jsonl(path: Path, records) -> str:
    """Write deterministic JSONL and return its checksum."""
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

    return sha256_file(path)


def group_by_article(dataset):
    """Group SQuAD records by their source article."""
    groups = defaultdict(list)

    for record in dataset:
        groups[record["title"]].append(record)

    return groups


def category_counts(records) -> dict[str, int]:
    """Return stable category counts."""
    counts = Counter(record.category for record in records)
    return {category: counts[category] for category in CATEGORIES}


def validate_counts(records, per_category: int):
    """Ensure the expected category balance."""
    counts = category_counts(records)

    for category in CATEGORIES:
        if counts[category] != per_category:
            raise ValueError(
                f"Incorrect {category} count: "
                f"expected {per_category}, got {counts[category]}"
            )

    if len(records) != per_category * len(CATEGORIES):
        raise ValueError("Unexpected total record count")


def validate_splits(dev, test):
    """Check record uniqueness and source isolation."""
    all_records = dev + test
    ids = [record.id for record in all_records]

    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate example IDs detected")

    dev_sources = {record.source_id for record in dev}
    test_sources = {record.source_id for record in test}

    if dev_sources & test_sources:
        raise ValueError("Source leakage between splits")

    dev_contexts = {record.context for record in dev}
    test_contexts = {record.context for record in test}

    if dev_contexts & test_contexts:
        raise ValueError("Duplicate contexts across splits")


def check_output_paths(paths: dict, overwrite: bool = False):
    """Protect existing output files."""
    if overwrite:
        return

    existing = [str(path) for path in paths.values() if path.exists()]

    if existing:
        raise FileExistsError(
            f"Outputs already exist: {existing}. "
            "Use --overwrite only in original dataset mode; "
            "use a new output directory for curated versions."
        )


# ---------------------------------------------------------
# Original deterministic sampling
# ---------------------------------------------------------

def sample_split(groups, start_index, per_category, rng):
    """
    Select balanced examples from distinct source groups.

    Each article contributes at most one example per category.
    """
    remaining = {category: per_category for category in CATEGORIES}
    selected = []
    index = start_index

    while any(remaining.values()) and index < len(groups):
        article_records = sorted(
            groups[index],
            key=lambda row: row["id"],
        )
        index += 1

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


def build_dataset(
    output_dir: Path,
    seed: int = 42,
    per_category: int = 10,
    revision: str | None = None,
    overwrite: bool = False,
):
    """Build the original source-disjoint development/test splits."""
    if per_category < 1:
        raise ValueError("per_category must be positive")

    output_dir = Path(output_dir)

    paths = {
        "dev": output_dir / "squad_dev.jsonl",
        "test": output_dir / "squad_test.jsonl",
        "manifest": output_dir / "squad_manifest.json",
    }

    check_output_paths(paths, overwrite)

    rng = random.Random(seed)

    dataset = load_dataset(
        DATASET_NAME,
        split=SOURCE_SPLIT,
        revision=revision,
    )

    groups = group_by_article(dataset)

    articles = sorted(groups)
    rng.shuffle(articles)

    ordered_groups = [groups[article] for article in articles]

    dev_raw, next_index = sample_split(
        ordered_groups, 0, per_category, rng
    )

    test_raw, _ = sample_split(
        ordered_groups, next_index, per_category, rng
    )

    dev = [adapt_squad_example(row) for row in dev_raw]
    test = [adapt_squad_example(row) for row in test_raw]

    validate_splits(dev, test)
    validate_counts(dev, per_category)
    validate_counts(test, per_category)

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
                "categories": category_counts(dev),
                "sha256": dev_hash,
            },
            "test": {
                "count": len(test),
                "categories": category_counts(test),
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


# ---------------------------------------------------------
# Baseline and curation validation
# ---------------------------------------------------------

def load_verified_baseline(baseline_dir: Path):
    """
    Load existing splits and verify them against their manifest.

    No source file is modified.
    """
    manifest_path = baseline_dir / "squad_manifest.json"

    manifest = json.loads(
        manifest_path.read_text(encoding="utf-8")
    )

    if manifest["dataset"] != DATASET_NAME:
        raise ValueError("Unexpected baseline dataset")

    if manifest["source_split"] != SOURCE_SPLIT:
        raise ValueError("Unexpected baseline source split")

    if manifest["grouping_strategy"] != "article_title":
        raise ValueError("Unsupported baseline grouping strategy")

    revision = manifest["source_revision"]

    if not re.fullmatch(r"[0-9a-fA-F]{40}", revision):
        raise ValueError(
            "Curated builds require a pinned 40-character "
            "dataset commit SHA"
        )

    dev_path = baseline_dir / "squad_dev.jsonl"
    test_path = baseline_dir / "squad_test.jsonl"

    for name, path in (
        ("dev", dev_path),
        ("test", test_path),
    ):
        expected_hash = manifest["splits"][name]["sha256"]

        if sha256_file(path) != expected_hash:
            raise ValueError(
                f"Baseline {name} checksum mismatch"
            )

    dev = read_jsonl(dev_path)
    test = read_jsonl(test_path)

    per_category = manifest["per_category_per_split"]

    validate_counts(dev, per_category)
    validate_counts(test, per_category)
    validate_splits(dev, test)

    return manifest, dev, test


def load_exclusions(
    exclusions_path: Path,
    revision: str,
) -> tuple[dict, set[str]]:
    """Load approved exclusion IDs and verify provenance."""
    config = json.loads(
        exclusions_path.read_text(encoding="utf-8")
    )

    if config["dataset"] != DATASET_NAME:
        raise ValueError("Exclusion dataset mismatch")

    if config["source_revision"] != revision:
        raise ValueError("Exclusion source revision mismatch")

    if config.get("review_status") != "project_owner_approved":
        raise ValueError("Exclusions are not project-owner approved")

    excluded_ids = set(config["excluded_ids"])

    if not excluded_ids:
        raise ValueError("Exclusion list is empty")

    challenge_ids = set(
        config.get("false_premise_challenge_candidates", [])
    )

    if not challenge_ids <= excluded_ids:
        raise ValueError(
            "Challenge candidates must be excluded records"
        )

    return config, excluded_ids


# ---------------------------------------------------------
# Deterministic replacement sampling
# ---------------------------------------------------------

def sample_replacements(
    dataset,
    excluded_ids: set[str],
    existing_dev: list[EvidenceExample],
    existing_test: list[EvidenceExample],
    accepted_dev: list[EvidenceExample],
    per_category: int,
    seed: int,
) -> list[EvidenceExample]:
    """
    Sample replacements without modifying approved records.

    Replacement candidates:
    - must not be excluded;
    - must not duplicate any original example ID;
    - must not share a source with the held-out test set;
    - must not duplicate existing contexts;
    - must restore the desired category balance.

    Candidates may share an article with accepted development
    records, because source isolation is required between
    development and test, not within development.
    """
    counts = category_counts(accepted_dev)

    remaining = {
        category: per_category - counts[category]
        for category in CATEGORIES
    }

    if any(value < 0 for value in remaining.values()):
        raise ValueError("Too many accepted examples in a category")

    if not any(remaining.values()):
        return []

    original_ids = {
        record.id for record in existing_dev + existing_test
    }

    blocked_sources = {
        record.source_id for record in existing_test
    }

    used_contexts = {
        record.context for record in existing_dev + existing_test
    }

    groups = group_by_article(dataset)

    rng = random.Random(seed)

    articles = sorted(groups)
    rng.shuffle(articles)

    replacements = []

    for article in articles:
        if not any(remaining.values()):
            break

        records = sorted(
            groups[article],
            key=lambda row: row["id"],
        )

        for category in CATEGORIES:
            if remaining[category] == 0:
                continue

            candidates = []

            for row in records:
                converted = adapt_squad_example(row)

                if converted.category != category:
                    continue

                if converted.id in excluded_ids:
                    continue

                if converted.id in original_ids:
                    continue

                if converted.source_id in blocked_sources:
                    continue

                if converted.context in used_contexts:
                    continue

                candidates.append(converted)

            if not candidates:
                continue

            selected = rng.choice(candidates)

            replacements.append(selected)

            original_ids.add(selected.id)
            used_contexts.add(selected.context)

            remaining[category] -= 1

    if any(remaining.values()):
        raise ValueError(
            "Insufficient eligible replacement examples: "
            f"{remaining}"
        )

    return replacements


# ---------------------------------------------------------
# Curated dataset builder
# ---------------------------------------------------------

def build_curated_dataset(
    output_dir: Path,
    baseline_dir: Path,
    exclusions_path: Path,
    seed: int = 42,
    per_category: int = 10,
    revision: str | None = None,
):
    """
    Produce curated development candidates with an unchanged test set.

    Never overwrites the original benchmark.

    Replacement examples are marked as pending manual review.
    """
    output_dir = Path(output_dir)
    baseline_dir = Path(baseline_dir)
    exclusions_path = Path(exclusions_path)

    if output_dir.resolve() == baseline_dir.resolve():
        raise ValueError(
            "Curated output must differ from baseline directory"
        )

    if per_category < 1:
        raise ValueError("per_category must be positive")

    paths = {
        "dev": output_dir / "squad_dev.jsonl",
        "test": output_dir / "squad_test.jsonl",
        "manifest": output_dir / "squad_manifest.json",
    }

    # Curated outputs are immutable by default.
    # Use a new output directory for another candidate version.
    check_output_paths(paths, overwrite=False)

    baseline_manifest, original_dev, original_test = (
        load_verified_baseline(baseline_dir)
    )

    source_revision = baseline_manifest["source_revision"]

    if revision is not None and revision != source_revision:
        raise ValueError(
            "Requested revision differs from baseline revision"
        )

    if (
        per_category
        != baseline_manifest["per_category_per_split"]
    ):
        raise ValueError(
            "Curated category target must match the baseline"
        )

    exclusion_config, excluded_ids = load_exclusions(
        exclusions_path,
        source_revision,
    )

    dev_ids = {record.id for record in original_dev}
    test_ids = {record.id for record in original_test}

    if not excluded_ids <= dev_ids:
        raise ValueError(
            "Excluded IDs must belong to the baseline development set"
        )

    if excluded_ids & test_ids:
        raise ValueError(
            "Exclusion list contains held-out test IDs"
        )

    # Preserve every approved development example unchanged.
    accepted_dev = [
        record
        for record in original_dev
        if record.id not in excluded_ids
    ]

    dataset = load_dataset(
        DATASET_NAME,
        split=SOURCE_SPLIT,
        revision=source_revision,
    )

    replacements = sample_replacements(
        dataset=dataset,
        excluded_ids=excluded_ids,
        existing_dev=original_dev,
        existing_test=original_test,
        accepted_dev=accepted_dev,
        per_category=per_category,
        seed=seed,
    )

    curated_dev = accepted_dev + replacements

    validate_counts(curated_dev, per_category)
    validate_counts(original_test, per_category)
    validate_splits(curated_dev, original_test)

    curated_ids = {record.id for record in curated_dev}

    if excluded_ids & curated_ids:
        raise ValueError(
            "Excluded IDs appeared in curated development data"
        )

    accepted_ids = {record.id for record in accepted_dev}
    replacement_ids = {record.id for record in replacements}

    if accepted_ids & replacement_ids:
        raise ValueError(
            "Replacement IDs overlap accepted records"
        )

    output_dir.mkdir(parents=True, exist_ok=True)

    dev_hash = write_jsonl(paths["dev"], curated_dev)

    # Copy held-out test BYTES rather than reserializing records.
    # This preserves the original file checksum exactly.
    original_test_path = baseline_dir / "squad_test.jsonl"
    shutil.copyfile(original_test_path, paths["test"])

    test_hash = sha256_file(paths["test"])
    original_test_hash = baseline_manifest["splits"]["test"]["sha256"]

    if test_hash != original_test_hash:
        raise ValueError("Held-out test set changed during curation")

    manifest = {
        "dataset": DATASET_NAME,
        "source_split": SOURCE_SPLIT,
        "source_revision": source_revision,
        "seed": seed,
        "per_category_per_split": per_category,
        "grouping_strategy": "article_title",
        "curation": {
            "status": "replacement_candidates_pending_review",
            "guideline_version": exclusion_config["guideline_version"],
            "baseline_manifest_sha256": sha256_file(
                baseline_dir / "squad_manifest.json"
            ),
            "baseline_dev_sha256": (
                baseline_manifest["splits"]["dev"]["sha256"]
            ),
            "baseline_test_sha256": original_test_hash,
            "exclusion_file_sha256": sha256_file(exclusions_path),
            "excluded_count": len(excluded_ids),
            "retained_dev_count": len(accepted_dev),
            "replacement_count": len(replacements),
            "retained_dev_ids": [record.id for record in accepted_dev],
            "replacement_ids": [record.id for record in replacements],
            "test_preserved_byte_for_byte": True,
        },
        "splits": {
            "dev": {
                "count": len(curated_dev),
                "categories": category_counts(curated_dev),
                "sha256": dev_hash,
                "review_status": "pending_replacement_audit",
            },
            "test": {
                "count": len(original_test),
                "categories": category_counts(original_test),
                "sha256": test_hash,
                "review_status": "unchanged_not_yet_audited",
            },
        },
    }

    paths["manifest"].write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(f"Retained development examples: {len(accepted_dev)}")
    print(f"Replacement candidates: {len(replacements)}")
    print(f"Curated development examples: {len(curated_dev)}")
    print(f"Held-out test examples: {len(original_test)}")
    print(f"Test checksum unchanged: {test_hash == original_test_hash}")
    print(f"Manifest: {paths['manifest']}")

    return manifest


# ---------------------------------------------------------
# Successive curated versions (curated_v2 and beyond)
# ---------------------------------------------------------

def load_verified_parent(
    parent_dir: Path,
    baseline_dir: Path,
    baseline_manifest: dict,
    baseline_dev: list[EvidenceExample],
    baseline_test: list[EvidenceExample],
) -> tuple[dict, list[EvidenceExample], set[str]]:
    """Verify parent lineage, unchanged test bytes, and prior exclusions.

    The original curated_v1 manifest predates the `excluded_ids` field.
    For that version only, historical exclusions are reconstructed from
    the original development IDs absent from its curated development set.
    """
    parent_manifest, parent_dev, parent_test = load_verified_baseline(
        parent_dir
    )

    if "curation" not in parent_manifest:
        raise ValueError("Parent is not a curated dataset")

    for field in (
        "dataset", "source_split", "source_revision",
        "per_category_per_split", "grouping_strategy",
    ):
        if parent_manifest[field] != baseline_manifest[field]:
            raise ValueError(f"Parent/baseline mismatch: {field}")

    curation = parent_manifest["curation"]
    if curation.get("status") not in {
        "replacement_candidates_pending_review", "approved_candidate_assembly",
    }:
        raise ValueError("Unsupported parent curation status")

    expected_baseline_manifest_sha = sha256_file(
        baseline_dir / "squad_manifest.json"
    )
    expected_dev_sha = baseline_manifest["splits"]["dev"]["sha256"]
    expected_test_sha = baseline_manifest["splits"]["test"]["sha256"]

    if curation.get("baseline_manifest_sha256") != expected_baseline_manifest_sha:
        raise ValueError("Parent baseline manifest checksum mismatch")

    if curation.get("baseline_dev_sha256") != expected_dev_sha:
        raise ValueError("Parent baseline development checksum mismatch")

    if curation.get("baseline_test_sha256") != expected_test_sha:
        raise ValueError("Parent baseline test checksum mismatch")

    if (
        (parent_dir / "squad_test.jsonl").read_bytes()
        != (baseline_dir / "squad_test.jsonl").read_bytes()
    ):
        raise ValueError("Parent held-out test differs from baseline")

    if curation.get("test_preserved_byte_for_byte") is not True:
        raise ValueError("Parent test preservation not documented")

    retained_ids = curation.get("retained_dev_ids", [])
    replacement_ids = curation.get("replacement_ids", [])
    parent_ids = {record.id for record in parent_dev}
    baseline_ids = {record.id for record in baseline_dev}

    # Records already present in the original baseline must remain
    # semantically and structurally unchanged in every curated version.
    original_by_id = {record.id: record for record in baseline_dev}
    for record in parent_dev:
        if record.id in original_by_id and record != original_by_id[record.id]:
            raise ValueError("Parent altered a baseline development record")

    if (
        len(retained_ids) != len(set(retained_ids))
        or len(replacement_ids) != len(set(replacement_ids))
        or set(retained_ids) & set(replacement_ids)
        or set(retained_ids) | set(replacement_ids) != parent_ids
        or len(retained_ids) != curation.get("retained_dev_count")
        or len(replacement_ids) != curation.get("replacement_count")
    ):
        raise ValueError("Parent curated record inventory mismatch")

    # For curated_v1, the baseline IDs missing from the parent are
    # exactly the previously approved first-round exclusions.
    prior_excluded_ids = set(curation.get("excluded_ids", []))
    if "excluded_ids" not in curation:
        prior_excluded_ids = baseline_ids - parent_ids
        if not set(retained_ids) <= baseline_ids:
            raise ValueError("Legacy parent retained ID provenance mismatch")

    if (
        len(prior_excluded_ids) != curation.get("excluded_count")
        or prior_excluded_ids & parent_ids
        or not (baseline_ids - parent_ids) <= prior_excluded_ids
    ):
        raise ValueError("Parent exclusion inventory mismatch")

    test_ids = {record.id for record in baseline_test}
    if prior_excluded_ids & test_ids:
        raise ValueError("Parent exclusions contain held-out test records")

    # load_verified_baseline already checked parent manifest hashes,
    # category balance, ID uniqueness and split source isolation.
    assert len(parent_test) == len(baseline_test)
    return parent_manifest, parent_dev, prior_excluded_ids


def build_successive_curated_dataset(
    output_dir: Path,
    baseline_dir: Path,
    parent_dir: Path,
    exclusions_path: Path,
    seed: int = 42,
    per_category: int = 10,
    revision: str | None = None,
):
    """Build the next curated dataset while preserving audited records.

    The exclusion file MUST contain cumulative exclusions and an explicit
    project-owner-approved `approved_retained_ids` inventory. This avoids
    silently treating unreviewed parent candidates as approved.

    No baseline, parent, or held-out test artifact is modified.
    """
    output_dir = Path(output_dir)
    baseline_dir = Path(baseline_dir)
    parent_dir = Path(parent_dir)
    exclusions_path = Path(exclusions_path)

    resolved = {
        output_dir.resolve(),
        baseline_dir.resolve(),
        parent_dir.resolve(),
    }
    if len(resolved) != 3:
        raise ValueError(
            "Curated output, parent, and baseline directories must differ"
        )

    if per_category < 1:
        raise ValueError("per_category must be positive")

    paths = {
        "dev": output_dir / "squad_dev.jsonl",
        "test": output_dir / "squad_test.jsonl",
        "manifest": output_dir / "squad_manifest.json",
    }
    check_output_paths(paths, overwrite=False)

    baseline_manifest, baseline_dev, baseline_test = load_verified_baseline(
        baseline_dir
    )
    source_revision = baseline_manifest["source_revision"]

    if revision is not None and revision != source_revision:
        raise ValueError("Requested revision differs from baseline revision")

    if per_category != baseline_manifest["per_category_per_split"]:
        raise ValueError(
            "Curated category target must match the baseline"
        )

    parent_manifest, parent_dev, prior_excluded_ids = load_verified_parent(
        parent_dir=parent_dir,
        baseline_dir=baseline_dir,
        baseline_manifest=baseline_manifest,
        baseline_dev=baseline_dev,
        baseline_test=baseline_test,
    )

    config, excluded_ids = load_exclusions(
        exclusions_path, source_revision
    )

    parent_ids = {record.id for record in parent_dev}
    baseline_ids = {record.id for record in baseline_dev}
    test_ids = {record.id for record in baseline_test}

    if excluded_ids & test_ids:
        raise ValueError("Exclusion list contains held-out test IDs")

    if not prior_excluded_ids <= excluded_ids:
        raise ValueError("Cumulative exclusions omit prior exclusions")

    allowed_exclusion_ids = baseline_ids | parent_ids | prior_excluded_ids
    if not excluded_ids <= allowed_exclusion_ids:
        raise ValueError("Exclusions contain unknown historical IDs")

    newly_excluded_ids = excluded_ids & parent_ids
    if not newly_excluded_ids:
        raise ValueError("No newly excluded parent examples")

    accepted_dev = [
        record for record in parent_dev
        if record.id not in excluded_ids
    ]
    accepted_ids = {record.id for record in accepted_dev}

    # Mandatory human approval inventory. Cumulative exclusions alone
    # would silently promote every unexcluded pending candidate.
    approved_ids = config.get("approved_retained_ids")
    if not isinstance(approved_ids, list) or not all(
        isinstance(item, str) for item in approved_ids
    ):
        raise ValueError(
            "Successive curation requires approved_retained_ids list"
        )
    if len(approved_ids) != len(set(approved_ids)):
        raise ValueError("Duplicate approved retained IDs")
    if set(approved_ids) != accepted_ids:
        raise ValueError("Approved retained IDs mismatch parent survivors")

    # Preserve the parent records byte-equivalent at the Pydantic model
    # level; never regenerate or adapt them from Hugging Face.
    dataset = load_dataset(
        DATASET_NAME,
        split=SOURCE_SPLIT,
        revision=source_revision,
    )

    replacements = sample_replacements(
        dataset=dataset,
        excluded_ids=excluded_ids,
        # Block both the original and the immediately preceding curated
        # examples. Excluded examples from earlier generations are
        # already blocked by the cumulative exclusion file.
        existing_dev=baseline_dev + parent_dev,
        existing_test=baseline_test,
        accepted_dev=accepted_dev,
        per_category=per_category,
        seed=seed,
    )

    curated_dev = accepted_dev + replacements
    validate_counts(curated_dev, per_category)
    validate_counts(baseline_test, per_category)
    validate_splits(curated_dev, baseline_test)

    curated_ids = {record.id for record in curated_dev}
    if curated_ids & excluded_ids:
        raise ValueError("Excluded IDs appeared in curated development data")

    new_ids = {record.id for record in replacements}
    if new_ids & (baseline_ids | parent_ids | test_ids):
        raise ValueError("Replacement IDs were previously used")

    output_dir.mkdir(parents=True, exist_ok=True)
    dev_hash = write_jsonl(paths["dev"], curated_dev)

    # The held-out test is copied from the ORIGINAL baseline, never
    # reserialized or reconstructed from the parent.
    shutil.copyfile(baseline_dir / "squad_test.jsonl", paths["test"])
    test_hash = sha256_file(paths["test"])
    original_test_hash = baseline_manifest["splits"]["test"]["sha256"]
    if test_hash != original_test_hash:
        raise ValueError("Held-out test set changed during curation")

    manifest = {
        "dataset": DATASET_NAME,
        "source_split": SOURCE_SPLIT,
        "source_revision": source_revision,
        "seed": seed,
        "per_category_per_split": per_category,
        "grouping_strategy": "article_title",
        "curation": {
            "status": "replacement_candidates_pending_review",
            "guideline_version": config["guideline_version"],
            "baseline_manifest_sha256": sha256_file(
                baseline_dir / "squad_manifest.json"
            ),
            "baseline_dev_sha256": baseline_manifest["splits"]["dev"]["sha256"],
            "baseline_test_sha256": original_test_hash,
            "parent_version": parent_dir.name,
            "parent_manifest_sha256": sha256_file(
                parent_dir / "squad_manifest.json"
            ),
            "parent_dev_sha256": parent_manifest["splits"]["dev"]["sha256"],
            "exclusion_file_sha256": sha256_file(exclusions_path),
            "excluded_count": len(excluded_ids),
            "excluded_ids": sorted(excluded_ids),
            "newly_excluded_count": len(newly_excluded_ids),
            "newly_excluded_ids": sorted(newly_excluded_ids),
            "retained_dev_count": len(accepted_dev),
            "replacement_count": len(replacements),
            "retained_dev_ids": [record.id for record in accepted_dev],
            "replacement_ids": [record.id for record in replacements],
            "approval_status": config["review_status"],
            "independent_double_review": config.get(
                "independent_double_review", False
            ),
            "test_preserved_byte_for_byte": True,
        },
        "splits": {
            "dev": {
                "count": len(curated_dev),
                "categories": category_counts(curated_dev),
                "sha256": dev_hash,
                "review_status": "pending_replacement_audit",
            },
            "test": {
                "count": len(baseline_test),
                "categories": category_counts(baseline_test),
                "sha256": test_hash,
                "review_status": "unchanged_not_yet_audited",
            },
        },
    }

    paths["manifest"].write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(f"Parent curated version: {parent_dir.name}")
    print(f"Newly excluded parent examples: {len(newly_excluded_ids)}")
    print(f"Retained development examples: {len(accepted_dev)}")
    print(f"Replacement candidates: {len(replacements)}")
    print(f"Curated development examples: {len(curated_dev)}")
    print(f"Held-out test examples: {len(baseline_test)}")
    print(f"Test checksum unchanged: {test_hash == original_test_hash}")
    print(f"Manifest: {paths['manifest']}")

    return manifest


# ---------------------------------------------------------
# CLI
# ---------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Build EvidenceTune SQuAD evaluation datasets"
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
    )

    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--per-category", type=int, default=10)

    parser.add_argument(
        "--revision",
        type=str,
        default=None,
        help="Pinned Hugging Face dataset commit revision",
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow overwrite in original dataset mode only",
    )

    parser.add_argument(
        "--curate-from",
        type=Path,
        default=None,
        help="Directory containing the verified original benchmark",
    )

    parser.add_argument(
        "--exclusions",
        type=Path,
        default=None,
        help="Approved exclusion configuration JSON",
    )

    parser.add_argument(
        "--parent-curated",
        type=Path,
        default=None,
        help="Prior curated directory for successive versions (v2+)",
    )

    args = parser.parse_args()

    if args.curate_from is not None:
        if args.exclusions is None:
            parser.error(
                "--exclusions is required with --curate-from"
            )

        if args.overwrite:
            parser.error(
                "--overwrite is not supported for curated builds"
            )

        if args.parent_curated is not None:
            build_successive_curated_dataset(
                output_dir=(
                    args.output_dir
                    or Path("data/eval/curated_v2")
                ),
                baseline_dir=args.curate_from,
                parent_dir=args.parent_curated,
                exclusions_path=args.exclusions,
                seed=args.seed,
                per_category=args.per_category,
                revision=args.revision,
            )
        else:
            build_curated_dataset(
                output_dir=(
                    args.output_dir
                    or Path("data/eval/curated_v1")
                ),
                baseline_dir=args.curate_from,
                exclusions_path=args.exclusions,
                seed=args.seed,
                per_category=args.per_category,
                revision=args.revision,
            )

    else:
        if args.exclusions is not None:
            parser.error("--exclusions requires --curate-from")
        if args.parent_curated is not None:
            parser.error("--parent-curated requires --curate-from")

        build_dataset(
            output_dir=(
                args.output_dir
                or Path("data/eval")
            ),
            seed=args.seed,
            per_category=args.per_category,
            revision=args.revision,
            overwrite=args.overwrite,
        )


if __name__ == "__main__":
    main()
