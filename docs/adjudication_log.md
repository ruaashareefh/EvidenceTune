# EvidenceTune: SQuAD Adjudication Log

**Milestone:** M1B.6 — Annotation Adjudication  
**Dataset:** SQuAD 2.0 (`rajpurkar/squad_v2`)  
**Source revision:** `3ffb306f725f7d2ce8394bc1873b24868140c412`  
**Evaluation split:** Development  
**Annotation guidelines:** v0.2  
**Review method:** AI-assisted evidence-based adjudication  
**Status:** Recommendations complete; independent verification pending

---

## 1. Objective

Resolve the nine examples flagged during the initial semantic audit, using EvidenceTune Annotation Guidelines v0.2.

The goal is to ensure that every example retained in the primary benchmark has a reliable category, evidence-supported reference answer, and sufficiently clear question.

Adjudication decisions must not depend on observed model performance.

## 2. Adjudication Principles

The following rules apply:

- Preserve the original SQuAD labels and reference answers.
- Accept examples only when their existing annotations are reliable under the primary benchmark rules.
- Exclude examples with unresolved ambiguity, unsupported reference answers, or incorrect annotations.
- Retain suitable false-premise examples separately as challenge-set candidates.
- Document the evidence and rationale for each decision.
- Require independent verification before treating recommendations as final approvals.

A recommendation to exclude does not establish that the original SQuAD annotation is universally incorrect. It establishes that the record is unsuitable for EvidenceTune's current evaluation requirements.

---

## 3. Individual Adjudication Results

### Example 2 — Ambiguous Answerability

**Record ID:** `squad_v2:5ad27697d7d075001a42951b`

**Original category:** `unanswerable`  
**Issue type:** `ambiguous_question`

**Question:** There is much net force when what is taken into consideration?

**Relevant evidence:** The passage explains that accounting for kinetic friction results in no net force during constant-velocity motion.

**Finding:** Kinetic friction appears to provide the requested information. However, the question's wording is grammatically unclear, making the intended interpretation unreliable.

**Recommended disposition:** Exclude from primary benchmark.

**Rationale:** The original abstention reference may penalize an evidence-grounded answer. The question cannot reliably distinguish correct answering from abstention.

### Example 4 — Ambiguous Geographic Reference

**Record ID:** `squad_v2:5a57fe29770dc0001aeeff1b`

**Original category:** `unanswerable`  
**Issue type:** `ambiguous_question`

**Question:** Where can lower rocks of the Grand Canyon be seen?

**Relevant evidence:** The passage identifies a location within the Maria Fold and Thrust Belt where the Grand Canyon's sedimentary sequence can be observed.

**Finding:** The context provides a plausible location, but it does not clearly establish what the question means by "lower rocks."

**Recommended disposition:** Exclude from primary benchmark.

**Rationale:** Multiple interpretations remain defensible. Retaining the original generic abstention reference could create an unreliable evaluation signal.

### Example 6 — Malformed Question

**Record ID:** `squad_v2:5a25d89aef59cd001a623cf8`

**Original category:** `unanswerable`  
**Issue type:** `malformed_question`

**Question:** Proper valuations happened in a government project because of what by the owner?

**Relevant evidence:** The passage discusses cost engineers performing valuations and government-project cost overruns involving change orders.

**Finding:** The question introduces a relationship involving the owner that cannot be reliably reconstructed from the passage.

**Recommended disposition:** Exclude from primary benchmark.

**Rationale:** The requested fact is unclear. Even if abstention is reasonable, the question is unsuitable for consistent annotation or scoring.

### Example 7 — Unsupported Reference Inference

**Record ID:** `squad_v2:56dde1d966d3e219004dad8d`

**Original category:** `answerable`  
**Issue type:** `unsupported_inference`

**Question:** Who upon arriving gave the original viking settlers a common identity?

**Original reference answer:** Rollo

**Relevant evidence:** The passage discusses Rollo's arrival and settlement in Normandy, along with earlier Viking populations.

**Finding:** Rollo is a plausible answer, but the context does not explicitly establish that he gave the settlers a common identity.

**Recommended disposition:** Exclude from primary benchmark.

**Rationale:** The reference answer requires an inference beyond what the provided evidence reliably establishes.

### Example 8 — Reversed Chronology

**Record ID:** `squad_v2:5ad3ad61604f3c001a3fec0d`

**Original category:** `unanswerable`  
**Issue type:** `false_premise`

**Question:** when did Nors encampments ivolve into destructive incursions?

**Relevant evidence:** The passage states that destructive Norse incursions evolved into more permanent encampments during the tenth century.

**Finding:** The question reverses the relationship established by the context.

**Recommended disposition:** Exclude from primary benchmark; retain as a false-premise challenge-set candidate.

**Preferred behavior:** Explain that destructive incursions evolved into permanent encampments during the tenth century, rather than the reverse.

**Rationale:** The current generic abstention reference does not measure evidence-grounded correction appropriately.

### Example 10 — Incorrect Presidential Ordinal

**Record ID:** `squad_v2:5acf808877cf76001a685004`

**Original category:** `unanswerable`  
**Issue type:** `false_premise`

**Question:** In what year did the fourth president, Robert Maynard Hutchins take office?

**Relevant evidence:** The passage identifies Robert Maynard Hutchins as the fifth president and states that he took office in 1929.

**Finding:** The question incorrectly calls Hutchins the fourth president. The evidence directly supports a correction.

**Recommended disposition:** Exclude from primary benchmark; retain as a false-premise challenge-set candidate.

**Preferred response:** Robert Maynard Hutchins was the fifth president, not the fourth. He took office in 1929.

**Rationale:** An evidence-grounded correction is more appropriate than generic abstention and requires a distinct evaluation criterion.

### Example 14 — Incorrect Numerical Premise

**Record ID:** `squad_v2:5ad03c7377cf76001a686ebc`

**Original category:** `unanswerable`  
**Issue type:** `false_premise`

**Question:** What year was the Northridge earthquake that caused $20 million in damage?

**Relevant evidence:** The passage identifies the 1994 Northridge earthquake and reports property damage exceeding $20 billion.

**Finding:** The question contains an incorrect damage amount. The year is nevertheless explicitly supported.

**Recommended disposition:** Exclude from primary benchmark; retain as a false-premise challenge-set candidate.

**Preferred response:** The Northridge earthquake occurred in 1994. The passage reports over $20 billion in damage, not $20 million.

**Rationale:** Generic abstention does not adequately evaluate the model's ability to recognize and correct the incorrect premise.

### Example 18 — Ambiguous Geographic Scope

**Record ID:** `squad_v2:5ad26d27d7d075001a4293c2`

**Original category:** `unanswerable`  
**Issue type:** `ambiguous_question`

**Question:** Where is the border of Germany?

**Relevant evidence:** The passage describes Lake Constance, its location across Germany, Switzerland, and Austria, and the states and cantons bordering its shores.

**Finding:** The question does not identify which German border or geographical relationship it asks about.

**Recommended disposition:** Exclude from primary benchmark.

**Rationale:** The requested answer cannot be interpreted consistently enough for reliable evaluation.

### Example 20 — Incorrect Terminology

**Record ID:** `squad_v2:5a8917433b2508001a72a4b2`

**Original category:** `unanswerable`  
**Issue type:** `malformed_question`

**Question:** Any even number larger than what cannot be considered distinct?

**Relevant evidence:** The passage states that no even number greater than 2 is prime and explains the existence of at least three distinct divisors.

**Finding:** The question uses "distinct" in a way that does not establish a meaningful mathematical request. The number 2 is present, but its relationship to the question is unclear.

**Recommended disposition:** Exclude from primary benchmark.

**Rationale:** The question's intended meaning cannot be reliably established.

---

## 4. Previously Confirmed Exclusion

### Example 15 — Incorrect Reference Answer

**Record ID:** `squad_v2:57306797396df919000960f1`

**Original category:** `answerable`  
**Issue type:** `incorrect_reference`

**Question:** Which is more costly, formal, or informal imperialism?

**Original reference answer:** informal

**Relevant evidence:** The passage states that informal rule is generally less costly than taking over territories formally.

**Finding:** The original reference answer contradicts the context. The evidence supports "formal."

**Recommended disposition:** Maintain exclusion from primary benchmark unless a reviewed correction is approved.

**Rationale:** The category `answerable` is appropriate, but the supplied reference answer is incorrect.

---

## 5. Adjudication Summary

### Recommended Outcomes

| Outcome | Count |
|---|---:|
| Initially reviewed examples | 20 |
| Accepted without adjudication | 10 |
| Flagged examples reviewed here | 9 |
| Previously identified exclusion | 1 |
| Recommended total exclusions | 10 |
| Unresolved recommendations | 0 |
| Pending independent verification | 10 exclusions |

### Expected Primary Benchmark Distribution

If all recommendations are approved:

| Original category | Retained | Excluded | Original total |
|---|---:|---:|---:|
| `answerable` | 8 | 2 | 10 |
| `unanswerable` | 2 | 8 | 10 |
| **Total** | **10** | **10** | **20** |

These totals represent proposed curation decisions, not a completed benchmark freeze.

### False-Premise Challenge-Set Candidates

| Example | Issue |
|---|---|
| 8 | Reversed chronology |
| 10 | Incorrect presidential ordinal |
| 14 | Incorrect numerical premise |

These records should be stored as candidates for separate evaluation, not incorporated into the primary benchmark without appropriate reference answers and scoring rules.

---

## 6. Quality Assurance and Verification

**Review method:** AI-assisted adjudication using the supplied passages and Annotation Guidelines v0.2.

**Independent review:** Not yet performed.

**Approval status:** Pending.

Before final approval:

1. Verify all record IDs against `data/eval/squad_dev.jsonl`.
2. Confirm that the original contexts, questions, and answers match the reviewed records.
3. Apply the current annotation guidelines to each recommendation.
4. Obtain independent human review where feasible.
5. Record any disagreements and their resolutions.
6. Approve the final inclusion and exclusion list.
7. Version the curation artifact.

A second review by the same assistant should not be reported as independent inter-annotator agreement.

---

## 7. Next Milestone

**M1B.7 — Reproducible Dataset Curation**

Once the adjudication recommendations are verified and approved:

- Create `data/curation/squad_exclusions.json` with the approved excluded record IDs and reasons.
- Update `src/data/build_eval.py` to support exclusion-based deterministic sampling.
- Add tests confirming excluded records cannot enter the generated benchmark.
- Regenerate development candidates using the pinned upstream revision.
- Audit all replacement examples.
- Independently review the held-out test set.
- Verify final category balance, source isolation, and artifact checksums.
- Freeze the benchmark only after all included records are approved.

**Current status:** Evidence-based adjudication recommendations complete. Final verification and approval pending.
