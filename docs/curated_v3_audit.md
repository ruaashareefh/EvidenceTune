# EvidenceTune: curated_v3 Candidate Audit

**Status:** Semantic adjudication complete; two retentions and one exclusion approved.
**Review method:** AI-assisted evidence review with project-owner adjudication; no independent double review.
**Parent:** curated_v2. **Source revision:** `3ffb306f725f7d2ce8394bc1873b24868140c412`.

## Generation and Integrity

The project owner approved the three v2 exclusions and all 17 retained records
in `adjudication_log.md`, and authorized this curation round. The new
`data/curation/squad_exclusions_v3.json` contains 19 cumulative exclusions,
17 approved retained IDs, and seven false-premise challenge candidates.
`create_v3_exclusions.py` reproduces the configuration and refuses to overwrite it.

The dataset was generated offline from the existing cache at the pinned revision:

```sh
HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 .venv/bin/python -m src.data.build_eval \
  --curate-from data/eval --parent-curated data/eval/curated_v2 \
  --exclusions data/curation/squad_exclusions_v3.json \
  --output-dir data/eval/curated_v3 --seed 42 --per-category 10 \
  --revision 3ffb306f725f7d2ce8394bc1873b24868140c412
```

Verification confirmed:

- All 17 approved parent records retained unchanged at the record-data level.
- Three previously unused unanswerable candidates; all 19 exclusions absent.
- 20 development records with 10/10 category balance.
- Development/test IDs, source IDs, and contexts disjoint.
- Original held-out test bytes preserved exactly.
- Original, v1, v2, and prior exclusion artifacts unchanged from commit `32f49ee`.
- Manifest checksums and parent/baseline/configuration provenance correct.
- Full regression suite: 89 passed, six intentionally skipped.

Development SHA-256: `6a8611b4d649d7afeac250570b3421a826d5aa94c06af1643f85bf4307edf429`.
Test SHA-256: `0c6f9b3c89104fc79ffcc26efa506df7541044e586d43b8efca57b3f8ce56e5b`.

## First-Pass Semantic Findings

All three candidates retain the source label `unanswerable` and the reference
"The provided context does not contain enough information to answer the question."
Approval status is recorded individually below; pending recommendations are not
approved curation decisions.

### 1. Saturn versus Mercury

**ID:** `squad_v2:5ad27fb9d7d075001a429782`

**Question:** Whose law did not explain the orbit of the planet Saturn?

**Evidence:** "It was only the orbit of the planet Mercury that Newton's Law of
Gravitation seemed not to fully explain." The passage describes Einstein's
correction for Mercury's orbit.

**Finding:** The question substitutes Saturn for Mercury despite the passage's
explicit "only" restriction. The evidence supports correcting the planet;
answering "Newton" would reinforce the incorrect premise.

**Approved disposition:** Exclude from the primary benchmark; retain as a
false-premise challenge candidate.

**Approval:** Project owner explicitly agreed to this disposition in conversation
on 2026-11-16 ("yes"). Decision recorded here only; existing dataset artifacts
and exclusion configurations remain unchanged.

### 2. Drill Cores and Water Location

**ID:** `squad_v2:5a581597770dc0001aeeffe4`

**Question:** What do drill cores show about water location?

**Evidence:** Drill cores supply samples of stratigraphic sections. Geophysical
surveys show subsurface stratigraphic units; combined data can help locate areas
for water, coal, and hydrocarbon extraction.

**Finding:** The passage describes a general use of combined data but does not
specify what drill cores themselves show about water location. A direct answer
would require an unsupported attribution or details absent from the context.
During joint review, the broad wording was judged to leave an identifiable
requested relationship: what drill cores specifically reveal about water
location. That relationship is not established by the supplied evidence.

**Approved disposition:** Retain as unanswerable with the original record unchanged.

**Approval:** Project owner explicitly agreed to retention in conversation
on 2026-11-16 ("yes").

### 3. Experienced Construction Workers

**ID:** `squad_v2:5a2358cc82b03a001a4aa797`

**Question:** What do people with experience not need to do?

**Evidence:** Experienced people "make detailed plans and maintain careful
oversight during the project to ensure a positive outcome."

**Finding:** The passage states actions experienced people take but identifies
no action they are exempt from. Literal abstention is defensible. However, the
negative question supplies no particular omitted action or requirement, making
its scope unclear. The passage does not prove that experienced people need to
do everything; a false premise is not established by this wording alone.

**Adjudication rationale:** The construction context supplies the domain and the
question requests an action experienced people need not perform. That request
is interpretable despite its breadth. No exemption is supplied, and observing
actions that people take does not establish which actions they do not need
to take. Negative wording alone does not justify exclusion or a false-premise
classification. This resolves the first-pass clarity concern.

**Approved disposition:** Retain as unanswerable with the original record unchanged.

**Approval:** Project owner explicitly agreed to retention in conversation
on 2026-11-16 ("yes").

## Next Step

All three candidates have approved dispositions. There are 19 approved
development records (10 answerable and nine unanswerable), one approved v3
exclusion, and no pending v3 candidate decisions. One new unanswerable replacement
is needed. Incorporating the Saturn/Mercury exclusion in a future configuration
would yield 20 cumulative exclusions, 19 approved retained IDs, and eight
false-premise challenge candidates. These latest decisions are documented only;
existing datasets and exclusion configurations remain unchanged.
No curated_v4 is authorized or generated by this audit.
