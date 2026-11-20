"""Assemble or verify an approved pool selection without sampling or downloads."""

import argparse
import fcntl
import hashlib
import json
from pathlib import Path

from src.data.build_eval import (
    DATASET_NAME, SOURCE_SPLIT, category_counts, load_exclusions,
    sha256_file, validate_counts, validate_splits,
)
from src.data.candidate_pool import digest, validate_events, verified_history, verify_pool


def checksum(data):
    return hashlib.sha256(data).hexdigest()


def json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def prepare_assembly(eval_root, pool_dir, candidate_id, reviews):
    """Validate frozen inputs and produce exact output bytes before any writes."""
    pm, candidates = verify_pool(pool_dir)
    parent_name = pm["parent_version"]
    names = set(pm["history"]) - {"baseline"}
    baseline, historical, test, parent, prior_excluded, history = verified_history(
        eval_root, parent_name, history_names=names
    )
    if history != pm["history"] or pm["source_revision"] != baseline["source_revision"]:
        raise ValueError("Pool historical provenance mismatch")
    cfg_path = pool_dir / "approval_snapshot.json"
    cfg, excluded = load_exclusions(cfg_path, baseline["source_revision"])
    historical_ids = {r.id for r in historical}
    if (cfg.get("parent_version") != parent_name or not prior_excluded <= excluded
            or not excluded <= historical_ids or excluded & {r.id for r in test}):
        raise ValueError("Invalid cumulative exclusions or approval parent")
    retained = [r for r in parent if r.id not in excluded]
    # The frozen approval inventory must match the surviving records AND order.
    if cfg.get("approved_retained_ids") != [r.id for r in retained]:
        raise ValueError("Approved retained inventory or ordering mismatch")
    selected = next((r for r in candidates if r.id == candidate_id), None)
    if selected is None:
        raise ValueError("Selected ID is not in the pool")
    pool_hash = sha256_file(pool_dir / "manifest.json")
    events = validate_events(reviews.decode("utf-8"), pool_hash, {r.id for r in candidates})
    decisions = [e for e in events if e["candidate_id"] == candidate_id
                 and e["event_type"] == "decision" and e["actor_role"] == "project_owner"]
    if not decisions or decisions[-1]["disposition"] != "accept":
        raise ValueError("Selection requires latest project-owner acceptance")
    decision = decisions[-1]
    # Recheck eligibility rather than trusting that generation once filtered it.
    previous_rows = []
    for name, expected in pm["previous_pools"].items():
        if Path(name).name != name or name in {".", ".."}:
            raise ValueError("Invalid previous pool name")
        directory = pool_dir.parent / name
        previous_manifest, rows = verify_pool(directory)
        if (sha256_file(directory / "manifest.json") != expected["manifest_sha256"]
                or previous_manifest["candidates_sha256"] != expected["candidates_sha256"]):
            raise ValueError("Previous pool provenance mismatch")
        previous_rows.extend(rows)
    blocked_ids = historical_ids | excluded | {r.id for r in previous_rows}
    blocked_contexts = {r.context for r in historical + previous_rows}
    if (digest(sorted(blocked_ids)) != pm["blocked_ids_sha256"]
            or digest(sorted(blocked_contexts)) != pm["blocked_contexts_sha256"]):
        raise ValueError("Pool eligibility provenance mismatch")
    if selected.id in blocked_ids or selected.context in blocked_contexts:
        raise ValueError("Selected candidate is historically blocked")
    records = retained + [selected]
    target = baseline["per_category_per_split"]
    validate_counts(records, target)
    validate_splits(records, test)
    if {r.id for r in records} & excluded:
        raise ValueError("Excluded record in assembly")
    dev_bytes = ("\n".join(json.dumps(r.model_dump(), ensure_ascii=False, sort_keys=True)
                            for r in records) + "\n").encode("utf-8")
    test_bytes = (eval_root / "squad_test.jsonl").read_bytes()
    curation = {
        "status": "approved_candidate_assembly", "assembly_policy": "explicit-approved-selection-v1",
        "guideline_version": cfg["guideline_version"],
        "baseline_manifest_sha256": history["baseline"]["squad_manifest.json"],
        "baseline_dev_sha256": history["baseline"]["squad_dev.jsonl"],
        "baseline_test_sha256": checksum(test_bytes),
        "parent_version": parent_name,
        "parent_manifest_sha256": history[parent_name]["squad_manifest.json"],
        "parent_dev_sha256": history[parent_name]["squad_dev.jsonl"],
        "exclusion_file_sha256": sha256_file(cfg_path),
        "excluded_ids": sorted(excluded), "excluded_count": len(excluded),
        "newly_excluded_ids": sorted(excluded & {r.id for r in parent}),
        "newly_excluded_count": len(excluded & {r.id for r in parent}),
        "false_premise_challenge_candidates": cfg.get("false_premise_challenge_candidates", []),
        "retained_dev_ids": [r.id for r in retained], "retained_dev_count": len(retained),
        "replacement_ids": [candidate_id], "replacement_count": 1,
        "selected_candidate_id": candidate_id,
        "approval_status": "project_owner_approved",
        "independent_double_review": cfg.get("independent_double_review", False),
        "test_preserved_byte_for_byte": True,
        "pool_name": pool_dir.name, "pool_manifest_sha256": pool_hash,
        "pool_candidates_sha256": pm["candidates_sha256"],
        "pool_sampling_policy": pm["policy"], "pool_seed": pm["seed"],
        "approval_snapshot_file": "approval_snapshot.json",
        "review_log_snapshot_file": "approval_reviews.jsonl",
        "review_log_snapshot_sha256": checksum(reviews),
        "approval_event_sha256": decision["event_sha256"],
        "approval_event_sequence": decision["sequence"],
        "approval_reference": decision["approval_reference"],
    }
    manifest = {
        "dataset": DATASET_NAME, "source_split": SOURCE_SPLIT,
        "source_revision": baseline["source_revision"],
        "per_category_per_split": target, "grouping_strategy": "article_title",
        "curation": curation,
        "splits": {
            "dev": {"count": len(records), "categories": category_counts(records),
                    "sha256": checksum(dev_bytes), "review_status": "project_owner_approved"},
            "test": {"count": len(test), "categories": category_counts(test),
                     "sha256": checksum(test_bytes), "review_status": "unchanged_not_yet_audited"},
        },
    }
    return manifest, {
        "squad_dev.jsonl": dev_bytes, "squad_test.jsonl": test_bytes,
        "squad_manifest.json": json_bytes(manifest),
        "approval_snapshot.json": cfg_path.read_bytes(),
        "approval_reviews.jsonl": reviews,
        "pool_manifest.json": (pool_dir / "manifest.json").read_bytes(),
    }


def assemble_curated(*, eval_root, pool_dir, output_dir, candidate_id):
    eval_root, pool_dir, output_dir = map(Path, (eval_root, pool_dir, output_dir))
    if output_dir.exists():
        raise FileExistsError(f"Output already exists: {output_dir}")
    # Hold a shared lock through assembly so owner decisions cannot change midway.
    with (pool_dir / "reviews.jsonl").open("rb") as log:
        fcntl.flock(log, fcntl.LOCK_SH)
        reviews = log.read()
        pm, _ = verify_pool(pool_dir)
        _, _, _, _, _, current_history = verified_history(eval_root, pm["parent_version"])
        if current_history != pm["history"]:
            raise ValueError("Benchmark history changed since pool generation")
        manifest, files = prepare_assembly(eval_root, pool_dir, candidate_id, reviews)
        output_dir.mkdir(parents=True, exist_ok=False)
        for name, contents in files.items():
            with (output_dir / name).open("xb") as file:
                file.write(contents)
    return manifest


def verify_assembly(*, eval_root, pool_dir, output_dir):
    """Read-only reconstruction against recorded review snapshot and frozen inputs."""
    eval_root, pool_dir, output_dir = map(Path, (eval_root, pool_dir, output_dir))
    actual = json.loads((output_dir / "squad_manifest.json").read_text())
    cid = actual["curation"]["selected_candidate_id"]
    reviews = (output_dir / "approval_reviews.jsonl").read_bytes()
    # The archived log must still be a byte-identical prefix of the append-only log.
    if not (pool_dir / "reviews.jsonl").read_bytes().startswith(reviews):
        raise ValueError("Archived approvals differ from append-only review history")
    expected, files = prepare_assembly(eval_root, pool_dir, cid, reviews)
    for name, contents in files.items():
        if (output_dir / name).read_bytes() != contents:
            raise ValueError(f"Assembly artifact mismatch: {name}")
    return expected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eval-root", type=Path, default=Path("data/eval"))
    parser.add_argument("--pool-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--candidate-id")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    options = dict(eval_root=args.eval_root, pool_dir=args.pool_dir, output_dir=args.output_dir)
    if args.verify:
        result = verify_assembly(**options)
    else:
        if not args.candidate_id:
            parser.error("--candidate-id is required for assembly")
        result = assemble_curated(**options, candidate_id=args.candidate_id)
    print(f"{'Verified' if args.verify else 'Assembled'} {args.output_dir}: "
          f"{result['splits']['dev']['count']} development records; "
          f"{result['curation']['retained_dev_count']} retained; original test preserved")


if __name__ == "__main__":
    main()
