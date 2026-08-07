import { useEffect, useState } from "react";
import Disclaimer from "./components/Disclaimer";
import WakingUp from "./components/WakingUp";
import PatientPicker from "./components/PatientPicker";
import ChatPanel from "./components/ChatPanel";
import TracePanel from "./components/TracePanel";
import Methodology from "./pages/Methodology";
import { checkHealth, fetchPatients } from "./api";

export default function App() {
  const [tab, setTab] = useState("chat");
  const [mode, setMode] = useState("patient");
  const [patients, setPatients] = useState([]);
  const [selectedPatientId, setSelectedPatientId] = useState(null);
  const [trace, setTrace] = useState(null);
  const [wakingUp, setWakingUp] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function wake() {
      const healthy = await checkHealth(4000);
      if (cancelled) return;
      if (healthy) {
        setWakingUp(false);
        return;
      }
      const interval = setInterval(async () => {
        const ok = await checkHealth(4000);
        if (cancelled) return;
        if (ok) {
          setWakingUp(false);
          clearInterval(interval);
        }
      }, 3000);
    }
    wake();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (wakingUp) return;
    fetchPatients().then(setPatients).catch(() => {});
  }, [wakingUp]);

  return (
    <div className="app">
      <header className="app-header">
        <div className="app-title">
          <span className="app-title-mark">RAG</span> Healthcare Chart Assistant
        </div>
        <nav className="tab-nav">
          <button
            className={tab === "chat" ? "active" : ""}
            onClick={() => setTab("chat")}
          >
            Demo
          </button>
          <button
            className={tab === "methodology" ? "active" : ""}
            onClick={() => setTab("methodology")}
          >
            Methodology &amp; Eval
          </button>
        </nav>
      </header>

      <Disclaimer />

      {wakingUp ? (
        <WakingUp />
      ) : tab === "methodology" ? (
        <Methodology />
      ) : (
        <main className="chat-layout">
          <aside className="chat-sidebar">
            <div className="mode-toggle">
              <button
                className={mode === "patient" ? "active" : ""}
                onClick={() => {
                  setMode("patient");
                  setTrace(null);
                }}
              >
                Patient chart
              </button>
              <button
                className={mode === "population" ? "active" : ""}
                onClick={() => {
                  setMode("population");
                  setTrace(null);
                }}
              >
                Population
              </button>
            </div>

            {mode === "patient" && (
              <PatientPicker
                patients={patients}
                selectedId={selectedPatientId}
                onSelect={(id) => {
                  setSelectedPatientId(id);
                  setTrace(null);
                }}
              />
            )}
            {mode === "population" && (
              <div className="population-note">
                <p>
                  Ask questions across all {patients.length || 1000} synthetic
                  patients. Counting/percentage questions are answered by a real
                  database query, not vector search &mdash; see the Methodology tab
                  for why.
                </p>
              </div>
            )}
          </aside>

          <section className="chat-main">
            <ChatPanel
              key={mode + (selectedPatientId || "")}
              mode={mode}
              patientId={selectedPatientId}
              onNewTrace={setTrace}
            />
          </section>

          <aside className="chat-trace">
            <TracePanel trace={trace} />
          </aside>
        </main>
      )}
    </div>
  );
}
