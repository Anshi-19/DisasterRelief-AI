# Week 4 V4 Evaluation Summary

**Project:** DisasterRelief-AI
**Objective:** Empirically evaluate three local Ollama code models on the existing Week 3 RAG application using a frozen 28-task dataset.
**AUTHORITATIVE VERSION:** `week4_v4_improved` (2026-09-18). `week4_v3_controlled` is historical and was not modified.

- Evaluation tasks: 28
- Models: 3 (`codellama:latest`, `qwen2.5-coder:7b`, `deepseek-coder:6.7b`)
- Categories: 7
- Planned experiments: 84
- Recorded experiments: 84
- Successful experiments: 84
- Failed experiments: 0
- Embedding: `nomic-embed-text:latest`; top-k=8; temperature=0.0; num_predict=640

Key measured findings (this benchmark only):

- CodeLlama: correctness=0.500, Hit@K=0.964, mean latency=26.70 s, code pass=0.000, fail=0.0000
- Qwen2.5-Coder: correctness=0.839, Hit@K=0.964, mean latency=20.66 s, code pass=0.750, fail=0.0000
- DeepSeek-Coder: correctness=0.500, Hit@K=0.964, mean latency=24.32 s, code pass=0.250, fail=0.0000

Retrieval Hit@K is identical across models because retrieval is shared.

RAG: inspector cases are real traces in `results/v4_improved/rag_case_studies.json`.

Repository: 12 multi-file items × 3 models are scored in `results/v4_improved/repository_evaluation.json`. Live path is App.jsx → /api/chat → process_question → retrieve_documents → build_context → generate_response. `backend/rag/` is legacy.

Limitations: rubric scoring is automatic; GPU is not measured; local hardware affects latency; 28 tasks are not a universal workload.

Reproduce: `python week4_evaluation/scripts/run_pipeline.py` then open `week4_evaluation/dashboard/index.html`.

Artifacts: `results/raw/week4_v4_improved.json`, `exports/week4_evaluation.xlsx`, `reports/week4_v4_report.md`, `reports/week4_v4_summary.md`, `dashboard/index.html`.