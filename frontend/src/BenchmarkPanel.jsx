import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";
import { WEEK4_BENCHMARK, QUALITY_KEYS, MODEL_OPTIONS } from "./week4Benchmark";

const MODEL_COLORS = {
  CodeLlama: "#4f6bed",
  "Qwen2.5-Coder": "#0d9488",
  "DeepSeek-Coder": "#d97706",
};

const DEFINITIONS = {
  correctness: "Rubric score: fully correct 1.0, partially correct 0.5, incorrect 0.0.",
  relevance: "How directly the answer addresses the requested task.",
  hitAtK: "Whether at least one expected relevant source appeared in the top K.",
  mrr: "Mean Reciprocal Rank measures how highly the first relevant result appears.",
  hallucination: "Rate of unsupported claims; lower is preferable for this metric.",
  codeTestPassRate: "Generated-code tests passed divided by executable generated tests.",
  taskLogicCorrectness: "Logic score separated from import and integration failures.",
};

function paddedDomain(values, floor = null) {
  const min = Math.min(...values);
  const max = Math.max(...values);
  const pad = Math.max((max - min) * 0.2, max < 2 ? 0.05 : max * 0.04);
  const lower = min - pad;
  return [floor == null ? lower : Math.max(floor, lower), max + pad];
}

function ChartTooltip({ active, payload, label, suffix = "" }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="chart-tooltip">
      {label && <strong>{label}</strong>}
      {payload.map((entry) => (
        <span key={entry.name}>
          <i style={{ background: entry.color || entry.payload?.fill }} />
          {entry.name}: <b>{Number(entry.value).toFixed(entry.value < 1 ? 3 : 2)}{suffix}</b>
        </span>
      ))}
    </div>
  );
}

function PanelHeader({ title, subtitle }) {
  return (
    <div className="chart-header">
      <div><h3>{title}</h3><p>{subtitle}</p></div>
      <span>{WEEK4_BENCHMARK.version}</span>
    </div>
  );
}

function HorizontalModelChart({ title, subtitle, dataKey, suffix = "", domain, height = 280 }) {
  const data = MODEL_OPTIONS.map((option) => ({
    model: WEEK4_BENCHMARK.models[option.id].label,
    value: WEEK4_BENCHMARK.models[option.id][dataKey],
  }));
  return (
    <article className="chart-panel">
      <PanelHeader title={title} subtitle={subtitle} />
      <div style={{ height }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ top: 12, right: 42, bottom: 8, left: 25 }}>
            <CartesianGrid stroke="#e8edf5" horizontal={false} />
            <XAxis type="number" domain={domain || [0, "dataMax"]} tick={{ fill: "#667085", fontSize: 11 }} axisLine={false} tickLine={false} />
            <YAxis dataKey="model" type="category" width={108} tick={{ fill: "#344054", fontSize: 12, fontWeight: 600 }} axisLine={false} tickLine={false} />
            <Tooltip content={<ChartTooltip suffix={suffix} />} cursor={{ fill: "#f6f8fc" }} />
            <Bar dataKey="value" name={title} radius={[0, 7, 7, 0]} barSize={20}>
              {data.map((entry) => <Cell key={entry.model} fill={MODEL_COLORS[entry.model]} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </article>
  );
}

export default function BenchmarkPanel({ selectedModel }) {
  const current = WEEK4_BENCHMARK.models[selectedModel];
  const models = MODEL_OPTIONS.map((option) => WEEK4_BENCHMARK.models[option.id]);
  const qualityData = QUALITY_KEYS.map(([key, label]) => ({
    metric: label.replace("Retrieval ", "").replace("Code Test-Pass Rate", "Code Test Pass").replace("Task/Logic Correctness", "Task / Logic"),
    CodeLlama: WEEK4_BENCHMARK.models["codellama:latest"][key],
    "Qwen2.5-Coder": WEEK4_BENCHMARK.models["qwen2.5-coder:7b"][key],
    "DeepSeek-Coder": WEEK4_BENCHMARK.models["deepseek-coder:6.7b"][key],
  }));
  const latencyData = models.map((model) => ({
    model: model.label,
    Mean: model.meanLatency,
    Median: model.medianLatency,
    P95: model.p95Latency,
  }));
  const scatterData = models.map((model) => ({
    model: model.label,
    latency: model.meanLatency,
    memory: model.memoryMb,
    correctness: model.correctness,
    fill: MODEL_COLORS[model.label],
  }));

  return (
    <section className="benchmark-panel">
      <div className="benchmark-hero">
        <div><span className="eyebrow">Week 4 controlled benchmark · {WEEK4_BENCHMARK.version}</span><h2>Measured model evaluation</h2><p>{WEEK4_BENCHMARK.subtitle}</p></div>
        <div className="benchmark-disclaimer">Benchmark measurements—not the current live query.</div>
      </div>

      <div className="quality-card-grid">
        {QUALITY_KEYS.map(([key, label]) => (
          <article className="quality-card" key={key} title={DEFINITIONS[key]}>
            <div><span>{label}</span><button type="button" aria-label={`About ${label}`}>i</button></div>
            <strong>{current[key].toFixed(3)}</strong>
            <div className="quality-meter"><span style={{ width: `${current[key] * 100}%` }} /></div>
            <small>{current.label}</small>
          </article>
        ))}
      </div>

      <div className="performance-ribbon">
        <div><small>Mean latency</small><strong>{current.meanLatency.toFixed(2)} s</strong></div>
        <div><small>Median latency</small><strong>{current.medianLatency.toFixed(2)} s</strong></div>
        <div><small>P95 latency</small><strong>{current.p95Latency.toFixed(2)} s</strong></div>
        <div><small>Throughput</small><strong>{current.throughput.toFixed(2)} tok/s</strong></div>
        <div><small>Memory</small><strong>~{current.memoryMb.toFixed(1)} MB</strong></div>
        <div><small>CPU</small><strong>~{current.cpuPercent.toFixed(1)}%</strong></div>
      </div>
      <p className="resource-note">{WEEK4_BENCHMARK.resourceNote}</p>

      <div className="benchmark-subhead"><span className="eyebrow">Model comparison</span><h2>Seven quality dimensions</h2><p>Consistent model colors are used across every visualization. No overall ranking is assigned.</p></div>
      <article className="chart-panel chart-wide quality-comparison">
        <PanelHeader title="Quality metric comparison" subtitle="Grouped horizontal bars · rubric and retrieval scores" />
        <div className="large-chart">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={qualityData} layout="vertical" margin={{ top: 18, right: 30, bottom: 8, left: 20 }} barGap={3}>
              <CartesianGrid stroke="#e8edf5" horizontal={false} />
              <XAxis type="number" domain={[0, 1]} tick={{ fill: "#667085", fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis dataKey="metric" type="category" width={112} tick={{ fill: "#344054", fontSize: 11, fontWeight: 600 }} axisLine={false} tickLine={false} />
              <Tooltip content={<ChartTooltip />} cursor={{ fill: "#f6f8fc" }} />
              <Legend iconType="circle" wrapperStyle={{ fontSize: 12, paddingTop: 10 }} />
              {models.map((model) => <Bar key={model.label} dataKey={model.label} fill={MODEL_COLORS[model.label]} radius={[0, 5, 5, 0]} barSize={10} />)}
            </BarChart>
          </ResponsiveContainer>
        </div>
      </article>

      <div className="model-bars">
        {QUALITY_KEYS.map(([key, label]) => (
          <article key={key} className="model-bar-group" title={DEFINITIONS[key]}>
            <div className="model-bar-title"><strong>{label}</strong><span>{DEFINITIONS[key]}</span></div>
            {models.map((model) => <div className="model-score-bar" key={model.label}><small>{model.label}</small><div><span style={{ width: `${model[key] * 100}%`, background: MODEL_COLORS[model.label] }} /></div><b>{model[key].toFixed(3)}</b></div>)}
          </article>
        ))}
      </div>

      <div className="charts-grid">
        <HorizontalModelChart title="Mean latency" subtitle="Average response time by model" dataKey="meanLatency" suffix=" s" height={250} />
        <article className="chart-panel">
          <PanelHeader title="Latency profile" subtitle="Mean, median, and P95 response latency" />
          <div style={{ height: 250 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={latencyData} margin={{ top: 12, right: 8, bottom: 6, left: -10 }}>
                <CartesianGrid stroke="#e8edf5" vertical={false} />
                <XAxis dataKey="model" tick={{ fill: "#667085", fontSize: 10 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: "#667085", fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip content={<ChartTooltip suffix=" s" />} cursor={{ fill: "#f6f8fc" }} />
                <Legend iconType="circle" wrapperStyle={{ fontSize: 11 }} />
                <Bar dataKey="Mean" fill="#4f6bed" radius={[5, 5, 0, 0]} />
                <Bar dataKey="Median" fill="#0d9488" radius={[5, 5, 0, 0]} />
                <Bar dataKey="P95" fill="#d97706" radius={[5, 5, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </article>
        <HorizontalModelChart title="Memory usage" subtitle="Observed process RSS in the local environment" dataKey="memoryMb" suffix=" MB" height={250} />
        <HorizontalModelChart title="Generation throughput" subtitle="Measured generated tokens per second" dataKey="throughput" suffix=" tok/s" height={250} />
      </div>

      <div className="scatter-grid">
        {[
          ["Quality vs latency", "Observed benchmark trade-off in the local evaluation environment.", "latency", "Mean latency (s)", paddedDomain(scatterData.map((point) => point.latency))],
          ["Quality vs memory", "Observed benchmark trade-off in the local evaluation environment.", "memory", "Memory (MB)", paddedDomain(scatterData.map((point) => point.memory))],
        ].map(([title, subtitle, xKey, xLabel, domain]) => (
          <article className="chart-panel" key={title}>
            <PanelHeader title={title} subtitle={subtitle} />
            <div style={{ height: 310 }}>
              <ResponsiveContainer width="100%" height="100%">
                <ScatterChart margin={{ top: 22, right: 28, bottom: 22, left: 5 }}>
                  <CartesianGrid stroke="#e8edf5" />
                  <XAxis type="number" dataKey={xKey} name={xLabel} domain={domain} tick={{ fill: "#667085", fontSize: 11 }} label={{ value: xLabel, position: "insideBottom", offset: -12, fill: "#667085", fontSize: 11 }} />
                  <YAxis type="number" dataKey="correctness" name="Correctness" domain={paddedDomain(scatterData.map((point) => point.correctness), 0)} tick={{ fill: "#667085", fontSize: 11 }} label={{ value: "Correctness", angle: -90, position: "insideLeft", fill: "#667085", fontSize: 11 }} />
                  <ZAxis range={[130, 130]} />
                  <Tooltip cursor={{ strokeDasharray: "4 4" }} content={<ChartTooltip />} />
                  {scatterData.map((point) => <Scatter key={point.model} name={point.model} data={[point]} fill={point.fill} />)}
                  <Legend iconType="circle" wrapperStyle={{ fontSize: 11 }} />
                </ScatterChart>
              </ResponsiveContainer>
            </div>
          </article>
        ))}
      </div>

      <details className="benchmark-table-details">
        <summary>View complete benchmark comparison table</summary>
        <div className="table-scroll">
          <table className="benchmark-table">
            <thead><tr><th>Metric</th>{models.map((model) => <th key={model.label}>{model.label}</th>)}</tr></thead>
            <tbody>
              {[
                ...QUALITY_KEYS.map(([key, label]) => [label, ...models.map((model) => model[key].toFixed(3))]),
                ["Mean latency", ...models.map((model) => `${model.meanLatency.toFixed(2)} s`)],
                ["Median latency", ...models.map((model) => `${model.medianLatency.toFixed(2)} s`)],
                ["P95 latency", ...models.map((model) => `${model.p95Latency.toFixed(2)} s`)],
                ["Throughput", ...models.map((model) => `${model.throughput.toFixed(2)} tok/s`)],
                ["Memory", ...models.map((model) => `~${model.memoryMb.toFixed(1)} MB`)],
                ["CPU", ...models.map((model) => `~${model.cpuPercent.toFixed(1)}%`)],
              ].map((row) => <tr key={row[0]}>{row.map((cell, index) => <td key={index}>{cell}</td>)}</tr>)}
            </tbody>
          </table>
        </div>
      </details>
    </section>
  );
}
