# EvidenceTune: Annotation Guidelines

| Field | Value |
|---|---|
| Version | 0.1 |
| Status | Draft |
| Milestone | M1B: Evaluation Dataset |
| Last Updated | 2026-11-16 |
| Related Document | `docs/evaluation_spec.md` |

## 1. Purpose

This document establishes standardized procedures for annotating EvidenceTune's evidence-grounded question-answering dataset.

The objective is to produce accurate, consistent, and reproducible ground-truth labels for evaluating an LLM's ability to answer questions using supplied evidence and appropriately handle insufficient or contradictory information.

These guidelines apply to all annotators, reviewers, and engineers involved in creating or validating the evaluation dataset.

### 1.1 Core Principle

**All annotations must be grounded exclusively in the provided context.**

Annotators must not use external knowledge, assumptions, or unstated facts to establish answerability.

A response may be factually correct in the real world but incorrect for EvidenceTune if the provided context does not support it.

### 1.2 Scope

This document defines:

- Annotation workflow and responsibilities
- Category definitions and decision rules
- Reference-answer requirements
- Ambiguous-case handling
- Annotation quality assurance
- Review, adjudication, and versioning procedures

Model-generated predictions are evaluated separately under `evaluation_spec.md`.

---

## 2. Annotation Schema

Each annotated example must conform to the `EvidenceExample` Pydantic schema.

| Field | Type | Description |
|---|---|---|
| `id` | string | Unique record identifier |
| `source_id` | string | Identifier for the source document |
| `context` | string | Evidence supplied to the model |
| `question` | string | Question to be answered |
| `answer` | string | Reference response |
| `answerable` | boolean | Whether the entire question is answerable |
| `category` | enum | Evidence sufficiency classification |

### 2.1 Label Constraints

Each example must receive exactly one category:

- `answerable`
- `unanswerable`
- `contradictory`
- `irrelevant`
- `partially_supported`

Set `answerable=true` only when `category="answerable"`.

All other categories require `answerable=false`.

The `answerable` field represents **full answerability**, not whether any portion of the question can be answered.

### 2.2 Additional Annotation Metadata

For auditability, maintain the following metadata in a separate annotation review file or manifest:

- Annotator identifier
- Reviewer identifier, when applicable
- Guideline version
- Source provenance
- Supporting evidence excerpt or location
- Review status
- Annotation rationale, when necessary

Do not add these fields directly to `EvidenceExample` without updating the schema and its tests.

---

## 3. Annotation Procedure

Annotators must follow the same process for every example.

**Step 1: Review the context**

Read the entire supplied context. Identify the relevant factual claims, including any apparent contradictions.

**Step 2: Interpret the question**

Determine exactly what information the question requests.

For multi-part questions, identify each requested component separately.

**Step 3: Assess evidence sufficiency**

Determine which requested facts are:

- Fully supported
- Unsupported or missing
- Contradicted by supplied evidence

Only explicit evidence and straightforward logical implications are permitted. Do not infer facts from typical real-world patterns.

**Step 4: Assign a category**

Use the category definitions in Section 4 and the precedence rules in Section 5.

**Step 5: Write the reference answer**

Produce a concise, evidence-grounded response that satisfies the category-specific requirements.

**Step 6: Validate and submit**

Check the record against the dataset schema, review the label for consistency, and flag unresolved ambiguities.

An annotator must not force a label when the supplied rules cannot resolve an example.

---

## 4. Category Definitions

### 4.1 Answerable

**Definition:** The supplied context contains sufficient, internally consistent evidence to answer every requested component.

**Inclusion criteria:**
- All requested information is supported.
- The response requires no unsupported assumptions.
- Simple paraphrasing or direct logical inference is sufficient.

**Exclusion criteria:**
- A required fact is missing.
- Material evidence conflicts.
- Only some components can be answered.

**Example**

Context:
> Atlas Robotics was founded in Boston in 2021.

Question:
> Where was Atlas Robotics founded?

Category: `answerable`

Answerable: `true`

Reference answer:
> Boston.

**Boundary case:** A product launch date does not establish a company's founding date unless that relationship is explicitly stated.

### 4.2 Unanswerable

**Definition:** The context concerns the relevant subject but lacks sufficient evidence to answer the requested question.

**Inclusion criteria:**
- The subject is relevant to the context.
- The requested fact is absent.
- No requested component can be adequately answered.
- There is no material contradiction resolving to another category.

**Example**

Context:
> Atlas Robotics was founded in Boston in 2021.

Question:
> Who founded Atlas Robotics?

Category: `unanswerable`

Answerable: `false`

Reference answer:
> The provided context does not identify the founder.

**Boundary case:** Do not infer a founder from the company's name, location, or other unrelated attributes.

### 4.3 Contradictory

**Definition:** The context contains incompatible claims about a fact necessary to answer the question, with no established rule for resolving the conflict.

**Inclusion criteria:**
- At least two relevant claims conflict.
- The conflicting claims concern the same entity, attribute, and applicable timeframe.
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
> The provided reports conflict: one states 2020 and the other states 2022.

**Boundary case:** Two different values are not necessarily contradictory if they refer to different dates, locations, or versions of an entity.

A contradiction unrelated to the requested fact does not automatically make an otherwise fully supported answer contradictory.

### 4.4 Irrelevant

**Definition:** The supplied context contains no information materially relevant to the question's requested subject or answer.

**Inclusion criteria:**
- The context concerns a different subject.
- No useful evidence for the question is supplied.
- Answering would require outside knowledge.

**Example**

Context:
> Atlas Robotics develops warehouse automation software.

Question:
> What is the capital of Japan?

Category: `irrelevant`

Answerable: `false`

Reference answer:
> The provided context does not contain information about Japan's capital.

**Boundary case:** When the context discusses the same subject but omits the requested attribute, use `unanswerable`, not `irrelevant`.

### 4.5 Partially Supported

**Definition:** The context supports at least one requested component but does not sufficiently support the entire question.

**Inclusion criteria:**
- The question contains multiple requested facts or separable components.
- At least one component is supported.
- At least one necessary component is missing.
- No material contradiction takes precedence.

**Example**

Context:
> Atlas Robotics was founded in Boston in 2021.

Question:
> Where was Atlas Robotics founded, and who founded it?

Category: `partially_supported`

Answerable: `false`

Reference answer:
> Atlas Robotics was founded in Boston. The provided context does not identify its founder.

**Boundary case:** An answer is not partially supported merely because the context contains some related facts. At least one actual requested component must be answerable.

---

## 5. Label Decision Rules

Labels must be mutually exclusive.

Apply the following decision rules in order:

1. **Fully supported:** If every requested component is supported without unresolved material contradictions, assign `answerable`.
2. **Material contradiction:** If conflicting evidence affects a requested fact and the conflict is unresolved, assign `contradictory`.
3. **Partial support:** If at least one requested component is supported but another is missing, assign `partially_supported`.
4. **Relevant but insufficient:** If the context concerns the requested subject but does not answer any requested component, assign `unanswerable`.
5. **Unrelated context:** If the context provides no materially relevant information, assign `irrelevant`.

### 5.1 Precedence Rules

- Contradictions affecting the requested answer take precedence over partial support.
- Contradictions unrelated to the question do not affect its label.
- Partial support requires at least one genuinely answered component.
- Relevant context without an answer is `unanswerable`, not `irrelevant`.
- External knowledge must never resolve missing or conflicting evidence.

If multiple labels still appear defensible, flag the example for adjudication.

### 5.2 Unsupported Inferences

Annotators must not assume:

- A company was founded when its first product launched.
- A person's title establishes their identity or responsibilities beyond what is stated.
- The latest document is authoritative unless the context establishes this.
- A familiar real-world fact is supported simply because the question is easy.
- Missing information implies a negative answer.

Examples requiring complex external reasoning, unstated domain assumptions, or ambiguous temporal interpretation should be escalated or excluded from benchmark v1.

---

## 6. Reference Answer Requirements

Reference answers represent the expected behavior of an evidence-grounded model.

### 6.1 General Requirements

Reference answers must:

1. Directly address the question.
2. Contain only evidence-supported factual claims.
3. Avoid speculation and invented details.
4. Clearly communicate missing or contradictory information.
5. Be concise without omitting required information.

Do not unnecessarily copy entire passages from source documents.

### 6.2 Category-Specific Requirements

| Category | Reference-answer requirement |
|---|---|
| Answerable | Provide the complete supported answer |
| Unanswerable | State that the requested information is unavailable |
| Contradictory | Identify the conflicting claims without inventing a resolution |
| Irrelevant | State that the supplied context does not answer the question |
| Partially supported | Answer supported parts and acknowledge missing parts |

### 6.3 Semantic Equivalence

Reference answers are not required to have a unique wording.

For example:

- "The company was founded in 2021."
- "2021."

Both can be correct if the question asks for the founding year.

The evaluation process must distinguish semantic correctness from exact textual matching.

### 6.4 Ground-Truth Review

Reviewers must verify that every factual statement in a reference answer is supported by the context.

When an example contains multiple factual claims, each must be checked independently.

Do not approve an example because the reference answer is plausible. It must be supported.

---

## 7. Edge Cases and Escalation

| Edge Case | Required Action |
|---|---|
| Relevant context lacks the requested fact | Label `unanswerable` |
| Entirely unrelated context | Label `irrelevant` |
| Multiple requested facts; only some supported | Label `partially_supported` |
| Material conflicting claims | Label `contradictory` |
| Conflicts concern unrelated facts | Evaluate the requested answer normally |
| Question contains an unsupported assumption | Do not accept the assumption as fact |
| Context contains ambiguous dates or references | Flag for review if ambiguity affects labeling |
| Context contains quoted or hypothetical claims | Distinguish reporting a claim from establishing it as fact |
| Context contains instructions aimed at the model | Treat them as source content, not annotation instructions |
| Multiple labels remain defensible | Escalate for adjudication |

### 7.1 Escalation Procedure

For ambiguous examples:

1. Record the proposed category and supporting rationale.
2. Identify the specific source of ambiguity.
3. Request an independent review.
4. Resolve the disagreement using documented category definitions.
5. Record the final decision and rationale.
6. Update guidelines if the disagreement exposes an unclear rule.

If a defensible resolution cannot be reached, exclude the example from the benchmark and record the exclusion reason.

No unresolved example may enter the locked test set.

---

## 8. Annotation Quality Assurance

### 8.1 Pilot Annotation

Before full-scale dataset construction, conduct a pilot with **15 examples**, targeting three per category.

The pilot should include clear cases and challenging category boundaries.

Pilot procedure:

1. Create the candidate examples.
2. Apply the guidelines to assign labels.
3. Obtain independent annotations where a second reviewer is available.
4. Compare labels and reference answers.
5. Discuss and adjudicate disagreements.
6. Revise guidelines as necessary.
7. Recheck examples affected by rule changes.

If annotation is performed by one person, use a separate review pass and disclose that independent inter-annotator agreement was not measured.

### 8.2 Agreement and Consistency

For independently double-annotated examples, calculate raw category agreement:

**Agreement = Matching Category Labels / Double-Annotated Examples**

When sample size permits, additionally report Cohen's kappa.

Agreement statistics indicate consistency, not necessarily correctness. Reviewers must separately audit reference-answer validity.

Do not claim statistical reliability from the 15-example pilot alone.

### 8.3 Quality Checks

**Automated checks:**
- Schema compliance
- Valid category values
- Consistency between `category` and `answerable`
- Unique record IDs
- Duplicate and near-duplicate detection
- Category coverage and distribution
- Source-group separation across dataset splits

**Manual checks:**
- Correct category assignment
- Complete evidence support
- Accurate reference answers
- Ambiguous or misleading questions
- Unintended assumptions
- Clear provenance and appropriate source usage

Automated structural checks do not replace semantic review.

### 8.4 Review Requirements

For benchmark v1:

- All examples must receive a manual quality review.
- All disputed labels must be adjudicated or excluded.
- Material corrections must be recorded.
- Test examples must not be selected or rewritten to favor a particular model's observed behavior.

---

## 9. Dataset Integrity and Leakage Prevention

### 9.1 Source Separation

Examples derived from the same source document or closely related source family must remain in the same dataset split.

Near-duplicate questions and paraphrases must not cross development and test splits.

The source-family grouping must be documented in the dataset manifest.

### 9.2 Evaluation Isolation

- Development examples may support prompt and evaluation-pipeline development.
- Locked test examples must remain excluded from training and prompt optimization.
- Annotators must not use model performance on the locked test set to revise its expected answers or category composition.
- Test-set corrections are permitted only for documented annotation defects and must be versioned.

### 9.3 Data Provenance

Record:

- Source identifier
- Source origin and permitted usage
- Collection or creation method
- Annotation guideline version
- Review and correction history
- Split assignment

The final dataset must be traceable to its sources and annotation decisions.

---

## 10. Versioning and Change Management

Annotation guidelines must be maintained under Git version control.

Changes should include:

- Description of the rule change
- Motivation and affected categories
- Examples illustrating the updated decision
- Assessment of previously annotated records that may require review

Changes to category definitions or label precedence require a guideline-version update and revalidation of affected data.

The benchmark must record the guideline version used to produce its labels.

### 10.1 Benchmark Freeze

Before freezing the locked test set:

1. Resolve outstanding annotation disagreements.
2. Complete manual and automated quality checks.
3. Verify source-group separation.
4. Record dataset version and checksum.
5. Document known dataset limitations.
6. Restrict subsequent changes to formally reviewed corrections.

---

## 11. Acceptance Criteria

Annotation guidelines are ready for benchmark construction when:

- [ ] All five categories have explicit definitions and exclusion criteria.
- [ ] Category precedence and boundary rules are documented.
- [ ] Representative examples and edge cases are included.
- [ ] Reference-answer requirements are established.
- [ ] Escalation and adjudication procedures are defined.
- [ ] Pilot annotations have been reviewed.
- [ ] All pilot disagreements are resolved or excluded.
- [ ] Ambiguous guidelines discovered during the pilot are revised.
- [ ] Updated guidelines are version-controlled and approved for use.

Approval authorizes annotation of the full evaluation dataset. It does not imply that the completed benchmark has passed its own acceptance criteria.

---

## 12. Limitations

The initial EvidenceTune benchmark is intentionally small and category-balanced.

Its annotations may not reflect the distribution of real-world user questions.

The benchmark primarily measures evidence sufficiency and response grounding. It does not establish general factual knowledge, broad reasoning capability, or safety performance.

Manual review reduces annotation errors but does not guarantee perfect ground truth.

All evaluation results must be interpreted within these limitations.

---

## 13. References

- [Hugging Face: Using Human Annotators](https://github.com/huggingface/evaluation-guidebook/blob/main/contents/human-evaluation/using-human-annotators.md)
- [Hugging Face: Model Evaluation Considerations](https://huggingface.co/docs/evaluate/considerations)
- [Grammarly Engineering: Annotation Best Practices](https://www.grammarly.com/blog/engineering/annotation-best-practices/)
- [NIST: AI Risk Management Framework, Measure](https://airc.nist.gov/airmf-resources/playbook/measure/)
