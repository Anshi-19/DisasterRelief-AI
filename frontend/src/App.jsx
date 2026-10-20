import { useState } from "react";
import ReactMarkdown from "react-markdown";
import "./App.css";
import BenchmarkPanel from "./BenchmarkPanel";
import { DEFAULT_MODEL, MODEL_OPTIONS, WEEK4_BENCHMARK } from "./week4Benchmark";

const API_URL = "http://127.0.0.1:8000/api/chat";
const COMPARE_API_URL = "http://127.0.0.1:8000/api/chat/compare";
const EXAMPLES = [
  ["Flood damage", "My house was damaged by a flood. What assistance may be relevant?"],
  ["Cyclone damage", "A cyclone damaged the roof of my house. What assistance should I look into?"],
  ["Earthquake damage", "My house suffered major damage after an earthquake. What should I do?"],
];

function Icon({ name, size = 18 }) {
  const paths = {
    shield: <path d="M12 3 5 6v5c0 4.6 2.9 8.7 7 10 4.1-1.3 7-5.4 7-10V6l-7-3Z" />,
    search: <><circle cx="11" cy="11" r="7" /><path d="m20 20-4-4" /></>,
    database: <><ellipse cx="12" cy="5" rx="8" ry="3" /><path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6" /></>,
    spark: <path d="m12 3 1.5 5.5L19 10l-5.5 1.5L12 17l-1.5-5.5L5 10l5.5-1.5L12 3Z" />,
    brain: <><path d="M9.5 4.5A3.5 3.5 0 0 0 6 8v.3A3.5 3.5 0 0 0 5 15a3 3 0 0 0 4.5 3.6M14.5 4.5A3.5 3.5 0 0 1 18 8v.3A3.5 3.5 0 0 1 19 15a3 3 0 0 1-4.5 3.6M12 4v16M9 9h3M12 15h3" /></>,
    file: <><path d="M6 3h8l4 4v14H6z" /><path d="M14 3v5h5M9 13h6M9 17h4" /></>,
    clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
    token: <><path d="M12 3 3 8l9 5 9-5-9-5Z" /><path d="m3 12 9 5 9-5M3 16l9 5 9-5" /></>,
    check: <path d="m5 12 4 4L19 6" />,
    arrow: <path d="m9 18 6-6-6-6" />,
    info: <><circle cx="12" cy="12" r="9" /><path d="M12 11v5M12 8h.01" /></>,
    chart: <><path d="M4 20V10M10 20V4M16 20v-7M22 20H2" /></>,
  };
  return (
    <svg className="icon" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {paths[name] || paths.spark}
    </svg>
  );
}

function modelLabel(id) {
  return MODEL_OPTIONS.find((model) => model.id === id)?.label || id;
}

function formatValue(value, digits = 2, suffix = "") {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "N/A";
  return `${Number(value).toFixed(digits)}${suffix}`;
}

function formatPages(pages) {
  if (!Array.isArray(pages) || !pages.length) return "Page N/A";
  return `${pages.length > 1 ? "Pages" : "Page"} ${pages.join("–")}`;
}

function getDisasterIcon(disaster) {
  return { flood: "🌊", cyclone: "🌀", earthquake: "◉", all: "◆" }[(disaster || "").toLowerCase()] || "◇";
}

function normalizeResult(data, requestedModel) {
  return {
    response: data.response || "",
    sources: data.sources || [],
    model: data.model || requestedModel,
    context: data.retrieved_context || "",
    metrics: {
      response_latency: data.response_latency,
      retrieval_latency: data.retrieval_latency,
      prompt_tokens: data.prompt_tokens,
      generated_tokens: data.generated_tokens,
      total_tokens: data.total_tokens,
      throughput: data.throughput,
      retrieved_chunk_count: data.retrieved_chunk_count ?? (data.sources || []).length,
    },
  };
}

function normalizeComparisonResult(item, shared) {
  return {
    response: item.response || "",
    sources: shared.sources || [],
    model: item.model,
    context: shared.retrieved_context || "",
    contextHash: shared.context_hash,
    success: item.success,
    error: item.error,
    metrics: {
      response_latency: item.response_latency,
      retrieval_latency: shared.retrieval_latency,
      prompt_tokens: item.prompt_tokens,
      generated_tokens: item.generated_tokens,
      total_tokens: item.total_tokens,
      throughput: item.throughput,
      retrieved_chunk_count:
        shared.retrieved_chunk_count ?? (shared.sources || []).length,
    },
  };
}

function MarkdownResponse({ children }) {
  return (
    <div className="markdown-response">
      <ReactMarkdown>{children || ""}</ReactMarkdown>
    </div>
  );
}

function ModelSelector({ selectedModel, onSelect }) {
  return (
    <section className="model-section">
      <div className="section-heading compact">
        <div><span className="eyebrow">Generation model</span><h2>Choose a local LLM</h2></div>
        <p>The knowledge base and retrieval pipeline stay unchanged.</p>
      </div>
      <div className="model-grid" role="radiogroup" aria-label="Generation model">
        {MODEL_OPTIONS.map((model, index) => {
          const selected = selectedModel === model.id;
          const score = WEEK4_BENCHMARK.models[model.id].correctness;
          return (
            <button type="button" role="radio" aria-checked={selected} key={model.id} className={`model-card model-${index} ${selected ? "selected" : ""}`} onClick={() => onSelect(model.id)}>
              <span className="model-card-top"><span className="model-monogram">{model.label.slice(0, 2).toUpperCase()}</span>{selected && <span className="selected-badge"><Icon name="check" size={12} /> Selected</span>}</span>
              <strong>{model.label}</strong>
              <code>{model.id}</code>
              <span className="model-score"><b>{score.toFixed(3)}</b><small>Benchmark correctness</small></span>
            </button>
          );
        })}
      </div>
    </section>
  );
}

function Pipeline({ selectedModel, loading, hasResult, chunkCount }) {
  const stages = [
    ["search", "Question", "User query"],
    ["brain", "Embedding", "nomic-embed-text"],
    ["database", "ChromaDB", "Top-K = 8"],
    ["file", "Retrieved", hasResult ? `${chunkCount} chunks` : "Knowledge sources"],
    ["spark", "Selected LLM", modelLabel(selectedModel)],
    ["check", "Response", hasResult ? "Generated" : "Evidence-grounded"],
  ];
  return (
    <section className={`pipeline-shell ${loading ? "is-running" : ""} ${hasResult ? "is-complete" : ""}`}>
      <div className="pipeline-title"><div><span className="eyebrow">Live architecture</span><h2>RAG pipeline</h2></div><span className="shared-pill"><Icon name="shield" size={14} /> Shared retrieval</span></div>
      <div className="pipeline">
        {stages.map(([icon, title, subtitle], index) => (
          <div className="pipeline-unit" key={title}>
            <div className={`pipeline-node ${loading && index <= 4 ? "active" : ""} ${hasResult && index < 6 ? "done" : ""} ${title === "Selected LLM" ? "llm-node" : ""}`}>
              <span className="pipeline-icon"><Icon name={icon} size={20} /></span>
              <span><small>{title}</small><strong>{subtitle}</strong></span>
            </div>
            {index < stages.length - 1 && <span className="pipeline-connector"><span /></span>}
          </div>
        ))}
      </div>
      {loading && <div className="pipeline-status"><span className="pulse-dot" /> Retrieving knowledge and generating with {modelLabel(selectedModel)}…</div>}
      {hasResult && !loading && <div className="pipeline-status complete"><Icon name="check" size={15} /> Response generated from retrieved evidence</div>}
    </section>
  );
}

function LiveMetrics({ metrics }) {
  const items = [
    ["clock", "Response", formatValue(metrics.response_latency, 2, " s"), "Total Ollama generation request time."],
    ["search", "Retrieval", formatValue(metrics.retrieval_latency, 2, " s"), "Time spent embedding and retrieving ChromaDB chunks."],
    ["token", "Prompt", metrics.prompt_tokens?.toLocaleString() ?? "N/A", "Tokens provided to the selected model."],
    ["spark", "Generated", metrics.generated_tokens?.toLocaleString() ?? "N/A", "Tokens generated for this response."],
    ["token", "Total", metrics.total_tokens?.toLocaleString() ?? "N/A", "Prompt plus generated tokens."],
    ["chart", "Throughput", metrics.throughput == null ? "N/A" : `${metrics.throughput.toFixed(2)} tok/s`, "Measured generated tokens per second."],
  ];
  return <div className="metric-strip">{items.map(([icon, label, value, tip]) => <div className="metric-item" key={label} title={tip}><span><Icon name={icon} size={17} /></span><div><small>{label}</small><strong>{value}</strong></div></div>)}</div>;
}

function EvidenceExplorer({ sources, metrics, context, question, response }) {
  const [expanded, setExpanded] = useState(null);
  const [traceOpen, setTraceOpen] = useState(false);
  const distances = sources.map((source) => source.distance).filter((value) => typeof value === "number");
  const minDistance = distances.length ? Math.min(...distances) : null;
  const maxDistance = distances.length ? Math.max(...distances) : null;
  const uniqueSources = [...new Set(sources.map((source) => source.document))];
  const topSource = sources[0]?.document;
  const proximityWidth = (distance) => {
    if (typeof distance !== "number" || minDistance === maxDistance) return 100;
    return 40 + ((maxDistance - distance) / (maxDistance - minDistance)) * 60;
  };

  return (
    <section className="evidence-section">
      <div className="section-heading">
        <div><span className="eyebrow">Live retrieval trace</span><h2>RAG Evidence Explorer</h2><p>See exactly which knowledge-base chunks were retrieved before generation.</p></div>
        <span className="live-data-badge"><span /> Live query data</span>
      </div>
      <div className="evidence-layout">
        <div className="ranked-sources">
          <div className="evidence-help"><Icon name="info" size={15} /> Chroma distance: lower means a closer embedding-space match. Bar length shows relative proximity within this retrieval only—not a relevance score.</div>
          {sources.map((source, index) => (
            <article className={`ranked-source ${expanded === index ? "expanded" : ""}`} key={`${source.document}-${index}`} onClick={() => setExpanded(expanded === index ? null : index)}>
              <span className="rank">{String(index + 1).padStart(2, "0")}</span>
              <div className="source-main">
                <div className="source-title-row"><div><strong>{source.document}</strong><span>{getDisasterIcon(source.disaster)} {source.disaster || "General"} · {formatPages(source.pages)}</span></div><button type="button" aria-label="Expand source"><Icon name="arrow" size={16} /></button></div>
                <div className="distance-row"><div className="distance-track"><span style={{ width: `${proximityWidth(source.distance)}%` }} /></div><b>{typeof source.distance === "number" ? source.distance.toFixed(1) : "N/A"}</b><small>1 chunk</small></div>
                {expanded === index && <div className="source-detail"><dl><div><dt>Authority</dt><dd>{source.authority || "N/A"}</dd></div><div><dt>Page</dt><dd>{formatPages(source.pages)}</dd></div><div><dt>Chroma distance</dt><dd>{formatValue(source.distance, 3)}</dd></div></dl><pre>{source.text || "No chunk text returned."}</pre></div>}
              </div>
            </article>
          ))}
        </div>
        <aside className="retrieval-quality">
          <span className="eyebrow">Retrieval quality</span>
          <h3>Current query</h3>
          <div className="quality-stat"><span>Retrieved chunks</span><strong>{metrics.retrieved_chunk_count ?? sources.length}</strong></div>
          <div className="quality-stat"><span>Unique documents</span><strong>{uniqueSources.length}</strong></div>
          <div className="quality-stat text"><span>Top source</span><strong>{topSource || "N/A"}</strong></div>
          <div className="quality-stat"><span>Best Chroma distance</span><strong>{formatValue(minDistance, 1)}</strong></div>
          <div className="quality-stat"><span>Retrieval latency</span><strong>{formatValue(metrics.retrieval_latency, 2, " s")}</strong></div>
        </aside>
      </div>
      <div className="trace-panel">
        <button type="button" className="trace-toggle" onClick={() => setTraceOpen(!traceOpen)}><span><Icon name="file" size={18} /><b>Trace this answer</b><small>Question → retrieved evidence → generated response</small></span><Icon name="arrow" size={18} /></button>
        {traceOpen && <div className="trace-content"><div className="trace-step"><span>01</span><div><small>Question</small><p>{question}</p></div></div>{sources.map((source, index) => <div className="trace-step" key={index}><span>{String(index + 2).padStart(2, "0")}</span><div><small>Retrieved source #{index + 1} · {formatPages(source.pages)}</small><strong>{source.document}</strong><blockquote>{source.text || "No excerpt returned."}</blockquote></div></div>)}<div className="trace-step response"><span>{String(sources.length + 2).padStart(2, "0")}</span><div><small>LLM response</small><p>{response}</p></div></div><details className="raw-context"><summary>View full retrieved context</summary><pre>{context || "N/A"}</pre></details></div>}
      </div>
    </section>
  );
}

function SourceMatrix({ comparisons, currentResult }) {
  const rows = [];
  const resultMap = { ...comparisons };
  if (currentResult?.model) resultMap[currentResult.model] = currentResult;
  Object.values(resultMap).forEach((result) => result.sources?.forEach((source) => {
    const key = `${source.document}|${formatPages(source.pages)}`;
    if (!rows.some((row) => row.key === key)) rows.push({ key, document: source.document, pages: formatPages(source.pages) });
  }));
  const complete = MODEL_OPTIONS.every((model) => resultMap[model.id]);
  const signatures = MODEL_OPTIONS.map((model) => resultMap[model.id]?.sources?.map((source) => `${source.document}|${formatPages(source.pages)}|${source.distance}`).join("::"));
  const shared = complete && new Set(signatures).size === 1;
  if (!rows.length) return null;
  return (
    <div className="source-matrix-shell">
      <div className="matrix-heading"><div><span className="eyebrow">Model × source comparison</span><h3>Same retrieval pipeline, different generation model</h3></div>{shared && <span className="shared-pill"><Icon name="check" size={14} /> Shared retrieval context</span>}</div>
      <div className="table-scroll"><table className="source-matrix"><thead><tr><th>Retrieved source</th>{MODEL_OPTIONS.map((model) => <th key={model.id}>{model.label}</th>)}</tr></thead><tbody>{rows.map((row) => <tr key={row.key}><td><strong>{row.document}</strong><small>{row.pages}</small></td>{MODEL_OPTIONS.map((model) => <td key={model.id}>{resultMap[model.id]?.sources?.some((source) => `${source.document}|${formatPages(source.pages)}` === row.key) ? <span className="matrix-check"><Icon name="check" size={15} /></span> : <span className="matrix-empty">—</span>}</td>)}</tr>)}</tbody></table></div>
      <p>{complete ? (shared ? "All three live responses received the same retrieved chunks." : "Sources shown are the actual chunks returned for each live request.") : "Run all three models to verify the shared live retrieval context across model requests."}</p>
    </div>
  );
}

function CompareModels({ message, comparisons, progress, onRun }) {
  const running = progress !== null;
  return (
    <section className="compare-section">
      <div className="section-heading"><div><span className="eyebrow">Live comparison · current query — measured live</span><h2>Compare the three local LLMs</h2><p>Same question · same knowledge base · same embedding model · one shared retrieval · different generation model</p></div><button type="button" className="secondary-action" disabled={!message.trim() || running} onClick={onRun}>{running ? <><span className="dark-spinner" /> Running 3 local models…</> : <><Icon name="spark" size={17} /> Run same query on all 3 models</>}</button></div>
      <div className="comparison-grid">{MODEL_OPTIONS.map((model) => {
        const result = comparisons[model.id];
        return <article className={`comparison-card ${result ? "has-result" : ""}`} key={model.id}><div className="comparison-card-head"><span className="model-monogram">{model.label.slice(0, 2).toUpperCase()}</span><div><strong>{model.label}</strong><code>{model.id}</code></div>{result && <span className={result.success ? "status-success" : "status-error"}>{result.success && <Icon name="check" size={12} />} {result.success ? "Complete" : "Failed"}</span>}</div>{result ? <><div className="comparison-answer"><MarkdownResponse>{result.response || "Unable to generate a response."}</MarkdownResponse></div><div className="comparison-meta"><span><b>{formatValue(result.metrics.response_latency, 2, " s")}</b> latency</span><span><b>{result.metrics.generated_tokens ?? "N/A"}</b> tokens</span><span><b>{formatValue(result.metrics.throughput, 2)}</b> tok/s</span><span><b>{result.metrics.retrieved_chunk_count ?? result.sources.length}</b> chunks</span></div></> : <div className="comparison-empty"><Icon name="spark" size={22} /><p>No live response yet.</p></div>}</article>;
      })}</div>
      {Object.keys(comparisons).length > 0 && <div className="live-summary table-scroll"><table><thead><tr><th>Model</th><th>Response time</th><th>Generated tokens</th><th>Throughput</th><th>Retrieved chunks</th><th>Status</th></tr></thead><tbody>{MODEL_OPTIONS.map((model) => { const result = comparisons[model.id]; return <tr key={model.id}><td>{model.label}</td><td>{result ? formatValue(result.metrics.response_latency, 2, " s") : "Pending"}</td><td>{result?.metrics.generated_tokens ?? "N/A"}</td><td>{result ? formatValue(result.metrics.throughput, 2, " tok/s") : "N/A"}</td><td>{result?.metrics.retrieved_chunk_count ?? "N/A"}</td><td>{result ? "Response received" : "Not run"}</td></tr>; })}</tbody></table></div>}
    </section>
  );
}

function App() {
  const [message, setMessage] = useState("");
  const [selectedModel, setSelectedModel] = useState(DEFAULT_MODEL);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [comparisons, setComparisons] = useState({});
  const [compareProgress, setCompareProgress] = useState(null);

  const selectedLabel = modelLabel(selectedModel);
  const detectedDisaster = result?.sources?.[0]?.disaster;

  const requestChat = async (model) => {
    const response = await fetch(API_URL, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message: message.trim(), model }) });
    if (!response.ok) throw new Error("Unable to connect to the DisasterRelief AI server.");
    return normalizeResult(await response.json(), model);
  };

  const analyzeSituation = async () => {
    if (!message.trim()) return;
    setLoading(true);
    setError("");
    setResult(null);
    try {
      setResult(await requestChat(selectedModel));
    } catch {
      setError("Unable to connect to the DisasterRelief AI server. Please make sure the backend is running.");
    } finally {
      setLoading(false);
    }
  };

  const runAllModels = async () => {
    if (!message.trim() || compareProgress !== null) return;
    setComparisons({});
    setError("");
    setCompareProgress(0);
    try {
      const response = await fetch(COMPARE_API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: message.trim() }),
      });
      if (!response.ok) {
        throw new Error("Unable to run the shared-retrieval comparison.");
      }
      const data = await response.json();
      const normalizedResults = Object.fromEntries(
        data.results.map((item) => [
          item.model,
          normalizeComparisonResult(item, data),
        ])
      );
      setComparisons(normalizedResults);
      setResult(normalizedResults[selectedModel] || null);
    } catch {
      setError(
        "Unable to run the live three-model comparison. Please make sure the backend is running."
      );
    } finally {
      setCompareProgress(null);
    }
  };

  const handleKeyDown = (event) => {
    if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) analyzeSituation();
  };

  return (
    <div className="app">
      <header className="header"><div className="header-inner"><div className="brand"><div className="brand-icon"><Icon name="shield" size={21} /></div><div><h1>DisasterRelief AI</h1><p>Evidence-Grounded Disaster Assistance</p></div></div><div className="header-status"><span className="status-dot" /><span><b>Knowledge-Grounded</b><small>Backend connected</small></span></div></div></header>

      <main className="main">
        <section className="hero"><div className="hero-copy"><span className="hero-badge"><Icon name="spark" size={14} /> Local multi-model RAG</span><h1>Evidence-grounded<br /><em>disaster assistance</em></h1><p>Ask a disaster-related question and compare how three local LLMs generate responses from the same retrieved knowledge.</p><div className="hero-facts"><span><Icon name="shield" size={15} /> Local models</span><span><Icon name="database" size={15} /> ChromaDB retrieval</span><span><Icon name="file" size={15} /> Source-grounded</span></div></div><div className="hero-visual"><div className="orb"><Icon name="brain" size={42} /></div><div className="orbit orbit-one" /><div className="orbit orbit-two" /><span className="floating-chip chip-one">3 local LLMs</span><span className="floating-chip chip-two">Top-K 8</span><span className="floating-chip chip-three">Live metrics</span></div></section>

        <ModelSelector selectedModel={selectedModel} onSelect={setSelectedModel} />

        <section className="ask-section"><div className="ask-header"><div><span className="eyebrow">Ask the knowledge base</span><h2>Describe your situation</h2></div><span className="shortcut">⌘ + Enter</span></div><textarea value={message} onChange={(event) => { setMessage(event.target.value); setComparisons({}); }} onKeyDown={handleKeyDown} placeholder="Example: My house was damaged by a flood. What assistance may be relevant?" rows="5" /><div className="ask-actions"><div className="example-list">{EXAMPLES.map(([label, query]) => <button type="button" key={label} onClick={() => { setMessage(query); setComparisons({}); }}>{label}</button>)}</div><button type="button" className="primary-action" onClick={analyzeSituation} disabled={loading || !message.trim()}>{loading ? <><span className="spinner" /> Generating with {selectedLabel}…</> : <>Analyze with {selectedLabel} <Icon name="arrow" size={17} /></>}</button></div>{error && <div className="error-banner">{error}</div>}</section>

        <Pipeline selectedModel={selectedModel} loading={loading} hasResult={Boolean(result)} chunkCount={result?.metrics?.retrieved_chunk_count ?? 0} />

        {result && <section className="response-section"><div className="response-heading"><div><span className="eyebrow">AI response</span><h2>Evidence-grounded analysis</h2></div>{detectedDisaster && <span className="disaster-badge">{getDisasterIcon(detectedDisaster)} {detectedDisaster}</span>}</div><article className="response-card"><div className="response-model"><span className="model-monogram">{modelLabel(result.model).slice(0, 2).toUpperCase()}</span><div><small>Selected model</small><strong>{modelLabel(result.model)}</strong><code>{result.model}</code></div><span className="grounded-badge"><Icon name="shield" size={13} /> Grounded</span></div><div className="answer-content"><MarkdownResponse>{result.response}</MarkdownResponse></div><div className="answer-meta"><span><Icon name="clock" size={14} /> {formatValue(result.metrics.response_latency, 2, " s")}</span><span><Icon name="token" size={14} /> {result.metrics.generated_tokens ?? "N/A"} generated tokens</span><span><Icon name="chart" size={14} /> {formatValue(result.metrics.throughput, 2, " tok/s")}</span></div></article><LiveMetrics metrics={result.metrics} /></section>}

        {result?.sources?.length > 0 && <><EvidenceExplorer sources={result.sources} metrics={result.metrics} context={result.context} question={message.trim()} response={result.response} /><SourceMatrix comparisons={comparisons} currentResult={result} /></>}

        <CompareModels message={message} comparisons={comparisons} progress={compareProgress} onRun={runAllModels} />
        <BenchmarkPanel selectedModel={selectedModel} />

        <section className="methodology"><div><span className="eyebrow">Methodology</span><h2>Controlled and transparent</h2><p>Live values come directly from the current FastAPI/Ollama request. Benchmark values are the Week 4 {WEEK4_BENCHMARK.version} measurements ({WEEK4_BENCHMARK.successfulExperiments}/{WEEK4_BENCHMARK.recordedExperiments} successful), not estimates for the current query.</p></div><div className="method-grid"><span><Icon name="brain" /> Same embedding model</span><span><Icon name="database" /> Same ChromaDB pipeline</span><span><Icon name="shield" /> No fabricated source scores</span><span><Icon name="chart" /> Measured runtime metrics</span></div></section>
      </main>

      <footer><div><strong>DisasterRelief AI</strong><span>Local LLMs · Evidence-grounded RAG · Week 4 evaluation</span></div><span>Final-year project demonstration</span></footer>
    </div>
  );
}

export default App;