import { useEffect, useState } from "react";
import { useAuth } from "../AuthContext";
import { api } from "../api";
import FileExplorer from "../components/FileExplorer";
import ReportDisplay from "../components/ReportDisplay";
import ChatPanel from "../components/ChatPanel";
import DocumentPreview from "../components/DocumentPreview";

export default function Dashboard() {
  const { user, logout } = useAuth();
  const [policies, setPolicies] = useState([]);
  const [contracts, setContracts] = useState([]);
  const [selected, setSelected] = useState(null); // { type, name }
  const [report, setReport] = useState(null);
  const [auditing, setAuditing] = useState(false);
  const [error, setError] = useState("");

  const refresh = async () => {
    try {
      const [p, c] = await Promise.all([api.listPolicies(), api.listContracts()]);
      setPolicies(p);
      setContracts(c);
    } catch (err) {
      setError(err.message);
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  const runAudit = async () => {
    if (!selected || selected.type !== "contract") return;
    setError("");
    setAuditing(true);
    setReport(null);
    try {
      const result = await api.runAudit(selected.name);
      setReport(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setAuditing(false);
    }
  };

  const canAudit = selected?.type === "contract" && !auditing;

  return (
    <div className="dashboard">
      <header className="topbar">
        <div className="brand">
          <div className="brand-logo">⚖</div>
          <span className="brand-text">AI Legal Auditor</span>
        </div>
        <div className="user">
          <div className="user-chip">
            <div className="user-chip-avatar">
              {user?.username?.[0]?.toUpperCase() ?? "?"}
            </div>
            <span>{user?.username}</span>
          </div>
          <button className="ghost" onClick={logout}>
            Sign out
          </button>
        </div>
      </header>

      <main className="layout">
        <aside className="sidebar">
          <FileExplorer
            policies={policies}
            contracts={contracts}
            selected={selected}
            onSelect={setSelected}
            onUploaded={refresh}
            onReindex={async () => {
              try {
                await api.indexPolicies();
                alert("Policies indexed");
              } catch (err) {
                alert("Indexing failed: " + err.message);
              }
            }}
          />
        </aside>

        <section className="center">
          <div className="actions">
            <div className="selected-label">
              {selected ? (
                <>
                  <span>Selected:</span>
                  <span className="pill">{selected.type}</span>
                  <span className="pill">{selected.name}</span>
                </>
              ) : (
                <span>Select a contract from the left to start an audit</span>
              )}
            </div>
            <button
              className="primary"
              disabled={!canAudit}
              onClick={runAudit}
              title={
                !selected
                  ? "Select a contract first"
                  : selected.type !== "contract"
                  ? "Only contracts can be audited"
                  : ""
              }
            >
              {auditing ? "Auditing…" : "Run Compliance Audit"}
            </button>
          </div>

          {error && <div className="error">{error}</div>}

          {selected?.type === "policy" ? (
            <DocumentPreview kind="policy" name={selected.name} />
          ) : selected?.type === "contract" && !report && !auditing ? (
            <DocumentPreview kind="contract" name={selected.name} />
          ) : (
            <ReportDisplay report={report} auditing={auditing} />
          )}
        </section>

        <aside className="chat">
          <ChatPanel contractName={selected?.type === "contract" ? selected.name : null} report={report} />
        </aside>
      </main>
    </div>
  );
}
