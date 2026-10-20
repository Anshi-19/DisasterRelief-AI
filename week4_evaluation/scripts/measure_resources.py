"""Resource sampling helpers and post-run aggregation.

GPU/VRAM is not reported. On Apple Silicon there is no reliable
per-model GPU utilization measurement available to this evaluation.
"""

from __future__ import annotations

import json
import threading
import time
from collections import defaultdict
from statistics import mean

import psutil

from eval_config import RAW_RESULTS_FILE, RESOURCE_METRICS_FILE, RESULTS_DIR


PROCESS_ERRORS = (
    psutil.NoSuchProcess,
    psutil.AccessDenied,
    psutil.ZombieProcess,
    PermissionError,
    SystemError,
    OSError,
)


def find_ollama_processes():
    processes = []
    try:
        iterator = psutil.process_iter(["pid", "name"])
    except PROCESS_ERRORS:
        return processes

    for proc in iterator:
        try:
            name = (proc.info.get("name") or "").lower()
            cmdline = ""
            try:
                cmdline = " ".join(proc.cmdline() or []).lower()
            except PROCESS_ERRORS:
                cmdline = ""
            if "ollama" in name or "ollama" in cmdline:
                processes.append(proc)
        except PROCESS_ERRORS:
            continue
    return processes


def snapshot_resources():
    processes = find_ollama_processes()
    rss = 0
    cpu = 0.0
    details = []
    for proc in processes:
        try:
            with proc.oneshot():
                mem = proc.memory_info().rss
                cpu_pct = proc.cpu_percent(interval=None)
                rss += mem
                cpu += cpu_pct
                details.append(
                    {
                        "pid": proc.pid,
                        "name": proc.name(),
                        "rss_bytes": mem,
                        "cpu_percent": cpu_pct,
                    }
                )
        except PROCESS_ERRORS:
            continue

    vm = psutil.virtual_memory()
    return {
        "ollama_process_count": len(details),
        "ollama_rss_bytes": rss,
        "ollama_rss_mb": round(rss / (1024 * 1024), 2),
        "ollama_cpu_percent": round(cpu, 2),
        "system_memory_percent": vm.percent,
        "system_available_memory_mb": round(vm.available / (1024 * 1024), 2),
        "process_details": details,
    }


class ResourceSampler:
    def __init__(self, interval=0.4):
        self.interval = interval
        self.samples = []
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        # Prime cpu_percent.
        for proc in find_ollama_processes():
            try:
                proc.cpu_percent(interval=None)
            except PROCESS_ERRORS:
                pass
        self.samples = []
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        while not self._stop.is_set():
            try:
                self.samples.append(snapshot_resources())
            except PROCESS_ERRORS:
                pass
            time.sleep(self.interval)

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
        if not self.samples:
            self.samples.append(snapshot_resources())
        return summarize_samples(self.samples)


def summarize_samples(samples):
    if not samples:
        return {
            "sample_count": 0,
            "mean_ollama_rss_mb": None,
            "max_ollama_rss_mb": None,
            "mean_ollama_cpu_percent": None,
            "max_ollama_cpu_percent": None,
        }

    rss = [s["ollama_rss_mb"] for s in samples]
    cpu = [s["ollama_cpu_percent"] for s in samples]
    return {
        "sample_count": len(samples),
        "mean_ollama_rss_mb": round(mean(rss), 2),
        "max_ollama_rss_mb": round(max(rss), 2),
        "mean_ollama_cpu_percent": round(mean(cpu), 2),
        "max_ollama_cpu_percent": round(max(cpu), 2),
        "gpu_utilization": None,
        "gpu_note": (
            "GPU utilization was not included because a reliable "
            "per-model GPU utilization measurement was not available "
            "in the evaluation environment."
        ),
    }


def ns_to_seconds(value):
    if value is None:
        return None
    return round(value / 1e9, 4)


def tokens_per_second(eval_count, eval_duration_ns):
    if not eval_count or not eval_duration_ns:
        return None
    seconds = eval_duration_ns / 1e9
    if seconds <= 0:
        return None
    return round(eval_count / seconds, 3)


def percentile(values, p):
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return round(ordered[0], 3)
    rank = (len(ordered) - 1) * (p / 100)
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    weight = rank - low
    return round(ordered[low] * (1 - weight) + ordered[high] * weight, 3)


def aggregate_resources(records):
    by_model = defaultdict(list)
    for record in records:
        by_model[record.get("model")].append(record)

    output = {
        "measurement_method": (
            "During each Ollama generation, a background sampler queried "
            "local processes whose name or command line contained 'ollama' "
            "approximately every 0.4 seconds using psutil. RSS is process "
            "resident set size. CPU percent is the sum of sampled Ollama "
            "process CPU percentages and can exceed 100 on multi-core hosts. "
            "Token timings come from Ollama's generate API duration fields."
        ),
        "gpu_utilization": None,
        "gpu_note": (
            "GPU utilization was not included because a reliable "
            "per-model GPU utilization measurement was not available "
            "in the evaluation environment."
        ),
        "models": {},
    }

    for model, rows in by_model.items():
        successful = [r for r in rows if r.get("success")]
        latencies = [
            r["response_latency"]
            for r in successful
            if r.get("response_latency") is not None
        ]
        retrieval = [
            r["retrieval_latency"]
            for r in successful
            if r.get("retrieval_latency") is not None
        ]
        prompt_tokens = [
            r["prompt_tokens"]
            for r in successful
            if r.get("prompt_tokens") is not None
        ]
        gen_tokens = [
            r["generated_tokens"]
            for r in successful
            if r.get("generated_tokens") is not None
        ]
        total_tokens = [
            r["total_tokens"]
            for r in successful
            if r.get("total_tokens") is not None
        ]
        throughput = [
            r["throughput"]
            for r in successful
            if r.get("throughput") is not None
        ]
        load_dur = [
            r["model_load_duration"]
            for r in successful
            if r.get("model_load_duration") is not None
        ]
        prompt_eval_dur = [
            r["prompt_eval_duration"]
            for r in successful
            if r.get("prompt_eval_duration") is not None
        ]
        rss = [
            r.get("resource_summary", {}).get("mean_ollama_rss_mb")
            for r in successful
            if r.get("resource_summary", {}).get("mean_ollama_rss_mb") is not None
        ]
        cpu = [
            r.get("resource_summary", {}).get("mean_ollama_cpu_percent")
            for r in successful
            if r.get("resource_summary", {}).get("mean_ollama_cpu_percent") is not None
        ]

        output["models"][model] = {
            "experiments": len(rows),
            "successful": len(successful),
            "failed": len(rows) - len(successful),
            "failure_rate": round((len(rows) - len(successful)) / len(rows), 4)
            if rows
            else None,
            "average_latency": round(mean(latencies), 3) if latencies else None,
            "median_latency": percentile(latencies, 50),
            "p95_latency": percentile(latencies, 95),
            "average_retrieval_latency": round(mean(retrieval), 3)
            if retrieval
            else None,
            "average_prompt_tokens": round(mean(prompt_tokens), 1)
            if prompt_tokens
            else None,
            "average_generated_tokens": round(mean(gen_tokens), 1)
            if gen_tokens
            else None,
            "average_total_tokens": round(mean(total_tokens), 1)
            if total_tokens
            else None,
            "average_throughput": round(mean(throughput), 3) if throughput else None,
            "average_model_load_duration": round(mean(load_dur), 4)
            if load_dur
            else None,
            "average_prompt_eval_duration": round(mean(prompt_eval_dur), 4)
            if prompt_eval_dur
            else None,
            "average_memory_mb": round(mean(rss), 2) if rss else None,
            "average_cpu_percent": round(mean(cpu), 2) if cpu else None,
        }

    return output


def main():
    RESOURCE_METRICS_FILE.parent.mkdir(parents=True, exist_ok=True)
    records = json.loads(RAW_RESULTS_FILE.read_text(encoding="utf-8"))
    metrics = aggregate_resources(records)
    RESOURCE_METRICS_FILE.write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Wrote {RESOURCE_METRICS_FILE}")
    for model, values in metrics["models"].items():
        print(f"\n{model}")
        for key, value in values.items():
            print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
