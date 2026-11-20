# Candidate Pools — Stage 1

Stage 1 generates review material without assembling a benchmark version.
Stage 2 is now implemented after explicit project-owner approval of Candidate 9.
See [the curated_v4 assembly report](curated_v4_assembly.md) for provenance and
verification commands.

## Current round

- Parent: `data/eval/curated_v3` (unchanged).
- Approval input: `data/curation/pool_round_001_approvals.json`.
- Approved exclusions: 20, including the v3 Saturn/Mercury decision.
- Approved retained records: 19 (10 answerable, nine unanswerable).
- False-premise challenge candidates: eight.
- Pool: `data/curation/candidate_pools/unanswerable_pool_001`.
- Candidate 9 is owner-approved and assembled into curated_v4; the other nine
  candidates remain unreviewed.
- [Manual review sheet](candidate_pool_001_review.md).

The approval input was constructed from the unchanged v3 exclusion configuration,
adding the explicitly approved Saturn/Mercury exclusion and the drill-core and
construction-worker retentions. It records the source audit's checksum. This is
an input snapshot for a review round, not a curated_v4 configuration.

## Sampling policy: sha256-article-record-v1

Implementation: `src/data/candidate_pool.py`.

1. Validate the original baseline's pinned revision, data checksums, balance,
   uniqueness, and split isolation with existing builder validation.
2. Discover every `curated_*` directory directly under the evaluation root.
   Validate each version's data, original-baseline provenance, unchanged test
   bytes, record inventories, and parent links. Missing/corrupt linked history
   is an error, not permission to forget previously used IDs.
3. Verify the round's approval inventory: source revision and approval status,
   cumulative historical exclusions, and the exact surviving parent ID set.
4. Discover all earlier pool directories under the pool root. Verify their
   manifests, candidate and approval-snapshot checksums, inventory, and review
   log integrity. Block their candidate IDs regardless of review status.
5. Group the pinned SQuAD validation records by exact article title. Reject
   duplicate upstream IDs. Rank articles by SHA-256 of the UTF-8 canonical JSON
   array `[policy, seed, "article", title]`. Canonical JSON uses sorted keys,
   no ASCII escaping, and compact separators. Ties use the title itself.
6. For each article in that order, adapt records and keep only unanswerable
   candidates whose IDs are absent from all historical benchmark versions,
   earlier pools, and approved exclusions. Also reject held-out test source IDs
   and contexts already present in any benchmark, earlier pool, or this pool.
7. Rank eligible records by SHA-256 of `[policy, seed, "record", adapted_id]`,
   breaking ties with the ID. Select the first, then move to the next article.
   At most one record per article/source enters this pool. Sharing an article
   with development records is allowed; sharing one with test records is not.
8. Stop at ten. If this greedy traversal cannot fill the pool, fail before
   writing output. Do not relax filters or backtrack to optimize the selection.

The procedure is independent of incoming row order and Python's random module.
It does not promise uniform sampling over all eligible records: article diversity
is intentional, and selection is reproducible under the named policy.
A different policy requires a new policy identifier. Different seeds may produce
other pools; the same seed and complete input inventory reproduce the same pool.

## Generation

```sh
HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 .venv/bin/python -m src.data.candidate_pool \
  --eval-root data/eval \
  --pools-root data/curation/candidate_pools \
  --pool-name unanswerable_pool_001 \
  --approvals data/curation/pool_round_001_approvals.json \
  --parent curated_v3 --count 10 --seed 42
```

The actual generation used the existing cache at revision
`3ffb306f725f7d2ce8394bc1873b24868140c412`; no network download was needed.
The library required permission to acquire its cache lock outside the repository.
All generated artifacts are inside the repository.

The command refuses to overwrite an existing output directory. Keep every earlier
pool under the same pool root. For exact replay, use the historical input inventory
recorded in the manifest: rerunning after adding other pools intentionally changes
eligibility. Regression tests use isolated temporary roots to compare identical
inputs without creating additional production pools.

## Artifacts and provenance

- `candidates.jsonl`: immutable EvidenceExample records; source labels are not
  approval decisions.
- `approval_snapshot.json`: immutable copy of the round's approved exclusions and
  retained IDs, including the source audit reference.
- `manifest.json`: policy version, seed, revision, source fingerprint, parent,
  checksums of all historical benchmark artifacts, previous pool provenance,
  blocked-ID/context digests, candidate IDs and checksum, and initial status.
- `reviews.jsonl`: initially empty; review events are stored separately.

The manifest does not include timestamps or output-directory-specific values,
so identical inputs produce identical manifest bytes. `initial_review_status`
remains `unreviewed`; later status must be derived from review events, not by
rewriting the immutable manifest. Prior-pool reviews do not affect sampling:
all prior-pool IDs remain blocked in new pools, including deferred or accepted
candidates. They can still be considered in their original pools.

## Append-only review protocol

`append_review(...)` is the sole implemented mutation API for review logs.
It has no delete, edit, reset, candidate-selection, or benchmark-assembly operation.
It validates the pool and existing log, obtains an advisory exclusive lock,
appends with OS `O_APPEND`, flushes and syncs the new event. A missing log is an
error; it is not silently recreated.

Events contain candidate ID, event type, actor role, reviewer, disposition
(`accept`, `reject`, `defer`), evidence, rationale, challenge-set eligibility,
optional supersession reference, sequence number, pool-manifest checksum,
previous-event checksum, and event checksum.

- `recommendation` + `ai_assisted`: advice only, never owner approval.
- `decision` + `project_owner`: requires an explicit approval reference to the
  actual owner's instruction. The caller must obtain that instruction first.
- Correct a decision by appending a new event that references the earlier event
  for the same candidate via `supersedes`; retain the old bytes.
- Reviewers must not treat a recommendation to accept as an accepted candidate.

This records provenance, not identity authentication. The hash chain detects
altered contents and ordering; it does not prevent someone with filesystem access
from rewriting a whole log or removing its tail. Git checkpoints preserve audit
history and provide an external record. Advisory locking coordinates writers that
use this API; it cannot control unrelated file editors.

One project-owner acceptance of Candidate 9 is now recorded. No other candidate
has a recommendation or decision recorded.

## Validation

`tests/test_candidate_pool.py` covers deterministic bytes under reversed source
order, immutable inputs, revision forwarding, cumulative approval validation,
all eligibility barriers, article/context diversity, prior-pool blocking,
missing/corrupt historical inputs, overwrite and insufficient-supply failures,
and review event validation, supersession, byte-prefix preservation, and tampering.

The real pool was separately checked against pre-generation hashes of all earlier
benchmark artifacts and exclusion configurations. All remained unchanged. There
was no curated_v4 directory at the Stage 1 checkpoint. Stage 2 has since created it.

Final Stage 1 test results:

- Targeted pool tests: **38 passed in 1.07s**.
- Full suite: **127 passed, six intentionally skipped in 1.60s**.
- `git diff --check`: passed.

The six skipped tests require explicit opt-in to the real SQuAD integration
suite. All new regression tests use synthetic data and temporary directories.

Stage 2 subsequently assembled the 19 retained records plus the explicitly
approved Candidate 9 with no resampling; see the linked assembly report.
