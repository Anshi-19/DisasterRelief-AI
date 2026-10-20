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

- Date: 2026-09-17
- Version: `week4_v3_controlled`
- Host: local macOS with Ollama
- Embedding model: `nomic-embed-text:latest`
- Retrieval top-k: 8
- Temperature: 0.0
- `num_predict`: 300
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
  "task_logic_correctness": "rubric over required imports, function use, inputs, and expected values, independent of import-path execution"
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
| CodeLlama | 0.571 | 0.696 | 0.964 | 0.752 | 0.054 | 0.500 | 28.17 | 22.52 | 38.92 | 21.51 | 0.0000 |
| Qwen2.5-Coder | 0.625 | 0.714 | 0.964 | 0.752 | 0.000 | 0.333 | 23.32 | 20.82 | 29.84 | 22.91 | 0.0000 |
| DeepSeek-Coder | 0.571 | 0.696 | 0.964 | 0.752 | 0.018 | 0.333 | 27.60 | 22.24 | 73.62 | 20.73 | 0.0000 |

These values are **measured or rubric-derived**. Interpretation follows in later sections and does not change the raw JSON.

## 12. Category-wise Analysis

| Category | Model | Correctness | Relevance | Retrieval Hit@K | Hallucination | Latency |
| --- | --- | --- | --- | --- | --- | --- |
| Bug Analysis | CodeLlama | 0.875 | 0.875 | 0.750 | 0.000 | 19.11 |
| Bug Analysis | Qwen2.5-Coder | 0.875 | 0.875 | 0.750 | 0.000 | 21.55 |
| Bug Analysis | DeepSeek-Coder | 0.625 | 0.750 | 0.750 | 0.000 | 21.51 |
| Code Generation | CodeLlama | 0.625 | 0.750 | 1 | 0.000 | 25.30 |
| Code Generation | Qwen2.5-Coder | 0.500 | 0.625 | 1 | 0.000 | 20.02 |
| Code Generation | DeepSeek-Coder | 0.500 | 0.625 | 1 | 0.000 | 23.43 |
| Code Retrieval | CodeLlama | 0.250 | 0.625 | 1 | 0.000 | 19.94 |
| Code Retrieval | Qwen2.5-Coder | 0.500 | 0.750 | 1 | 0.000 | 13.65 |
| Code Retrieval | DeepSeek-Coder | 0.500 | 0.750 | 1 | 0.000 | 16.01 |
| Dependency Understanding | CodeLlama | 0.750 | 0.750 | 1 | 0.250 | 28.33 |
| Dependency Understanding | Qwen2.5-Coder | 0.750 | 0.750 | 1 | 0.000 | 20.38 |
| Dependency Understanding | DeepSeek-Coder | 0.625 | 0.750 | 1 | 0.000 | 28.59 |
| Explanation | CodeLlama | 0.375 | 0.500 | 1 | 0.000 | 23.93 |
| Explanation | Qwen2.5-Coder | 0.375 | 0.500 | 1 | 0.000 | 24.52 |
| Explanation | DeepSeek-Coder | 0.500 | 0.625 | 1 | 0.000 | 22.21 |
| RAG | CodeLlama | 0.500 | 0.625 | 1 | 0.000 | 56.45 |
| RAG | Qwen2.5-Coder | 0.625 | 0.750 | 1 | 0.000 | 40.81 |
| RAG | DeepSeek-Coder | 0.500 | 0.625 | 1 | 0.000 | 56.81 |
| Refactoring | CodeLlama | 0.625 | 0.750 | 1 | 0.125 | 24.11 |
| Refactoring | Qwen2.5-Coder | 0.750 | 0.750 | 1 | 0.000 | 22.33 |
| Refactoring | DeepSeek-Coder | 0.750 | 0.750 | 1 | 0.125 | 24.62 |

**Bug Analysis.** In this benchmark, CodeLlama recorded the highest rubric correctness for Bug Analysis (0.875). Qwen2.5-Coder recorded the highest mean latency in this category (21.55 s).

**Code Generation.** In this benchmark, CodeLlama recorded the highest rubric correctness for Code Generation (0.625). CodeLlama recorded the highest mean latency in this category (25.30 s).

**Code Retrieval.** In this benchmark, Qwen2.5-Coder recorded the highest rubric correctness for Code Retrieval (0.500). CodeLlama recorded the highest mean latency in this category (19.94 s).

**Dependency Understanding.** In this benchmark, CodeLlama recorded the highest rubric correctness for Dependency Understanding (0.750). DeepSeek-Coder recorded the highest mean latency in this category (28.59 s).

**Explanation.** In this benchmark, DeepSeek-Coder recorded the highest rubric correctness for Explanation (0.500). Qwen2.5-Coder recorded the highest mean latency in this category (24.52 s).

**RAG.** In this benchmark, Qwen2.5-Coder recorded the highest rubric correctness for RAG (0.625). DeepSeek-Coder recorded the highest mean latency in this category (56.81 s).

**Refactoring.** In this benchmark, Qwen2.5-Coder recorded the highest rubric correctness for Refactoring (0.750). DeepSeek-Coder recorded the highest mean latency in this category (24.62 s).

## 13. Code Generation Analysis

CG01–CG04 were executed against the real `backend/` package. Import-path failures are reported separately from task-logic correctness.

- `codellama:latest`: test_pass_rate=0.500, functional_pass_rate=0.500, mean_task_logic_correctness=0.500, passed=2/4, errors={'import': 1, 'runtime': 1}
- `qwen2.5-coder:7b`: test_pass_rate=0.333, functional_pass_rate=0.250, mean_task_logic_correctness=0.625, passed=1/4, errors={'runtime': 2, 'syntax': 1}
- `deepseek-coder:6.7b`: test_pass_rate=0.333, functional_pass_rate=0.250, mean_task_logic_correctness=0.500, passed=1/4, errors={'import': 2, 'syntax': 1}

## 14. RAG Pipeline Analysis

Inspector cases are stored in `results/rag_case_studies.json` and were selected from actual traces.

### RG03 / codellama:latest — relevant context but wrong/incomplete answer selection

**Question.** According to the NDMA cyclone guidelines, what major structural mitigation measure is specifically discussed under the section on buildings?

**Ground truth.** The cyclone guidelines specifically discuss cyclone shelters under the buildings section.

**Key relevant facts in context.** 1.3 times, wind speed

**Missed facts.** cyclone shelter, shelter

**Model response.** According to the National Disaster Management Authority (NDMA) guidelines, the major structural mitigation measure specifically discussed under the section on buildings is the design of buildings to be carried out for 1.3 times the basic wind speed as recommended in the IS 875 - 1987 part 3.

**Scores.** correctness=0.000, relevance=0.500, hallucination=0.000, hit@K=True

**Analysis.** Retrieved context contained a buildings-section detail about designing for 1.3× basic wind speed (IS 875). The expected ground-truth fact (cyclone shelters) was not present in the retrieved chunks. The model answered from a different retrieved buildings fact. This is classified as a context-use / answer-selection problem combined with retrieval miss of the shelter passage, not as hallucination of the 1.3× figure.

### RG01 / codellama:latest — strong retrieval → correct grounded response

**Question.** According to the NDMA flood guidelines in the DisasterRelief AI knowledge base, what logistics and basic amenities are mentioned for setting up relief camps for people whose houses have been damaged by floods?

**Ground truth.** The flood guidelines mention mobilising relief supplies, tents, water supply and sanitation systems, transport and communication systems, and medical supplies for setting up relief camps.

**Key relevant facts in context.** tent, water, sanitation, transport, communication, medical, relief

**Missed facts.** None

**Model response.** According to the National Disaster Management Authority (NDMA) guidelines in the DisasterRelief AI knowledge base, the logistics and basic amenities for setting up relief camps for people whose houses have been damaged by floods are:

* Mobilising relief supplies, tents, water supply and sanitation systems, transport and communication systems, and medical supplies.
* Providing basic amenities such as food, shelter, and medical care.

These are mentioned in the context of the National Disaster Management Guidelines: Management of Floods, which are available in the DisasterRelief AI knowledge base.

**Scores.** correctness=1.000, relevance=1.000, hallucination=0.000, hit@K=True

**Analysis.** At least one expected source was retrieved and the answer matched the ground-truth rubric without unsupported claims.

### E02 / codellama:latest — partially successful retrieval and generation

**Question.** Explain how retrieve_documents() retrieves and selects relevant disaster-related document chunks from ChromaDB.

**Ground truth.** retrieve_documents() first detects the disaster type from the query using detect_disaster(). It generates an embedding using generate_embedding(), queries the persistent ChromaDB disaster_relief collection for candidate chunks, and requests more candidates than the final top_k. If a disaster type is detected, retrieval applies a disaster filter. Candidates whose distance is greater than 350 are discarded. Results are also limited per document using the configured per-document limit, and the final relevant chunks are returned.

**Key relevant facts in context.** None matched

**Missed facts.** None

**Model response.** The `retrieve_documents()` function in the `rag_service.py` file retrieves and selects relevant disaster-related document chunks from ChromaDB by following these steps:

1. The function first retrieves all the relevant documents from ChromaDB that contain the user's input query. This is done by using the `ChromaDB` class's `search()` method, which takes the user's input query as an argument and returns a list of matching documents.
2. Next, the function filters the list of retrieved documents to select only those that contain the disaster-related keywords. This is done by using the `ChromaDB` class's `filter()` method, which takes a list of keywords as an argument and returns a new list of documents that contain at least one of the keywords.
3. The function then selects the most relevant document chunk from the filtered list of documents. This is done by using the `ChromaDB` class's `select()` method, which takes a list of documents as an argument and returns a list of document chunks that contain the most relevant information for the user's query.
4. Finally, the function returns the selected document chunk as a string, which is then used as input to the language model for generating the response.

Overall, the `retrieve_documents()` function plays a crucial role

**Scores.** correctness=0.000, relevance=0.500, hallucination=0.000, hit@K=True

**Analysis.** Observed RAG behavior for this question/model pair based on the retrieved chunks, rubric scores, and ground-truth facts.

### RG02 / codellama:latest — relevant context but wrong/incomplete answer selection

**Question.** According to the NDMA earthquake guidelines, what logistics and basic amenities are mentioned in connection with relief camps for people whose houses have been damaged by an earthquake?

**Ground truth.** The earthquake guidelines mention mobilising relief supplies, tents, water supply and sanitation systems, transport and communication systems, and medical supplies for relief camps.

**Key relevant facts in context.** tent, water, sanitation, transport, communication, medical, relief

**Missed facts.** None

**Model response.** According to the National Disaster Management Authority's (NDMA) guidelines for managing earthquakes, relief camps for people whose houses have been damaged by an earthquake will require the mobilization and deployment of specialized equipment, such as tents, water supply and sanitation systems, transport and communication systems, and medical supplies. Additionally, the camps will need to provide basic amenities such as food, shelter, and medical care. The guidelines also suggest that hospitals in the affected areas will create a surge capacity for the required number of beds by discharging non-critical patients and mobilizing doctors and support staff, additional orthopaedic equipment and supplies at short notice.

**Scores.** correctness=0.500, relevance=0.500, hallucination=0.000, hit@K=True

**Analysis.** The retrieved context contained at least one required fact, but the model answer did not fully use those facts. This is classified as a context-use / answer-selection problem rather than hallucination.

### RG04 / codellama:latest — relevant context but wrong/incomplete answer selection

**Question.** According to the 2024 Ministry of Home Affairs guidelines, what is the purpose of the Recovery and Reconstruction Funding Window?

**Ground truth.** The Recovery and Reconstruction Funding Window is intended to help people affected by disasters on a long-term basis. The guidelines recommend a Recovery and Reconstruction Facility within both SDRF and NDRF.

**Key relevant facts in context.** long-term, recovery, reconstruction

**Missed facts.** None

**Model response.** The purpose of the Recovery and Reconstruction Funding Window is to provide financial assistance to States for recovery and reconstruction activities in the aftermath of a disaster. The guidelines state that the assistance will be determined on the basis of an assessment of damage and loss, and will be a percentage of the total cost of recovery and reconstruction. The funding window will be operationalized under the State Disaster Response Fund (SDRF) and the National Disaster Response Fund (NDRF), and will be released annually against expenditures. The assistance will be shared between the Union and States, and will be used to support recovery and reconstruction activities that are essential and justified.

**Scores.** correctness=0.500, relevance=0.500, hallucination=0.000, hit@K=True

**Analysis.** The retrieved context contained at least one required fact, but the model answer did not fully use those facts. This is classified as a context-use / answer-selection problem rather than hallucination.

## 15. Repository-level Analysis

Multi-file items evaluate whether models identify `App.jsx` → `/api/chat` → `process_question` → `retrieve_documents` → `build_context` → `generate_response` → Ollama, plus disaster detection, Chroma access, `top_k`, fallback, and embedding dependencies.

- `codellama:latest`: file identification=0.361, dependency reasoning=0.525, overall=0.476
- `qwen2.5-coder:7b`: file identification=0.417, dependency reasoning=0.694, overall=0.551
- `deepseek-coder:6.7b`: file identification=0.445, dependency reasoning=0.606, overall=0.517

## 16. Quality–Latency–Resource Trade-off

The scatter comparison in the dashboard plots measured mean latency against rubric correctness for this benchmark only. It is not a universal ranking.

- CodeLlama: correctness=0.571, mean latency=28.17 s, median=22.52 s, p95=38.92 s, memory=5501.6 MB, CPU=25.9%, throughput=21.51 tok/s. Labels: Highest code test-pass rate.
- Qwen2.5-Coder: correctness=0.625, mean latency=23.32 s, median=20.82 s, p95=29.84 s, memory=4537.8 MB, CPU=22.4%, throughput=22.91 tok/s. Labels: Highest measured correctness; Highest measured relevance; Lowest measured mean latency; Lowest measured median latency; Highest measured generation throughput.
- DeepSeek-Coder: correctness=0.571, mean latency=27.60 s, median=22.24 s, p95=73.62 s, memory=5443.6 MB, CPU=23.9%, throughput=20.73 tok/s. Labels: no unique extremal label in this benchmark.

## 17. Failure Analysis

- Generation failures in the final `week4_v3_controlled` run: 0 of 84.
- An earlier evaluation attempt interrupted during RG02 because a background `psutil` sampler raised a macOS process-permission error. Completed answers were preserved; remaining items were resumed without rerunning successful experiments. The sampler now treats permission errors as missing resource samples rather than aborting generation.
- Code-generation failures observed after execution against the repository include missing imports, `unittest` methods defined with `self` but not run as TestCase methods, and placeholder module names. Task/logic correctness is scored separately from executable pass/fail.
- Historical V1/V2 JSON files under `results/archive_pre_v3/` and `results/raw/` (non-v3 files) are not used in this report.

## 18. Limitations

- Automatic rubric scoring can under-credit a verbose but correct answer that omits a required token, and can over-credit keyword overlap. A human-review template is provided.
- `num_predict=300` can truncate long refactoring answers; this matches the Week 3 application setting.
- CPU percent is sampled from Ollama processes and can exceed 100 on multi-core hosts.
- GPU/VRAM is not reported.
- Nested Python methods are indexed inside class chunks, which can reduce symbol-level recall.
- Old `backend/rag/` files can appear in repository retrieval even though they are not on the live API path.

## 19. Conclusions

Conclusions are restricted to this 28-task local benchmark:

- `codellama:latest`: Highest code test-pass rate.
- `qwen2.5-coder:7b`: Highest measured correctness; Highest measured relevance; Lowest measured mean latency; Lowest measured median latency; Highest measured generation throughput.

No model is described as universally best.

## 20. Reproducibility

From the repository root, with Ollama running:

```bash
source backend/venv/bin/activate
python week4_evaluation/scripts/create_dataset.py
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