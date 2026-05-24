import { useState, useEffect, useRef } from "react";
import { api } from "../api";

export default function ChatPanel({ contractName, report }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const scrollRef = useRef(null);

  // Reset the chat whenever the user switches to a different contract
  // or when a new audit report arrives.
  useEffect(() => {
    setMessages([]);
  }, [contractName, report]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: 9e9, behavior: "smooth" });
  }, [messages, busy]);

  const canChat = !!contractName && !!report && !report.error;

  const send = async (e) => {
    e.preventDefault();
    const text = input.trim();
    if (!text || !canChat || busy) return;

    const userTurn = { role: "user", content: text };
    setMessages((prev) => [...prev, userTurn]);
    setInput("");
    setBusy(true);

    try {
      const { reply } = await api.chat({
        contractName,
        auditReport: report,
        history: messages, // current history BEFORE this new turn — backend appends user_message
        message: text,
      });
      setMessages((prev) => [...prev, { role: "assistant", content: reply }]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: "system", content: `Error: ${err.message}` },
      ]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="chat-panel">
      <div className="chat-head">
        <h3>Chat</h3>
        {contractName ? (
          <p className="muted small">
            {report
              ? `About: ${contractName}`
              : "Run the audit first, then chat about it."}
          </p>
        ) : (
          <p className="muted small">Select a contract to chat about it.</p>
        )}
      </div>

      <div className="chat-body" ref={scrollRef}>
        {messages.length === 0 ? (
          <p className="muted small" style={{ padding: "8px 4px" }}>
            {canChat ? (
              <>
                Ask the assistant about the audit. Example:
                <br />
                <em>"Rewrite clause 3 to comply with the payment policy."</em>
              </>
            ) : (
              <em>Run a compliance audit first — then the chat unlocks.</em>
            )}
          </p>
        ) : (
          messages.map((m, i) => (
            <div key={i} className={`bubble ${m.role}`}>
              {m.content}
            </div>
          ))
        )}
        {busy && (
          <div className="bubble assistant">
            <span className="typing">
              <span></span>
              <span></span>
              <span></span>
            </span>
          </div>
        )}
      </div>

      <form className="chat-input" onSubmit={send}>
        <input
          placeholder={
            !canChat
              ? "Run the audit first"
              : busy
              ? "Waiting for reply…"
              : "Type a message…"
          }
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={!canChat || busy}
        />
        <button
          type="submit"
          disabled={!canChat || !input.trim() || busy}
        >
          Send
        </button>
      </form>
    </div>
  );
}
