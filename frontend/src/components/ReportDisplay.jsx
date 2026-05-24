export default function ReportDisplay({ report, auditing }) {
  if (auditing) {
    return (
      <div className="report empty">
        <div className="spinner" />
        <p>Running compliance audit…</p>
        <p className="muted small">
          The agent is reading the contract, searching policies via RAG, and
          drafting findings. This usually takes 30–60 seconds.
        </p>
      </div>
    );
  }

  if (!report) {
    return (
      <div className="report empty">
        <div className="empty-illustration">📋</div>
        <p style={{ color: "var(--text-2)", fontWeight: 500 }}>
          No audit run yet
        </p>
        <p className="muted small">
          Choose a contract from the file explorer and click{" "}
          <strong>Run Compliance Audit</strong> to start.
        </p>
      </div>
    );
  }

  if (report.error) {
    return (
      <div className="report empty">
        <div className="empty-illustration">⚠️</div>
        <p style={{ color: "var(--danger)", fontWeight: 500 }}>
          Could not parse the audit report
        </p>
        <p className="muted small">{report.error}</p>
        <details style={{ marginTop: 12, maxWidth: 600 }}>
          <summary style={{ cursor: "pointer", color: "var(--accent-2)" }}>
            Show raw response
          </summary>
          <pre className="raw">{report.raw}</pre>
        </details>
      </div>
    );
  }

  const findings = report.findings ?? [];
  const grouped = { high: [], medium: [], low: [] };
  for (const f of findings) {
    (grouped[f.severity] ?? grouped.low).push(f);
  }

  return (
    <div className="report">
      <div className="report-head">
        <div>
          <h2>{report.contract}</h2>
          <p className="summary">{report.summary}</p>
        </div>
        <span className={`badge ${report.compliant ? "ok" : "bad"}`}>
          {report.compliant ? "COMPLIANT" : "NOT COMPLIANT"}
        </span>
      </div>

      {findings.length > 0 && (
        <div className="stats-row">
          <div className="stat">
            <div className="stat-value">{findings.length}</div>
            <div className="stat-label">Total Findings</div>
          </div>
          <div className="stat high">
            <div className="stat-value">{grouped.high.length}</div>
            <div className="stat-label">High Severity</div>
          </div>
          <div className="stat medium">
            <div className="stat-value">{grouped.medium.length}</div>
            <div className="stat-label">Medium Severity</div>
          </div>
          <div className="stat low">
            <div className="stat-value">{grouped.low.length}</div>
            <div className="stat-label">Low Severity</div>
          </div>
        </div>
      )}

      {findings.length === 0 ? (
        <p className="muted">No findings — contract appears to comply.</p>
      ) : (
        <>
          {["high", "medium", "low"].map((sev) =>
            grouped[sev].length ? (
              <section key={sev} className={`findings-group ${sev}`}>
                <h3>
                  {sev} severity{" "}
                  <span className="count-pill">{grouped[sev].length}</span>
                </h3>
                {grouped[sev].map((f, i) => (
                  <Finding key={i} f={f} />
                ))}
              </section>
            ) : null
          )}
        </>
      )}
    </div>
  );
}

function Finding({ f }) {
  const isUnverified = f.verified === false;
  return (
    <article className={`finding ${isUnverified ? "unverified" : ""}`}>
      {isUnverified && (
        <div className="verification-badge" title={f.verification_warnings?.join(" · ")}>
          ⚠ Unverified — {f.verification_warnings?.[0] ?? "needs review"}
        </div>
      )}
      <div className="finding-grid">
        <div>
          <h4>Contract clause</h4>
          <p>{f.contract_clause}</p>
        </div>
        <div>
          <h4>Policy reference</h4>
          <p>{f.policy_reference}</p>
        </div>
      </div>
      <div className="finding-issue">
        <h4>Issue</h4>
        <p>{f.issue}</p>
      </div>
      <div className="finding-fix">
        <h4>Suggested fix</h4>
        <p>{f.suggested_fix}</p>
      </div>
    </article>
  );
}
