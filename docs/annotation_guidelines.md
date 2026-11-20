# EvidenceTune: Annotation Guidelines

| Field | Value |
|---|---|
| Version | 0.2 |
| Status | Draft, pending adjudication |
| Milestone | M1B: Evaluation Dataset |
| Last Updated | 2026-11-16 |
| Related Documents | `docs/evaluation_spec.md`, `docs/dataset_audit.md` |
| Dataset Schema | `src/data/schema.py` |

---

## 1. Purpose

This document establishes standardized procedures for annotating EvidenceTune's evidence-grounded question-answering dataset.

The objective is to produce accurate, consistent, and reproducible ground-truth labels for evaluating an LLM's ability to:

1. Answer questions using supplied evidence.
2. Abstain when required information is missing.
3. Recognize contradictory evidence.
4. Reject irrelevant evidence.
5. Distinguish partially supported answers from fully supported answers.
6. Identify and appropriately correct false premises when supported by evidence.

These guidelines apply to annotators, reviewers, and engineers involved in creating, validating, and curating the evaluation dataset.

### 1.1 Core Principle

**All annotations must be grounded exclusively in the provided context.**

Annotators must not use external knowledge, assumptions, or unstated facts to establish answerability.

A response may be factually correct in the real world but incorrect for EvidenceTune if the supplied context does not support it.

EvidenceTune evaluates evidence-grounded behavior, not simply whether a model knows the correct answer.

### 1.2 Annotation Objectives

The annotation process must establish:

- Whether the question is fully answerable.
- What information is directly supported.
- What information is missing.
- Whether relevant evidence conflicts.
- Whether the question contains unsupported or false assumptions.
- What an evidence-grounded response should contain.

### 1.3 Scope

This document defines:

- Annotation workflow and responsibilities.
- The five primary category definitions.
- Category assignment and precedence rules.
- Reference-answer requirements.
- False-premise detection and correction policy.
- Ambiguous-case handling.
- Annotation quality assurance.
- Review and adjudication procedures.
- Dataset curation, leakage prevention, and versioning.

Model predictions, scoring, and evaluation metrics are governed separately by `docs/evaluation_spec.md`.

---

## 2. Annotation Schema

Each example included in the primary benchmark must conform to the `EvidenceExample` Pydantic schema.

| Field | Type | Description |
|---|---|---|
| `id` | string | Unique record identifier |
| `source_id` | string | Identifier for the source document |
| `context` | string | Evidence supplied to the model |
| `question` | string | Question to be answered |
| `answer` | string | Reference response |
| `answerable` | boolean | Whether the entire question is answerable |
| `category` | enum | Evidence sufficiency classification |

### 2.1 Primary Categories

Every example in the primary benchmark must receive exactly one category:

1. `answerable`
2. `unanswerable`
3. `contradictory`
4. `irrelevant`
5. `partially_supported`

Set `answerable=true` only when `category="answerable"`.

All other categories require `answerable=false`.

The `answerable` field represents **full answerability**, not whether any portion of the question can be answered.

### 2.2 Separate Annotation Metadata

For auditability, maintain additional metadata separately from `EvidenceExample`.

Recommended fields include:

| Field | Description |
|---|---|
| `source_record_id` | Identifier in the original dataset |
| `original_category` | Original source classification |
| `annotator_id` | Identifier of the annotator |
| `reviewer_id` | Identifier of the reviewer |
| `guideline_version` | Annotation guideline version |
| `source_revision` | Pinned upstream dataset revision |
| `review_status` | Pending, accepted, flagged, or excluded |
| `issue_type` | Identified annotation or question-quality problem |
| `expected_behavior` | Intended model behavior when special handling is required |
| `evidence_excerpt` | Supporting or contradicting text |
| `rationale` | Explanation of the annotation decision |

Possible issue types include:

- `false_premise`
- `ambiguous_question`
- `unsupported_inference`
- `incorrect_reference`
- `label_conflict`
- `insufficient_evidence`
- `malformed_question`

These issue types are **review metadata, not additional primary categories**.

Do not add metadata fields directly to `EvidenceExample` without updating the schema, validators, and tests.

### 2.3 Original Source Labels

When importing external datasets such as SQuAD 2.0:

- Preserve the original source labels.
- Record changes in a separate review or curation artifact.
- Do not silently overwrite source annotations.
- Do not assume external benchmark labels are error-free.
- Distinguish source annotations from EvidenceTune's final adjudicated decisions.

---

## 3. Annotation Procedure

Annotators must follow the same process for every example.

### Step 1: Review the Context

Read the entire supplied context.

Identify:

- Relevant factual claims.
- Named entities.
- Dates and quantities.
- Relationships between entities.
- Potentially conflicting statements.
- Any limitations in the evidence.

### Step 2: Interpret the Question

Identify exactly what information the question requests.

For multi-part questions, separate each requested component.

Determine whether the question contains:

- Ambiguous wording.
- Missing referents.
- Unsupported assumptions.
- Claims contradicted by the context.
- Multiple possible interpretations.

### Step 3: Check Question Validity

Before assigning a primary category, determine whether the question is suitable for the benchmark.

A question must be flagged when:

- Its intended meaning cannot be established reliably.
- It contains a material false premise requiring specialized evaluation.
- Its wording reverses or misrepresents a relationship in the context.
- Its reference answer contradicts the supplied evidence.

Such examples must be reviewed before inclusion in the primary benchmark.

### Step 4: Assess Evidence Sufficiency

For each requested fact, determine whether it is:

- Fully supported.
- Partially supported.
- Missing.
- Contradicted by supplied evidence.
- Unrelated to the provided context.

Only explicit evidence and straightforward logical implications are permitted.

Do not infer facts based on typical real-world patterns.

### Step 5: Assign a Category

For examples suitable for the primary benchmark, apply the category definitions in Section 4 and decision rules in Section 5.

### Step 6: Write the Reference Answer

Produce a concise, evidence-grounded response appropriate to the category.

The reference response must not include unsupported information.

### Step 7: Validate and Submit

Verify:

- Schema compliance.
- Correct category assignment.
- Consistency between `category` and `answerable`.
- Reference-answer accuracy.
- Evidence support.
- Question clarity.
- Review metadata completeness.

Flag unresolved cases rather than forcing a category.

---

## 4. Primary Category Definitions

### 4.1 Answerable

**Definition:** The supplied context contains sufficient, internally consistent evidence to answer every requested component.

**Inclusion criteria:**

- All requested information is supported.
- No unsupported assumptions are required.
- No unresolved material contradiction affects the answer.
- Direct extraction, paraphrasing, or straightforward logical inference is sufficient.

**Exclusion criteria:**

- A necessary fact is missing.
- Material evidence conflicts.
- Only some components can be answered.
- The expected reference answer is contradicted by the context.

**Example**

Context:

> Atlas Robotics was founded in Boston in 2021.

Question:

> Where was Atlas Robotics founded?

Category: `answerable`

Answerable: `true`

Reference answer:

> Boston.

**Boundary case:** A product's launch date does not establish the company's founding date unless the context explicitly connects them.

### 4.2 Unanswerable

**Definition:** The context concerns the relevant subject but lacks sufficient evidence to answer the requested question.

**Inclusion criteria:**

- The subject is relevant to the context.
- The requested fact is absent.
- No requested component can be adequately answered.
- No unresolved material contradiction requires another category.

**Example**

Context:

> Atlas Robotics was founded in Boston in 2021.

Question:

> Who founded Atlas Robotics?

Category: `unanswerable`

Answerable: `false`

Reference answer:

> The provided context does not identify the founder.

**Boundary case:** Missing evidence does not establish a negative answer.

If the context does not identify the founder, annotators cannot conclude that the company has no founder.

### 4.3 Contradictory

**Definition:** The context contains incompatible claims about a fact necessary to answer the question, without an established basis for resolving the conflict.

**Inclusion criteria:**

- At least two relevant claims conflict.
- The claims concern the same entity, attribute, and applicable timeframe.
- The conflict affects the requested answer.
- The context does not establish an authoritative resolution.

**Example**

Context:

> Report A states that Project Nova began in 2020. Report B states that Project Nova began in 2022.

Question:

> When did Project Nova begin?

Category: `contradictory`

Answerable: `false`

Reference answer:

> The reports provide conflicting dates: 2020 and 2022.

**Boundary cases:**

- Different values are not necessarily contradictory if they refer to different periods or entities.
- Contradictions unrelated to the requested fact do not automatically affect the category.
- A question containing a false premise is not automatically classified as `contradictory`.

**Important distinction:** The `contradictory` category concerns conflicting claims **within the evidence**. A false-premise question concerns a conflict **between the question's assumption and the evidence**.

These must be evaluated differently.

### 4.4 Irrelevant

**Definition:** The supplied context contains no information materially relevant to the question's requested subject or answer.

**Inclusion criteria:**

- The context concerns a different subject.
- No useful evidence for the requested answer is supplied.
- Answering would require external knowledge.

**Example**

Context:

> Atlas Robotics develops warehouse automation software.

Question:

> What is the capital of Japan?

Category: `irrelevant`

Answerable: `false`

Reference answer:

> The provided context does not contain information about Japan's capital.

**Boundary case:** If the context discusses the same subject but omits the requested attribute, use `unanswerable`, not `irrelevant`.

### 4.5 Partially Supported

**Definition:** The context supports at least one requested component but does not sufficiently support the entire question.

**Inclusion criteria:**

- The question contains multiple requested facts or separable components.
- At least one component is supported.
- At least one required component is missing.
- No material contradiction takes precedence.

**Example**

Context:

> Atlas Robotics was founded in Boston in 2021.

Question:

> Where was Atlas Robotics founded, and who founded it?

Category: `partially_supported`

Answerable: `false`

Reference answer:

> Atlas Robotics was founded in Boston. The context does not identify its founder.

**Boundary case:** An example is not partially supported merely because the context contains related information.

At least one actual requested component must be answerable.

---

## 5. Label Decision Rules

Primary categories must be mutually exclusive.

Before classification, check whether the question contains a material false premise, is malformed, or has an unreliable reference answer. Flag such records for adjudication when these issues prevent dependable evaluation.

For eligible primary-benchmark examples, apply the following rules:

1. **Material contradiction:** If unresolved conflicting claims in the context affect the requested answer, assign `contradictory`.
2. **Fully supported:** If every requested component is supported without material conflicts, assign `answerable`.
3. **Partially supported:** If at least one requested component is supported and another necessary component is missing, assign `partially_supported`.
4. **Relevant but insufficient:** If the context concerns the requested subject but does not answer any requested component, assign `unanswerable`.
5. **Irrelevant evidence:** If the context provides no materially relevant information, assign `irrelevant`.

### 5.1 Precedence Rules

- Material contradictions take precedence over partial support.
- Contradictions unrelated to the question do not affect its category.
- Partial support requires at least one genuinely answered component.
- Relevant but insufficient context is `unanswerable`, not `irrelevant`.
- External knowledge must not resolve missing or conflicting evidence.
- An incorrect reference answer must be corrected through documented adjudication or excluded.
- A false premise must not be treated as an ordinary missing-information case without review.

If multiple labels remain defensible, flag the example for adjudication.

### 5.2 Unsupported Inferences

Annotators must not assume:

- A company was founded when its first product launched.
- A person's title establishes unstated responsibilities.
- The latest document is authoritative unless the context establishes this.
- A familiar fact is supported simply because it is common knowledge.
- Missing information establishes a negative answer.
- Mentioning an entity establishes a specific relationship involving that entity.

Examples requiring complex external reasoning, unstated assumptions, or ambiguous temporal interpretation should be escalated or excluded from benchmark v1.

### 5.3 Question Validity Versus Answerability

Question quality and evidence sufficiency are separate dimensions.

An example may be unanswerable yet unsuitable for a benchmark because the question is malformed.

Similarly, an example may be labeled answerable by its source dataset while containing an unsupported reference answer.

**A valid source label does not automatically make an example suitable for EvidenceTune.**

---

## 6. Reference Answer Requirements

Reference answers represent the expected behavior of an evidence-grounded model.

### 6.1 General Requirements

Reference answers must:

1. Directly address the question.
2. Contain only evidence-supported claims.
3. Avoid speculation and invented details.
4. Communicate missing or contradictory information accurately.
5. Remain concise without omitting necessary information.
6. Avoid reinforcing assumptions contradicted by the evidence.

Do not unnecessarily reproduce entire source passages.

### 6.2 Category-Specific Requirements

| Category | Reference-answer requirement |
|---|---|
| `answerable` | Provide the complete supported answer |
| `unanswerable` | State that the requested information is unavailable |
| `contradictory` | Identify conflicting claims without inventing a resolution |
| `irrelevant` | Explain that the supplied context does not answer the question |
| `partially_supported` | Answer supported components and acknowledge missing components |

### 6.3 Semantic Equivalence

Reference answers are not required to use identical wording.

For example:

- "The company was founded in 2021."
- "2021."

Both may be correct when the question requests the founding year.

The evaluation process must distinguish semantic correctness from exact textual matching.

Lexical similarity alone is insufficient to determine factual correctness.

### 6.4 Ground-Truth Review

Reviewers must verify that every factual claim in a reference answer is supported.

For multi-component answers, each claim must be checked independently.

Do not approve a reference answer because it is plausible.

**Reference answers must be supported by evidence, not merely consistent with an annotator's expectations.**

### 6.5 Incorrect Reference Answers

When the original reference answer is incorrect:

1. Preserve the source annotation.
2. Document the discrepancy.
3. Identify the evidence-supported answer.
4. Flag the record for independent review.
5. Either approve a documented correction or exclude the example.

**EvidenceTune SQuAD audit example**

Question:

> Which is more costly, formal, or informal imperialism?

Context states:

> Informal rule is generally less costly than taking over territories formally.

Original reference answer:

> informal

Evidence-supported answer:

> formal

Decision: Exclude from the current benchmark unless a correction is independently reviewed and approved.

The original SQuAD record must remain unchanged.

---

## 7. False-Premise Question Policy

### 7.1 Definition

A false-premise question contains an assumption that is explicitly contradicted by the supplied evidence.

The question may still request information that the context provides.

For example:

Context:

> In 1929, the university's fifth president, Robert Maynard Hutchins, took office.

Question:

> When did the fourth president, Robert Maynard Hutchins, take office?

The question incorrectly describes Hutchins as the fourth president.

The context identifies him as the fifth president and supplies the year 1929.

### 7.2 Core Policy

**When the evidence contradicts a question's premise, the preferred model behavior is to identify the contradiction and provide an evidence-supported correction when possible.**

The model should not automatically produce a generic abstention response when the context contains enough information to explain the incorrect assumption.

However, the model must not invent missing facts to complete a correction.

### 7.3 Expected Behavior

Apply these rules in order:

1. Identify whether the supplied evidence explicitly contradicts a material assumption in the question.
2. If the contradiction is established, acknowledge it.
3. If the context supports a corrected answer, provide it.
4. If the context establishes that the premise is false but does not provide a replacement answer, identify the incorrect premise without guessing.
5. If the context merely lacks evidence, do not assert that the premise is false.
6. Do not use external factual knowledge to justify a correction.

### 7.4 Example: Evidence Supports a Correction

Context:

> In 1929, the university's fifth president, Robert Maynard Hutchins, took office.

Question:

> When did the fourth president, Robert Maynard Hutchins, take office?

**Preferred response:**

> Robert Maynard Hutchins was the fifth president, not the fourth. He took office in 1929.

**Insufficient response:**

> The provided context does not contain enough information.

This avoids fabrication but fails to use the available correction.

**Incorrect response:**

> The fourth president, Robert Maynard Hutchins, took office in 1929.

This repeats the false premise as fact.

### 7.5 Example: Correction Not Available

Context:

> Project Nova was not founded by Jordan Lee. The project was established in 2022.

Question:

> In what year did Jordan Lee found Project Nova?

**Preferred response:**

> The context states that Jordan Lee did not found Project Nova. It does not identify who founded it.

The model must not invent a founder or imply that Jordan Lee founded the project in 2022.

### 7.6 Example: Missing Evidence Is Not a False Premise

Context:

> Atlas Robotics was founded in Boston in 2021.

Question:

> In which university did the founder study?

The passage does not identify the founder or their university.

There is no evidence establishing that the question's assumption is false.

The correct behavior is to abstain:

> The context does not identify the founder or their university.

**Rule:** Absence of evidence does not establish a false premise.

### 7.7 Types of False-Premise Problems

| Issue | Description | Expected behavior |
|---|---|---|
| Incorrect entity attribute | Wrong title, position, or characteristic | Correct the attribute if supported |
| Incorrect numerical value | Question contains a number contradicted by evidence | Identify the discrepancy |
| Reversed relationship | Question reverses a documented causal or temporal relationship | Correct the relationship |
| Incorrect entity association | Question attributes an event or action to the wrong entity | Identify the correct entity if supported |
| Incorrect chronology | Question assumes an event happened before or after another incorrectly | State the supported chronology |

Do not automatically treat every grammatically awkward question as a false-premise example.

A false premise requires a demonstrable contradiction, not merely unclear wording.

### 7.8 False Premises Versus Contradictory Evidence

These are distinct failure modes.

**Contradictory evidence:**

Context:

> Report A states the launch occurred in 2020. Report B states it occurred in 2022.

Question:

> When did the launch occur?

The supplied context contains unresolved conflicting claims.

Primary category: `contradictory`.

**False-premise question:**

Context:

> The launch occurred in 2022.

Question:

> Why was the product launched in 2020?

The evidence contradicts the year assumed by the question.

Issue type: `false_premise`.

Expected behavior: Correct the premise where possible.

A false-premise question does not become `contradictory` merely because its assumption conflicts with the context.

### 7.9 Benchmark Treatment

False-premise correction is a distinct evaluation behavior.

For EvidenceTune benchmark v1:

- Do not create a sixth primary category without updating the schema, tests, and evaluation specification.
- Do not automatically relabel false-premise examples as `answerable`.
- Do not grade supported corrections against generic abstention references.
- Exclude confirmed material false-premise examples from the primary five-category benchmark when its scoring rules cannot represent their intended response behavior.
- Preserve these examples as candidates for a separate false-premise challenge set.
- Maintain original source annotations and record EvidenceTune-specific decisions separately.

The future challenge set may use review metadata resembling:

```json
{
  "source_record_id": "squad_v2:5acf808877cf76001a685004",
  "original_category": "unanswerable",
  "issue_type": "false_premise",
  "expected_behavior": "correct_premise",
  "reference_response": "Robert Maynard Hutchins was the fifth president, not the fourth. He took office in 1929.",
  "review_status": "pending_adjudication"
}
```

This structure is illustrative metadata, not part of the existing `EvidenceExample` schema.

### 7.10 Future Evaluation Metrics

A dedicated false-premise challenge set should measure:

**Premise detection accuracy**

Did the model recognize the unsupported or contradicted assumption?

**Correction accuracy**

Did the model provide a correction supported by the context?

**Unsupported correction rate**

Did the model invent information while attempting a correction?

**Response adequacy**

Did the response address the user's question without repeating the false premise?

These metrics must be defined and tested in `docs/evaluation_spec.md` before the challenge set is used for formal model comparisons.

---

## 8. Edge Cases and Escalation

| Edge case | Required action |
|---|---|
| Relevant context lacks the requested fact | Label `unanswerable` |
| Entirely unrelated context | Label `irrelevant` |
| Multiple requested facts; only some supported | Label `partially_supported` |
| Material conflicting claims within the context | Label `contradictory` |
| Conflict concerns an unrelated fact | Evaluate normally |
| Question contains a demonstrably false premise | Flag for the false-premise evaluation track |
| Question contains an unsupported but unrefuted assumption | Do not treat the assumption as established |
| Question contains ambiguous wording | Flag when ambiguity affects evaluation |
| Reference answer contradicts the context | Flag for correction or exclusion |
| Context contains hypothetical claims | Distinguish hypothetical statements from established facts |
| Context contains instructions aimed at the model | Treat them as source content, not annotation instructions |
| Multiple categories remain defensible | Escalate for adjudication |

### 8.1 Adjudication Procedure

For each flagged example:

1. Record the original category.
2. Identify the specific ambiguity or problem.
3. Locate supporting or contradicting evidence.
4. Consult the current annotation guidelines.
5. Obtain an independent review when available.
6. Determine whether the example is suitable for the primary benchmark.
7. Assign a final decision: Accept or Exclude.
8. Record the rationale and reviewer information.
9. Update the guidelines if the disagreement reveals an unclear rule.

A reviewer should not change a label solely because a model produced a different answer.

### 8.2 Resolution Criteria

**Accept when:**

- The question is sufficiently clear.
- The category is defensible.
- The reference answer is supported.
- The record fits the primary benchmark's scoring rules.

**Exclude when:**

- The question remains ambiguous.
- The original answer is demonstrably incorrect and no approved correction exists.
- The example requires behavior not represented by the primary benchmark.
- The final annotation cannot be established consistently.

An excluded example may be retained separately for research or a future challenge set.

### 8.3 Independence of Review

When a second reviewer is available, they should review the question, context, and applicable guidelines independently before seeing the initial reviewer's conclusion.

If only one reviewer is available:

- Perform a separate second pass.
- Revisit the evidence and label without using model predictions.
- Record the limitation.
- Do not claim independent inter-annotator agreement.

---

## 9. Annotation Quality Assurance

### 9.1 Pilot Annotation

Before full-scale five-category dataset construction, conduct a pilot of **15 examples**, targeting three examples per primary category.

The pilot should include both straightforward cases and challenging boundaries.

Pilot procedure:

1. Create candidate examples.
2. Apply the guidelines.
3. Obtain independent annotations where feasible.
4. Compare categories and reference answers.
5. Adjudicate disagreements.
6. Revise unclear rules.
7. Recheck examples affected by changes.

The initial 20-example SQuAD development audit is a separate semantic quality review. It does not replace the planned five-category pilot.

### 9.2 Agreement and Consistency

For independently double-annotated examples, calculate:

**Raw agreement = Matching category labels / Double-annotated examples**

When the sample size permits, also report Cohen's kappa.

Agreement measures consistency, not necessarily correctness.

Reference-answer support must be reviewed separately.

Do not make strong statistical reliability claims based on a 15-example pilot.

### 9.3 Automated Quality Checks

Automated validation should include:

- Schema compliance.
- Valid category values.
- Category and `answerable` consistency.
- Unique record IDs.
- Duplicate and near-duplicate detection.
- Category coverage.
- Expected category counts.
- Source-group separation.
- Deterministic sampling.
- Artifact checksums.
- Exclusion-list enforcement.

### 9.4 Manual Quality Checks

Manual review should verify:

- Correct category assignment.
- Sufficient supporting evidence.
- Accurate reference answers.
- Clear question wording.
- Absence of unsupported inference.
- Correct handling of false premises.
- Appropriate treatment of conflicting evidence.
- Source provenance.

**Automated structural validation does not replace semantic review.**

### 9.5 Review Requirements

For benchmark v1:

- Every included example must undergo manual quality review.
- All flagged records must be adjudicated or excluded.
- Material corrections must be documented.
- Excluded records must have explicit reasons.
- Replacement records must be independently reviewed before acceptance.
- Held-out test examples must not be selected or rewritten based on model performance.

### 9.6 SQuAD Development Audit Findings

EvidenceTune's initial SQuAD development sample contains 20 records:

- 10 originally labeled `answerable`.
- 10 originally labeled `unanswerable`.

The first-pass review identified:

- 10 accepted records.
- 9 flagged records requiring adjudication.
- 1 excluded record with an incorrect reference answer.

These are provisional audit results, not a final benchmark acceptance report.

The review demonstrated that external benchmark labels may contain ambiguities, false premises, or reference-answer errors.

The sample is too small to estimate the overall SQuAD 2.0 error rate.

Detailed records and decisions are maintained in `docs/dataset_audit.md`.

---

## 10. Dataset Curation and Leakage Prevention

### 10.1 Source Separation

Examples derived from the same source document or closely related source family must remain in the same evaluation split.

Near-duplicate questions and paraphrases should not cross development and test splits.

The source-family grouping strategy must be documented in the manifest.

Article-title grouping is the current SQuAD implementation, but it does not guarantee detection of all semantically related sources.

### 10.2 Evaluation Isolation

- Development data may be used to develop prompts, model-serving code, and evaluation logic.
- Locked test examples must not enter training or prompt optimization.
- Model predictions on the test set must not determine which records are retained.
- Test-set corrections are permitted only for independently established annotation defects and must be versioned.
- Repeated model-guided test-set revisions must be avoided.

### 10.3 Exclusion Policy

Excluded records must be tracked separately.

A proposed curation artifact is:

`data/curation/squad_exclusions.json`

Each exclusion should record:

- Original record ID.
- Reason for exclusion.
- Review decision.
- Guideline version.
- Reviewer information, when available.

Do not manually remove records from the generated JSONL without recording the corresponding curation rule.

### 10.4 Deterministic Replacement

When excluded examples reduce the required category count:

1. Load the pinned upstream dataset.
2. Apply the reviewed exclusions before sampling.
3. Select replacement candidates deterministically.
4. Preserve category distribution.
5. Preserve source-group separation.
6. Validate new records.
7. Conduct semantic review of replacements.
8. Regenerate dataset artifacts.
9. Recalculate checksums.
10. Record the new manifest version.

A replacement is not automatically accepted merely because the pipeline generated it successfully.

### 10.5 Dataset Provenance

Record:

- Dataset name and source.
- Dataset license or permitted usage.
- Pinned source revision.
- Source split.
- Sampling configuration.
- Random seed.
- Grouping strategy.
- Annotation guideline version.
- Review and correction history.
- Curation configuration.
- Artifact checksums.

All finalized examples must be traceable to their original sources and annotation decisions.

---

## 11. Versioning and Change Management

Annotation guidelines must be maintained under Git version control.

Changes should include:

- Description of the change.
- Motivation.
- Affected categories or decision rules.
- Representative examples.
- Impact on previously reviewed records.

Changes affecting category definitions, precedence, or expected behavior require a guideline-version update.

Affected records must be rechecked under the new rules.

### 11.1 Guideline Change Log

| Version | Date | Changes |
|---|---|---|
| 0.1 | 2026-11-16 | Initial five-category annotation guidelines, quality assurance, and dataset integrity rules |
| 0.2 | 2026-11-16 | Added false-premise correction policy, separation of question validity from answerability, dedicated challenge-set guidance, and adjudication rules informed by the SQuAD audit |

### 11.2 Benchmark Freeze

Before freezing the locked test set:

1. Complete all first-pass reviews.
2. Resolve every flagged example.
3. Review all replacement records.
4. Verify schema and category consistency.
5. Confirm source-group separation.
6. Verify reference-answer support.
7. Record dataset and guideline versions.
8. Verify artifact checksums.
9. Document known limitations.
10. Restrict subsequent changes to reviewed and versioned corrections.

A frozen benchmark must not be modified to improve the observed performance of a particular model.

---

## 12. Acceptance Criteria

### 12.1 Annotation Guideline Readiness

The guidelines are ready for use when:

- [x] All five primary categories have explicit definitions.
- [x] Category boundaries and precedence rules are documented.
- [x] Reference-answer requirements are established.
- [x] Unsupported-inference rules are documented.
- [x] False-premise handling rules are defined.
- [x] Adjudication and escalation procedures are documented.
- [x] Dataset curation and provenance requirements are specified.
- [ ] The revised false-premise policy is approved.
- [ ] Affected examples from the SQuAD audit are adjudicated.
- [ ] The five-category annotation pilot is completed.
- [ ] Pilot disagreements are resolved.
- [ ] Guidelines are approved for benchmark construction.

### 12.2 Benchmark Readiness

The evaluation benchmark is ready for formal use when:

- [ ] All included records pass automated validation.
- [ ] All included records pass semantic review.
- [ ] All flagged examples are resolved or excluded.
- [ ] Replacement records are audited.
- [ ] All five target categories are represented.
- [ ] Development and test sources remain isolated.
- [ ] Final dataset manifests contain immutable source revisions.
- [ ] Final artifact checksums are verified.
- [ ] The held-out test set is frozen.
- [ ] Known limitations are documented.
- [ ] The benchmark evaluation procedure is finalized.

Guideline approval does not automatically imply benchmark approval.

---

## 13. Limitations

The initial EvidenceTune benchmark is intentionally small and category-balanced.

Its examples may not reflect the distribution of real-world user questions.

The benchmark primarily measures evidence sufficiency and response grounding. It does not establish general factual knowledge, broad reasoning capability, or safety performance.

Manual review reduces annotation errors but does not guarantee perfect ground truth.

A single-reviewer audit cannot establish independent inter-annotator agreement.

Source-group separation reduces leakage risk but does not guarantee that examples are absent from an open-weight model's pretraining data.

SQuAD-derived examples primarily measure answerability and may not adequately represent realistic multi-document reasoning, adversarial evidence, or contradictory claims.

False-premise correction requires separate evaluation rules and should not be treated as equivalent to ordinary abstention.

All evaluation results must be interpreted within these limitations.

---

## 14. References

### Internal Documents

- `docs/evaluation_spec.md`
- `docs/dataset_audit.md`
- `src/data/schema.py`
- `src/data/build_eval.py`

### External Resources

- [Hugging Face: Using Human Annotators](https://github.com/huggingface/evaluation-guidebook/blob/main/contents/human-evaluation/using-human-annotators.md)
- [Hugging Face: Model Evaluation Considerations](https://huggingface.co/docs/evaluate/considerations)
- [Grammarly Engineering: Annotation Best Practices](https://www.grammarly.com/blog/engineering/annotation-best-practices/)
- [NIST: AI Risk Management Framework, Measure](https://airc.nist.gov/airmf-resources/playbook/measure/)

---

**Document status:** Version 0.2, draft pending final adjudication and approval.

**Next milestone:** M1B.6, adjudication of the nine flagged SQuAD development examples and implementation of reproducible dataset curation.
