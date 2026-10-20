# Live RAG query diagnosis

Date: 2026-09-18  
Frozen benchmark file (untouched): `week4_evaluation/results/raw/week4_v4_improved.json`  
Live query: `My house was damaged by a flood. What assistance may be relevant?`

This report diagnoses retrieval vs generation for that live question. It does not change the evaluation dataset, ground truth, rubric, or frozen V4 raw scores.

---

## 1. Dataset / ground-truth audit

Closest evaluation item: **RG01** (RAG). Not modified.

| Field | Value |
| --- | --- |
| **id** | RG01 |
| **question** | According to the NDMA flood guidelines in the DisasterRelief AI knowledge base, what logistics and basic amenities are mentioned for setting up relief camps for people whose houses have been damaged by floods? |
| **ground_truth** | The flood guidelines mention mobilising relief supplies, tents, water supply and sanitation systems, transport and communication systems, and medical supplies for setting up relief camps. |
| **correctness_criteria** | Must identify relief supplies, tents, water supply and sanitation systems, transport and communication systems, and medical supplies. |
| **relevant_files** | knowledge_base/flood/flood_guidelines.pdf |
| **retrieval_criteria** | Retrieved source should be the NDMA flood guidelines and contain the relief-camp passage. |

The live query is shorter and more colloquial, but it asks the same user need: flood-damaged house + relevant assistance. RG01’s gold passage is NDMA Flood Guidelines §8.9.2 Relief Camps (page 93). That passage exists in Chroma (`disaster=flood`).

RG01 V4 scores (frozen): CodeLlama 0.5, Qwen 1.0, DeepSeek 1.0. For the long RG01 wording, retrieve_documents already ranked page 93 first.

**CASE D does not apply.** Ground truth matches the knowledge base.

---

## 2. Retrieval audit (before the fix)

Function: live `retrieve_documents()` in `backend/services/retrieval_service.py`, `top_k=8` (same as `/api/chat`).

- Query: `My house was damaged by a flood. What assistance may be relevant?`
- Detected disaster: `flood` (metadata filter `where={"disaster": "flood"}`)
- Dual embedding queries: original + sorted tokens `assistance damaged flood house may relevant was`
- Candidate pool after merge: 143 flood chunks; gold page-93 camp chunk was **chroma-order rank 31** (distance 225.369)

### Top 8 before the fix

| Rank | Pages | Distance | Useful for flood-damaged house + assistance? | Assessment |
| --- | --- | --- | --- | --- |
| 1 | [31] | 189.66 | Weak / misleading | Overview of flood response. Literal phrase **“Immediate medical assistance”**. This is what CodeLlama copied. |
| 2 | [94] | 194.33 | No | Waste disposal, insecticide-treated mosquito nets, psychosocial response. |
| 3 | [83, 84] | 199.62 | No | Flood education / capacity development. |
| 4 | [43] | 201.68 | No | Documentation of floods; ad-hoc flood-management complaints. |
| 5 | [86] | 202.66 | Partial | Preparedness: constructing flood shelters (not the damaged-house camp list). |
| 6 | [21] | 208.33 | No | Executive-summary capacity-development bullets. |
| 7 | [96, 97] | 211.23 | No | Flood-proofing implementation / public awareness. |
| 8 | [64] | 211.89 | Partial | Raised platforms / flood shelters with drinking water, sanitation, tents. Housing-adjacent, but not §8.9.2. |

Gold chunk (not in top 8):

```
Document: National Disaster Management Guidelines: Management of Floods
Pages: [93]
Distance: 225.369 (pool rank 31)
8.9.2 Relief Camps
The setting up of relief camps for the people whose houses have been damaged
by floods and the provision of basic amenities in such camps involves complex
logistics of mobilising relief supplies, tents, water supply and sanitation systems,
transport and communication systems, and medical supplies.
```

Before-fix context hash: `5ed22d1d16b14241064086005f5e159efc7a9077984342ea86f068b8a747e122`

Live generation also poisoned ranking inside the prompt. `build_focus_excerpt()` ranked passages by raw token overlap and dropped `flood` as a stopword. Remaining terms were `house, damaged, assistance, may, was`. The word **house** did not match **houses**, while **assistance** matched **“Immediate medical assistance”**. The internal hint was:

```
- Immediate medical assistance to
```

---

## 3. Case classification

**Primary: CASE B — retrieval ranking / query formulation.**

The correct assistance passage is in the index and in the flood-filtered candidate pool, but it ranks 31st under the live wording. The long RG01 question retrieves the same chunk at rank 1 (distance 133.99). Increasing `top_k` was not used as the fix.

**Contributing: CASE C — generation / context-use.**

Even among the old top 8, ranks 5 and 8 mentioned shelters/amenities. CodeLlama ignored them and answered from ranks 1–2 (medical assistance, epidemics, mosquito nets). The live focus excerpt pointed at that weaker evidence.

**Not CASE A.** Page 93 is indexed.  
**Not CASE D.** RG01 ground truth matches the KB.

Secondary filter issue (not the main miss): 84 MHA Recovery & Reconstruction chunks are tagged `disaster=all` and were excluded by `where={"disaster": "flood"}`. Those distances start around 218, so they still would not have beaten medical chunks without a better query.

---

## 4. Proposed / implemented fix

Change type: **retrieval (primary) + live generation context-use (secondary)**.

Not done: raise `top_k`; rewrite dataset/ground truth; post-process answers before benchmark scoring; overwrite `week4_v4_improved.json`.

### Retrieval (`retrieve_documents`)

1. When the question has housing-damage terms **and** assistance/disaster terms, add one extra embedding query:
   `relief camps for people whose houses have been damaged {disaster} basic amenities shelter reconstruction immediate relief`
   This is query formulation from detected need, not a hardcoded amenities list.
2. When a disaster filter is applied, also include `disaster=all` so common reconstruction guidance can compete.

Chroma order + existing heading injection are unchanged (an overlap-only rerank was tested and dropped cyclone-shelter / RG04 purpose chunks).

### Live generation only (`llm_service.py`)

Week 4 scoring uses `eval_config.SYSTEM_INSTRUCTION` and Ollama `/api/generate`, not this chat prompt.

1. Stem tokens in `build_focus_excerpt` / `query_focus_support` so `house` matches `houses`.
2. For assistance questions that mention a damaged house, instruct the model to prefer relief-camp / shelter / reconstruction evidence over medical-epidemic lead-ins unless health was asked.

---

## 5. Retrieval after the fix

Expanded queries for the live question:

1. original user text  
2. `assistance damaged flood house may relevant was`  
3. `relief camps for people whose houses have been damaged flood basic amenities shelter reconstruction immediate relief`

| Rank | Pages | Distance | Assessment |
| --- | --- | --- | --- |
| 1 | [93] | 152.05 | DIRECT: §8.9.2 houses damaged + relief camps + amenities list |
| 2 | [86] | 159.84 | PARTIAL: flood shelters |
| 3 | [64] | 172.67 | PARTIAL: raised platforms / flood shelter |
| 4 | [31] | 174.09 | WEAK: medical-assistance overview (still present, no longer rank 1) |
| 5 | [64] | 179.35 | PARTIAL: amenities at flood shelters |
| 6 | [98] | 181.30 | BACKGROUND: FM plans |
| 7 | [90, 91] | 182.51 | PARTIAL: emergency shelters / distributing relief |
| 8 | [115] | 187.47 | PARTIAL: Relief Camps index entry |

After-fix context hash: `552be592aa0d1b6bdce59ebf7fdefcd89d65e35dbeaeb202d5f416a99382d177`

RG03 still retrieves cyclone shelters at rank 2 (heading injection). Extra expansion does not fire on that question (no house/assistance terms).

---

## 6. Before / after live response

**Before (CodeLlama, old top-8 medical context):**

- Immediate medical assistance to the affected people.
- Steps for prevention of outbreaks of epidemics after floods are essential components of flood response.
- Provision of insecticide-treated mosquito nets are recommended.

**After (same query, shared retrieval, 2026-09-18):**

Shared `context_hash`: `552be592aa0d1b6bdce59ebf7fdefcd89d65e35dbeaeb202d5f416a99382d177`  
All three models received this same context (`/api/chat/compare`). Rank 1 is now NDMA §8.9.2 Relief Camps (page 93).

**CodeLlama** now cites relief camps, tents, water/sanitation, transport/communication, and medical supplies for people whose houses were damaged. It still pastes nearby CRF/panchayat-plinth sentences and was truncated at `num_predict=220`.

**DeepSeek-Coder** leads with relief camps for damaged houses, then still includes medical/epidemic and QRMT evidence that is in the new top 8 (page 115), plus flood-shelter construction.

**Qwen2.5-Coder** leads with relief-camp amenities and shelter construction. “Quick Reaction Medical Teams / mobile field hospitals” is supported by page 115. “Reconstruction: support for rebuilding homes and infrastructure” overstates the retrieved flood-proofing/shelter text; it is not the MHA R&R funding window.

---

## 8. Live three-model verification

| Model | Success | Same context hash |
| --- | --- | --- |
| codellama:latest | yes | 552be592aa0d1b6bdce59ebf7fdefcd89d65e35dbeaeb202d5f416a99382d177 |
| qwen2.5-coder:7b | yes | 552be592aa0d1b6bdce59ebf7fdefcd89d65e35dbeaeb202d5f416a99382d177 |
| deepseek-coder:6.7b | yes | 552be592aa0d1b6bdce59ebf7fdefcd89d65e35dbeaeb202d5f416a99382d177 |

API hash matched a local SHA-256 of `retrieved_context`.

Live app: frontend http://127.0.0.1:5173/ · backend http://127.0.0.1:8000/

---

## 7. Benchmark policy

- Frozen V4 raw file is not overwritten.
- `retrieve_documents` is shared with RAG eval questions (RG01–RG04 only). Repository questions use `disaster_relief_code` and are unaffected.
- A follow-up RAG-only eval, if run, writes a **new** raw file via `WEEK4_RAW_RESULTS`. It must not replace `week4_v4_improved.json`.
- Live prompt changes do not enter benchmark scoring.

### Frozen V4 (old) overall

| Model | Correctness | Hallucination | Hit@K | MRR |
| --- | --- | --- | --- | --- |
| CodeLlama | 0.500 | 0.1071 | 0.9643 | 0.9226 |
| Qwen2.5-Coder | 0.8393 | 0.0357 | 0.9643 | 0.9226 |
| DeepSeek-Coder | 0.500 | 0.0893 | 0.9643 | 0.9226 |

New RAG-only eval (12 runs) was written to `results/raw/week4_query_formulation_rag.json`. Frozen `week4_v4_improved.json` remains 84/84 `week4_v4_improved`.

Document-level RAG retrieval metrics did not change (Hit@K 1.0, MRR 1.0, P@K 0.875 on RG01–RG04). The live-query failure was **chunk ranking inside the flood PDF**, which this file-level metric does not see.

### Frozen V4 overall (old, 84/84)

| Model | Correctness | Hallucination | Hit@K | MRR |
| --- | --- | --- | --- | --- |
| CodeLlama | 0.500 | 0.1071 | 0.9643 | 0.9226 |
| Qwen2.5-Coder | 0.8393 | 0.0357 | 0.9643 | 0.9226 |
| DeepSeek-Coder | 0.500 | 0.0893 | 0.9643 | 0.9226 |

### After query-formulation change (RAG items re-scored; 24 non-RAG rows frozen)

| Model | Old C | New C | Old H | New H |
| --- | --- | --- | --- | --- |
| CodeLlama | 0.500 | 0.500 | 0.1071 | 0.1071 |
| Qwen2.5-Coder | 0.8393 | 0.8393 | 0.0357 | 0.0357 |
| DeepSeek-Coder | 0.500 | 0.536 | 0.0893 | 0.0893 |

RAG cases (12): **1 improved, 0 regressed, 11 unchanged**. The only score change is RG02 / DeepSeek-Coder 0.0 → 1.0. CodeLlama RG01 stayed 0.5 (still missed some amenity groups). Hallucination unchanged.

The frontend still displays frozen V4 numbers. That is intentional.
