# M2C: Baseline Error Analysis

## Objective and setup

Characterize why the unmodified Qwen/Qwen3-1.7B baseline answers beyond supplied
evidence, and distinguish grounding problems from response-format failures and
benchmark disagreements before designing an SFT experiment.

This analysis uses the saved M2B predictions for curated_v4 development only:
20 examples (10 answerable, 10 unanswerable). Saved generation settings are
`enable_thinking=false`, `do_sample=false`, and `max_new_tokens=128`. The system
prompt requests context-only answers and exactly `ABSTAIN` when evidence is
insufficient. No inference was rerun, no weights were downloaded, and no held-out
test examples were used.

The existing scorer reproduces AUCM **TP=10, FP=9, FN=0, TN=1**, strict abstention
recall **0.10** (1/10), and mean answerable token F1 **0.3707**. The 10/10 answerable
responses were judged correct in **provisional AI-assisted reviews**. These are
not independently validated results. Their metric definitions and original input
artifacts are unchanged.

## Method

The project owner supplied approved primary/secondary classifications for nine
manually reviewed cases. We matched these by full example ID to the saved question,
context, response, gold label, and earlier review. The other 11 examples have no
identified primary failure under this review; this is not a universal correctness
claim. No independent second annotator or inter-annotator agreement is reported.

`dev_20_errors.jsonl` is an additional analysis layer with exactly four fields:
`example_id`, `primary_failure`, `secondary_failure`, and `explanation`.
`no_identified_failure` is an explicit primary label; absent secondary labels are
JSON `null`. Primary labels are mutually exclusive. Secondary labels describe
additional characteristics and do not increase primary counts. The taxonomy
separates unsupported-answer mechanisms (inference, entity, definition, scope,
and premise acceptance) from output-format failure and annotation disagreement.

## Results

| Primary classification | Count |
|---|---:|
| Unsupported inference | 1 |
| Entity mismatch | 1 |
| Unsupported definition | 2 |
| Scope overgeneralization | 2 |
| False-premise acceptance | 1 |
| Abstention-format failure | 1 |
| Annotation disagreement | 1 |
| No identified failure | 11 |
| **Total** | **20** |

The nine exact-abstention misses comprise **seven primary unsupported-answer
failures**, **one primary format failure**, and **one annotation disagreement**.
Thus nine misses must not be reported as nine hallucinations. The unsupported
assertion in the format-failure example remains documented, but does not add a
second primary failure. Six secondary `unsupported_inference` labels also do not
increase the count of seven unsupported-answer cases.

## Representative cases

### Example 8 — Entity mismatch

ID: `squad_v2:5ad031ef77cf76001a686df6`

**Question:** What religion did the English spread along with their imperialism?

**Model response (verbatim):**

> Catholicism.

The passage attributes Catholicism to the French empire. The question asks about English imperialism; matching a nearby religion while changing the entity is unsupported.

### Example 18 — Annotation disagreement

ID: `squad_v2:5a581597770dc0001aeeffe4`

**Question:** What do drill cores show about water location?

**Model response (verbatim):**

> Drill cores show the locations of stratigraphic units in the subsurface, which can help identify areas for water, coal, and hydrocarbon extraction.

The owner judged this response sufficiently supported by the passage linking stratigraphic analysis with extraction areas. The earlier review instead considered the attribution to drill cores unsupported. The original unanswerable gold label and earlier review remain intact; M2C records the disagreement without rescoring or relabeling.

### Example 19 — Abstention-format failure

ID: `squad_v2:5a2358cc82b03a001a4aa797`

**Question:** What do people with experience not need to do?

**Model response (verbatim):**

> People with experience in the field do not need to do anything specific that is not already covered by the context provided. The context states that those with experience make detailed plans and maintain careful oversight during the project to ensure a positive outcome. Therefore, the answer is not provided in the context.

The final sentence recognizes missing evidence, but the response is not exactly ABSTAIN. The opening assertion about what experienced people need not do is also unsupported. This is not an entirely flawless semantic abstention. Its approved secondary classification remains null.

### Example 20 — False-premise acceptance

ID: `squad_v2:5acf9d3477cf76001a685516`

**Question:** What year did the College have the highest acceptance rate in its history?

**Model response (verbatim):**

> The College of the University of Chicago had the highest acceptance rate in its history in 2015.

The passage calls the 2015 rate the lowest in the College’s history. The response treats that year as the highest, accepting the requested framing despite the contrary relation in the evidence.

## Observations and limitations

- The answerable results and seven unsupported-answer cases suggest that finding
  relevant text and respecting its evidential boundaries are different abilities.
  The observed errors involve entity substitution, added definitions, widened
  scope, and reversal of the stated relation—not only invented factual content.
- Strict abstention recall measures compliance with an exact output contract.
  Example 19 shows that a model can recognize insufficient evidence yet receive
  no abstention credit. The score may therefore underestimate semantic recognition;
  the mixed unsupported wording prevents treating it as clean semantic success.
  We do not introduce an adjusted recall or change the existing metric.
- Example 18 exposes annotation uncertainty. The historical FP remains in the
  original metric result; the additional disagreement layer explains why that
  FP should not automatically be interpreted as an evidence-grounding failure.
- Twenty curated development examples are too few for broad performance claims.
  The provisional correctness judgments lack independent validation. Token F1
  measures lexical overlap and can penalize verbose/paraphrased correct answers;
  its 0.3707 value is not a 37.07% semantic accuracy estimate. Development findings
  guide hypotheses, not claims about held-out performance or training efficacy.

## Hypotheses for a future SFT experiment

1. Contrastive training examples that change entity, scope, or a highest/lowest
   relation may improve evidence-boundary sensitivity. Test whether unsupported
   answers decrease without increasing incorrect abstention on answerable items.
2. Explicit supervision of unsupported definitions and inference gaps may help
   distinguish information present in context from plausible background knowledge.
3. Exact-token abstention targets may improve format compliance; evaluate format
   and semantic evidence recognition separately so one does not mask the other.
4. Adjudicating ambiguous training annotations before SFT may reduce conflicting
   supervision. Treat disagreements as audit evidence, not automatic permission
   to rewrite frozen benchmark labels after observing model outputs.

These are testable hypotheses, not claims that fine-tuning will solve the observed
problems. No training or M3 implementation is part of this milestone.

## Reproduction and preservation

Run from the repository root:

```sh
.venv/bin/python -m scripts.summarize_error_analysis
.venv/bin/python -m scripts.score_dev_baseline
.venv/bin/python -m pytest tests/test_error_analysis.py -q --basetemp=.pytest_cache/m2c-targeted
.venv/bin/python -m pytest -q --basetemp=.pytest_cache/m2c-full
git diff --check
```

The summary script validates IDs, duplicate/missing records, taxonomy, secondary
labels, and explanations. It only reads annotations and predictions; it neither
runs the model nor updates any artifact. Tests pin the approved nine-case mapping,
11 remaining cases, counts, and the following pre-M2C input hashes:

Validation on 2026-11-23: **26 targeted tests passed in 0.32s**; the full suite
reported **252 passed, six intentionally skipped in 12.55s**. The six skips are
opt-in SQuAD integration tests. The tests-first run preceded implementation
(21 expected failures for the missing summary module, five input checks passed).
Final byte comparisons against `HEAD` confirmed all four inputs below unchanged;
`git diff --check` passed. No existing files were modified and no commit, push,
or merge was performed.

| Input | SHA-256 |
|---|---|
| `data/eval/curated_v4/squad_dev.jsonl` | `a2b5fc8aa23cf6ca2738f482b993bf4c6626bed5f6adc5dd03461bfe4edb99b5` |
| `reports/baseline/dev_20_predictions.jsonl` | `05226110ead008ec23c8f540e0ad10a2f3d88f731309576797d25e84cdaf7c73` |
| `reports/baseline/dev_20_reviews.jsonl` | `6b9c60bbb4bb83412425346a7f43ad06242c9b9f5e647484bc8ff3c5a41216ca` |
| `src/evaluation/metrics.py` | `88c76dede90cb95aa35d20aded31ba9763fe4a9e901e996fa8f7ddee40b6b087` |
