# Week 4 Evaluation Summary

**Project:** DisasterRelief-AI
**Objective:** Empirically evaluate three local Ollama code models on the existing Week 3 RAG application using a frozen 28-task dataset.
**Authoritative version:** `week4_v3_controlled` (2026-09-17). Historical V1/V2 files are not included in these figures.

- Evaluation tasks: 28
- Models: 3 (`codellama:latest`, `qwen2.5-coder:7b`, `deepseek-coder:6.7b`)
- Categories: 7
- Planned experiments: 84
- Recorded experiments: 84
- Successful experiments: 84
- Failed experiments: 0
- Embedding: `nomic-embed-text:latest`; top-k=8; temperature=0.0; num_predict=300

Key measured findings (this benchmark only):

- CodeLlama: correctness=0.571, Hit@K=0.964, mean latency=28.17 s, code pass=0.500, fail=0.0000
- Qwen2.5-Coder: correctness=0.625, Hit@K=0.964, mean latency=23.32 s, code pass=0.333, fail=0.0000
- DeepSeek-Coder: correctness=0.571, Hit@K=0.964, mean latency=27.60 s, code pass=0.333, fail=0.0000

Retrieval Hit@K is identical across models because retrieval is shared.

RAG: inspector cases are real traces in `results/rag_case_studies.json`, including RG03 where models used a retrieved 1.3× wind-speed buildings fact instead of cyclone shelters (not in the retrieved chunks).

Repository: 12 multi-file items × 3 models are scored in `results/repository_evaluation.json`. Live path is App.jsx → /api/chat → process_question → retrieve_documents → build_context → generate_response. `backend/rag/` is legacy.

Limitations: rubric scoring is automatic; GPU is not measured; local hardware affects latency; 28 tasks are not a universal workload.

Reproduce: `python week4_evaluation/scripts/run_pipeline.py` then open `week4_evaluation/dashboard/index.html`.

Artifacts: `results/`, `exports/week4_evaluation.xlsx`, `reports/week4_technical_report.md`, `dashboard/index.html`.