# Week 4 Evaluation Dataset

28 frozen tasks for DisasterRelief-AI. The same rows are used for every model.

| IDs | Category | Count |
| --- | --- | --- |
| E01–E04 | Explanation | 4 |
| CR01–CR04 | Code Retrieval | 4 |
| D01–D04 | Dependency Understanding | 4 |
| B01–B04 | Bug Analysis | 4 |
| CG01–CG04 | Code Generation | 4 |
| RF01–RF04 | Refactoring | 4 |
| RG01–RG04 | RAG-based Questions | 4 |

Each row includes:

`id, category, question, ground_truth, relevant_files, rag_required, code_execution_required, correctness_criteria, relevance_criteria, hallucination_criteria, retrieval_criteria`

Regenerate with:

```bash
python week4_evaluation/scripts/create_dataset.py
```

Do not edit questions after a benchmark run if you need to compare against stored results. Create a new evaluation version instead.
