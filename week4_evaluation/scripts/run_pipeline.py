#!/usr/bin/env python3
"""Run the full Week 4 pipeline after Ollama is available."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
STEPS = [
    "index_repository.py",
    "test_repository_retrieval.py",
    "run_evaluation.py",
    "evaluate_retrieval.py",
    "evaluate_quality.py",
    "measure_resources.py",
    "analyze_rag.py",
    "analyze_repository.py",
    "generate_report.py",
]


def main():
    python = sys.executable
    for script in STEPS:
        path = SCRIPTS / script
        print("\n" + "=" * 70)
        print(f"RUNNING {script}")
        print("=" * 70)
        completed = subprocess.run([python, str(path)], check=False)
        if completed.returncode != 0:
            raise SystemExit(f"{script} failed with exit code {completed.returncode}")
    print("\nPipeline complete.")


if __name__ == "__main__":
    main()
