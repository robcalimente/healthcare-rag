import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { sendChat } from "../api";

const PATIENT_SUGGESTIONS = [
  "What medications is this patient currently on?",
  "What conditions has this patient been diagnosed with?",
  "Summarize this patient's recent visit history.",
];

const POPULATION_SUGGESTIONS = [
  "How many patients have hypertension?",
  "What percentage of patients are taking lisinopril?",
  "What conditions are commonly seen alongside diabetes in this population?",
];

export default function ChatPanel({ mode, patientId, onNewTrace }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const suggestions = mode === "patient" ? PATIENT_SUGGESTIONS : POPULATION_SUGGESTIONS;
  const disabled = mode === "patient" && !patientId;

  async function ask(question) {
    if (!question.trim() || disabled) return;
    setError(null);
    setInput("");
    setMessages((m) => [...m, { role: "user", text: question }]);
    setLoading(true);
    try {
      const data = await sendChat({ mode, question, patientId });
      setMessages((m) => [...m, { role: "assistant", text: data.answer }]);
      onNewTrace(data.trace);
    } catch (err) {
      setError(err.message || "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="chat-panel">
      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="chat-empty">
            {disabled ? (
              <p>Select a patient to start asking questions about their chart.</p>
            ) : (
              <>
                <p>Try asking:</p>
                <div className="suggestion-list">
                  {suggestions.map((s) => (
                    <button key={s} className="suggestion-chip" onClick={() => ask(s)}>
                      {s}
                    </button>
                  ))}
                </div>
              </>
            )}
          </div>
        )}
        <AnimatePresence initial={false}>
          {messages.map((m, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className={`chat-message chat-message-${m.role}`}
            >
              {m.text}
            </motion.div>
          ))}
        </AnimatePresence>
        {loading && (
          <div className="chat-message chat-message-assistant chat-loading">
            <span className="dot" />
            <span className="dot" />
            <span className="dot" />
          </div>
        )}
        {error && <div className="chat-error">{error}</div>}
      </div>

      <form
        className="chat-input-row"
        onSubmit={(e) => {
          e.preventDefault();
          ask(input);
        }}
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={
            disabled ? "Select a patient first..." : "Ask a question..."
          }
          disabled={disabled || loading}
        />
        <button type="submit" disabled={disabled || loading || !input.trim()}>
          Ask
        </button>
      </form>
    </div>
  );
}
