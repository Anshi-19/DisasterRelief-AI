# DisasterRelief-AI Week 4 Technical Report

## 1. Introduction

This report documents a controlled Week 4 evaluation of local Ollama code models on the existing DisasterRelief-AI Week 3 RAG application. All quantitative figures below are computed from `week4_evaluation/results/` after actually running retrieval, generation, scoring, and resource sampling. No scores were edited to favor a model.

## 2. Week 3 System Overview

The live application path is:

1. `frontend/src/App.jsx` `analyzeSituation()` posts `{message}` to `POST /api/chat`.
2. `backend/main.py` `chat()` calls `process_question(request.message, top_k=8)`.
3. `process_question()` in `orchestration_service.py` calls `retrieve_documents()`.
4. If retrieval is empty, it returns the insufficient-knowledge fallback and does not call the LLM.
5. Otherwise `build_context()` formats document/authority/disaster/pages/content and `generate_response()` posts to Ollama.
6. Retrieval uses `nomic-embed-text:latest`, Chroma collection `disaster_relief`, optional `detect_disaster()` metadata filter, distance cutoff 350, and per-document limits `max(2, top_k // 2)`.
7. The application LLM remains `codellama:latest`. Week 4 benchmarking did not permanently replace that setting.

`backend/rag/` contains an older RAG implementation. It was indexed for repository search but is not the live `/api/chat` path.

## 3. Week 4 Objectives

- Evaluate the same 28 tasks on at least three local models.
- Measure quality, retrieval, latency, tokens, and host resources.
- Analyze RAG traces and multi-file repository understanding.
- Produce reproducible JSON, Excel, markdown, and dashboard artifacts.

## 4. System Architecture

Live Week 3 path (used by the application):

`frontend/src/App.jsx` `analyzeSituation()` → `POST /api/chat` in `backend/main.py` → `process_question()` → `retrieve_documents()` (Chroma `disaster_relief`) → `build_context()` → `generate_response()` → Ollama `codellama:latest`.

Legacy path (indexed, not called by `/api/chat`): `backend/rag/rag_service.py`, `backend/rag/retrieval.py`, `backend/rag/embeddings.py`.

Week 4 evaluation retrieves repository questions from collection `disaster_relief_code` and RAG questions through the live `retrieve_documents()` function. Retrieval is executed once per question; all three models receive the same frozen context.

## 5. Evaluation Environment

- Date: 2026-09-18
- Version: `week4_v4_improved`
- Host: local macOS with Ollama
- Embedding model: `nomic-embed-text:latest`
- Retrieval top-k: 8
- Temperature: 0.0
- `num_predict`: 640
- Disaster collection: `vector_store/chroma_db` / `disaster_relief`
- Code collection: `vector_store` / `disaster_relief_code`

GPU utilization was not included because a reliable per-model GPU utilization measurement was not available in the evaluation environment.

Resource method: During each Ollama generation, a background sampler queried local processes whose name or command line contained 'ollama' approximately every 0.4 seconds using psutil. RSS is process resident set size. CPU percent is the sum of sampled Ollama process CPU percentages and can exceed 100 on multi-core hosts. Token timings come from Ollama's generate API duration fields.

## 6. Models

- `codellama:latest` (display: CodeLlama)
- `qwen2.5-coder:7b` (display: Qwen2.5-Coder)
- `deepseek-coder:6.7b` (display: DeepSeek-Coder)

Fairness: identical questions, prompt wrapper, top-k, temperature, max tokens, embedding model, and frozen retrieval context per question.

## 7. Dataset

28 tasks, 7 categories × 4 items: E01–E04, CR01–CR04, D01–D04, B01–B04, CG01–CG04, RF01–RF04, RG01–RG04. Each row stores ground truth, relevant files, and explicit correctness/relevance/hallucination/retrieval rubrics. Code-generation items specify required imports, function use, inputs, expected values, and syntactic validity.

## 8. Experimental Methodology

Repository questions retrieve from `disaster_relief_code`. RAG questions retrieve through the Week 3 `retrieve_documents()` function. Each Ollama `generate` call is retried up to two times on transient errors. Persistent failures are stored with HTTP/error text, counted in failure rate, and excluded from quality averages.

## 9. Metrics and Definitions

{
  "correctness": "1.0 fully satisfies the dataset rubric, 0.5 partial, 0.0 incorrect. Failed generations are excluded.",
  "relevance": "1.0 directly answers, 0.5 partial, 0.0 largely irrelevant.",
  "hallucination": "0 none, 0.5 minor unsupported claim, 1 significant unsupported claim. Wrong selection from retrieved context is not counted as hallucination.",
  "test_pass_rate": "passed generated-code tests / syntactically valid generated-code tests",
  "task_logic_correctness": "rubric over required imports, function use, inputs, and expected values, independent of import-path execution. CG02 accepts detect_disaster(query) when a nearby string assignment is a non-disaster query, not only inline string literals.",
  "codegen_execution": "A generated unittest that reports OK and exit code 0 is a pass even if unittest.main() exited before the harness printed TEST_PASS. This corrects a V3 scoring bug; it does not change the dataset rubric."
}

Retrieval Hit@K, MRR, Precision@K and Recall@K use dataset `relevant_files`, not answer keyword overlap.

## 10. Retrieval Methodology

Hit@K is 1 if at least one ground-truth relevant file or document appears in the top-K retrieved chunks. MRR is the mean of 1/rank of the first relevant result (0 if none). Precision@K is the fraction of retrieved chunks whose source matches a ground-truth item. Recall@K is the fraction of ground-truth items found in the retrieved set.

Because retrieval is executed once per question and the same chunks are passed to every model, Hit@K, MRR, Precision@K, and Recall@K are identical across models for the same question. Model differences therefore come from generation, not from different retrieval.

The live application collection `disaster_relief` is stored under `vector_store/chroma_db`. The Week 4 code collection `disaster_relief_code` is stored under `vector_store` and does not replace the disaster knowledge base.

## 11. Quantitative Results

- Recorded experiments: 84
- Successful: 84
- Failed: 0

| Model | Correctness | Relevance | Hit@K | MRR | Hallucination | Code pass | Mean lat. | Median | p95 | Tok/s | Fail |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CodeLlama | 0.500 | 0.643 | 0.964 | 0.923 | 0.107 | 0.000 | 26.70 | 26.29 | 39.96 | 22.62 | 0.0000 |
| Qwen2.5-Coder | 0.839 | 0.857 | 0.964 | 0.923 | 0.036 | 0.750 | 20.66 | 17.59 | 36.77 | 25.43 | 0.0000 |
| DeepSeek-Coder | 0.500 | 0.661 | 0.964 | 0.923 | 0.089 | 0.250 | 24.32 | 24.38 | 31.04 | 22.89 | 0.0000 |

These values are **measured or rubric-derived**. Interpretation follows in later sections and does not change the raw JSON.

## 12. Category-wise Analysis

| Category | Model | Correctness | Relevance | Retrieval Hit@K | Hallucination | Latency |
| --- | --- | --- | --- | --- | --- | --- |
| Bug Analysis | CodeLlama | 0.750 | 0.750 | 1 | 0.000 | 20.58 |
| Bug Analysis | Qwen2.5-Coder | 1.000 | 1.000 | 1 | 0.000 | 15.28 |
| Bug Analysis | DeepSeek-Coder | 0.750 | 0.750 | 1 | 0.000 | 23.76 |
| Code Generation | CodeLlama | 0.375 | 0.500 | 0.750 | 0.250 | 25.68 |
| Code Generation | Qwen2.5-Coder | 0.875 | 0.875 | 0.750 | 0.000 | 18.35 |
| Code Generation | DeepSeek-Coder | 0.625 | 0.625 | 0.750 | 0.250 | 24.29 |
| Code Retrieval | CodeLlama | 0.250 | 0.625 | 1 | 0.125 | 25.50 |
| Code Retrieval | Qwen2.5-Coder | 0.750 | 0.875 | 1 | 0.250 | 15.59 |
| Code Retrieval | DeepSeek-Coder | 0.250 | 0.625 | 1 | 0.125 | 22.91 |
| Dependency Understanding | CodeLlama | 0.625 | 0.750 | 1 | 0.125 | 27.00 |
| Dependency Understanding | Qwen2.5-Coder | 0.875 | 0.875 | 1 | 0.000 | 21.40 |
| Dependency Understanding | DeepSeek-Coder | 0.500 | 0.750 | 1 | 0.000 | 26.87 |
| Explanation | CodeLlama | 0.375 | 0.500 | 1 | 0.000 | 31.88 |
| Explanation | Qwen2.5-Coder | 0.500 | 0.500 | 1 | 0.000 | 27.18 |
| Explanation | DeepSeek-Coder | 0.125 | 0.500 | 1 | 0.250 | 30.52 |
| RAG | CodeLlama | 0.500 | 0.625 | 1 | 0.250 | 23.20 |
| RAG | Qwen2.5-Coder | 0.875 | 0.875 | 1 | 0.000 | 15.87 |
| RAG | DeepSeek-Coder | 0.625 | 0.625 | 1 | 0.000 | 16.20 |
| Refactoring | CodeLlama | 0.625 | 0.750 | 1 | 0.000 | 33.04 |
| Refactoring | Qwen2.5-Coder | 1.000 | 1.000 | 1 | 0.000 | 30.93 |
| Refactoring | DeepSeek-Coder | 0.625 | 0.750 | 1 | 0.000 | 25.70 |

**Bug Analysis.** In this benchmark, Qwen2.5-Coder recorded the highest rubric correctness for Bug Analysis (1.000). DeepSeek-Coder recorded the highest mean latency in this category (23.76 s).

**Code Generation.** In this benchmark, Qwen2.5-Coder recorded the highest rubric correctness for Code Generation (0.875). CodeLlama recorded the highest mean latency in this category (25.68 s).

**Code Retrieval.** In this benchmark, Qwen2.5-Coder recorded the highest rubric correctness for Code Retrieval (0.750). CodeLlama recorded the highest mean latency in this category (25.50 s).

**Dependency Understanding.** In this benchmark, Qwen2.5-Coder recorded the highest rubric correctness for Dependency Understanding (0.875). CodeLlama recorded the highest mean latency in this category (27.00 s).

**Explanation.** In this benchmark, Qwen2.5-Coder recorded the highest rubric correctness for Explanation (0.500). CodeLlama recorded the highest mean latency in this category (31.88 s).

**RAG.** In this benchmark, Qwen2.5-Coder recorded the highest rubric correctness for RAG (0.875). CodeLlama recorded the highest mean latency in this category (23.20 s).

**Refactoring.** In this benchmark, Qwen2.5-Coder recorded the highest rubric correctness for Refactoring (1.000). CodeLlama recorded the highest mean latency in this category (33.04 s).

## 13. Code Generation Analysis

CG01–CG04 were executed against the real `backend/` package. Import-path failures are reported separately from task-logic correctness.

- `codellama:latest`: test_pass_rate=0.000, functional_pass_rate=0.000, mean_task_logic_correctness=0.375, passed=0/4, errors={'import': 1, 'runtime': 3}
- `qwen2.5-coder:7b`: test_pass_rate=0.750, functional_pass_rate=0.750, mean_task_logic_correctness=0.875, passed=3/4, errors={'import': 1}
- `deepseek-coder:6.7b`: test_pass_rate=0.250, functional_pass_rate=0.250, mean_task_logic_correctness=0.625, passed=1/4, errors={'import': 3}

## 14. RAG Pipeline Analysis

Inspector cases are stored in `results/rag_case_studies.json` and were selected from actual traces.

### RG03 / codellama:latest — relevant context but wrong/incomplete answer selection

**Question.** According to the NDMA cyclone guidelines, what major structural mitigation measure is specifically discussed under the section on buildings?

**Ground truth.** The cyclone guidelines specifically discuss cyclone shelters under the buildings section.

**Key relevant facts in context.** cyclone shelter, shelter, 1.3 times, wind speed

**Missed facts.** None

**Model response.** According to the National Disaster Management Authority (NDMA) guidelines, the major structural mitigation measure specifically discussed under the section on buildings is the design of cyclone-resistant buildings. The guidelines recommend that buildings be designed to withstand the fury of cyclones, including wind and storm surge, and that the basic design specifications for buildings be based on the Indian Building Codes and Standards and IRC Specifications. Additionally, the guidelines emphasize the importance of ensuring that the local community constructs cyclone-resistant buildings, and that urban local bodies and panchayati raj institutions encourage this.

**Scores.** correctness=0.000, relevance=0.500, hallucination=0.000, hit@K=True

**Analysis.** The retrieved context contained at least one required fact, but the model answer did not fully use those facts. This is classified as a context-use / answer-selection problem rather than hallucination.

### RG01 / qwen2.5-coder:7b — strong retrieval → correct grounded response

**Question.** According to the NDMA flood guidelines in the DisasterRelief AI knowledge base, what logistics and basic amenities are mentioned for setting up relief camps for people whose houses have been damaged by floods?

**Ground truth.** The flood guidelines mention mobilising relief supplies, tents, water supply and sanitation systems, transport and communication systems, and medical supplies for setting up relief camps.

**Key relevant facts in context.** tent, water, sanitation, transport, communication, medical, relief

**Missed facts.** None

**Model response.** **Fact:** The setting up of relief camps for people whose houses have been damaged by floods involves complex logistics of mobilising relief supplies, tents, water supply and sanitation systems, transport and communication systems, and medical supplies.

**Key Points:**
- **Relief Supplies:** Mobilising relief supplies
- **Tents:** Providing tents
- **Water Supply and Sanitation Systems:** Ensuring water supply and sanitation systems
- **Transport and Communication Systems:** Setting up transport and communication systems
- **Medical Supplies:** Providing medical supplies

**Evidence:** National Disaster Management Guidelines: Management of Floods, p.[93]

**Scores.** correctness=1.000, relevance=1.000, hallucination=0.000, hit@K=True

**Analysis.** At least one expected source was retrieved and the answer matched the ground-truth rubric without unsupported claims.

### RG04 / codellama:latest — hallucination despite retrieved context

**Question.** According to the 2024 Ministry of Home Affairs guidelines, what is the purpose of the Recovery and Reconstruction Funding Window?

**Ground truth.** The Recovery and Reconstruction Funding Window is intended to help people affected by disasters on a long-term basis. The guidelines recommend a Recovery and Reconstruction Facility within both SDRF and NDRF.

**Key relevant facts in context.** long-term, recovery, reconstruction

**Missed facts.** None

**Model response.** The Recovery and Reconstruction Funding Window is a funding mechanism provided by the Ministry of Home Affairs to support States in their efforts to recover and rebuild from disasters. The purpose of the Recovery and Reconstruction Funding Window is to provide financial assistance to States to support their efforts to recover and rebuild from disasters, with a focus on the recovery and reconstruction of infrastructure and other essential services. The funding window is designed to provide a flexible approach to funding recovery and reconstruction activities, allowing States to prioritize their efforts based on the specific needs of their communities.

**Scores.** correctness=0.500, relevance=0.500, hallucination=1.000, hit@K=True

**Analysis.** The answer included unsupported claims relative to the retrieved context and dataset hallucination criteria.

### E02 / codellama:latest — partially successful retrieval and generation

**Question.** Explain how retrieve_documents() retrieves and selects relevant disaster-related document chunks from ChromaDB.

**Ground truth.** retrieve_documents() first detects the disaster type from the query using detect_disaster(). It generates an embedding using generate_embedding(), queries the persistent ChromaDB disaster_relief collection for candidate chunks, and requests more candidates than the final top_k. If a disaster type is detected, retrieval applies a disaster filter. Candidates whose distance is greater than 350 are discarded. Results are also limited per document using the configured per-document limit, and the final relevant chunks are returned.

**Key relevant facts in context.** None matched

**Missed facts.** None

**Model response.** The `retrieve_documents()` function in the `ingestion` module of the DisasterRelief AI backend retrieves and selects relevant disaster-related document chunks from ChromaDB. Here's a step-by-step explanation of how it works:

1. The function first retrieves all the document chunks from ChromaDB using the `get_all_chunks()` function. This function returns a list of all the document chunks in the database.
2. The function then filters the list of chunks to only include those that contain relevant disaster-related information. This is done by checking if the chunk contains any of the keywords from the `DISASTER_KEYWORDS` list.
3. The filtered list of chunks is then passed to the `select_relevant_chunks()` function, which selects the top-k most relevant chunks based on their relevance scores. The relevance scores are calculated using the `calculate_relevance_scores()` function, which calculates the cosine similarity between the query vector and the vector representations of the chunks in the database.
4. The selected chunks are then returned as a list of dictionaries, where each dictionary represents a single chunk and contains its ID, relevance score, and the actual text of the chunk.

The `retrieve_documents()` function is called in the `analyze_situation()` function in the `frontend` module, which is responsible for analyzing the user's input and retrieving relevant disaster-related information from ChromaDB. The function then passes the selected chunks to the `Pipeline` component in the frontend, which uses them to generate a response to the user's input.

**Scores.** correctness=0.000, relevance=0.500, hallucination=0.000, hit@K=True

**Analysis.** Observed RAG behavior for this question/model pair based on the retrieved chunks, rubric scores, and ground-truth facts.

### RG01 / codellama:latest — relevant context but wrong/incomplete answer selection

**Question.** According to the NDMA flood guidelines in the DisasterRelief AI knowledge base, what logistics and basic amenities are mentioned for setting up relief camps for people whose houses have been damaged by floods?

**Ground truth.** The flood guidelines mention mobilising relief supplies, tents, water supply and sanitation systems, transport and communication systems, and medical supplies for setting up relief camps.

**Key relevant facts in context.** tent, water, sanitation, transport, communication, medical, relief

**Missed facts.** None

**Model response.** According to the National Disaster Management Authority (NDMA) guidelines, the following logistics and basic amenities are mentioned for setting up relief camps for people whose houses have been damaged by floods:

* Adequate number of raised platforms/flood shelters at suitable locations in the flood plains with basic amenities such as drinking water, sanitation, medical treatment, cooking, tents, lanterns, and life jackets for the people to take shelter during floods.
* Maintenance of shelters is a major issue. The MOWR will, in consultation with the CWC, Brahmaputra Board, GFCC, Central Building Research Institute (CBRI) and the state governments, evolve a model design of the shelters for flood-prone areas in different regions.
* The state governments/SDMAs will ensure use of the shelters through the district and local authorities for purposes such as running schools, anganwadis, and other community-based organizations.
* The NDMA/MHA will take up with the Thirteenth Finance Commission the need for earmarking adequate funds for maintenance of the dams, embankments, levees, and town protection works under appropriate heads of account in plan/non-plan budgets.
* The state governments/SDMAs will take steps to make all public utility installations flood-safe.
* The NDMA/MHA will take up with the Thirteenth Finance Commission the need for earmarking adequate funds for maintenance of the dams, embankments, levees, and town protection works under appropriate heads of account in plan/non-plan budgets.
* The state governments/SDMAs will ensure use of the shelters through the district and local authorities for purposes such as running schools, anganwadis, and other community-based organizations.
* The NDMA/MHA will take up with the Thirteenth Finance Commission the need for earmarking adequate funds for maintenance of the dams, embankments, levees, and town protection works under appropriate heads of account in plan/non-plan budgets.
* The state governments/SDMAs will ensure use of the shelters through the district and local authorities for purposes such as running schools, anganwadis, and other community-based organizations.
* The NDMA/MHA will take up with the Thirteenth Finance Commission the need for earmarking adequate funds for maintenance of the dams, embankments, levees, and town protection works under appropriate heads of account in plan/non-plan budgets.
* The state governments/SDMAs will ensure use of the shelters through the district and local authorities for purposes such as running schools, anganwadis, and other community-based organizations.
* The

**Scores.** correctness=0.500, relevance=0.500, hallucination=0.000, hit@K=True

**Analysis.** The retrieved context contained at least one required fact, but the model answer did not fully use those facts. This is classified as a context-use / answer-selection problem rather than hallucination.

### RG02 / codellama:latest — strong retrieval → correct grounded response

**Question.** According to the NDMA earthquake guidelines, what logistics and basic amenities are mentioned in connection with relief camps for people whose houses have been damaged by an earthquake?

**Ground truth.** The earthquake guidelines mention mobilising relief supplies, tents, water supply and sanitation systems, transport and communication systems, and medical supplies for relief camps.

**Key relevant facts in context.** tent, water, sanitation, transport, communication, medical, relief

**Missed facts.** None

**Model response.** According to the National Disaster Management Guidelines: Management of Earthquakes, the logistics and basic amenities mentioned in connection with relief camps for people whose houses have been damaged by an earthquake are:

* Mobilising relief supplies, tents, water supply and sanitation systems, transport and communication systems, and medical supplies.
* Setting up relief camps for the people whose houses have been damaged by an earthquake and providing basic amenities such as food, shelter, and medical care.

**Scores.** correctness=1.000, relevance=1.000, hallucination=0.000, hit@K=True

**Analysis.** At least one expected source was retrieved and the answer matched the ground-truth rubric without unsupported claims.

## 15. Repository-level Analysis

Multi-file items evaluate whether models identify `App.jsx` → `/api/chat` → `process_question` → `retrieve_documents` → `build_context` → `generate_response` → Ollama, plus disaster detection, Chroma access, `top_k`, fallback, and embedding dependencies.

- `codellama:latest`: file identification=0.347, dependency reasoning=0.583, overall=0.477
- `qwen2.5-coder:7b`: file identification=0.611, dependency reasoning=0.775, overall=0.740
- `deepseek-coder:6.7b`: file identification=0.347, dependency reasoning=0.481, overall=0.415

## 16. Quality–Latency–Resource Trade-off

The scatter comparison in the dashboard plots measured mean latency against rubric correctness for this benchmark only. It is not a universal ranking.

- CodeLlama: correctness=0.500, mean latency=26.70 s, median=26.29 s, p95=39.96 s, memory=5620.9 MB, CPU=28.9%, throughput=22.62 tok/s. Labels: no unique extremal label in this benchmark.
- Qwen2.5-Coder: correctness=0.839, mean latency=20.66 s, median=17.59 s, p95=36.77 s, memory=4586.0 MB, CPU=22.2%, throughput=25.43 tok/s. Labels: Highest measured correctness; Highest measured relevance; Lowest measured mean latency; Lowest measured median latency; Highest code test-pass rate; Highest measured generation throughput.
- DeepSeek-Coder: correctness=0.500, mean latency=24.32 s, median=24.38 s, p95=31.04 s, memory=5501.9 MB, CPU=27.4%, throughput=22.89 tok/s. Labels: no unique extremal label in this benchmark.

## 17. Failure Analysis

- Generation failures in the `week4_v4_improved` run: 0 of 84.
- Code-generation scoring now treats a unittest that reports OK with exit code 0 as a pass, even if `unittest.main()` exited before the harness printed `TEST_PASS`. This is a documented evaluator bugfix, not a rubric change.
- `week4_v3_controlled` remains historical and was not overwritten.

## 18. Limitations

- Automatic rubric scoring can under-credit a verbose but correct answer that omits a required token, and can over-credit keyword overlap. A human-review template is provided.
- `num_predict=640` is shared across all three models.
- CPU percent is sampled from Ollama processes and can exceed 100 on multi-core hosts.
- GPU/VRAM is not reported.
- Nested Python methods are indexed inside class chunks, which can reduce symbol-level recall.
- Old `backend/rag/` files can appear in repository retrieval even though they are not on the live API path.

## 19. V3 vs V4

Historical `week4_v3_controlled` is unchanged. The numbers below compare that frozen run with this `week4_v4_improved` run.

| Model | V3 corr. | V4 corr. | V3 rel. | V4 rel. | V3 Hit@K | V4 Hit@K | V3 hall. | V4 hall. | V3 code pass | V4 code pass |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CodeLlama | 0.571 | 0.500 | 0.696 | 0.643 | 0.964 | 0.964 | 0.054 | 0.107 | 0.500 | 0.000 |
| Qwen2.5-Coder | 0.625 | 0.839 | 0.714 | 0.857 | 0.964 | 0.964 | 0.000 | 0.036 | 0.333 | 0.750 |
| DeepSeek-Coder | 0.571 | 0.500 | 0.696 | 0.661 | 0.964 | 0.964 | 0.018 | 0.089 | 0.333 | 0.250 |

| Category | Model | V3 correctness | V4 correctness |
| --- | --- | --- | --- |
| Bug Analysis | CodeLlama | 0.875 | 0.750 |
| Bug Analysis | Qwen2.5-Coder | 0.875 | 1.000 |
| Bug Analysis | DeepSeek-Coder | 0.625 | 0.750 |
| Code Generation | CodeLlama | 0.625 | 0.375 |
| Code Generation | Qwen2.5-Coder | 0.500 | 0.875 |
| Code Generation | DeepSeek-Coder | 0.500 | 0.625 |
| Code Retrieval | CodeLlama | 0.250 | 0.250 |
| Code Retrieval | Qwen2.5-Coder | 0.500 | 0.750 |
| Code Retrieval | DeepSeek-Coder | 0.500 | 0.250 |
| Dependency Understanding | CodeLlama | 0.750 | 0.625 |
| Dependency Understanding | Qwen2.5-Coder | 0.750 | 0.875 |
| Dependency Understanding | DeepSeek-Coder | 0.625 | 0.500 |
| Explanation | CodeLlama | 0.375 | 0.375 |
| Explanation | Qwen2.5-Coder | 0.375 | 0.500 |
| Explanation | DeepSeek-Coder | 0.500 | 0.125 |
| RAG | CodeLlama | 0.500 | 0.500 |
| RAG | Qwen2.5-Coder | 0.625 | 0.875 |
| RAG | DeepSeek-Coder | 0.500 | 0.625 |
| Refactoring | CodeLlama | 0.625 | 0.625 |
| Refactoring | Qwen2.5-Coder | 0.750 | 1.000 |
| Refactoring | DeepSeek-Coder | 0.750 | 0.625 |

## 20. Conclusions

Conclusions are restricted to this 28-task local benchmark:

- `qwen2.5-coder:7b`: Highest measured correctness; Highest measured relevance; Lowest measured mean latency; Lowest measured median latency; Highest code test-pass rate; Highest measured generation throughput.

No model is described as universally best.

## 21. Reproducibility

From the repository root, with Ollama running. Do not rerun `create_dataset.py`; the 28 questions are frozen.

```bash
source backend/venv/bin/activate
python week4_evaluation/scripts/index_repository.py
python week4_evaluation/scripts/test_repository_retrieval.py
python week4_evaluation/scripts/run_evaluation.py
python week4_evaluation/scripts/evaluate_retrieval.py
python week4_evaluation/scripts/evaluate_quality.py
python week4_evaluation/scripts/measure_resources.py
python week4_evaluation/scripts/analyze_rag.py
python week4_evaluation/scripts/analyze_repository.py
python week4_evaluation/scripts/generate_report.py
```

Open `week4_evaluation/dashboard/index.html` in a browser.