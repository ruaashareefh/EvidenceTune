# curated_v4 — Approved Candidate Assembly

Stage 2 completed on 2026-11-17. No model training or subsequent milestone work
was performed. The benchmark is not frozen: the held-out test still needs its
separate semantic review.

## Approval

The pool review log was empty on inspection. The project owner explicitly stated:
"I explicitly approved Candidate 9: squad_v2:5acf9d3477cf76001a685516."
This approval was appended through `candidate_pool.append_review`, as a
`decision` by `project_owner` with disposition `accept`. No other approvals or
rejections were inferred.

Approval event SHA-256:
`4da6b1f150df3c354aa114e60b452e3b8cdb1c96f5939b9d312bdf8b37019b26`.

Candidate 9 asks which year had the College's highest acceptance rate. Its
context gives the lowest rate, not the year of the highest rate. Its original
unanswerable label and record data are preserved.

## Implementation

`src/data/assemble_curated.py` provides explicit selection and read-only
verification. It does not call the source loader or any sampler.

Before writing, assembly verifies:

1. The pool records and approval-snapshot checksums.
2. Pinned source revision, historical benchmark hashes, and parent lineage.
3. All cumulative exclusions and the exact approved survivor inventory/order.
4. The review hash chain and the latest project-owner decision for the selected
   candidate. It must be `accept`; AI recommendations cannot grant or revoke
   owner approval, and a later owner rejection or deferral blocks assembly.
5. Historical and previous-pool ID/context restrictions, held-out source
   isolation, unique IDs, and final category balance.

The parent survivors are serialized in parent order; the unchanged selected
pool record is appended last. The original held-out test bytes are copied
without reserialization. Existing output directories are refused, including
empty directories; there is no overwrite option.

A shared review-log lock is held during assembly. The output archives the
approval log as `approval_reviews.jsonl`, along with `approval_snapshot.json`
and `pool_manifest.json`. The dataset manifest records the pool checksum,
parent/baseline checksums, selected ID, exact approval event and reference,
review-snapshot checksum, all exclusions, retained IDs, ordering, and split hashes.

`verify_assembly` reconstructs all six expected artifacts from the frozen inputs
and archived approval log. It also verifies that the archived review bytes remain
an unchanged prefix of the live append-only log. Additional reviews can be appended
without changing the historical evidence used to create this dataset. Verification
reports validity at assembly time; later owner decisions are not retroactive edits
of an immutable version.

The existing parent validator now recognizes `approved_candidate_assembly` as
well as generation-time pending-review status. Earlier manifests were not edited.
The pool history validator can validate the exact recorded history independently
of later versions, allowing read-only verification after v4 exists.

## Result

- 20 development records: 10 answerable and 10 unanswerable.
- 19 previously approved v3 records preserved unchanged and in order.
- Candidate 9, `squad_v2:5acf9d3477cf76001a685516`, is the final record.
- All 20 cumulative exclusions absent.
- Development/test IDs, sources, and contexts disjoint.
- Original test bytes preserved.
- Earlier benchmark artifacts, configurations, and immutable pool artifacts
  matched their pre-assembly checksums.
- Exactly one owner-decision event exists; other nine candidates remain unreviewed.

| Artifact | SHA-256 |
|---|---|
| Development | `a2b5fc8aa23cf6ca2738f482b993bf4c6626bed5f6adc5dd03461bfe4edb99b5` |
| Held-out test | `0c6f9b3c89104fc79ffcc26efa506df7541044e586d43b8efca57b3f8ce56e5b` |
| Manifest | `ef7e26c2612264f4c666898b8f9e60c50d2f147db252da2b78070616ab84c5b8` |

## Commands

Run from the repository root. The following assembly command was executed once;
it intentionally refuses a rerun at the existing output path:

```sh
.venv/bin/python -m src.data.assemble_curated \
  --eval-root data/eval \
  --pool-dir data/curation/candidate_pools/unanswerable_pool_001 \
  --output-dir data/eval/curated_v4 \
  --candidate-id squad_v2:5acf9d3477cf76001a685516
```

Safe read-only artifact verification:

```sh
.venv/bin/python -m src.data.assemble_curated --verify \
  --eval-root data/eval \
  --pool-dir data/curation/candidate_pools/unanswerable_pool_001 \
  --output-dir data/eval/curated_v4
cmp data/eval/squad_test.jsonl data/eval/curated_v4/squad_test.jsonl
shasum -a 256 data/eval/curated_v4/squad_dev.jsonl \
  data/eval/curated_v4/squad_test.jsonl data/eval/curated_v4/squad_manifest.json
```

Regression commands:

```sh
.venv/bin/python -m pytest tests/test_assemble_curated.py -q \
  --basetemp=.pytest_cache/assembly-targeted
.venv/bin/python -m pytest -q --basetemp=.pytest_cache/stage2-full
git diff --check
```

Results: **29 targeted tests passed in 2.60s**; **156 full-suite tests passed,
six intentionally skipped in 4.78s**. The skips are opt-in SQuAD integration
tests. Regression coverage includes selection authorization, revocation,
determinism, no sampling, invalid approvals, parent/pool corruption, overwrite
protection, preservation, order, archived approvals, and artifact verification.
