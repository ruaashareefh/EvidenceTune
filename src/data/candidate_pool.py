"""Stage 1: immutable SQuAD review pools; no benchmark assembly."""

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path

from datasets import load_dataset

from src.data.adapters.squad_v2 import adapt_squad_example
from src.data.build_eval import (
    DATASET_NAME, SOURCE_SPLIT, group_by_article, load_exclusions,
    load_verified_baseline, load_verified_parent, read_jsonl, sha256_file,
    write_jsonl,
)

POLICY = "sha256-article-record-v1"


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def rank(seed, kind, value):
    return digest([POLICY, seed, kind, value])


def inventory(directory):
    return {
        name: sha256_file(directory / name)
        for name in ("squad_manifest.json", "squad_dev.jsonl", "squad_test.jsonl")
    }


def verified_history(eval_root, parent_name, *, history_names=None):
    """Discover all curated versions, validate lineage, and block all their IDs."""
    baseline, dev, test = load_verified_baseline(eval_root)
    manifests = {"baseline": baseline}
    records = dev + test
    snapshots = {"baseline": inventory(eval_root)}
    versions = sorted(p for p in eval_root.iterdir() if p.is_dir() and p.name.startswith("curated_"))
    if history_names is not None:
        if not set(history_names) <= {p.name for p in versions}:
            raise ValueError("Missing recorded historical version")
        versions = [p for p in versions if p.name in history_names]
    prior_exclusions = set()
    parent_dev = None
    for folder in versions:
        manifest, rows, excluded = load_verified_parent(
            folder, eval_root, baseline, dev, test
        )
        manifests[folder.name] = manifest
        snapshots[folder.name] = inventory(folder)
        records.extend(rows)
        prior_exclusions.update(excluded)
        if folder.name == parent_name:
            parent_dev = rows
    if parent_dev is None:
        raise ValueError("Unknown curated parent")
    # Check links separately so directory ordering (v10 before v2) is irrelevant.
    for name, manifest in manifests.items():
        curation = manifest.get("curation", {})
        ancestor = curation.get("parent_version")
        if ancestor is None:
            if name not in {"baseline", "curated_v1"}:
                raise ValueError("Missing parent lineage")
            continue
        if ancestor not in manifests or ancestor in {name, "baseline"}:
            raise ValueError("Unknown or invalid parent lineage")
        expected = snapshots[ancestor]
        if (curation.get("parent_manifest_sha256") != expected["squad_manifest.json"]
                or curation.get("parent_dev_sha256") != expected["squad_dev.jsonl"]):
            raise ValueError("Parent lineage checksum mismatch")
        seen = {name}
        current = ancestor
        while current != "baseline":
            if current in seen:
                raise ValueError("Cyclic parent lineage")
            seen.add(current)
            current = manifests[current].get("curation", {}).get("parent_version", "baseline")
            if current not in manifests:
                raise ValueError("Unknown parent lineage")
    return baseline, records, test, parent_dev, prior_exclusions, snapshots


def verify_pool(directory):
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if (manifest.get("format_version") != 1 or manifest.get("policy") != POLICY
            or manifest.get("dataset") != DATASET_NAME
            or manifest.get("source_split") != SOURCE_SPLIT
            or manifest.get("initial_review_status") != "unreviewed"):
        raise ValueError("Unsupported pool format or policy")
    for filename, field in (("candidates.jsonl", "candidates_sha256"),
                            ("approval_snapshot.json", "approval_snapshot_sha256")):
        if sha256_file(directory / filename) != manifest[field]:
            raise ValueError("Pool checksum mismatch")
    rows = read_jsonl(directory / "candidates.jsonl")
    if (len(rows) != manifest["count"] or [r.id for r in rows] != manifest["candidate_ids"]
            or len({r.id for r in rows}) != len(rows)
            or len({r.source_id for r in rows}) != len(rows)
            or len({r.context for r in rows}) != len(rows)
            or any(r.category != "unanswerable" for r in rows)):
        raise ValueError("Invalid pool inventory")
    return manifest, rows


def validate_events(contents, manifest_hash, ids):
    """Validate append order and actor distinctions; not identity authentication."""
    previous = None
    events = []
    if contents and not contents.endswith("\n"):
        raise ValueError("Incomplete review log entry")
    for line in contents.splitlines():
        event = json.loads(line)
        payload = {k: v for k, v in event.items() if k != "event_sha256"}
        if (event.get("event_sha256") != digest(payload)
                or event.get("sequence") != len(events) + 1
                or event.get("previous_event_sha256") != previous
                or event.get("pool_manifest_sha256") != manifest_hash
                or event.get("candidate_id") not in ids):
            raise ValueError("Review log integrity mismatch")
        validate_review_fields(event)
        supersedes = event.get("supersedes")
        if supersedes is not None and not any(
            old["event_sha256"] == supersedes
            and old["candidate_id"] == event["candidate_id"] for old in events
        ):
            raise ValueError("Invalid superseded event")
        previous = event["event_sha256"]
        events.append(event)
    return events


def validate_review_fields(event):
    if event.get("disposition") not in {"accept", "reject", "defer"}:
        raise ValueError("Invalid review disposition")
    if not all(isinstance(event.get(k), str) and event[k].strip()
               for k in ("reviewer", "evidence", "rationale")):
        raise ValueError("Reviewer, evidence, and rationale are required")
    if not isinstance(event.get("challenge_candidate"), bool):
        raise ValueError("Challenge eligibility must be boolean")
    pair = (event.get("event_type"), event.get("actor_role"))
    if pair not in {("recommendation", "ai_assisted"), ("decision", "project_owner")}:
        raise ValueError("Actor role does not match event type")
    reference = event.get("approval_reference")
    if pair[0] == "decision" and (not isinstance(reference, str) or not reference.strip()):
        raise ValueError("Project-owner decisions require an approval reference")
    if pair[0] == "recommendation" and reference is not None:
        raise ValueError("AI recommendations cannot claim owner approval")


def append_review(directory, *, candidate_id, event_type, actor_role, reviewer,
                  disposition, evidence, rationale, challenge_candidate=False,
                  approval_reference=None, supersedes=None):
    """Append an event; corrections reference old events instead of rewriting them.

    A project_owner role records externally obtained approval; it cannot prove
    who authorized a call. Callers must supply actual approval evidence.
    """
    directory = Path(directory)
    _, rows = verify_pool(directory)
    manifest_hash = sha256_file(directory / "manifest.json")
    ids = {r.id for r in rows}
    fields = dict(candidate_id=candidate_id, event_type=event_type,
                  actor_role=actor_role, reviewer=reviewer, disposition=disposition,
                  evidence=evidence, rationale=rationale, challenge_candidate=challenge_candidate,
                  approval_reference=approval_reference, supersedes=supersedes)
    validate_review_fields(fields)
    if candidate_id not in ids:
        raise ValueError("Unknown pool candidate")
    # O_APPEND plus an exclusive advisory lock prevents cooperating writers from
    # replacing old bytes or assigning the same sequence number concurrently.
    descriptor = os.open(directory / "reviews.jsonl", os.O_RDWR | os.O_APPEND)
    with os.fdopen(descriptor, "r+", encoding="utf-8") as file:
        fcntl.flock(file, fcntl.LOCK_EX)
        file.seek(0)
        events = validate_events(file.read(), manifest_hash, ids)
        payload = {
            **fields, "sequence": len(events) + 1,
            "pool_manifest_sha256": manifest_hash,
            "previous_event_sha256": events[-1]["event_sha256"] if events else None,
        }
        event = {**payload, "event_sha256": digest(payload)}
        # Validate supersession before appending any bytes.
        validate_events("".join(canonical(e) + "\n" for e in events + [event]), manifest_hash, ids)
        file.write(canonical(event) + "\n")
        file.flush()
        os.fsync(file.fileno())
    return event


def sample_pool(dataset, *, count, seed, blocked_ids, blocked_contexts, test_sources):
    """Rank articles and eligible records by SHA-256; take one per article."""
    if count < 1:
        raise ValueError("Pool count must be positive")
    ids, contexts = set(blocked_ids), set(blocked_contexts)
    selected, sources = [], set()
    groups = group_by_article(dataset)
    raw_ids = [row["id"] for rows in groups.values() for row in rows]
    if len(raw_ids) != len(set(raw_ids)):
        raise ValueError("Duplicate source dataset IDs")
    for title in sorted(groups, key=lambda t: (rank(seed, "article", t), t)):
        eligible = []
        for row in groups[title]:
            record = adapt_squad_example(row)
            if (record.category == "unanswerable" and record.id not in ids
                    and record.context not in contexts
                    and record.source_id not in test_sources | sources):
                eligible.append(record)
        if not eligible:
            continue
        record = min(eligible, key=lambda r: (rank(seed, "record", r.id), r.id))
        selected.append(record)
        ids.add(record.id)
        contexts.add(record.context)
        sources.add(record.source_id)
        if len(selected) == count:
            return selected
    raise ValueError(f"Insufficient eligible articles: requested {count}, found {len(selected)}")


def build_pool(*, eval_root, pools_root, pool_name, approvals_path,
               parent_name="curated_v3", count=10, seed=42):
    eval_root, pools_root, approvals_path = map(Path, (eval_root, pools_root, approvals_path))
    if not pool_name or Path(pool_name).name != pool_name or pool_name in {".", ".."}:
        raise ValueError("Pool name must be a directory name")
    output = pools_root / pool_name
    if output.exists():
        raise FileExistsError(f"Pool already exists: {output}")
    if count < 1:
        raise ValueError("Pool count must be positive")
    baseline, historical, test, parent, prior_exclusions, history = verified_history(eval_root, parent_name)
    revision = baseline["source_revision"]
    config, excluded = load_exclusions(approvals_path, revision)
    if config.get("parent_version") != parent_name:
        raise ValueError("Approval parent mismatch")
    if not prior_exclusions <= excluded:
        raise ValueError("Cumulative exclusions omit history")
    historical_ids = {r.id for r in historical}
    if not excluded <= historical_ids or excluded & {r.id for r in test}:
        raise ValueError("Invalid historical exclusions")
    approved = config.get("approved_retained_ids")
    if (not isinstance(approved, list) or not all(isinstance(i, str) for i in approved)
            or len(set(approved)) != len(approved)
            or set(approved) != {r.id for r in parent} - excluded):
        raise ValueError("Approved retained IDs mismatch parent survivors")
    prior_pools, prior_rows = {}, []
    if pools_root.exists():
        for folder in sorted(pools_root.iterdir()):
            if not folder.is_dir():
                continue
            manifest, rows = verify_pool(folder)
            if manifest["dataset"] != DATASET_NAME or manifest["source_revision"] != revision:
                raise ValueError("Prior pool source mismatch")
            manifest_hash = sha256_file(folder / "manifest.json")
            validate_events((folder / "reviews.jsonl").read_text(encoding="utf-8"),
                            manifest_hash, {r.id for r in rows})
            prior_pools[folder.name] = {
                "manifest_sha256": manifest_hash,
                "candidates_sha256": manifest["candidates_sha256"],
            }
            prior_rows.extend(rows)
    blocked_ids = historical_ids | excluded | {r.id for r in prior_rows}
    blocked_contexts = {r.context for r in historical + prior_rows}
    dataset = load_dataset(DATASET_NAME, split=SOURCE_SPLIT, revision=revision)
    selected = sample_pool(dataset, count=count, seed=seed, blocked_ids=blocked_ids,
                           blocked_contexts=blocked_contexts, test_sources={r.source_id for r in test})
    # No output is written until validation and sampling have succeeded.
    # mkdir(exist_ok=False) also protects concurrent attempts at this pool name.
    output.mkdir(parents=True, exist_ok=False)
    (output / "approval_snapshot.json").write_bytes(approvals_path.read_bytes())
    candidates_hash = write_jsonl(output / "candidates.jsonl", selected)
    manifest = {
        "format_version": 1, "policy": POLICY, "dataset": DATASET_NAME,
        "source_split": SOURCE_SPLIT, "source_revision": revision,
        "source_fingerprint": getattr(dataset, "_fingerprint", None),
        "seed": seed, "count": count, "category": "unanswerable",
        "initial_review_status": "unreviewed", "parent_version": parent_name,
        "history": history, "previous_pools": prior_pools,
        "approval_snapshot_sha256": sha256_file(output / "approval_snapshot.json"),
        "blocked_ids_sha256": digest(sorted(blocked_ids)),
        "blocked_contexts_sha256": digest(sorted(blocked_contexts)),
        "candidate_ids": [r.id for r in selected], "candidates_sha256": candidates_hash,
        "review_log": "reviews.jsonl",
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "reviews.jsonl").touch(exist_ok=False)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eval-root", type=Path, default=Path("data/eval"))
    parser.add_argument("--pools-root", type=Path, default=Path("data/curation/candidate_pools"))
    parser.add_argument("--pool-name", required=True)
    parser.add_argument("--approvals", type=Path, required=True)
    parser.add_argument("--parent", default="curated_v3")
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    manifest = build_pool(eval_root=args.eval_root, pools_root=args.pools_root,
                          pool_name=args.pool_name, approvals_path=args.approvals,
                          parent_name=args.parent, count=args.count, seed=args.seed)
    print(f"Generated {manifest['count']} unreviewed candidates; policy={POLICY}")


if __name__ == "__main__":
    main()
