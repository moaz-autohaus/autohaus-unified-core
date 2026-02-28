import { useState, useEffect } from "react";
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { T, FINANCE_DATA, TWIN_FLAGS, ENTITY_OPTIONS, INVENTORY_DATA } from "../contexts/OrchestratorContext";
import type { EntityOption } from "../contexts/OrchestratorContext";
import { KV, ActionBtn, ChartTooltip } from "./ui";

function PlateHeader({ title, subtitle, tag, onClose, tagColor }: {
  title: string; subtitle: string; tag: string; onClose: () => void; tagColor?: string;
}) {
  const colors: Record<string, string> = { FINANCE: T.blue, INVENTORY: T.gold, COMPLIANCE: T.red, SERVICE: T.green, LOGISTICS: T.purple };
  const c = tagColor || colors[tag] || T.gold;
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 20, paddingBottom: 16, borderBottom: `1px solid ${T.border}` }}>
      <div>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
          <span style={{ fontSize: 9, fontFamily: "monospace", fontWeight: 700, letterSpacing: "0.12em", color: c, padding: "2px 8px", border: `1px solid ${c}33`, borderRadius: 3, background: `${c}0a` }}>{tag}</span>
          <span style={{ fontSize: 8, color: T.muted, fontFamily: "monospace" }}>MOUNT_PLATE · WEBSOCKET</span>
        </div>
        <h2 style={{ color: T.text, fontSize: 14, fontWeight: 700, letterSpacing: "0.08em", fontFamily: "monospace", margin: 0 }}>{title}</h2>
        <p style={{ color: T.textDim, fontSize: 11, marginTop: 3, fontFamily: "'DM Sans', sans-serif" }}>{subtitle}</p>
      </div>
      <button onClick={onClose} style={{ background: "transparent", border: `1px solid ${T.border2}`, color: T.dim, cursor: "pointer", width: 26, height: 26, borderRadius: 4, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12, transition: "all 0.15s" }}
        onMouseEnter={e => { e.currentTarget.style.borderColor = T.red; e.currentTarget.style.color = T.red; }}
        onMouseLeave={e => { e.currentTarget.style.borderColor = T.border2; e.currentTarget.style.color = T.dim; }}>✕</button>
    </div>
  );
}

export function FinancePlate({ onClose }: { onClose: () => void }) {
  const [filter, setFilter] = useState("ALL");
  const entities = ["ALL", "AutoHaus", "KAMM", "AstroLogistics", "Carlux"];
  const colors: Record<string, string> = { AutoHaus: T.gold, KAMM: T.blue, AstroLogistics: T.purple, Carlux: T.green };

  const data = FINANCE_DATA.map(d => filter === "ALL" ? d : { week: d.week, [filter]: (d as Record<string, unknown>)[filter] });
  const activeKeys = filter === "ALL" ? Object.keys(colors) : [filter];

  const totals = { revenue: 192400, margin: 31.2, growth: 12.4 };

  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column", padding: 24 }}>
      <PlateHeader title="FINANCE AGGREGATE" subtitle="All entities · 6-week rolling margin" tag="FINANCE" onClose={onClose} />
      <div style={{ display: "flex", gap: 6, marginBottom: 20 }}>
        {entities.map(e => (
          <button key={e} onClick={() => setFilter(e)} style={{
            padding: "4px 12px", borderRadius: 20, border: `1px solid ${filter === e ? T.gold : T.border2}`,
            background: filter === e ? `${T.gold}12` : "transparent",
            color: filter === e ? T.gold : T.dim, fontSize: 10, fontFamily: "monospace",
            cursor: "pointer", letterSpacing: "0.05em", transition: "all 0.15s"
          }}>{e}</button>
        ))}
      </div>
      <div style={{ flex: 1, minHeight: 0 }}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
            <defs>
              {Object.entries(colors).map(([k, c]) => (
                <linearGradient key={k} id={`gf-${k}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={c} stopOpacity={0.25} />
                  <stop offset="95%" stopColor={c} stopOpacity={0} />
                </linearGradient>
              ))}
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke={T.border} />
            <XAxis dataKey="week" tick={{ fill: T.dim, fontSize: 10, fontFamily: "monospace" }} axisLine={{ stroke: T.border }} />
            <YAxis tick={{ fill: T.dim, fontSize: 10, fontFamily: "monospace" }} axisLine={{ stroke: T.border }} tickFormatter={(v: number) => `$${(v/1000).toFixed(0)}k`} />
            <Tooltip content={<ChartTooltip />} />
            {activeKeys.map(k => (
              <Area key={k} type="monotone" dataKey={k} stroke={colors[k]} fill={`url(#gf-${k})`} strokeWidth={1.5} dot={{ fill: colors[k], r: 2.5 }} />
            ))}
          </AreaChart>
        </ResponsiveContainer>
      </div>
      <div style={{ display: "flex", gap: 12, marginTop: 16 }}>
        {[
          { label: "TOTAL REVENUE", val: `$${totals.revenue.toLocaleString()}`, delta: `+${totals.growth}%`, color: T.green },
          { label: "NET MARGIN",    val: `${totals.margin}%`,                   delta: "+2.1% WoW",          color: T.gold },
          { label: "ENTITIES",      val: "4 LLCs",                              delta: "Consolidated",        color: T.blue },
          { label: "LEDGER ROWS",   val: "2,841",                               delta: "This period",         color: T.dim },
        ].map(s => (
          <div key={s.label} style={{ flex: 1, background: T.surface, border: `1px solid ${T.border}`, borderRadius: 8, padding: "10px 12px" }}>
            <p style={{ color: T.dim, fontSize: 8, fontFamily: "monospace", letterSpacing: "0.1em", marginBottom: 4 }}>{s.label}</p>
            <p style={{ color: T.text, fontSize: 16, fontWeight: 700, fontFamily: "monospace" }}>{s.val}</p>
            <p style={{ color: s.color, fontSize: 10, marginTop: 2, fontFamily: "monospace" }}>{s.delta}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

export function TwinPlate({ onClose }: { onClose: () => void }) {
  const sev: Record<string, string> = { RED: T.red, YELLOW: "#eab308", GREEN: T.green };
  const counts = { RED: TWIN_FLAGS.filter(f => f.severity === "RED").length, YELLOW: TWIN_FLAGS.filter(f => f.severity === "YELLOW").length, GREEN: TWIN_FLAGS.filter(f => f.severity === "GREEN").length };

  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column", padding: 24 }}>
      <PlateHeader title="DIGITAL TWIN" subtitle="2023 BMW M4 Competition · WBA93HM0XP1234567 · KAMM LLC" tag="INVENTORY" onClose={onClose} />
      <div style={{ display: "flex", gap: 8, marginBottom: 18 }}>
        {Object.entries(counts).map(([s, n]) => (
          <div key={s} style={{ display: "flex", alignItems: "center", gap: 6, padding: "4px 12px", background: `${sev[s]}0d`, border: `1px solid ${sev[s]}33`, borderRadius: 20 }}>
            <div style={{ width: 6, height: 6, borderRadius: "50%", background: sev[s], boxShadow: s === "RED" ? `0 0 6px ${sev[s]}` : "none" }} />
            <span style={{ color: sev[s], fontSize: 10, fontFamily: "monospace", fontWeight: 700 }}>{n} {s}</span>
          </div>
        ))}
        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 4 }}>
          <span style={{ color: T.dim, fontSize: 9, fontFamily: "monospace" }}>SOURCE:</span>
          <span style={{ color: T.goldDim, fontSize: 9, fontFamily: "monospace" }}>GEMINI VEO + MECHANIC AUDIO</span>
        </div>
      </div>
      <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: 8, paddingRight: 4 }}>
        {TWIN_FLAGS.map((f, i) => (
          <div key={i} style={{
            background: T.surface, borderLeft: `3px solid ${sev[f.severity]}`,
            border: `1px solid ${T.border}`, borderLeftColor: sev[f.severity],
            borderRadius: "0 8px 8px 0", padding: "12px 14px",
            display: "flex", justifyContent: "space-between", alignItems: "center",
            animation: `msg-in 0.2s ${i * 0.05}s both ease`
          }}>
            <div>
              <p style={{ color: T.text, fontWeight: 600, fontSize: 12, marginBottom: 3, fontFamily: "monospace" }}>{f.zone}</p>
              <p style={{ color: T.textDim, fontSize: 11, fontFamily: "'DM Sans', sans-serif" }}>{f.issue}</p>
            </div>
            <div style={{ textAlign: "right", flexShrink: 0, marginLeft: 12 }}>
              <span style={{ color: sev[f.severity], fontSize: 9, fontWeight: 700, letterSpacing: "0.1em", fontFamily: "monospace" }}>{f.severity}</span>
              <p style={{ color: T.muted, fontSize: 9, marginTop: 2, fontFamily: "monospace" }}>{f.source}</p>
              <p style={{ color: T.muted, fontSize: 9, fontFamily: "monospace" }}>{f.confidence}% conf.</p>
            </div>
          </div>
        ))}
      </div>
      <div style={{ display: "flex", gap: 10, marginTop: 16 }}>
        <ActionBtn label="ESCALATE RED FLAG" color={T.red} />
        <ActionBtn label="GENERATE QUOTE" color={T.gold} />
        <ActionBtn label="VIEW INSURANCE" color={T.blue} />
      </div>
    </div>
  );
}

export function AnomalyPlate({ onClose, onDecision }: { onClose: () => void; onDecision: (type: string) => void }) {
  const [state, setState] = useState<string | null>(null);
  const [overrideText, setOverrideText] = useState("");
  const [showOverride, setShowOverride] = useState(false);

  const handleDecision = (type: string) => {
    setState(type);
    onDecision(type);
  };

  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column", padding: 24, background: state ? T.surface : `linear-gradient(180deg, #0d0404 0%, ${T.surface} 40%)` }}>
      <PlateHeader title="ANOMALY ALERT" subtitle="Sleep Monitor · Fired 14 minutes ago · Urgency 9.2" tag="COMPLIANCE" onClose={onClose} tagColor={T.red} />

      {state ? (
        <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 16 }}>
          <div style={{ width: 56, height: 56, borderRadius: "50%", background: state === "APPROVED" ? "#22c55e12" : `${T.gold}12`, border: `2px solid ${state === "APPROVED" ? T.green : T.gold}`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 24 }}>
            {state === "APPROVED" ? "✓" : "⚡"}
          </div>
          <p style={{ color: T.text, fontWeight: 700, fontFamily: "monospace", letterSpacing: "0.08em" }}>{state === "APPROVED" ? "APPROVED & LOGGED" : "OVERRIDE LOGGED"}</p>
          {state === "OVERRIDE" && overrideText && <p style={{ color: T.gold, fontSize: 11, fontFamily: "monospace", textAlign: "center", maxWidth: 280 }}>Reason: "{overrideText}"</p>}
          <p style={{ color: T.dim, fontSize: 10, fontFamily: "monospace", textAlign: "center" }}>Written to system_audit_ledger · {new Date().toISOString()}</p>
          <p style={{ color: T.dim, fontSize: 10, fontFamily: "monospace" }}>Attributed: AHSIN_CEO · Carbon LLC</p>
        </div>
      ) : (
        <>
          <div style={{ background: `${T.red}08`, border: `1px solid ${T.red}22`, borderRadius: 10, padding: 16, marginBottom: 14 }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 12 }}>
              <span style={{ color: T.red, fontWeight: 700, fontSize: 11, letterSpacing: "0.1em", fontFamily: "monospace" }}>⚠ TRANSPORT COST SPIKE · 2.3σ</span>
              <span style={{ color: T.dim, fontSize: 9, fontFamily: "monospace" }}>30-day baseline: $312</span>
            </div>
            {[
              { k: "VIN",         v: "WBA123 · BMW M4 Competition" },
              { k: "COST FLAGGED",v: "$847" },
              { k: "30-DAY MEAN", v: "$312 avg" },
              { k: "DISPATCHER",  v: "Moaz · Carlux LLC" },
              { k: "ROUTE",       v: "Iowa City → Des Moines" },
              { k: "ENTITY PATH", v: "CARLUX_LLC → AUTOHAUS_SERVICES_LLC" },
            ].map(r => (
              <div key={r.k} style={{ display: "flex", justifyContent: "space-between", padding: "5px 0", borderBottom: `1px solid ${T.border}` }}>
                <span style={{ color: T.dim, fontSize: 10, fontFamily: "monospace" }}>{r.k}</span>
                <span style={{ color: T.text, fontSize: 10, fontFamily: "monospace" }}>{r.v}</span>
              </div>
            ))}
          </div>

          <div style={{ marginBottom: 14 }}>
            <p style={{ color: T.dim, fontSize: 9, fontFamily: "monospace", letterSpacing: "0.08em", marginBottom: 8 }}>INSURANCE TRANSFER · AUTO-TRIGGERED</p>
            <div style={{ display: "flex", gap: 8 }}>
              {[{ dir: "FROM", entity: "AstroLogistics", coverage: "Bailee Coverage" }, { dir: "TO", entity: "AutoHaus Services", coverage: "Garagekeepers" }].map((p, i) => (
                <div key={i} style={{ flex: 1, background: T.surface, border: `1px solid ${T.border2}`, borderRadius: 6, padding: "10px 12px" }}>
                  <p style={{ color: T.gold, fontSize: 9, fontFamily: "monospace", marginBottom: 4 }}>{p.dir}</p>
                  <p style={{ color: T.text, fontSize: 11, fontFamily: "monospace" }}>{p.coverage}</p>
                  <p style={{ color: T.dim, fontSize: 9, fontFamily: "monospace", marginTop: 2 }}>{p.entity}</p>
                </div>
              ))}
            </div>
          </div>

          {showOverride && (
            <div style={{ marginBottom: 12 }}>
              <input value={overrideText} onChange={e => setOverrideText(e.target.value)}
                placeholder="Enter override reason (e.g. Rush job · VIP client)..."
                style={{ width: "100%", background: T.surface, border: `1px solid ${T.gold}44`, borderRadius: 6, padding: "8px 12px", color: T.text, fontSize: 11, fontFamily: "monospace", boxSizing: "border-box" }} />
            </div>
          )}

          <div style={{ display: "flex", gap: 8, marginTop: "auto" }}>
            <button onClick={() => handleDecision("APPROVED")} style={{ flex: 1, padding: 11, background: "#22c55e0f", border: `1px solid #22c55e44`, color: T.green, borderRadius: 8, fontSize: 11, fontWeight: 700, fontFamily: "monospace", cursor: "pointer", letterSpacing: "0.06em" }}>APPROVE</button>
            <button onClick={() => { if (!showOverride) { setShowOverride(true); } else if (overrideText) { handleDecision("OVERRIDE"); } }}
              style={{ flex: 1, padding: 11, background: `${T.gold}0f`, border: `1px solid ${T.gold}44`, color: T.gold, borderRadius: 8, fontSize: 11, fontWeight: 700, fontFamily: "monospace", cursor: "pointer", letterSpacing: "0.06em" }}>
              {showOverride ? (overrideText ? "CONFIRM OVERRIDE" : "ENTER REASON...") : "OVERRIDE + LOG"}
            </button>
            <button onClick={() => {}} style={{ padding: "11px 14px", background: `${T.blue}0f`, border: `1px solid ${T.blue}44`, color: T.blue, borderRadius: 8, fontSize: 11, fontWeight: 700, fontFamily: "monospace", cursor: "pointer" }}>INVESTIGATE</button>
          </div>
        </>
      )}
    </div>
  );
}

export function CollisionPlate({ onClose, onResolve }: { onClose: () => void; onResolve: (v: EntityOption) => void }) {
  const [selected, setSelected] = useState<number | null>(null);
  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column", padding: 24 }}>
      <PlateHeader title="AMBIGUITY RESOLUTION" subtitle="Identity Engine collision · 2 entities matched" tag="INVENTORY" onClose={onClose} />
      <p style={{ color: T.textDim, fontSize: 11, marginBottom: 20, fontFamily: "'DM Sans', sans-serif", lineHeight: 1.6 }}>
        The Identity Engine found two BMW M4 Competition units matching your query. Select the correct vehicle to resume the workflow. This decision will be logged.
      </p>
      <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 12 }}>
        {ENTITY_OPTIONS.map((opt, i) => (
          <div key={i} onClick={() => setSelected(i)} style={{
            background: selected === i ? `${T.gold}08` : T.surface,
            border: `1px solid ${selected === i ? T.gold : T.border2}`,
            borderRadius: 10, padding: 18, cursor: "pointer",
            transition: "all 0.2s", position: "relative",
          }}>
            {selected === i && <div style={{ position: "absolute", top: 14, right: 14, width: 20, height: 20, borderRadius: "50%", background: T.gold, display: "flex", alignItems: "center", justifyContent: "center" }}><span style={{ color: "#000", fontSize: 10, fontWeight: 700 }}>✓</span></div>}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 10 }}>
              <div>
                <p style={{ color: T.text, fontWeight: 700, fontSize: 13, fontFamily: "monospace" }}>{opt.year} {opt.model}</p>
                <p style={{ color: T.textDim, fontSize: 11, marginTop: 2, fontFamily: "'DM Sans', sans-serif" }}>{opt.color}</p>
              </div>
              <span style={{ color: T.gold, fontSize: 10, fontFamily: "monospace", fontWeight: 700 }}>{opt.entity}</span>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              <KV k="VIN" v={opt.vin} mono />
              <KV k="LOCATION" v={opt.lot} />
              <KV k="DAYS ON LOT" v={`${opt.daysOnLot} days`} color={opt.daysOnLot > 20 ? "#eab308" : T.green} />
              <KV k="INSURANCE" v={opt.insurance} />
            </div>
          </div>
        ))}
      </div>
      <button onClick={() => selected !== null && onResolve(ENTITY_OPTIONS[selected])} style={{
        marginTop: 16, padding: 13, background: selected !== null ? `${T.gold}12` : T.surface,
        border: `1px solid ${selected !== null ? T.gold : T.border}`,
        color: selected !== null ? T.gold : T.dim, borderRadius: 8, fontSize: 12,
        fontWeight: 700, fontFamily: "monospace", cursor: selected !== null ? "pointer" : "not-allowed",
        letterSpacing: "0.08em", transition: "all 0.2s"
      }}>
        CONFIRM SELECTION · RESUME WORKFLOW →
      </button>
    </div>
  );
}

export function InventoryPlate({ onClose }: { onClose: () => void }) {
  const [sort, setSort] = useState("days");
  const statusColors: Record<string, string> = { RECON: "#eab308", AVAILABLE: T.green, SERVICE: T.blue, COSMETIC: T.purple };
  const sorted = [...INVENTORY_DATA].sort((a, b) => sort === "days" ? b.days - a.days : b.price - a.price);

  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column", padding: 24 }}>
      <PlateHeader title="INVENTORY MASTER" subtitle="5 vehicles · 4 entities · Live from BigQuery" tag="INVENTORY" onClose={onClose} />
      <div style={{ display: "flex", gap: 6, marginBottom: 16 }}>
        {["days", "price"].map(s => (
          <button key={s} onClick={() => setSort(s)} style={{ padding: "3px 10px", fontSize: 9, fontFamily: "monospace", border: `1px solid ${sort === s ? T.gold : T.border2}`, background: sort === s ? `${T.gold}10` : "transparent", color: sort === s ? T.gold : T.dim, borderRadius: 4, cursor: "pointer" }}>
            SORT: {s.toUpperCase()}
          </button>
        ))}
        <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
          {Object.entries(statusColors).map(([s, c]) => (
            <div key={s} style={{ display: "flex", alignItems: "center", gap: 4 }}>
              <div style={{ width: 5, height: 5, borderRadius: "50%", background: c }} />
              <span style={{ color: T.dim, fontSize: 8, fontFamily: "monospace" }}>{s}</span>
            </div>
          ))}
        </div>
      </div>
      <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: 8 }}>
        {sorted.map((v, i) => (
          <div key={v.vin} style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 8, padding: "12px 14px", display: "flex", alignItems: "center", gap: 16, animation: `msg-in 0.2s ${i*0.05}s both ease` }}>
            <div style={{ flex: 1 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                <span style={{ color: T.text, fontWeight: 600, fontSize: 12, fontFamily: "monospace" }}>{v.year} {v.make} {v.model}</span>
                <span style={{ color: statusColors[v.status], fontSize: 8, fontFamily: "monospace", fontWeight: 700, padding: "1px 6px", border: `1px solid ${statusColors[v.status]}44`, borderRadius: 3 }}>{v.status}</span>
              </div>
              <div style={{ display: "flex", gap: 16 }}>
                <span style={{ color: T.dim, fontSize: 9, fontFamily: "monospace" }}>VIN: {v.vin.slice(-8)}</span>
                <span style={{ color: T.dim, fontSize: 9, fontFamily: "monospace" }}>{v.color}</span>
                <span style={{ color: T.gold, fontSize: 9, fontFamily: "monospace" }}>{v.entity}</span>
              </div>
            </div>
            <div style={{ textAlign: "right" }}>
              <p style={{ color: T.text, fontSize: 14, fontWeight: 700, fontFamily: "monospace" }}>${v.price.toLocaleString()}</p>
              <p style={{ color: v.days > 20 ? "#eab308" : T.dim, fontSize: 9, fontFamily: "monospace", marginTop: 2 }}>{v.days}d on lot</p>
            </div>
          </div>
        ))}
      </div>
      <div style={{ display: "flex", gap: 10, marginTop: 14 }}>
        <div style={{ flex: 1, background: T.surface, border: `1px solid ${T.border}`, borderRadius: 6, padding: "10px 12px", textAlign: "center" }}>
          <p style={{ color: T.dim, fontSize: 8, fontFamily: "monospace" }}>TOTAL VALUE</p>
          <p style={{ color: T.text, fontSize: 14, fontWeight: 700, fontFamily: "monospace" }}>${INVENTORY_DATA.reduce((a, v) => a + v.price, 0).toLocaleString()}</p>
        </div>
        <div style={{ flex: 1, background: T.surface, border: `1px solid ${T.border}`, borderRadius: 6, padding: "10px 12px", textAlign: "center" }}>
          <p style={{ color: T.dim, fontSize: 8, fontFamily: "monospace" }}>AVG DAYS</p>
          <p style={{ color: "#eab308", fontSize: 14, fontWeight: 700, fontFamily: "monospace" }}>{Math.round(INVENTORY_DATA.reduce((a,v)=>a+v.days,0)/INVENTORY_DATA.length)}d</p>
        </div>
        <div style={{ flex: 1, background: T.surface, border: `1px solid ${T.border}`, borderRadius: 6, padding: "10px 12px", textAlign: "center" }}>
          <p style={{ color: T.dim, fontSize: 8, fontFamily: "monospace" }}>IN RECON</p>
          <p style={{ color: T.gold, fontSize: 14, fontWeight: 700, fontFamily: "monospace" }}>{INVENTORY_DATA.filter(v=>v.status!=="AVAILABLE").length}</p>
        </div>
      </div>
    </div>
  );
}

export function LogisticPlate({ onClose }: { onClose: () => void }) {
  const [eta, setEta] = useState(12);
  useEffect(() => { const t = setInterval(() => setEta(e => Math.max(0, e - 1)), 8000); return () => clearInterval(t); }, []);
  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column", padding: 24 }}>
      <PlateHeader title="LIVE DISPATCH · CARLUX" subtitle="Moaz · En route · P&D Active" tag="LOGISTICS" onClose={onClose} tagColor={T.purple} />
      <div style={{ flex: 1, background: T.surface, border: `1px solid ${T.border}`, borderRadius: 10, position: "relative", overflow: "hidden", marginBottom: 16 }}>
        <div style={{ position: "absolute", inset: 0, background: "linear-gradient(135deg, #0a0a12 0%, #080810 100%)" }}>
          {[...Array(8)].map((_, i) => <div key={`h${i}`} style={{ position: "absolute", left: 0, right: 0, top: `${i*14}%`, height: 1, background: "#ffffff08" }} />)}
          {[...Array(8)].map((_, i) => <div key={`v${i}`} style={{ position: "absolute", top: 0, bottom: 0, left: `${i*14}%`, width: 1, background: "#ffffff08" }} />)}
          <svg style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}>
            <path d="M 20% 70% Q 50% 40% 80% 25%" stroke={`${T.gold}66`} strokeWidth="2" fill="none" strokeDasharray="6 4" />
          </svg>
          <div style={{ position: "absolute", left: "45%", top: "45%", transform: "translate(-50%,-50%)" }}>
            <div style={{ width: 14, height: 14, borderRadius: "50%", background: T.gold, boxShadow: `0 0 12px ${T.gold}, 0 0 24px ${T.gold}44`, animation: "pulse-dot 2s infinite" }} />
            <div style={{ position: "absolute", top: 18, left: "50%", transform: "translateX(-50%)", whiteSpace: "nowrap", background: T.surface, border: `1px solid ${T.gold}44`, borderRadius: 4, padding: "2px 6px", color: T.gold, fontSize: 8, fontFamily: "monospace" }}>MOAZ · CARLUX</div>
          </div>
          <div style={{ position: "absolute", left: "78%", top: "22%", transform: "translate(-50%,-50%)" }}>
            <div style={{ width: 10, height: 10, borderRadius: "50%", background: T.green, boxShadow: `0 0 8px ${T.green}` }} />
            <div style={{ position: "absolute", top: 14, left: "50%", transform: "translateX(-50%)", whiteSpace: "nowrap", background: T.surface, border: `1px solid ${T.green}44`, borderRadius: 4, padding: "2px 6px", color: T.green, fontSize: 8, fontFamily: "monospace" }}>CUSTOMER</div>
          </div>
          <div style={{ position: "absolute", top: 14, right: 14, background: "#000000cc", border: `1px solid ${T.border2}`, borderRadius: 8, padding: "10px 14px", textAlign: "right" }}>
            <p style={{ color: T.dim, fontSize: 8, fontFamily: "monospace", letterSpacing: "0.1em" }}>ETA</p>
            <p style={{ color: T.text, fontSize: 22, fontWeight: 700, fontFamily: "monospace" }}>{eta}m</p>
            <p style={{ color: T.dim, fontSize: 8, fontFamily: "monospace" }}>LIVE</p>
          </div>
        </div>
      </div>
      <div style={{ display: "flex", gap: 10 }}>
        {[
          { k: "DRIVER",   v: "Moaz Sial",           c: T.text },
          { k: "VEHICLE",  v: "2023 BMW M4",          c: T.gold },
          { k: "STATUS",   v: "EN ROUTE",             c: T.green },
          { k: "DISTANCE", v: "4.2 mi remaining",     c: T.textDim },
        ].map(s => (
          <div key={s.k} style={{ flex: 1, background: T.surface, border: `1px solid ${T.border}`, borderRadius: 6, padding: "8px 10px" }}>
            <p style={{ color: T.dim, fontSize: 8, fontFamily: "monospace", marginBottom: 3 }}>{s.k}</p>
            <p style={{ color: s.c, fontSize: 11, fontFamily: "monospace", fontWeight: 600 }}>{s.v}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

export function EmptyPlate() {
  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 20 }}>
      <div style={{ opacity: 0.15 }}>
        <div style={{ width: 72, height: 72, border: `1px solid ${T.gold}`, borderRadius: 16, display: "flex", alignItems: "center", justifyContent: "center", marginBottom: 16, marginLeft: "auto", marginRight: "auto" }}>
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke={T.gold} strokeWidth="1">
            <rect x="3" y="3" width="18" height="18" rx="2" /><path d="M3 9h18M9 21V9" />
          </svg>
        </div>
        <p style={{ color: T.gold, fontSize: 11, fontFamily: "monospace", letterSpacing: "0.14em", textAlign: "center", marginBottom: 6 }}>JIT HYDRATION CANVAS</p>
        <p style={{ color: T.dim, fontSize: 10, fontFamily: "'DM Sans', sans-serif", textAlign: "center" }}>Awaiting MOUNT_PLATE event</p>
        <p style={{ color: T.muted, fontSize: 9, fontFamily: "monospace", textAlign: "center", marginTop: 6 }}>wss://autohaus.cil/ws/chat</p>
      </div>
    </div>
  );
}
