export default function TracePanel({ trace }) {
  if (!trace) {
    return (
      <div className="trace-panel trace-empty">
        <div className="trace-title">Retrieval trace</div>
        <p className="trace-hint">
          Ask a question &mdash; this panel shows exactly what the system retrieved and
          which path answered it, so you can audit the answer instead of trusting it
          blindly.
        </p>
      </div>
    );
  }

  return (
    <div className="trace-panel">
      <div className="trace-title">Retrieval trace</div>

      <div className="trace-row">
        <span className="trace-label">Router path</span>
        <span className={`trace-badge trace-badge-${trace.router_path}`}>
          {trace.router_path === "structured" ? "Structured query" : "Vector RAG"}
        </span>
      </div>
      <div className="trace-reason">{trace.router_reason}</div>

      {trace.sql && (
        <div className="trace-sql">
          <div className="trace-label">SQL executed</div>
          <pre>{trace.sql}</pre>
        </div>
      )}

      {trace.retrieved && trace.retrieved.length > 0 && (
        <div className="trace-chunks">
          <div className="trace-label">
            Retrieved chunks ({trace.retrieved.length})
          </div>
          {trace.retrieved.map((chunk) => (
            <div
              key={chunk.id}
              className={`trace-chunk${
                trace.cited_ids?.includes(chunk.id) ? " cited" : ""
              }`}
            >
              <div className="trace-chunk-header">
                <span className="trace-chunk-type">{chunk.record_type}</span>
                <span className="trace-chunk-date">{chunk.date}</span>
                <span className="trace-chunk-score">{chunk.score.toFixed(3)}</span>
              </div>
              <div className="trace-chunk-snippet">{chunk.snippet}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
