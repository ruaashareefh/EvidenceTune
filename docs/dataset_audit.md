# EvidenceTune: Dataset Quality Audit

**Milestone:** M1B  
**Dataset:** SQuAD 2.0  
**Source:** `rajpurkar/squad_v2`  
**Source revision:** `3ffb306f725f7d2ce8394bc1873b24868140c412`  
**Source split:** validation  
**Evaluation split:** Development  
**Sampling seed:** 42  
**Total examples:** 20  
**Review status:** First-pass review complete (20/20); adjudication pending

---

## 1. Audit Objective

This audit evaluates the semantic quality of EvidenceTune's development dataset before it is used to benchmark language models.

Automated tests verify schema validity, label consistency, reproducibility, and source-group isolation. However, these checks cannot establish whether individual reference answers and answerability labels are semantically correct.

The audit evaluates four dimensions:

1. **Label correctness:** Does the original answerability category accurately reflect the evidence?
2. **Reference answer correctness:** Is the expected answer supported by the context?
3. **Question quality:** Is the question sufficiently clear and unambiguous?
4. **Evidence grounding:** Can the expected response be justified using only the supplied context?

The goal is to construct a reliable benchmark for measuring evidence-grounded answering and appropriate abstention.

## 2. Dataset Information

### Source Configuration

| Property | Value |
|---|---|
| Dataset | SQuAD 2.0 |
| Hugging Face repository | `rajpurkar/squad_v2` |
| Revision | `3ffb306f725f7d2ce8394bc1873b24868140c412` |
| Source split | validation |
| Sampling seed | 42 |
| Grouping strategy | Article title |
| Development examples | 20 |
| Answerable examples | 10 |
| Unanswerable examples | 10 |

### Artifact Checksums

**Development dataset**

`squad_dev.jsonl`

SHA-256:

`aef86cd90bb3a76c5b4052009d2d6715563fad1b0a34badc2011f1b81268fd57`

**Held-out test dataset**

`squad_test.jsonl`

SHA-256:

`0c6f9b3c89104fc79ffcc26efa506df7541044e586d43b8efca57b3f8ce56e5b`

Both checksums were independently verified against the generated files using `shasum -a 256`.

The source revision is pinned, and the dataset generation pipeline uses deterministic sampling.

The test split has not yet undergone semantic review.

---

## 3. Review Policy

### Accept

An example is accepted when:

- The assigned category is correct.
- The reference answer is consistent with the context.
- The question is sufficiently clear.
- The expected response provides a reliable evaluation target.

### Flag

An example is flagged when:

- The category may be incorrect.
- The reference answer may not be fully supported.
- The question contains ambiguity or a misleading premise.
- Further review is necessary before determining whether to retain the record.

### Exclude

An example is excluded when:

- The reference answer is demonstrably incorrect.
- The assigned label contradicts the evidence.
- The question is unsuitable for reliable evaluation.
- Its ambiguity remains unresolved after adjudication.

### Curation Principles

- Preserve original SQuAD source records and labels.
- Record curation decisions separately from source data.
- Do not modify labels to improve model evaluation scores.
- Resolve flagged records before benchmark finalization.
- Document every exclusion with a specific reason.
- Select replacements deterministically.
- Audit replacement examples before accepting them.
- Do not use held-out model predictions to guide benchmark corrections.

---

## 4. Development Dataset Review

### Examples 1–5

| # | Record ID | Original label | Decision | Reason |
|---|---|---|---|---|
| 1 | `squad_v2:57377aac1c4567190057447d` | answerable | Accept | The context explicitly identifies "force" as the notion retaining its meaning in quantum mechanics. |
| 2 | `squad_v2:5ad27697d7d075001a42951b` | unanswerable | Flag | The question is awkwardly phrased, but kinetic friction appears to provide an evidence-supported answer. |
| 3 | `squad_v2:57266193dd62a815002e832e` | answerable | Accept | "Wave speeds" is explicitly supported by the passage. |
| 4 | `squad_v2:5a57fe29770dc0001aeeff1b` | unanswerable | Flag | The context identifies the Maria Fold and Thrust Belt as a relevant location. The phrase "lower rocks" introduces ambiguity. |
| 5 | `squad_v2:572756fe708984140094dc74` | answerable | Accept | The specified safety equipment and procedures are explicitly supported by the passage. |

### Examples 6–10

| # | Record ID | Original label | Decision | Reason |
|---|---|---|---|---|
| 6 | `squad_v2:5a25d89aef59cd001a623cf8` | unanswerable | Flag | The question is poorly constructed and does not clearly establish the intended relationship between valuations, government projects, and the owner. |
| 7 | `squad_v2:56dde1d966d3e219004dad8d` | answerable | Flag | Rollo is a plausible reference answer, but the specific claim about giving Viking settlers a common identity is not explicitly established. |
| 8 | `squad_v2:5ad3ad61604f3c001a3fec0d` | unanswerable | Flag | The question reverses the chronology in the context. Destructive incursions evolved into permanent encampments, not vice versa. |
| 9 | `squad_v2:572861cc4b864d1900164960` | answerable | Accept | The context explicitly identifies 1996 as the start of the bachelor's program in Cinema & Media Studies. |
| 10 | `squad_v2:5acf808877cf76001a685004` | unanswerable | Flag | The question identifies Hutchins as the fourth president, while the passage calls him the fifth. The passage nevertheless provides 1929 as his starting year. |

### Examples 11–15

| # | Record ID | Original label | Decision | Reason |
|---|---|---|---|---|
| 11 | `squad_v2:57263c78ec44d21400f3dc7b` | answerable | Accept | The passage explicitly states that ARPANET and SITA HLN became operational in 1969. |
| 12 | `squad_v2:5a66797c846392001a1e1c49` | unanswerable | Accept | The passage does not establish a specific packet delivery method when there is no shared physical medium. |
| 13 | `squad_v2:570611c475f01819005e793c` | answerable | Accept | The Port of Los Angeles is explicitly identified as the United States' busiest commercial port. |
| 14 | `squad_v2:5ad03c7377cf76001a686ebc` | unanswerable | Flag | The question says $20 million in earthquake damage, whereas the passage reports over $20 billion. The year is available, but the premise is false. |
| 15 | `squad_v2:57306797396df919000960f1` | answerable | Exclude | The reference answer "informal" contradicts the passage. The context indicates that formal territorial control is more costly. |

### Examples 16–20

| # | Record ID | Original label | Decision | Reason |
|---|---|---|---|---|
| 16 | `squad_v2:5ad031ef77cf76001a686df6` | unanswerable | Accept | The passage discusses French imperialism and the spread of Catholicism, but the question asks about English imperialism. The requested answer is not supported for England. |
| 17 | `squad_v2:57300a25a23a5019007fcc9b` | answerable | Accept | The passage explicitly dates the Rhine crisis to 1840. |
| 18 | `squad_v2:5ad26d27d7d075001a4293c2` | unanswerable | Flag | The question "Where is the border of Germany?" is insufficiently specific. The passage describes Lake Constance and surrounding regions without identifying the intended border. |
| 19 | `squad_v2:572991943f37b319004784a2` | answerable | Accept | Twin primes are explicitly defined as pairs of primes that differ by 2. |
| 20 | `squad_v2:5a8917433b2508001a72a4b2` | unanswerable | Flag | The passage establishes that even numbers greater than 2 are not prime, but the question incorrectly uses the term "distinct." The intended relationship is unclear even though the number 2 appears. |

---

## 5. Audit Summary

### Overall Results

| Metric | Count | Percentage |
|---|---:|---:|
| Total development examples | 20 | 100% |
| Reviewed | 20 | 100% |
| Accepted | 10 | 50% |
| Flagged | 9 | 45% |
| Excluded | 1 | 5% |
| Remaining unreviewed | 0 | 0% |

**First-pass review status:** Complete

**Adjudication status:** Pending

### Results by Original Category

| Original category | Accepted | Flagged | Excluded | Total |
|---|---:|---:|---:|---:|
| answerable | 8 | 1 | 1 | 10 |
| unanswerable | 2 | 8 | 0 | 10 |
| **Total** | **10** | **9** | **1** | **20** |

### Interpretation

The initial audit identified a relatively high proportion of questionable unanswerable examples.

Eight of the ten original unanswerable examples were flagged for review.

However, **a flagged example is not necessarily incorrectly labeled**. Some records may be legitimately unanswerable while containing poorly constructed questions or false premises.

The observed rates describe only this 20-record sample. They should not be generalized to the full SQuAD 2.0 dataset.

---

## 6. Key Findings

### Finding 1: Potential Answerability Label Errors

Examples 2 and 4 are labeled `unanswerable`, despite containing information that appears to provide answers.

**Example 2**

The question asks what is taken into consideration when discussing net force.

The passage explicitly refers to kinetic friction.

**Example 4**

The question asks about the location of certain Grand Canyon rock layers.

The passage identifies the Maria Fold and Thrust Belt as a potentially relevant location.

These examples could penalize models for producing evidence-supported answers when the benchmark expects abstention.

Both require further adjudication before a final decision.

### Finding 2: False Premises and Reversed Relationships

Examples 8, 10, 14, and 20 contain false, reversed, or semantically inconsistent premises.

Examples include:

- Example 8 reverses the transition from destructive incursions to permanent encampments.
- Example 10 incorrectly identifies Hutchins as the fourth president instead of the fifth.
- Example 14 incorrectly describes earthquake damage as $20 million instead of over $20 billion.
- Example 20 uses "distinct" where the context discusses whether even numbers are prime.

These findings raise an important annotation-policy question:

**Should the model abstain completely when a question contains a false premise, or should it correct the premise using the provided evidence?**

EvidenceTune must define its expected behavior consistently.

Until that policy is finalized, these examples remain flagged.

### Finding 3: Unsupported Inferences

Example 7 expects "Rollo" as its reference answer.

Although Rollo's arrival and settlement are discussed, the passage does not directly establish that he provided the original Viking settlers with a common identity.

This illustrates the distinction between:

- An answer that is plausible given the topic.
- An answer explicitly or sufficiently supported by the evidence.

EvidenceTune should require adequate evidence support rather than relying on plausibility alone.

### Finding 4: Incorrect Reference Answer

Example 15 contains a confirmed reference-answer error.

**Question:** Which is more costly, formal, or informal imperialism?

**Original reference answer:** informal

**Evidence-supported answer:** formal

The passage states that informal rule is generally less costly than formally taking over territories.

The original reference answer therefore contradicts the evidence.

**Decision:** Exclude from the current benchmark unless a documented correction is independently reviewed and approved.

### Finding 5: Ambiguous Question Scope

Examples 6 and 18 contain questions whose intended meaning is unclear.

**Example 6:** The question does not clearly express the relationship it asks about.

**Example 18:** The question does not specify which German border is being discussed.

Even when abstention is reasonable, poorly constructed questions can introduce noise into evaluation results.

### Finding 6: Valid Unanswerable Questions

Examples 12 and 16 illustrate cases where the supplied context does not support the requested answer.

Example 16 is especially useful because the passage discusses France, while the question asks about England.

Although Catholicism is mentioned, the passage does not establish what religion the English spread.

Answering "Catholicism" for England would improperly transfer evidence from one subject to another.

This example is provisionally accepted as an evidence-grounded abstention case.

---

## 7. Flagged Example Adjudication

The following nine examples require a final decision.

| Example | Main issue | Required review |
|---|---|---|
| 2 | Potential answer in context | Determine whether kinetic friction directly answers the intended question |
| 4 | Potential location in context | Determine whether the Maria Fold and Thrust Belt satisfies the question |
| 6 | Malformed question | Determine whether the example can be interpreted consistently |
| 7 | Unsupported inference | Determine whether "Rollo" meets the evidence-support threshold |
| 8 | Reversed chronology | Apply the false-premise response policy |
| 10 | Incorrect president number | Apply the false-premise response policy |
| 14 | Incorrect damage amount | Apply the false-premise response policy |
| 18 | Ambiguous geographic question | Determine whether the question has a sufficiently clear interpretation |
| 20 | Incorrect terminology | Determine whether the intended question can be established reliably |

### Adjudication Procedure

For each flagged example:

1. Review the complete context and question again.
2. Consult `docs/annotation_guidelines.md`.
3. Identify the precise evidence supporting or contradicting the expected response.
4. Determine whether the original category is defensible.
5. Assign a final decision of Accept or Exclude.
6. Record the decision and its rationale.
7. Keep the original source annotation unchanged.

If an example cannot be evaluated consistently under the guidelines, exclude it from the finalized benchmark.

---

## 8. Curation Plan

Once flagged records are resolved, implement deterministic curation.

### Proposed Exclusion File

`data/curation/squad_exclusions.json`

The file should contain excluded example IDs and documented reasons.

### Pipeline Requirements

The curation pipeline must:

1. Load the original pinned SQuAD dataset.
2. Load the reviewed exclusion list.
3. Remove excluded candidates before sampling.
4. Generate replacements using a fixed seed.
5. Preserve the expected category distribution.
6. Maintain source-group isolation between development and test splits.
7. Validate all selected examples.
8. Record exclusion-list provenance in the manifest.
9. Recalculate artifact checksums.
10. Require independent review of replacement examples.

### Important Constraint

Removing an invalid example does not automatically make its replacement valid.

Replacement records must undergo the same semantic quality review before being included in the frozen benchmark.

---

## 9. Test Dataset Review

The held-out test dataset contains:

- 10 answerable examples.
- 10 unanswerable examples.
- 20 examples total.

Its artifact checksum has been verified, but its semantic quality has not yet been reviewed.

Before freezing the test split:

1. Review its labels and reference answers independently of model predictions.
2. Document ambiguous or incorrect records.
3. Apply the finalized annotation guidelines.
4. Replace excluded records deterministically.
5. Verify source separation and checksums.
6. Freeze the final test dataset.

No model-generated answers should be used to decide which test records are retained.

---

## 10. Remaining Work

### Completed

- [x] Define semantic audit criteria.
- [x] Review examples 1–5.
- [x] Review examples 6–10.
- [x] Review examples 11–15.
- [x] Review examples 16–20.
- [x] Complete first-pass development review.
- [x] Identify the confirmed reference-answer error.
- [x] Document ambiguous and potentially incorrect labels.
- [x] Verify the pinned source revision and generated file checksums.

### Pending

- [ ] Finalize the false-premise annotation policy.
- [ ] Resolve all nine flagged examples.
- [ ] Finalize accepted and excluded record lists.
- [ ] Create the exclusion-list artifact.
- [ ] Implement deterministic replacement sampling.
- [ ] Test curation logic.
- [ ] Audit replacement records.
- [ ] Audit the held-out test set.
- [ ] Complete the remaining EvidenceTune evaluation categories.
- [ ] Regenerate and verify the final manifest.
- [ ] Freeze the benchmark.
- [ ] Merge the approved M1B changes.

---

## 11. Conclusion

EvidenceTune's SQuAD 2.0 development dataset has completed its initial semantic quality review.

All 20 examples were inspected against their contexts, questions, and reference answers.

The review resulted in:

- **10 accepted examples**
- **9 flagged examples**
- **1 excluded example**

The audit identified potential answerability-label errors, unsupported inferences, false premises, ambiguous questions, and a confirmed incorrect reference answer.

These findings demonstrate that successful automated validation does not guarantee that an evaluation dataset is semantically reliable.

A reproducible benchmark requires both technical correctness and independently reviewed ground truth.

**Current milestone status:** M1B first-pass semantic audit complete. Adjudication, curation, replacement review, and benchmark finalization remain pending.

**Benchmark approval:** Not yet approved for final baseline evaluation.
