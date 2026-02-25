# Replit Agent Handshake & Initialization Packet: AutoHaus C-OS v3.1

This packet contains the comprehensive instructions, code state, and architectural rules required for the Replit Agent to successfully build out the frontend (The Skin) and connect it to the existing backend (The Brain).

## 1. Project Strategy: Do We Start Over or Continue?

**DECISION:** **DO NOT START A NEW APP.**
We must continue with the existing Replit application.

**Why?**
The current backend is already wired up with the WebSocket infrastructure, the Gemini AI routing, and the BigQuery/Google Auth mock setups. The frontend already has the basic Vite + React + Tailwind scaffolding. Throwing this away means rewriting the complex `ws://` routing and API reverse-proxy wiring.

We will **REFIT** the existing frontend, ripping out the static dashboard UI and replacing it with the **Conversational Operating System (C-OS)** architecture.

---

## 2. Instructions for the Replit Agent

**PASTE THIS EXACT PROMPT INTO REPLIT:**

> "Agent, we are refactoring our existing Vite/React frontend to implement the 'Conversational Operating System (C-OS)' architecture. 
> 
> **CONTEXT:**
> The backend is a FastAPI server representing the 'Brain'. It serves a WebSocket connection (`/ws/chat`), over which it pushes **JIT Plates** (Just-In-Time UI components) and **Skin Directives** (JSON instructions on how the app should look based on the urgency of the conversation). 
> 
> **NEW MODULE:** The Brain now has **Omni-Channel Membrane Expansion (Ambient Listening)**. It monitors the Google Drive `00_Inbox` in real-time. If a file is dropped, the Brain classifies it and pushes a Plate with `origin: AMBIENT_DISCOVERY`.
> 
> **YOUR MISSION:**
> 1. Wipe the old static routing/dashboard layout. 
> 2. Implement the `OrchestratorContext` as the global state provider wrapping our app. This provider will manage the WebSocket connection to the backend and handle dynamic CSS variable injection.
> 3. Create the `CommandCenter.tsx` page to serve as the unified chat interface + JIT Plate mounting zone.
> 4. Ensure Tailwind CSS is configured to support the dynamic theme variables.
> 
> Here is the specific code you need to implement. Follow these files exactly."

---

## 3. The Core Code Payload for Replit

### FILE 1: `src/contexts/OrchestratorContext.tsx`

```tsx
import { createContext, useContext, useState, useEffect, useRef, useCallback } from 'react';
import type { ReactNode } from 'react';

export type SkinType = "SUPER_ADMIN" | "FIELD_DIAGNOSTIC" | "CLIENT_HANDSHAKE" | "GHOST" | "AMBIENT_RECON";

export interface UIStrategy {
    skin: SkinType;
    urgency: number;
    vibration: boolean;
    overlay: string | null;
}

export interface PlatePayload {
    type: string;
    plate_id: string;
    intent: string;
    confidence: number;
    entities: Record<string, any>;
    target_entity: string;
    suggested_action: string;
    strategy: UIStrategy;
    timestamp: string;
    dataset: any[];
    origin?: string;
}

export interface ChatMessage {
    id: string | number;
    isBot: boolean;
    time: string;
    text: string | null;
    intent?: string;
    entity?: string;
    confidence?: number;
}

interface User {
    id: string;
    name: string;
    role: string;
    access: string;
    entities: string[];
}

interface OrchestratorState {
    activeSkin: SkinType;
    setSkin: (skin: SkinType) => void;
    latestPlate: PlatePayload | null;
    setPlate: (plate: PlatePayload | null) => void;
    isConnected: boolean;
    sendMessage: (text: string) => void;
    user: User;
    setUser: (user: User) => void;
    mode: string;
    setMode: (mode: string) => void;
    wsState: string;
    anomalyCount: number;
    messages: ChatMessage[];
}

export const USERS = {
    AHSIN: { id: "AHSIN_CEO", name: "Ahsin", role: "CEO", access: "SOVEREIGN", entities: ["ALL"] },
    MOAZ: { id: "MOAZ_LOGISTICS", name: "Moaz", role: "Logistics", access: "FIELD", entities: ["FLUIDITRUCK", "CARLUX"] },
};

const OrchestratorContext = createContext<OrchestratorState | null>(null);

export const useOrchestrator = () => {
    const context = useContext(OrchestratorContext);
    if (!context) throw new Error("useOrchestrator must be used within OrchestratorProvider");
    return context;
};

export const OrchestratorProvider = ({ children }: { children: ReactNode }) => {
    const [activeSkin, setActiveSkin] = useState<SkinType>("SUPER_ADMIN");
    const [latestPlate, setLatestPlate] = useState<PlatePayload | null>(null);
    const [isConnected, setIsConnected] = useState(false);
    const [user, setUser] = useState<User>(USERS.AHSIN);
    const [mode, setMode] = useState("STANDARD");
    const [messages, setMessages] = useState<ChatMessage[]>([{
        id: 0, isBot: true, time: "09:41",
        text: "AutoHaus C-OS v3.1 Online. Standing by for strategic directives.",
        intent: "SYSTEM", entity: "CARBON_LLC", confidence: 100
    }]);

    const wsRef = useRef<WebSocket | null>(null);

    useEffect(() => {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        let wsUrl = `${protocol}//${window.location.host}/ws/chat`;
        const ws = new WebSocket(wsUrl);

        ws.onopen = () => setIsConnected(true);
        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (data.type === 'MOUNT_PLATE') {
                    setLatestPlate(data);
                    if (data.strategy?.skin) setActiveSkin(data.strategy.skin);
                }
                if (data.type === 'SYSTEM' || data.type === 'CHAT_RESPONSE') {
                    setMessages(p => [...p, {
                        id: Date.now(),
                        isBot: true,
                        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
                        text: data.message || data.text,
                        intent: data.intent,
                        entity: data.entity,
                        confidence: data.confidence
                    }]);
                }
            } catch (e) { console.error(e); }
        };
        ws.onclose = () => setIsConnected(false);
        wsRef.current = ws;
        return () => ws.close();
    }, []);

    const sendMessage = (text: string) => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({ message: text }));
            setMessages(p => [...p, { id: Date.now(), isBot: false, text, time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) }]);
        }
    };

    return (
        <OrchestratorContext.Provider value={{
            activeSkin, setSkin: setActiveSkin, latestPlate, setPlate: setLatestPlate,
            isConnected, sendMessage, user, setUser, mode, setMode, 
            wsState: isConnected ? "LIVE" : "OFFLINE", anomalyCount: 1, messages
        }}>
            <div className={`theme-${activeSkin.toLowerCase()} w-full h-full min-h-screen transition-colors duration-300`}>
                {children}
            </div>
        </OrchestratorContext.Provider>
    );
};
```

### FILE 2: `src/pages/CommandCenter.tsx`

```tsx
import { useState, useEffect, useRef } from 'react';
import { Send, Zap, FileText, CheckCircle2 } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { useOrchestrator, USERS, ChatMessage as ChatMessageType, PlatePayload } from '../contexts/OrchestratorContext';
import { clsx } from 'clsx';

const T = { gold: "#C5A059", blue: "#3b82f6", green: "#22c55e" };

function ChatMessage({ msg, user }: { msg: ChatMessageType, user: any }) {
    return (
        <div className={clsx("flex flex-col mb-5", msg.isBot ? "items-start" : "items-end")}>
            <div className="flex items-center gap-2 mb-1.5 font-mono text-[10px] text-zinc-500">
                {msg.isBot ? <span>CIL Chief of Staff</span> : <span>{user.name}</span>}
            </div>
            <div className={clsx("max-w-[85%] px-4 py-2.5 rounded-xl text-sm transition-all", 
                msg.isBot ? "bg-zinc-900 border border-zinc-800 text-zinc-200 rounded-tl-none" : "bg-gold/10 border border-gold/30 text-zinc-100 rounded-tr-none")}>
                {msg.text}
            </div>
            <div className="mt-1 text-[9px] text-zinc-600 font-mono">{msg.time}</div>
        </div>
    );
}

export function CommandCenter() {
    const { user, messages, latestPlate, setPlate, sendMessage, isConnected, wsState, mode, setMode, setUser } = useOrchestrator();
    const [input, setInput] = useState("");
    const chatRef = useRef<HTMLDivElement>(null);

    useEffect(() => { chatRef.current?.scrollTo({ top: chatRef.current.scrollHeight, behavior: "smooth" }); }, [messages]);

    const handleSend = (e: React.FormEvent) => {
        e.preventDefault();
        if (input.trim() && isConnected) { sendMessage(input); setInput(""); }
    };

    return (
        <div className="flex flex-col h-screen w-full bg-black font-sans overflow-hidden">
            {/* Status Bar */}
            <div className="h-11 bg-zinc-900 border-b border-zinc-800 flex items-center px-5 shrink-0 justify-between">
                <div className="flex items-center gap-2.5">
                    <div className="w-1.5 h-1.5 rounded-full bg-gold shadow-[0_0_8px_#C5A059]" />
                    <span className="text-gold font-mono font-bold text-xs tracking-widest uppercase">AutoHaus C-OS</span>
                </div>
                <div className="flex items-center gap-4">
                    <div className={clsx("text-[9px] font-mono", isConnected ? "text-green-500" : "text-red-500")}>WS {wsState}</div>
                    <select value={user.id} onChange={e => setUser(Object.values(USERS).find(u => u.id === e.target.value) || USERS.AHSIN)} className="bg-zinc-800 text-zinc-300 text-[10px] px-2 py-1 rounded outline-none border border-zinc-700 font-mono">
                        {Object.values(USERS).map(u => <option key={u.id} value={u.id}>{u.name} · {u.role}</option>)}
                    </select>
                </div>
            </div>

            <div className="flex flex-1 overflow-hidden">
                {/* Chat Panel */}
                <div className={clsx("flex flex-col border-r border-zinc-800 transition-all duration-500", latestPlate ? "w-[40%]" : "w-[60%]")}>
                    <div ref={chatRef} className="flex-1 overflow-y-auto p-6 space-y-2">
                        {messages.map((msg) => <ChatMessage key={msg.id} msg={msg} user={user} />)}
                    </div>
                    <form onSubmit={handleSend} className="p-5 bg-zinc-900/50 border-t border-zinc-800 flex items-center gap-3">
                        <input value={input} onChange={e => setInput(e.target.value)} placeholder="Command the CIL..." className="flex-1 bg-black border border-zinc-800 rounded-xl px-4 py-2.5 text-sm text-white focus:border-gold/40 outline-none font-mono" />
                        <button type="submit" disabled={!isConnected} className="p-2.5 bg-gold/10 text-gold rounded-xl hover:bg-gold/20 disabled:opacity-30 transition-all"><Send className="w-4 h-4" /></button>
                    </form>
                </div>

                {/* Canvas Panel */}
                <div className="flex-1 bg-zinc-950/20 relative">
                    {latestPlate ? (
                        <div className="p-8 h-full flex flex-col">
                            <div className="flex justify-between items-start border-b border-zinc-800 pb-4 mb-6">
                                <div>
                                    <span className="text-[9px] font-mono font-bold text-gold px-2 py-0.5 border border-gold/30 rounded bg-gold/5">{latestPlate.plate_id}</span>
                                    <h2 className="text-white font-bold mt-2 tracking-wide uppercase text-sm font-mono">{latestPlate.intent}</h2>
                                </div>
                                <button onClick={() => setPlate(null)} className="text-zinc-600 hover:text-white">✕</button>
                            </div>
                            <div className="flex-1 bg-zinc-900/40 rounded-xl border border-zinc-800 p-6">
                                <p className="text-zinc-400 text-[10px] uppercase font-mono mb-2">Findings / Suggested Action</p>
                                <p className="text-zinc-100 text-sm leading-relaxed">{latestPlate.suggested_action || "Processing ambient discovery..."}</p>
                                <div className="mt-8 grid grid-cols-1 gap-3">
                                    {latestPlate.entities && Object.entries(latestPlate.entities).map(([k, v]) => (
                                        <div key={k} className="flex justify-between border-b border-zinc-800/50 py-2">
                                            <span className="text-zinc-500 font-mono text-[10px] uppercase">{k}</span>
                                            <span className="text-zinc-300 font-mono text-[10px]">{String(v)}</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </div>
                    ) : (
                        <div className="h-full flex flex-col items-center justify-center opacity-20">
                            <Zap className="w-12 h-12 text-gold mb-4" />
                            <p className="text-gold font-mono text-[10px] tracking-[0.2em]">JIT HYDRATION CANVAS</p>
                        </div>
                    )}
                </div>
            </div>
            
            {/* Primitives Footer */}
            <div className="h-8 bg-zinc-900 border-t border-zinc-800 flex items-center px-5 gap-6">
                {["identity_engine", "agentic_router", "sovereign_memory", "drive_ear"].map(p => (
                    <div key={p} className="flex items-center gap-1.5">
                        <div className="w-1 h-1 rounded-full bg-green-500/60" />
                        <span className="text-[8px] font-mono text-zinc-500 uppercase">{p}</span>
                    </div>
                ))}
            </div>
        </div>
    );
}
```

### FILE 3: `src/index.css`

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  :root {
    --bg-primary: #080808;
    --bg-card: #0f0f0f;
    --text-primary: #e8e8e8;
    --brand-border: #1c1c1c;
    --accent-primary: #C5A059;
  }
  .theme-super_admin { --bg-primary: #080808; --accent-primary: #C5A059; }
  .theme-field_diagnostic { --bg-primary: #190505; --accent-primary: #f87171; }
  .theme-ambient_recon { --bg-primary: #080810; --accent-primary: #a78bfa; }
}

@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap');

body {
  @apply bg-[#080808] text-[#e8e8e8] antialiased;
  margin: 0;
  height: 100vh;
  font-family: 'DM Sans', sans-serif;
}

::-webkit-scrollbar { width: 3px; }
::-webkit-scrollbar-thumb { background: #2a2a2a; border-radius: 2px; }
```

### FILE 4: `src/App.tsx`

```tsx
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { CommandCenter } from './pages/CommandCenter';
import { OrchestratorProvider } from './contexts/OrchestratorContext';
import './index.css';

function App() {
  return (
    <OrchestratorProvider>
      <Router>
        <Routes>
          <Route path="/" element={<CommandCenter />} />
          <Route path="*" element={<CommandCenter />} />
        </Routes>
      </Router>
    </OrchestratorProvider>
  );
}
export default App;
```

---

## 4. Replit Secrets Checklist (MANDATORY)

Add these secrets to the Replit **Secrets** tab:

| Secret Name | Value |
| :--- | :--- |
| `GEMINI_API_KEY` | `REDACTED_USE_REPLIT_SECRET` |
| `GCP_SERVICE_ACCOUNT_JSON` | `REDACTED_USE_SERVICE_ACCOUNT_SECRET` |
| `GITHUB_PAT` | `REDACTED_USE_GITHUB_PAT_SECRET` |
