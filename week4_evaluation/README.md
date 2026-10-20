# Week 4 Multi-Model Evaluation

Controlled evaluation of local Ollama models on the existing DisasterRelief-AI Week 3 RAG application.

**Authoritative version:** `week4_v3_controlled`  
Do not mix V1/V2 numbers from `results/archive_pre_v3/` into reports.

The live application LLM remains `codellama:latest`. Benchmarking calls Ollama separately.

## Prerequisites

```bash
ollama list
source backend/venv/bin/activate
```

Required models:

- `codellama:latest`
- `qwen2.5-coder:7b`
- `deepseek-coder:6.7b`
- `nomic-embed-text:latest`

Week 3 disaster collection: `vector_store/chroma_db` / `disaster_relief` (do not destroy).

## Reproduce

From the repository root:

```bash
source backend/venv/bin/activate

# 1. Models
ollama list

# 2. Dataset (only if regenerating; freeze before comparing to stored results)
python week4_evaluation/scripts/create_dataset.py

# 3. Repository index
python week4_evaluation/scripts/index_repository.py

# 4. Retrieval smoke test
python week4_evaluation/scripts/test_repository_retrieval.py

# 5. Evaluation (resumes incomplete week4_v3_controlled records)
python week4_evaluation/scripts/run_evaluation.py

# 6. Retrieval metrics
python week4_evaluation/scripts/evaluate_retrieval.py

# 7. Quality + code-generation execution
python week4_evaluation/scripts/evaluate_quality.py

# 8. Resource aggregation
python week4_evaluation/scripts/measure_resources.py

# 9. RAG case studies
python week4_evaluation/scripts/analyze_rag.py

# 10. Repository evaluation
python week4_evaluation/scripts/analyze_repository.py

# 11. Excel, reports, dashboard_data.json
python week4_evaluation/scripts/generate_report.py
```

Or:

```bash
python week4_evaluation/scripts/run_pipeline.py
```

## Open the dashboard

```bash
open week4_evaluation/dashboard/index.html
```

Or:

```bash
cd week4_evaluation && python3 -m http.server 8765
# then open http://127.0.0.1:8765/dashboard/
```

Dashboard data: `dashboard/dashboard_data.json` (also mirrored as `benchmark_data.js` for `file://`).

## Outputs

| Artifact | Path |
| --- | --- |
| Dataset | `dataset/evaluation_dataset.csv` |
| Raw experiments | `results/model_evaluation_results.json` |
| Canonical copy | `results/raw/week4_v3_controlled.json` |
| Quality | `results/quality_scores.json` |
| Retrieval | `results/retrieval_metrics.json` |
| Resources | `results/resource_metrics.json` |
| RAG cases | `results/rag_case_studies.json` |
| Repository eval | `results/repository_evaluation.json` |
| Human review | `results/human_review_template.csv` |
| Excel | `exports/week4_evaluation.xlsx` |
| Technical report | `reports/week4_technical_report.md` |
| Executive summary | `reports/week4_summary.md` |
| Dashboard | `dashboard/index.html` |
