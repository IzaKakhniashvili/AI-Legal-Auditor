import { useRef } from "react";
import { api } from "../api";

export default function FileExplorer({
  policies,
  contracts,
  selected,
  onSelect,
  onUploaded,
  onReindex,
}) {
  const policyInputRef = useRef(null);
  const contractInputRef = useRef(null);

  const handleUpload = async (file, type) => {
    if (!file) return;
    try {
      if (type === "policy") await api.uploadPolicy(file);
      else await api.uploadContract(file);
      onUploaded?.();
    } catch (err) {
      alert("Upload failed: " + err.message);
    }
  };

  return (
    <div className="file-explorer">
      <Section
        title="Policies"
        count={policies.length}
        action={
          <>
            <button
              className="ghost small"
              onClick={() => policyInputRef.current?.click()}
            >
              + Upload
            </button>
            <input
              ref={policyInputRef}
              type="file"
              accept="application/pdf"
              hidden
              onChange={(e) => handleUpload(e.target.files?.[0], "policy")}
            />
          </>
        }
      >
        {policies.map((f) => (
          <FileRow
            key={f.name}
            file={f}
            type="policy"
            selected={
              selected?.type === "policy" &&
              selected.name === f.name.replace(/\.pdf$/i, ".txt")
            }
            onSelect={onSelect}
          />
        ))}
      </Section>

      <Section
        title="Contracts"
        count={contracts.length}
        action={
          <>
            <button
              className="ghost small"
              onClick={() => contractInputRef.current?.click()}
            >
              + Upload
            </button>
            <input
              ref={contractInputRef}
              type="file"
              accept="application/pdf"
              hidden
              onChange={(e) => handleUpload(e.target.files?.[0], "contract")}
            />
          </>
        }
      >
        {contracts.map((f) => (
          <FileRow
            key={f.name}
            file={f}
            type="contract"
            selected={
              selected?.type === "contract" &&
              selected.name === f.name.replace(/\.pdf$/i, ".txt")
            }
            onSelect={onSelect}
          />
        ))}
      </Section>

      <button className="ghost reindex" onClick={onReindex}>
        Re-index policies (RAG)
      </button>
    </div>
  );
}

function Section({ title, count, action, children }) {
  return (
    <div className="explorer-section">
      <div className="section-head">
        <h3>
          {title} <span className="count">{count}</span>
        </h3>
        {action}
      </div>
      <ul>{children.length ? children : <li className="muted small">No files yet</li>}</ul>
    </div>
  );
}

function FileRow({ file, type, selected, onSelect }) {
  // We list .pdf names; the agent works with the .txt sibling.
  const txtName = file.name.replace(/\.pdf$/i, ".txt");
  return (
    <li
      className={`file-row ${selected ? "selected" : ""}`}
      onClick={() => onSelect({ type, name: txtName })}
      title={file.name}
    >
      <DocIcon />
      <span className="file-name">{file.name}</span>
    </li>
  );
}

function DocIcon() {
  return (
    <svg
      className="file-icon"
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <path d="M14 2v6h6" />
      <path d="M8 13h6" />
      <path d="M8 17h8" />
      <path d="M8 9h2" />
    </svg>
  );
}
