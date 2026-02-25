import React, { useState, useEffect, useRef } from 'react';
import { Send, Zap, ShieldAlert, FileText, CheckCircle2 } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';

interface ChatMessage {
    id: string;
    sender: 'user' | 'system';
    text: string;
}

interface PlatePayload {
    plate_id: string;
    intent: string;
    confidence: number;
    entities: Record<string, any>;
    dataset?: any[];
    [key: string]: any;
}

// -------------------------------------------------------------
// JIT Plates
// -------------------------------------------------------------
function PlateHydrator({ payload }: { payload: PlatePayload | null }) {
    if (!payload) return <div className="text-zinc-600 italic text-sm mt-4">Awaiting C-OS telemetry...</div>;

    switch (payload.plate_id) {
        case 'AMBIGUITY_RESOLUTION':
            return (
                <div className="mt-4 bg-amber-950/20 border border-amber-900/50 rounded-lg p-4">
                    <div className="flex items-center text-amber-500 mb-2">
                        <ShieldAlert className="w-5 h-5 mr-2" />
                        <span className="font-semibold text-sm">Ambiguity Detected</span>
                    </div>
                    <p className="text-sm text-amber-200/80 mb-3 text-balance">
                        The CIL detected collision across entities. Please clarify targets.
                    </p>
                    <div className="grid grid-cols-2 gap-2">
                        <button className="bg-zinc-900 border border-zinc-700 hover:border-amber-500 text-xs py-2 px-3 rounded transition-colors text-left flex flex-col items-center justify-center text-zinc-300">
                            <span className="font-bold">KAMM LLC</span>
                        </button>
                        <button className="bg-zinc-900 border border-zinc-700 hover:border-amber-500 text-xs py-2 px-3 rounded transition-colors text-left flex flex-col items-center justify-center text-zinc-300">
                            <span className="font-bold">Fluiditruck</span>
                        </button>
                    </div>
                </div>
            );

        case 'FINANCE_CHART':
        case 'FINANCE_DASHBOARD':
            const data = payload.dataset || [
                { name: 'Mon', revenue: 4000 },
                { name: 'Tue', revenue: 3000 },
                { name: 'Wed', revenue: 2000 },
                { name: 'Thu', revenue: 2780 },
                { name: 'Fri', revenue: 1890 },
            ];
            return (
                <div className="mt-4 bg-[#0a0a0a] border border-zinc-800 rounded-lg p-4">
                    <div className="flex items-center text-zinc-300 mb-4">
                        <Zap className="w-5 h-5 mr-2 text-gold" style={{ color: '#c5a059' }} />
                        <span className="font-semibold text-sm">Financial Telemetry Generated</span>
                    </div>
                    <div className="h-48 w-full">
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={data}>
                                <XAxis dataKey="name" stroke="#52525b" fontSize={12} tickLine={false} axisLine={false} />
                                <Tooltip cursor={{ fill: '#27272a' }} contentStyle={{ backgroundColor: '#18181b', border: '1px solid #3f3f46' }} />
                                <Bar dataKey="revenue" fill="#e11d48" radius={[4, 4, 0, 0]} />
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                </div>
            );

        case 'QUOTE_APPROVAL_PLATE':
        case 'CRM_DASHBOARD':
        case 'INVENTORY_LIST':
        case 'SERVICE_RO_PLATE':
        case 'LOGISTICS_MAP':
        case 'COMPLIANCE_ALERT':
            return (
                <div className="mt-4 bg-zinc-900 border border-zinc-800 rounded-lg p-4">
                    <div className="flex items-center text-white mb-2">
                        <FileText className="w-5 h-5 mr-2 text-zinc-400" />
                        <span className="font-semibold text-sm">{payload.plate_id.replace(/_/g, ' ')}</span>
                    </div>
                    <div className="text-xs text-zinc-400 font-mono space-y-1 mb-3">
                        <div>Intent: <span className="text-red-400">{payload.intent}</span></div>
                        <div>Confidence: <span className="text-green-400">{(payload.confidence * 100).toFixed(1)}%</span></div>
                    </div>
                    {Object.keys(payload.entities).length > 0 && (
                        <div className="bg-black rounded border border-zinc-800 p-2 text-xs text-zinc-500 font-mono">
                            {JSON.stringify(payload.entities, null, 2)}
                        </div>
                    )}
                </div>
            );

        case 'CHAT_RESPONSE':
        default:
            return null;
    }
}

// -------------------------------------------------------------
// Command Center Component
// -------------------------------------------------------------
export function CommandCenter() {
    const [messages, setMessages] = useState<ChatMessage[]>([]);
    const [input, setInput] = useState('');
    const [activePlate, setActivePlate] = useState<PlatePayload | null>(null);
    const [isConnected, setIsConnected] = useState(false);

    const wsRef = useRef<WebSocket | null>(null);
    const scrollRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        // Determine WS URL based on current host (supporting Replit / localhost)
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        // When running Vite dev server locally, route to backend port 8000
        // If proxied (e.g. via Replit), use the same host
        let wsUrl = `${protocol}//localhost:8000/ws/chat`;
        if (window.location.hostname.includes('replit')) {
            wsUrl = `${protocol}//${window.location.host}/ws/chat`;
        }

        const ws = new WebSocket(wsUrl);

        ws.onopen = () => setIsConnected(true);

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);

                if (data.type === 'WELCOME') {
                    setMessages(prev => [...prev, { id: Date.now().toString(), sender: 'system', text: data.message }]);
                } else if (data.type === 'MOUNT_PLATE') {
                    // Push text message
                    let msgText = `Resolved intent to [${data.intent}] with ${(data.confidence * 100).toFixed(1)}% confidence.`;
                    if (data.plate_id === 'AMBIGUITY_RESOLUTION') {
                        msgText = "I need clarification on the entities you requested.";
                    }
                    if (data.suggested_action) {
                        msgText += ` Suggested action: ${data.suggested_action}`;
                    }

                    setMessages(prev => [...prev, { id: Date.now().toString(), sender: 'system', text: msgText }]);
                    // Mount dynamic plate
                    setActivePlate(data);
                }
            } catch (e) {
                console.error("Failed parsing WS message", e);
            }
        };

        ws.onclose = () => setIsConnected(false);
        wsRef.current = ws;

        return () => ws.close();
    }, []);

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [messages, activePlate]);

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (!input.trim()) return;

        setMessages(prev => [...prev, { id: Date.now().toString(), sender: 'user', text: input }]);

        // In strict C-OS architecture, we simply push plaintext strings 
        // to the websocket, allowing the Backend Agentic Router to handle intent.
        if (wsRef.current && isConnected) {
            wsRef.current.send(input);
        } else {
            setMessages(prev => [...prev, { id: (Date.now() + 1).toString(), sender: 'system', text: "Error: CIL Backend disconnected." }]);
        }

        setInput('');
    };

    return (
        <div className="flex h-full gap-6">

            {/* LEFT: Central Intelligence Stream (Chat feed) */}
            <div className="flex-1 flex flex-col bg-zinc-900/50 border border-zinc-800 rounded-xl overflow-hidden shadow-2xl relative">
                <div className="h-12 border-b border-zinc-800 flex items-center px-4 justify-between bg-zinc-950">
                    <div className="flex items-center space-x-2">
                        <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`}></div>
                        <span className="text-xs font-mono text-zinc-400">wss://autohaus.cil/ws/chat</span>
                    </div>
                    <span className="text-xs font-semibold tracking-widest text-zinc-600 uppercase">Input Stream</span>
                </div>

                <div ref={scrollRef} className="flex-1 p-4 overflow-y-auto space-y-4">
                    {messages.map((msg) => (
                        <div key={msg.id} className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}>
                            <div className={`max-w-[80%] rounded-2xl px-4 py-2 ${msg.sender === 'user'
                                    ? 'bg-red-600 text-white rounded-br-none'
                                    : 'bg-zinc-800 text-zinc-200 border border-zinc-700 rounded-bl-none text-sm'
                                }`}>
                                {msg.sender === 'system' && (
                                    <div className="flex items-center mb-1 text-[10px] uppercase tracking-wider text-zinc-500 font-bold mb-1">
                                        <CheckCircle2 className="w-3 h-3 mr-1" /> Sovereign Core
                                    </div>
                                )}
                                {msg.text}
                            </div>
                        </div>
                    ))}

                    {/* Inject rendering block inside the stream context */}
                    {activePlate && msgIndexIsLatest(messages) && (
                        <div className="flex justify-start w-full pr-12">
                            <div className="w-full">
                                <PlateHydrator payload={activePlate} />
                            </div>
                        </div>
                    )}
                </div>

                <div className="p-4 bg-zinc-950 border-t border-zinc-800 shrink-0">
                    <form onSubmit={handleSubmit} className="flex relative items-center">
                        <input
                            type="text"
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            placeholder="Ask the CIL... (e.g. 'Show financials for KAMM')"
                            className="w-full bg-[#0a0a0a] border border-zinc-800 text-white rounded-full pl-5 pr-12 py-3 focus:outline-none focus:border-red-500 focus:ring-1 focus:ring-red-500 transition-all text-sm shadow-inner"
                        />
                        <button
                            type="submit"
                            disabled={!isConnected || !input.trim()}
                            className="absolute right-2 p-2 bg-red-600 hover:bg-red-500 text-white rounded-full transition-transform disabled:opacity-50 disabled:hover:bg-red-600 hover:scale-105"
                        >
                            <Send className="w-4 h-4 ml-0.5" />
                        </button>
                    </form>
                </div>
            </div>

            {/* RIGHT: JIT Hydration Canvas - Focus Mode */}
            <div className="w-1/3 min-w-[350px] bg-zinc-900 border border-zinc-800 rounded-xl flex flex-col">
                <div className="h-12 border-b border-zinc-800 flex items-center px-4 bg-zinc-950">
                    <span className="text-xs font-semibold tracking-widest text-zinc-500 uppercase">JIT Hydration Canvas</span>
                </div>
                <div className="flex-1 p-6 flex flex-col items-center justify-center relative">
                    {activePlate ? (
                        <div className="w-full h-full animate-in fade-in zoom-in duration-300">
                            <PlateHydrator payload={activePlate} />
                        </div>
                    ) : (
                        <div className="text-center opacity-30">
                            <Zap className="w-12 h-12 text-zinc-500 mx-auto mb-4" />
                            <p className="text-zinc-400 text-sm font-mono uppercase tracking-widest">Plate Awaiting Hydration</p>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

// Utility
function msgIndexIsLatest(messages: ChatMessage[]) {
    // Logic to attach the plate to the bottom of the feed could go here
    return false;
}
