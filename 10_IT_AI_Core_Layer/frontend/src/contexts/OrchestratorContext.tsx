import { createContext, useContext, useState, useEffect, useRef, useCallback } from 'react';
import type { ReactNode } from 'react';
import { z } from 'zod';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
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
    findings?: any[];
    is_corrupt?: boolean;
    validation_error?: string;
}

// ─── VALIDATION SCHEMAS ──────────────────────────────────────────────────────
const FinancePlateSchema = z.object({
    vin: z.string(),
    lender_name: z.string(),
    principal_amount: z.number(),
    interest_rate: z.number().optional(),
    maturity_date: z.string().optional()
});

const InventoryPlateSchema = z.object({
    vin: z.string(),
    make: z.string().optional(),
    model: z.string().optional(),
    status: z.string()
});

const GenericPlateSchema = z.object({
    type: z.string(),
    plate_id: z.string(),
    intent: z.string(),
    confidence: z.number(),
    entities: z.record(z.string(), z.any()),
    target_entity: z.string(),
    suggested_action: z.string(),
    strategy: z.object({
        skin: z.string(),
        urgency: z.number(),
        vibration: z.boolean(),
        overlay: z.string().nullable()
    }),
    timestamp: z.string(),
    dataset: z.array(z.any())
});

function validatePlatePayload(plateId: string, payload: unknown) {
    // 1. Initial structural check
    const baseResult = GenericPlateSchema.safeParse(payload);
    if (!baseResult.success) return baseResult;

    // 2. Type-specific internal schema check
    switch (plateId) {
        case "FINANCE_NOTE":
        case "FINANCE_CHART":
            return FinancePlateSchema.safeParse(payload);
        case "INVENTORY_TABLE":
            return InventoryPlateSchema.safeParse(payload);
        default:
            return baseResult;
    }
}

export interface ChatMessage {
    id: string | number;
    isBot: boolean;
    time: string;
    text: string | null;
    intent?: string;
    entity?: string;
    confidence?: number;
    attachments?: any[];
    findings?: any[];
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
    setMessages: React.Dispatch<React.SetStateAction<ChatMessage[]>>;
}

// ---------------------------------------------------------------------------
// Constants Mock (Aligning with Prototype)
// ---------------------------------------------------------------------------
export const USERS = {
    AHSIN: { id: "AHSIN_CEO", name: "Ahsin", role: "CEO", access: "SOVEREIGN", entities: ["ALL"] },
    MOAZ: { id: "MOAZ_LOGISTICS", name: "Moaz", role: "Logistics", access: "FIELD", entities: ["FLUIDITRUCK", "CARLUX"] },
    ASIM: { id: "ASIM_SALES", name: "Asim", role: "Sales/Ops", access: "STANDARD", entities: ["KAMM", "AUTOHAUS_SERVICES"] },
    MOHSIN: { id: "MOHSIN_OPS", name: "Mohsin", role: "Lane B Ops", access: "STANDARD", entities: ["ASTROLOGISTICS", "AUTOHAUS_SERVICES"] },
};

// ---------------------------------------------------------------------------
// Context + Default
// ---------------------------------------------------------------------------
const OrchestratorContext = createContext<OrchestratorState | null>(null);

export const useOrchestrator = () => {
    const context = useContext(OrchestratorContext);
    if (!context) throw new Error("useOrchestrator must be used within OrchestratorProvider");
    return context;
};

// ---------------------------------------------------------------------------
// Provider: Owns the WebSocket globally
// ---------------------------------------------------------------------------
export const OrchestratorProvider = ({ children }: { children: ReactNode }) => {
    const [activeSkin, setActiveSkin] = useState<SkinType>("SUPER_ADMIN");
    const [latestPlate, setLatestPlate] = useState<PlatePayload | null>(null);
    const [isConnected, setIsConnected] = useState(false);
    const [user, setUser] = useState<User>(USERS.AHSIN);
    const [mode, setMode] = useState("STANDARD");
    const [anomalyCount] = useState(1);
    const [messages, setMessages] = useState<ChatMessage[]>([{
        id: 0, isBot: true, time: "09:41",
        text: `Good morning, Ahsin. System primitives active. Neural Membrane monitoring 00_Inbox. How would you like to begin?`,
        intent: "SYSTEM", entity: "CARBON_LLC", confidence: 100
    }]);

    const wsRef = useRef<WebSocket | null>(null);

    const now = () => new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

    // ----- Haptic / Audio Feedback Engine -----
    const triggerSensoryFeedback = useCallback((strategy: UIStrategy) => {
        if (strategy.vibration && 'vibrate' in navigator) {
            navigator.vibrate([200, 100, 200]);
        }
        if (strategy.urgency >= 9) {
            try {
                const ctx = new (window.AudioContext || (window as any).webkitAudioContext)();
                const osc = ctx.createOscillator();
                const gain = ctx.createGain();
                osc.connect(gain);
                gain.connect(ctx.destination);
                osc.frequency.setValueAtTime(220, ctx.currentTime);
                osc.frequency.exponentialRampToValueAtTime(440, ctx.currentTime + 0.15);
                gain.gain.setValueAtTime(0.08, ctx.currentTime);
                gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.3);
                osc.start(ctx.currentTime);
                osc.stop(ctx.currentTime + 0.3);
            } catch { }
        }
    }, []);

    // ----- Global WebSocket Lifecycle -----
    useEffect(() => {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        let wsUrl = `${protocol}//localhost:8000/ws/chat`;
        if (window.location.hostname.includes('replit')) {
            wsUrl = `${protocol}//${window.location.host}/ws/chat`;
        }

        const ws = new WebSocket(wsUrl);

        ws.onopen = () => setIsConnected(true);

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);

                if (data.type === 'MOUNT_PLATE' && data.strategy) {
                    const validationResult = validatePlatePayload(data.plate_id, data);

                    if (!validationResult.success) {
                        console.error("Orchestrator: Plate validation failed", validationResult.error);
                        const failedPayload = {
                            ...data,
                            validation_error: validationResult.error?.issues[0]?.message || "Validation failed",
                            is_corrupt: true
                        };
                        setLatestPlate(failedPayload as any);

                        // Auto-report to backend ledger
                        const apiBase = window.location.origin;
                        fetch(`${apiBase}/api/events/render-error`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                plate_type: data.plate_id || "UNKNOWN",
                                reason: validationResult.error?.issues[0]?.message || "Schema mismatch",
                                payload_snapshot_hash: "sha256:stub",
                                target_id: data.target_id || "SYSTEM_ORPHAN"
                            })
                        }).catch(err => console.error("Failed to log render error to ledger", err));

                        return;
                    }

                    const strategy: UIStrategy = data.strategy;
                    setActiveSkin(strategy.skin as SkinType);
                    triggerSensoryFeedback(strategy);
                    setLatestPlate(data as PlatePayload);
                    return;
                }

                if (data.type === 'SYSTEM' || data.type === 'CHAT_RESPONSE') {
                    setMessages(p => [...p, {
                        id: Date.now(),
                        isBot: true,
                        time: now(),
                        text: data.message || data.text,
                        intent: data.intent,
                        entity: data.target_entity || data.entity,
                        confidence: data.confidence
                    }]);
                }
            } catch (e) {
                console.error("Orchestrator: Failed parsing WS message", e);
            }
        };

        ws.onclose = () => setIsConnected(false);
        wsRef.current = ws;

        return () => ws.close();
    }, [triggerSensoryFeedback]);

    const sendMessage = useCallback((text: string) => {
        if (wsRef.current && isConnected) {
            wsRef.current.send(JSON.stringify({ message: text }));
            setMessages(p => [...p, {
                id: Date.now(),
                isBot: false,
                time: now(),
                text: text
            }]);
        }
    }, [isConnected]);

    return (
        <OrchestratorContext.Provider value={{
            activeSkin,
            setSkin: setActiveSkin,
            latestPlate,
            setPlate: setLatestPlate,
            isConnected,
            sendMessage,
            user,
            setUser,
            mode,
            setMode,
            wsState: isConnected ? "LIVE" : "DISCONNECTED",
            anomalyCount,
            messages,
            setMessages
        }}>
            <div className={`theme-${activeSkin.toLowerCase()} w-full h-full min-h-screen transition-colors duration-300`}>
                {children}
            </div>
        </OrchestratorContext.Provider>
    );
};
