import { useState, useEffect, useRef, useCallback } from 'react';
import { Send, Zap, ShieldAlert, FileText, CheckCircle2, ChevronRight, MapPin, Clock, DollarSign, Package } from 'lucide-react';
import { AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { useOrchestrator, USERS, ChatMessage as ChatMessageType, PlatePayload } from '../contexts/OrchestratorContext';
import { clsx } from 'clsx';

// ─── DESIGN TOKENS (Shared with context) ──────────────────────────────────
const T = {
    bg: "#080808",
    surface: "#0f0f0f",
    elevated: "#141414",
    border: "#1c1c1c",
    border2: "#242424",
    gold: "#C5A059",
    goldDim: "#8a6d3b",
    red: "#E30613",
    green: "#22c55e",
    blue: "#3b82f6",
    purple: "#a78bfa",
    dim: "#525252",
    muted: "#3a3a3a",
    text: "#e8e8e8",
    textDim: "#888888",
};

// ─── MOCK DATA (Baseline for Demo) ──────────────────────────────────────────
const FINANCE_DATA = [
    { week: "W1", AutoHaus: 14200, KAMM: 8400, AstroLogistics: 5100, Carlux: 3200 },
    { week: "W2", AutoHaus: 16800, KAMM: 9100, AstroLogistics: 6300, Carlux: 4100 },
    { week: "W3", AutoHaus: 13400, KAMM: 7800, AstroLogistics: 7900, Carlux: 3800 },
    { week: "W4", AutoHaus: 18900, KAMM: 11200, AstroLogistics: 5600, Carlux: 5200 },
    { week: "W5", AutoHaus: 21300, KAMM: 9800, AstroLogistics: 8200, Carlux: 4600 },
    { week: "W6", AutoHaus: 19700, KAMM: 12400, AstroLogistics: 9100, Carlux: 6100 },
];

const TWIN_FLAGS = [
    { zone: "Engine Bay", issue: "Oil seepage detected — valve cover gasket", severity: "RED", source: "Mechanic Audio", confidence: 94 },
    { zone: "Subframe", issue: "Surface oxidation — minor rust present", severity: "YELLOW", source: "Gemini Veo", confidence: 88 },
    { zone: "Front Bumper", issue: "Paint chip 2cm — door ding pattern", severity: "YELLOW", source: "Visual Scribe", confidence: 91 },
    { zone: "Tires", issue: "7/32 tread depth — within acceptable range", severity: "GREEN", source: "Walk-around", confidence: 97 },
];

const PRIMITIVES = [
    { id: "identity_engine", label: "Identity Engine", status: "ACTIVE" },
    { id: "agentic_router", label: "Agentic Router", status: "ACTIVE" },
    { id: "jit_websocket", label: "JIT WebSocket", status: "ACTIVE" },
    { id: "sovereign_memory", label: "Sovereign Memory", status: "ACTIVE" },
    { id: "anomaly_monitor", label: "Anomaly Monitor", status: "ACTIVE" },
    { id: "drive_ear", label: "Drive Ear (Neural Membrane)", status: "ACTIVE" },
];

// ─── HELPER COMPONENTS ───────────────────────────────────────────────────────
function Tag({ label, color }: { label: string, color: string }) {
    return (
        <span style={{ fontSize: 8, fontFamily: "monospace", fontWeight: 700, letterSpacing: "0.08em", color, padding: "1px 6px", border: `1px solid ${color}33`, borderRadius: 3, background: `${color}0a` }}>
            {label}
        </span>
    );
}

function KV({ k, v, mono, color }: { k: string, v: string, mono?: boolean, color?: string }) {
    return (
        <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
            <span style={{ color: T.dim, fontSize: 9, fontFamily: "monospace" }}>{k}</span>
            <span style={{ color: color || T.textDim, fontSize: 9, fontFamily: mono ? "monospace" : "inherit" }}>{v}</span>
        </div>
    );
}

function ActionBtn({ label, color, onClick }: { label: string, color: string, onClick?: () => void }) {
    return (
        <button onClick={onClick} style={{ flex: 1, padding: "10px 0", background: `${color}0f`, border: `1px solid ${color}44`, color, borderRadius: 8, fontSize: 10, fontWeight: 700, fontFamily: "monospace", cursor: "pointer", letterSpacing: "0.06em", transition: "all 0.15s" }}>
            {label}
        </button>
    );
}

// ─── CHAT MESSAGE ────────────────────────────────────────────────────────────
function ChatMessage({ msg, isLatest, user }: { msg: ChatMessageType, isLatest: boolean, user: any }) {
    const isBot = msg.isBot;
    return (
        <div className={clsx("flex flex-col mb-5 animate-in fade-in slide-in-from-bottom-2", isBot ? "items-start" : "items-end")}>
            <div className="flex items-center gap-2 mb-1.5">
                {isBot ? (
                    <>
                        <div className="w-5 h-5 rounded-full bg-gold/10 border border-gold/30 flex items-center justify-center">
                            <span className="text-[7px] text-gold font-bold">CIL</span>
                        </div>
                        <span className="text-[10px] text-zinc-500 font-mono">Chief of Staff</span>
                        {msg.intent && <Tag label={msg.intent} color={T.blue} />}
                        {msg.confidence && <Tag label={`${(msg.confidence * 100).toFixed(0)}%`} color={T.green} />}
                    </>
                ) : (
                    <>
                        <span className="text-[10px] text-zinc-500 font-mono">{user.name}</span>
                        <Tag label={user.access} color={user.access === "SOVEREIGN" ? T.gold : T.blue} />
                    </>
                )}
            </div>
            <div className={clsx(
                "max-w-[85%] px-3.5 py-2.5 rounded-xl text-sm leading-relaxed",
                isBot ? "bg-zinc-900 border border-zinc-800 text-zinc-200 rounded-tl-none" : "bg-gold/10 border border-gold/30 text-zinc-100 rounded-tr-none"
            )}>
                {msg.text}
            </div>
            <div className="mt-1 text-[9px] text-zinc-600 font-mono">{msg.time}</div>
        </div>
    );
}

// ─── STATUS BAR ─────────────────────────────────────────────────────────────
function StatusBar() {
    const { user, wsState, anomalyCount, mode, setMode, setUser } = useOrchestrator();
    const [time, setTime] = useState(new Date());
    useEffect(() => { const t = setInterval(() => setTime(new Date()), 1000); return () => clearInterval(t); }, []);

    const modeColors: Record<string, string> = { STANDARD: T.gold, FIELD: "#3b82f6", AMBIENT: T.dim };

    return (
        <div className="h-11 bg-zinc-900 border-b border-zinc-800 flex items-center px-5 gap-0 flex-shrink-0 relative z-50">
            <div className="flex items-center gap-2.5 mr-7 border-r border-zinc-800 pr-7">
                <div className="w-1.5 h-1.5 rounded-full bg-gold shadow-[0_0_8px_#C5A059]" />
                <span className="text-gold font-mono font-bold text-xs tracking-widest">AUTOHAUS</span>
                <span className="text-zinc-600 text-[10px] font-mono">C-OS v3.1</span>
            </div>

            <div className="flex items-center gap-5 flex-1">
                <div className="flex items-center gap-1.5">
                    <div className={clsx("w-1 h-1 rounded-full", wsState === "LIVE" ? "bg-green-500" : "bg-red-500")} />
                    <span className={clsx("text-[9px] font-mono font-bold", wsState === "LIVE" ? "text-green-500" : "text-red-500")}>WS {wsState}</span>
                </div>
                <div className="flex gap-1">
                    {["STANDARD", "FIELD", "AMBIENT"].map(m => (
                        <button key={m} onClick={() => setMode(m)} className={clsx(
                            "px-2 py-0.5 text-[9px] font-mono font-bold border rounded transition-all",
                            mode === m ? "border-gold/40 bg-gold/10 text-gold" : "border-zinc-800 text-zinc-600"
                        )}>{m}</button>
                    ))}
                </div>
            </div>

            <div className="flex items-center gap-4 border-l border-zinc-800 pl-5">
                <select
                    value={user.id}
                    onChange={e => setUser(Object.values(USERS).find(u => u.id === e.target.value) || USERS.AHSIN)}
                    className="bg-zinc-800 border border-zinc-700 text-zinc-300 text-[10px] font-mono px-2 py-1 rounded cursor-pointer outline-none"
                >
                    {Object.values(USERS).map(u => <option key={u.id} value={u.id}>{u.name} · {u.role}</option>)}
                </select>
                <span className="text-zinc-500 text-[10px] font-mono w-16">{time.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}</span>
            </div>
        </div>
    );
}

// ─── PLATES ────────────────────────────────────────────────────────────────
function FinancePlate({ payload, onClose }: { payload: PlatePayload, onClose: () => void }) {
    return (
        <div className="h-full flex flex-col p-6 overflow-hidden">
            <div className="flex justify-between items-start mb-6 border-b border-zinc-800 pb-4">
                <div>
                    <Tag label="FINANCE" color={T.blue} />
                    <h2 className="text-white text-sm font-bold font-mono tracking-wider mt-2">FINANCE AGGREGATE</h2>
                    <p className="text-zinc-500 text-[11px] mt-1">Consolidated entity P&L · 6-week rolling</p>
                </div>
                <button onClick={onClose} className="text-zinc-600 hover:text-zinc-400">✕</button>
            </div>
            <div className="flex-1 min-h-0">
                <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={FINANCE_DATA}>
                        <defs>
                            <linearGradient id="colorAH" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="5%" stopColor={T.gold} stopOpacity={0.3} />
                                <stop offset="95%" stopColor={T.gold} stopOpacity={0} />
                            </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="#1c1c1c" />
                        <XAxis dataKey="week" stroke="#525252" fontSize={10} />
                        <YAxis stroke="#525252" fontSize={10} tickFormatter={v => `$${v / 1000}k`} />
                        <Tooltip contentStyle={{ background: '#0a0a0a', border: '1px solid #1c1c1c' }} />
                        <Area type="monotone" dataKey="AutoHaus" stroke={T.gold} fillOpacity={1} fill="url(#colorAH)" strokeWidth={2} />
                    </AreaChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
}

function GenericPlate({ payload, onClose }: { payload: PlatePayload, onClose: () => void }) {
    return (
        <div className="h-full flex flex-col p-6">
            <div className="flex justify-between items-start mb-6 border-b border-zinc-800 pb-4">
                <div>
                    <Tag label={payload.intent || "SYSTEM"} color={T.gold} />
                    <h2 className="text-white text-sm font-bold font-mono tracking-wider mt-2">{payload.plate_id.replace(/_/g, ' ')}</h2>
                    <p className="text-zinc-500 text-[11px] mt-1">{payload.target_entity || "Active Discovery"}</p>
                </div>
                <button onClick={onClose} className="text-zinc-600 hover:text-zinc-400">✕</button>
            </div>
            <div className="flex-1 overflow-auto space-y-4">
                <div className="p-4 bg-zinc-900 border border-zinc-800 rounded-lg">
                    <p className="text-zinc-400 text-xs font-mono mb-2 uppercase tracking-widest text-[10px]">Suggested Action</p>
                    <p className="text-zinc-100 text-sm">{payload.suggested_action}</p>
                </div>
                <div className="p-4 bg-black border border-zinc-800 rounded flex flex-col gap-2 font-mono text-[11px]">
                    {payload.entities && Object.entries(payload.entities).map(([k, v]) => (
                        <KV key={k} k={k.toUpperCase()} v={String(v)} />
                    ))}
                </div>
            </div>
        </div>
    );
}

// ─── MAIN COMPONENT ──────────────────────────────────────────────────────────
export function CommandCenter() {
    const { user, mode, messages, latestPlate, setPlate, sendMessage, isConnected } = useOrchestrator();
    const [input, setInput] = useState("");
    const chatRef = useRef<HTMLDivElement>(null);

    useEffect(() => { chatRef.current?.scrollTo({ top: chatRef.current.scrollHeight, behavior: "smooth" }); }, [messages]);

    const handleSend = (e?: React.FormEvent) => {
        e?.preventDefault();
        if (!input.trim() || !isConnected) return;
        sendMessage(input);
        setInput("");
    };

    const renderPlate = () => {
        if (!latestPlate) return (
            <div className="h-full flex flex-col items-center justify-center opacity-20 select-none">
                <Zap className="w-12 h-12 text-gold mb-4" />
                <p className="text-gold font-mono text-[10px] tracking-[0.2em]">JIT HYDRATION CANVAS</p>
                <p className="text-zinc-500 text-[9px] mt-2">Awaiting MOUNT_PLATE event</p>
            </div>
        );

        if (latestPlate.plate_id === 'FINANCE_CHART' || latestPlate.plate_id === 'FINANCE') {
            return <FinancePlate payload={latestPlate} onClose={() => setPlate(null)} />;
        }

        return <GenericPlate payload={latestPlate} onClose={() => setPlate(null)} />;
    };

    return (
        <div className="flex flex-col h-screen w-full bg-black font-sans overflow-hidden">
            <StatusBar />

            <div className="flex flex-1 overflow-hidden">
                {/* LEFT: CONVERSATION */}
                <div className={clsx(
                    "flex flex-col border-r border-zinc-800 transition-all duration-500 ease-out",
                    latestPlate ? "w-[40%]" : "w-[60%]"
                )}>
                    {/* Quick Commands */}
                    <div className="p-4 flex gap-2 border-b border-zinc-800 overflow-x-auto whitespace-nowrap scrollbar-none">
                        {["Show Financials", "Inventory Status", "Check Anomalies"].map(cmd => (
                            <button
                                key={cmd}
                                onClick={() => sendMessage(cmd)}
                                className="px-3 py-1.5 border border-zinc-800 rounded-full text-[10px] font-mono text-zinc-500 hover:border-gold/50 hover:text-gold transition-colors"
                            >
                                {cmd}
                            </button>
                        ))}
                    </div>

                    <div ref={chatRef} className="flex-1 overflow-y-auto p-6 space-y-2">
                        {messages.map((msg, i) => (
                            <ChatMessage key={msg.id} msg={msg} isLatest={i === messages.length - 1} user={user} />
                        ))}
                    </div>

                    {/* Input */}
                    <div className="p-5 bg-zinc-900/50 backdrop-blur-md border-t border-zinc-800">
                        <form onSubmit={handleSend} className="relative flex items-center bg-zinc-950 border border-zinc-800 rounded-xl focus-within:border-gold/40 transition-colors">
                            <input
                                value={input}
                                onChange={e => setInput(e.target.value)}
                                placeholder={`Command the CIL, ${user.name}...`}
                                className="flex-1 bg-transparent px-4 py-3 text-sm text-zinc-100 placeholder:text-zinc-700 outline-none font-mono"
                            />
                            <button
                                type="submit"
                                disabled={!input.trim() || !isConnected}
                                className="mr-2 p-2 bg-gold/10 text-gold rounded-lg hover:bg-gold/20 disabled:opacity-30 transition-all"
                            >
                                <Send className="w-4 h-4" />
                            </button>
                        </form>
                    </div>
                </div>

                {/* RIGHT: PLATE VIEWPORT */}
                <div className="flex-1 bg-zinc-950/20 relative overflow-hidden">
                    {renderPlate()}
                </div>
            </div>

            {/* Primitives Footer */}
            <div className="h-8 bg-zinc-900 border-t border-zinc-800 flex items-center px-5 gap-6">
                {PRIMITIVES.map(p => (
                    <div key={p.id} className="flex items-center gap-1.5">
                        <div className="w-1 h-1 rounded-full bg-green-500/60" />
                        <span className="text-[8px] font-mono text-zinc-500 uppercase tracking-wider">{p.label}</span>
                    </div>
                ))}
            </div>
        </div>
    );
}
