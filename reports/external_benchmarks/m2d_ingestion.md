# M2D: External benchmark ingestion

## Objective and scope

Expand development evaluation of unmodified Qwen3-1.7B before SFT. This milestone
only ingests and validates data; it produces no model predictions or performance
claims. Existing curated datasets, baseline artifacts, metrics, and M2C findings
are unchanged.

## Source and provenance

Source: Lavi, Milo, and Geva, [Detecting (Un)answerability in Large Language Models
with Linear Directions, EACL 2026](https://aclanthology.org/2026.eacl-long.29/).
The paper describes 800 balanced development examples per dataset. The four
released files actually contain 400 records each, confirming that count.

Repository: [MaorLavi/unanswerability-directions, pinned revision](https://github.com/MaorLavi/unanswerability-directions/tree/9ea9afbd2aa02052c7b3ee4995aa5f26e9b6cd2f).
Full commit: `9ea9afbd2aa02052c7b3ee4995aa5f26e9b6cd2f`.
Only `data/abstain_aware_prompt/{squad,repliqa}/{answerable,unanswerable}_val.json`
was downloaded. No repository clone, models, train, val2, or authors' test files
were downloaded. The raw cache is outside the project at
`/private/tmp/evidencetune-lavi-9ea9afbd`; it can be recreated from the pinned URLs.

The versioned output is `data/eval/external/lavi2026_v1/`. Its manifest records
each source URL, published split (`val`), label partition, record count, byte size,
SHA256, and Git blob SHA1, as well as hashes of the outputs and existing benchmark
files used for overlap checks. `source_records.jsonl` maps each generated ID to
its source filename, zero-based row index, canonical JSON record checksum, and
additional fields. This is provenance, not a review log or owner approval.

## Conversion policy

All 1,600 released records have `instruction`, `gt_answer`, and `category` fields;
`category` is null throughout. No original example, article, or document IDs are
supplied. The adapter validates the exact prompt prefix, passage/question
separator, and answer suffix, rejecting missing or ambiguous boundaries. It
removes only that wrapper, preserving passage, question, and reference strings.
The authors' prompt instructions never become EvidenceTune context.

Answerability and the existing schema's category come from the filename. Every
unanswerable reference must equal `The answer is not found in the document.`;
answerable references must be nonempty and must not equal that sentinel. The
original sentinel is retained, not replaced with EvidenceTune's output token
`ABSTAIN`. These structural checks do not independently validate semantic labels.

Example IDs encode the pinned release prefix, dataset, split, label partition,
and row index. Identical content at different positions still gets distinct IDs
and is reported rather than dropped. `source_id` explicitly means an exact
passage SHA256, **not an article identifier**. Output order is answerable source
order followed by unanswerable source order. There is no sampling or shuffling.

## Imported datasets and audit

| Dataset | Answerable | Unanswerable | Total |
|---|---:|---:|---:|
| SQuAD development | 400 | 400 | 800 |
| RepLiQA development | 400 | 400 | 800 |
| Total | 800 | 800 | 1,600 |

All records validate against `EvidenceExample`; all 1,600 generated IDs are unique.
Reconstruction from the pinned source bytes reproduces every output byte,
including the manifest and audit. Existing curated_v4 development and held-out
test checksums are verified before ingestion. The output directory cannot be
overwritten by the builder.

`overlap_audit.json` compares the four released label partitions and the existing
curated_v4 development/test sets. Exact record comparisons use context, question,
reference, and category, excluding generated identifiers. Normalized comparisons
apply Unicode NFKC, case folding, and whitespace collapse; punctuation remains.
The audit stores matching IDs and hashed keys, not held-out text.

| Check | Result |
|---|---|
| Duplicate context/question pairs, exact or normalized, within/across audited collections | 0 |
| Duplicate exact records within/across audited collections | 0 |
| Imported context/question overlap with curated_v4 dev or test | 0 |
| Imported passage overlap with curated_v4 dev or test, exact or normalized | 0 |
| SQuAD–RepLiQA shared passages, exact or normalized | 0 |
| Conflicting answerability labels on normalized context/question matches | 0 |
| Shared passages between SQuAD answerable/unanswerable partitions | 7 distinct passages; 7 records on each side |
| Shared passages between RepLiQA answerable/unanswerable partitions | 33 distinct passages; 34 records on each side; 35 matching pairs |

Repeated passage groups also occur within individual partitions: SQuAD has 2
answerable groups (4 records) and 8 unanswerable groups (16 records); RepLiQA has
17 answerable groups (34 records) and 28 unanswerable groups (57 records). Exact
and normalized passage checks give the same counts. These are shared contexts
with different questions, not duplicated QA examples. No rows were removed.

A lightweight reference-substring screen flags 370 RepLiQA answerable references
and zero SQuAD references. Paraphrased or synthesized references need not be
literal substrings; these flags are **not annotation-error findings**. No labels
were changed and the imported examples have not received an independent manual
semantic audit.

## Limitations and decisions before evaluation

- Missing original document IDs prevent certification of document-level source
  isolation. Different excerpts from the same document can evade passage checks.
  Authors' train/val2/test isolation was not checked because those files were not
  retrieved. Absence of text matches also says nothing about model pretraining
  exposure.
- Shared passages make some questions dependent. Report per-dataset results and
  consider passage-group uncertainty estimates; do not treat 1,600 questions as
  1,600 independent documents. Published development membership remains intact.
- These are external **development** evaluations, not a new untouched test set.
  Repeated use for experiment choices must be recorded. Existing held-out data
  was accessed only for automated integrity and overlap checks, not selection.
- Before inference, decide the common EvidenceTune prompt, exact abstention
  contract, context-length handling, and reference-based versus semantic review
  policy. Preserve the external negative references while evaluating abstention
  through answerability and the existing output contract. Avoid silent passage
  truncation. RepLiQA's non-extractive references merit attention when interpreting
  token overlap metrics.
- Running EvidenceTune's prompt is not an exact reproduction of the paper's
  prompting protocol. Report that distinction. Confirm applicable upstream
  dataset terms before redistribution; repository licensing alone does not
  establish all underlying data rights.

## Reproduction and validation

From the repository root, using its existing virtual environment:

```bash
# Re-download only the four pinned files if the temporary cache is absent,
# then verify the existing import without overwriting it.
.venv/bin/python -m src.data.import_lavi \
  --source-dir /private/tmp/evidencetune-lavi-9ea9afbd --download --verify

# Rebuild only when the versioned output does not yet exist:
.venv/bin/python -m src.data.import_lavi \
  --source-dir /private/tmp/evidencetune-lavi-9ea9afbd

.venv/bin/python -m pytest tests/test_lavi_ingestion.py -q
.venv/bin/python -m pytest -q
```

Tests were written before the adapter and builder. They cover strict extraction,
reference preservation, malformed templates, filename/answer disagreements,
deterministic bytes, schema/counts/IDs, source and output corruption, no overwrite,
existing benchmark preservation, normalized overlaps and conflicting labels,
duplicate retention, and the restricted downloader. Real-artifact checks run
offline; full reconstruction additionally requires the pinned raw cache.

Validation on 2026-11-24: targeted suite **26 passed**; full regression suite
**278 passed, 6 skipped** (the existing opt-in integration tests). The runs used
`--basetemp=.pytest_cache/m2d-targeted-final` and
`--basetemp=.pytest_cache/m2d-full`, respectively. Source-based `--verify` passed.
All 79 previously tracked files were compared byte-for-byte with `HEAD`: none
changed or went missing. In particular, curated_v4 checksums remain:

- Development: `a2b5fc8aa23cf6ca2738f482b993bf4c6626bed5f6adc5dd03461bfe4edb99b5`
- Held-out test: `0c6f9b3c89104fc79ffcc26efa506df7541044e586d43b8efca57b3f8ce56e5b`
