import { useState, useEffect } from "react";
import { T, USERS, PRIMITIVES } from "../contexts/OrchestratorContext";
import type { User } from "../contexts/OrchestratorContext";
import { Stat } from "./ui";

export function StatusBar({ user, wsState, anomalyCount, mode, onUserChange, onModeChange }: {
  user: User; wsState: string; anomalyCount: number; mode: string;
  onUserChange: (u: User) => void; onModeChange: (m: string) => void;
}) {
  const [time, setTime] = useState(new Date());
  useEffect(() => { const t = setInterval(() => setTime(new Date()), 1000); return () => clearInterval(t); }, []);

  const activeCount = PRIMITIVES.filter(p => p.status === "ACTIVE").length;
  const modeColors: Record<string, string> = { STANDARD: T.gold, FIELD: "#3b82f6", URGENCY: T.red, AMBIENT: T.dim };

  return (
    <div style={{
      height: 44, background: T.surface, borderBottom: `1px solid ${T.border}`,
      display: "flex", alignItems: "center", padding: "0 20px",
      gap: 0, flexShrink: 0, position: "relative", zIndex: 100,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginRight: 28, borderRight: `1px solid ${T.border}`, paddingRight: 28 }}>
        <div style={{ width: 6, height: 6, borderRadius: "50%", background: T.gold, boxShadow: `0 0 8px ${T.gold}` }} />
        <span style={{ color: T.gold, fontFamily: "monospace", fontWeight: 700, fontSize: 12, letterSpacing: "0.18em" }}>AUTOHAUS</span>
        <span style={{ color: T.muted, fontSize: 10, fontFamily: "monospace" }}>C-OS v3.1.1</span>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 20, flex: 1 }}>
        <Stat label="PRIMITIVES" value={`${activeCount}/${PRIMITIVES.length}`} color={T.green} />
        <Stat label="ENTITIES" value="7" color={T.gold} />
        <Stat label="ANOMALIES" value={anomalyCount} color={anomalyCount > 0 ? T.red : T.dim} pulse={anomalyCount > 0} />
        <Stat label="INVENTORY" value="5 VIN" color={T.textDim} />

        <div style={{ display: "flex", alignItems: "center", gap: 5, padding: "3px 10px", background: wsState === "LIVE" ? "#22c55e0d" : "#e306130d", border: `1px solid ${wsState === "LIVE" ? "#22c55e33" : "#e3061333"}`, borderRadius: 20 }}>
          <div style={{ width: 5, height: 5, borderRadius: "50%", background: wsState === "LIVE" ? T.green : T.red, animation: wsState === "LIVE" ? "pulse-dot 2s infinite" : "none" }} />
          <span style={{ color: wsState === "LIVE" ? T.green : T.red, fontSize: 9, fontFamily: "monospace", fontWeight: 700, letterSpacing: "0.1em" }}>WS {wsState}</span>
        </div>

        <div style={{ display: "flex", gap: 4 }}>
          {["STANDARD", "FIELD", "AMBIENT"].map(m => (
            <button key={m} onClick={() => onModeChange(m)} style={{
              padding: "2px 8px", fontSize: 9, fontFamily: "monospace", fontWeight: 700,
              letterSpacing: "0.08em", border: `1px solid ${mode === m ? (modeColors[m] || T.dim) + "66" : T.border}`,
              background: mode === m ? (modeColors[m] || T.dim) + "12" : "transparent",
              color: mode === m ? (modeColors[m] || T.dim) : T.dim, borderRadius: 3, cursor: "pointer"
            }}>{m}</button>
          ))}
        </div>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 16, borderLeft: `1px solid ${T.border}`, paddingLeft: 20 }}>
        <select value={user.id} onChange={e => onUserChange(Object.values(USERS).find(u => u.id === e.target.value)!)}
          style={{ background: T.elevated, border: `1px solid ${T.border2}`, color: T.text, fontSize: 10, fontFamily: "monospace", padding: "3px 8px", borderRadius: 4, cursor: "pointer" }}>
          {Object.values(USERS).map(u => <option key={u.id} value={u.id}>{u.name} · {u.role}</option>)}
        </select>
        <span style={{ color: T.dim, fontSize: 10, fontFamily: "monospace", letterSpacing: "0.05em" }}>
          {time.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
        </span>
      </div>
    </div>
  );
}

export function PrimitivesBar() {
  return (
    <div style={{ height: 32, background: T.surface, borderTop: `1px solid ${T.border}`, display: "flex", alignItems: "center", padding: "0 20px", gap: 20, overflowX: "auto" }}>
      {PRIMITIVES.map(p => (
        <div key={p.id} style={{ display: "flex", alignItems: "center", gap: 5, flexShrink: 0 }}>
          <div style={{ width: 4, height: 4, borderRadius: "50%", background: T.green }} />
          <span style={{ color: T.muted, fontSize: 8, fontFamily: "monospace", letterSpacing: "0.05em" }}>{p.label}</span>
        </div>
      ))}
      <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 6, flexShrink: 0 }}>
        <span style={{ color: T.muted, fontSize: 8, fontFamily: "monospace" }}>system_audit_ledger</span>
        <span style={{ color: T.green, fontSize: 8, fontFamily: "monospace" }}>APPEND-ONLY · ACTIVE</span>
      </div>
    </div>
  );
}
