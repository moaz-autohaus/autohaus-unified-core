import { useState } from "react";
import { OrchestratorProvider } from "./contexts/OrchestratorContext";
import { CommandCenter } from "./pages/CommandCenter";
import { ActionCenter } from "./pages/ActionCenter";

function App() {
  const [view, setView] = useState<"command" | "action" | "public">("command");

  return (
    <OrchestratorProvider>
      {view === "command" && <CommandCenter onNavigate={(v) => setView(v as "action" | "public")} />}
      {view === "action" && (
        <div style={{ height: "100vh", display: "flex", flexDirection: "column", background: "#080808" }}>
          <div style={{ padding: "12px 20px", borderBottom: "1px solid #1c1c1c", display: "flex", alignItems: "center", gap: 12 }}>
            <button
              onClick={() => setView("command")}
              style={{
                padding: "4px 12px", borderRadius: 4, border: "1px solid #C5A05944",
                background: "#C5A05912", color: "#C5A059", fontSize: 10,
                fontFamily: "monospace", fontWeight: 700, cursor: "pointer",
              }}
            >
              ← COMMAND CENTER
            </button>
            <span style={{ color: "#525252", fontSize: 9, fontFamily: "monospace" }}>CIL GOVERNANCE API</span>
          </div>
          <div style={{ flex: 1, overflow: "auto", padding: 24 }}>
            <ActionCenter />
          </div>
        </div>
      )}
      {view === "public" && (
        <div style={{ height: "100vh", display: "flex", flexDirection: "column", background: "#080808" }}>
          <div style={{ padding: "12px 20px", borderBottom: "1px solid #1c1c1c", display: "flex", alignItems: "center", gap: 12 }}>
            <button
              onClick={() => setView("command")}
              style={{
                padding: "4px 12px", borderRadius: 4, border: "1px solid #C5A05944",
                background: "#C5A05912", color: "#C5A059", fontSize: 10,
                fontFamily: "monospace", fontWeight: 700, cursor: "pointer",
              }}
            >
              ← COMMAND CENTER
            </button>
            <span style={{ color: "#525252", fontSize: 9, fontFamily: "monospace" }}>PUBLIC API TEST</span>
          </div>
          <div style={{ flex: 1, overflow: "auto", padding: 24, display: "flex", alignItems: "center", justifyContent: "center" }}>
            <span style={{ color: "#525252", fontSize: 12, fontFamily: "monospace" }}>Public API test panel — coming soon</span>
          </div>
        </div>
      )}
    </OrchestratorProvider>
  );
}

export default App;
