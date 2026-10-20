import v4Summary from "../../week4_evaluation/results/v4_improved/benchmark_summary.json";

export const ALLOWED_MODELS = [
  "codellama:latest",
  "qwen2.5-coder:7b",
  "deepseek-coder:6.7b",
];

export const DEFAULT_MODEL = "codellama:latest";

export const MODEL_OPTIONS = [
  { id: "codellama:latest", label: "CodeLlama" },
  { id: "qwen2.5-coder:7b", label: "Qwen2.5-Coder" },
  { id: "deepseek-coder:6.7b", label: "DeepSeek-Coder" },
];

function mapModel(id, label) {
  const stats = v4Summary.model_stats[id];
  return {
    label,
    correctness: stats.correctness,
    relevance: stats.relevance,
    hitAtK: stats.hit_at_k,
    mrr: stats.mrr,
    hallucination: stats.hallucination,
    codeTestPassRate: stats.test_pass_rate,
    taskLogicCorrectness: stats.task_logic_correctness,
    meanLatency: stats.mean_latency,
    medianLatency: stats.median_latency,
    p95Latency: stats.p95_latency,
    throughput: stats.throughput,
    memoryMb: stats.memory_mb,
    cpuPercent: stats.cpu_percent,
  };
}

/** Week 4 V4 metrics from week4_v4_improved.json (via results/v4_improved/benchmark_summary.json). */
export const WEEK4_BENCHMARK = {
  title: "WEEK 4 CONTROLLED BENCHMARK",
  subtitle: `${v4Summary.questions} tasks × ${v4Summary.models.length} models = ${v4Summary.recorded_experiments} evaluations`,
  version: v4Summary.evaluation_version,
  source: "week4_evaluation/results/raw/week4_v4_improved.json",
  recordedExperiments: v4Summary.recorded_experiments,
  successfulExperiments: v4Summary.successful_experiments,
  disclaimer:
    "These are controlled benchmark measurements, not measurements of the current single query.",
  resourceNote: "Observed in the local Week 4 evaluation environment.",
  models: Object.fromEntries(
    MODEL_OPTIONS.map((option) => [option.id, mapModel(option.id, option.label)]),
  ),
};

export const QUALITY_KEYS = [
  ["correctness", "Correctness"],
  ["relevance", "Relevance"],
  ["hitAtK", "Retrieval Hit@K"],
  ["mrr", "MRR"],
  ["hallucination", "Hallucination"],
  ["codeTestPassRate", "Code Test-Pass Rate"],
  ["taskLogicCorrectness", "Task/Logic Correctness"],
];
