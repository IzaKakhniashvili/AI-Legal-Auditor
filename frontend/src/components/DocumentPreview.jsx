import { useEffect, useState } from "react";
import { api } from "../api";

export default function DocumentPreview({ kind, name }) {
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!name) return;
    setLoading(true);
    setError("");
    setContent("");
    api
      .preview(kind, name)
      .then((data) => setContent(data.content))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [kind, name]);

  if (loading) {
    return (
      <div className="report empty">
        <div className="spinner" />
        <p className="muted small">Loading preview…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="report empty">
        <div className="empty-illustration">⚠️</div>
        <p style={{ color: "var(--danger)", fontWeight: 500 }}>
          Could not load preview
        </p>
        <p className="muted small">{error}</p>
      </div>
    );
  }

  const lines = content.split("\n").length;
  const chars = content.length;

  return (
    <div className="preview">
      <div className="preview-head">
        <div>
          <div className="preview-kind">{kind}</div>
          <h2>{name}</h2>
        </div>
        <div className="preview-meta">
          <span className="meta-chip">{lines.toLocaleString()} lines</span>
          <span className="meta-chip">{chars.toLocaleString()} chars</span>
          {kind === "policy" && (
            <span className="meta-chip indexed">Indexed in RAG</span>
          )}
        </div>
      </div>

      <pre className="preview-content">{content}</pre>
    </div>
  );
}
