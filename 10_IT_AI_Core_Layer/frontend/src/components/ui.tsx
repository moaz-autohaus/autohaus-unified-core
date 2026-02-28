import { useState, useEffect } from "react";
import { T, formatFileSize } from "../contexts/OrchestratorContext";
import type { StagedFile, Finding } from "../contexts/OrchestratorContext";

export function Tag({ label, color }: { label: string; color: string }) {
  return (
    <span style={{ fontSize: 8, fontFamily: "monospace", fontWeight: 700, letterSpacing: "0.08em", color, padding: "1px 6px", border: `1px solid ${color}33`, borderRadius: 3, background: `${color}0a` }}>
      {label}
    </span>
  );
}

export function KV({ k, v, mono, color }: { k: string; v: string; mono?: boolean; color?: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
      <span style={{ color: T.dim, fontSize: 9, fontFamily: "monospace" }}>{k}</span>
      <span style={{ color: color || T.textDim, fontSize: 9, fontFamily: mono ? "monospace" : "'DM Sans', sans-serif" }}>{v}</span>
    </div>
  );
}

export function ActionBtn({ label, color, onClick }: { label: string; color: string; onClick?: () => void }) {
  return (
    <button onClick={onClick} style={{ flex: 1, padding: "10px 0", background: `${color}0f`, border: `1px solid ${color}44`, color, borderRadius: 8, fontSize: 10, fontWeight: 700, fontFamily: "monospace", cursor: "pointer", letterSpacing: "0.06em", transition: "all 0.15s" }}
      onMouseEnter={e => { e.currentTarget.style.background = `${color}1a`; }}
      onMouseLeave={e => { e.currentTarget.style.background = `${color}0f`; }}>
      {label}
    </button>
  );
}

export function Stat({ label, value, color, pulse }: { label: string; value: string | number; color: string; pulse?: boolean }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <div style={{ width: 5, height: 5, borderRadius: "50%", background: color, animation: pulse ? "pulse-dot 1.5s infinite" : "none" }} />
      <span style={{ color: T.dim, fontSize: 9, fontFamily: "monospace", letterSpacing: "0.08em" }}>{label}</span>
      <span style={{ color, fontSize: 10, fontFamily: "monospace", fontWeight: 700 }}>{value}</span>
    </div>
  );
}

export function ChartTooltip({ active, payload, label }: { active?: boolean; payload?: Array<{ name: string; value: number; color: string }>; label?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background: "#0a0a0a", border: `1px solid ${T.border2}`, borderRadius: 6, padding: "10px 14px", fontSize: 11, fontFamily: "monospace" }}>
      <p style={{ color: T.gold, marginBottom: 6, letterSpacing: "0.06em" }}>{label}</p>
      {payload.map(p => (
        <p key={p.name} style={{ color: p.color, margin: "2px 0" }}>
          {p.name}: <span style={{ color: T.text }}>${p.value.toLocaleString()}</span>
        </p>
      ))}
    </div>
  );
}

export function AttachmentBubble({ file }: { file: StagedFile }) {
  const isImage = file.preview && file.type.startsWith("image/");
  const isVideo = file.type.startsWith("video/");
  const isPdf   = file.type === "application/pdf" || file.name.endsWith(".pdf");
  const icon    = isVideo ? "🎬" : isPdf ? "📄" : "📎";
  return isImage ? (
    <div style={{ marginTop: 8, borderRadius: 8, overflow: "hidden", border: `1px solid ${T.border2}`, maxWidth: 280 }}>
      <img src={file.preview!} alt={file.name} style={{ width: "100%", display: "block", objectFit: "cover", maxHeight: 200 }} />
      <div style={{ background: T.elevated, padding: "5px 10px", display: "flex", justifyContent: "space-between" }}>
        <span style={{ color: T.textDim, fontSize: 9, fontFamily: "monospace" }}>{file.name}</span>
        <span style={{ color: T.dim, fontSize: 9, fontFamily: "monospace" }}>{formatFileSize(file.size)}</span>
      </div>
    </div>
  ) : (
    <div style={{ marginTop: 8, display: "flex", alignItems: "center", gap: 10, padding: "10px 12px", background: T.elevated, border: `1px solid ${T.border2}`, borderRadius: 8, maxWidth: 260 }}>
      <span style={{ fontSize: 20 }}>{icon}</span>
      <div style={{ minWidth: 0 }}>
        <p style={{ color: T.text, fontSize: 11, fontFamily: "monospace", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{file.name}</p>
        <p style={{ color: T.dim, fontSize: 9, fontFamily: "monospace", marginTop: 2 }}>{formatFileSize(file.size)}</p>
      </div>
      <div style={{ width: 6, height: 6, borderRadius: "50%", background: T.green, flexShrink: 0 }} />
    </div>
  );
}

export function FindingsCard({ findings }: { findings: Finding[] }) {
  const sev: Record<string, string> = { RED: T.red, YELLOW: "#eab308", GREEN: T.green };
  return (
    <div style={{ marginTop: 10, borderRadius: 8, overflow: "hidden", border: `1px solid ${T.border2}` }}>
      <div style={{ padding: "7px 12px", background: T.elevated, borderBottom: `1px solid ${T.border}`, display: "flex", alignItems: "center", gap: 6 }}>
        <span style={{ color: T.goldDim, fontSize: 8, fontFamily: "monospace", fontWeight: 700, letterSpacing: "0.1em" }}>GEMINI VEO · EXTRACTED FINDINGS</span>
      </div>
      {findings.map((f, i) => (
        <div key={i} style={{ padding: "8px 12px", borderBottom: i < findings.length - 1 ? `1px solid ${T.border}` : "none", background: i % 2 === 0 ? T.surface : `${T.bg}cc`, display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
          <div>
            <p style={{ color: T.textDim, fontSize: 10, fontFamily: "monospace", marginBottom: 2 }}>{f.zone}</p>
            <p style={{ color: T.text, fontSize: 11, fontFamily: "'DM Sans', sans-serif" }}>{f.issue}</p>
          </div>
          <div style={{ textAlign: "right", flexShrink: 0 }}>
            <span style={{ color: sev[f.severity], fontSize: 8, fontFamily: "monospace", fontWeight: 700, display: "block" }}>{f.severity}</span>
            <span style={{ color: T.muted, fontSize: 8, fontFamily: "monospace" }}>{f.confidence}%</span>
          </div>
        </div>
      ))}
    </div>
  );
}

export function StagedAttachments({ files, onRemove }: { files: StagedFile[]; onRemove: (i: number) => void }) {
  if (!files.length) return null;
  return (
    <div style={{ padding: "10px 16px 0", display: "flex", gap: 8, flexWrap: "wrap" }}>
      {files.map((f, i) => {
        const isImage = f.preview && f.type.startsWith("image/");
        return (
          <div key={i} style={{ position: "relative", animation: "msg-in 0.2s ease" }}>
            {isImage ? (
              <div style={{ width: 56, height: 56, borderRadius: 6, overflow: "hidden", border: `1px solid ${T.gold}55` }}>
                <img src={f.preview!} alt="" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
              </div>
            ) : (
              <div style={{ height: 56, padding: "0 12px", borderRadius: 6, border: `1px solid ${T.border2}`, background: T.elevated, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 3, minWidth: 64 }}>
                <span style={{ fontSize: 18 }}>{f.type.startsWith("video/") ? "🎬" : f.name.endsWith(".pdf") ? "📄" : "📎"}</span>
                <span style={{ color: T.dim, fontSize: 8, fontFamily: "monospace", maxWidth: 60, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{f.name.split(".").pop()?.toUpperCase()}</span>
              </div>
            )}
            <button onClick={() => onRemove(i)} style={{ position: "absolute", top: -6, right: -6, width: 16, height: 16, borderRadius: "50%", background: T.red, border: "none", color: "#fff", fontSize: 9, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 700, lineHeight: 1 }}>✕</button>
          </div>
        );
      })}
    </div>
  );
}

export function Processing({ hasMedia }: { hasMedia: boolean }) {
  const textSteps  = ["Identity Engine resolving...", "Agentic Router classifying...", "CIL executing query...", "Translating output..."];
  const mediaSteps = ["Uploading to Intelligence Layer...", "Gemini Veo analyzing frames...", "Extracting defect zones...", "Writing to Digital Twin..."];
  const steps = hasMedia ? mediaSteps : textSteps;
  const [step, setStep] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setStep(s => (s + 1) % steps.length), 600);
    return () => clearInterval(t);
  }, [steps.length]);
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16, padding: "8px 12px", background: T.elevated, borderRadius: 8, border: `1px solid ${T.border}` }}>
      <div style={{ display: "flex", gap: 3 }}>
        {[0,1,2].map(i => <div key={i} style={{ width: 4, height: 4, borderRadius: "50%", background: T.gold, animation: `pulse-dot 1.2s ${i*0.2}s infinite` }} />)}
      </div>
      <span style={{ color: T.goldDim, fontSize: 10, fontFamily: "monospace", letterSpacing: "0.05em" }}>{steps[step]}</span>
    </div>
  );
}

export function AmbientLog() {
  const logs = [
    "Anomaly engine sweep complete — no new flags",
    "identity_resolution.py merged 2 duplicate records",
    "Invoice AUTO-2024-0892 filed to Drive successfully",
    "Twilio webhook received — routed to Asim",
    "BigQuery ledger append — 847ms",
    "Gemini Flash processed walk-around video VIN WBA123",
    "KAMM compliance check passed — 0 disclosures pending",
  ];
  const [visible, setVisible] = useState([logs[0]]);
  useEffect(() => {
    let i = 1;
    const t = setInterval(() => {
      if (i < logs.length) { setVisible(v => [logs[i], ...v].slice(0, 4)); i++; }
    }, 3000);
    return () => clearInterval(t);
  }, []);
  return (
    <div style={{ padding: "12px 16px" }}>
      <div style={{ color: T.dim, fontSize: 9, fontFamily: "monospace", letterSpacing: "0.1em", marginBottom: 10 }}>CIL AUTONOMOUS ACTIVITY</div>
      {visible.map((log, i) => (
        <div key={log} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6, opacity: 1 - i * 0.2, animation: i === 0 ? "msg-in 0.3s ease" : "none" }}>
          <span style={{ color: T.green, fontSize: 9 }}>◆</span>
          <span style={{ color: T.dim, fontSize: 10, fontFamily: "monospace" }}>{log}</span>
        </div>
      ))}
    </div>
  );
}

export function QuickCommands({ onSend, user, onNavigate }: { onSend: (cmd: string) => void; user: { access: string; role: string }; onNavigate?: (v: string) => void }) {
  const cmds = user.access === "SOVEREIGN"
    ? [
        { label: "KAMM Financials", cmd: "Show me KAMM financials" },
        { label: "M4 Digital Twin", cmd: "Pull up the digital twin for the M4" },
        { label: "Anomaly Alert",   cmd: "Show me the latest anomaly alert" },
        { label: "Collision",       cmd: "Update the M4 mileage" },
        { label: "Inventory",       cmd: "Show full inventory" },
        { label: "Dispatch",        cmd: "Track the Carlux driver" },
      ]
    : user.role === "Logistics"
    ? [
        { label: "My Dispatch",    cmd: "Track the Carlux driver" },
        { label: "Fleet Status",   cmd: "Show full inventory" },
      ]
    : [
        { label: "Service ROs",    cmd: "Show full inventory" },
        { label: "KAMM Status",    cmd: "Show me KAMM financials" },
      ];

  return (
    <div style={{ padding: "10px 16px 0", display: "flex", gap: 6, flexWrap: "wrap", borderBottom: `1px solid ${T.border}`, paddingBottom: 10 }}>
      {cmds.map(c => (
        <button key={c.label} onClick={() => onSend(c.cmd)}
          onMouseEnter={e => { (e.target as HTMLButtonElement).style.borderColor = T.gold; (e.target as HTMLButtonElement).style.color = T.gold; }}
          onMouseLeave={e => { (e.target as HTMLButtonElement).style.borderColor = T.border2; (e.target as HTMLButtonElement).style.color = T.dim; }}
          style={{ padding: "4px 10px", background: "transparent", border: `1px solid ${T.border2}`, borderRadius: 20, color: T.dim, fontSize: 10, fontFamily: "monospace", cursor: "pointer", letterSpacing: "0.04em", transition: "all 0.15s" }}>
          {c.label}
        </button>
      ))}
      {onNavigate && user.access === "SOVEREIGN" && (
        <button onClick={() => onNavigate("action")}
          onMouseEnter={e => { (e.target as HTMLButtonElement).style.borderColor = "#22c55e"; (e.target as HTMLButtonElement).style.color = "#22c55e"; (e.target as HTMLButtonElement).style.background = "#22c55e0f"; }}
          onMouseLeave={e => { (e.target as HTMLButtonElement).style.borderColor = "#22c55e55"; (e.target as HTMLButtonElement).style.color = "#22c55e"; (e.target as HTMLButtonElement).style.background = "#22c55e08"; }}
          style={{ padding: "4px 10px", background: "#22c55e08", border: "1px solid #22c55e55", borderRadius: 20, color: "#22c55e", fontSize: 10, fontFamily: "monospace", cursor: "pointer", letterSpacing: "0.04em", fontWeight: 700, transition: "all 0.15s" }}>
          Action Center
        </button>
      )}
    </div>
  );
}
