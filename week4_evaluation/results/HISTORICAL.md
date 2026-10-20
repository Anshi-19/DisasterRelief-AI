# Historical evaluation versions (not authoritative)

The **authoritative Week 4 submission** is:

`week4_v3_controlled`

Canonical raw file:

- `results/model_evaluation_results.json`
- copy: `results/raw/week4_v3_controlled.json`

Do **not** mix these historical files into the dashboard, Excel, or technical report:

| Location | What it is |
| --- | --- |
| `results/archive_pre_v3/` | Earlier V1/V2 runs. Some repository questions used the disaster knowledge base instead of `disaster_relief_code`. |
| `results/scored_results.csv` | Keyword-overlap scores from an earlier scorer. |
| `results/manual_evaluation_sheet.csv` | Earlier worksheet. |
| `results/retrieval_quality_results.csv` | Earlier retrieval export. |
| `scripts/score_results.py`, `score_results_v2.py`, `run_evaluation_v2.py` | Historical scripts kept for provenance. |

Final numbers come only from `week4_v3_controlled`.
