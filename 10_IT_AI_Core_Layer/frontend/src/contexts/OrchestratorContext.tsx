import { useState, useEffect, useRef, useCallback, createContext, useContext } from "react";

export const T = {
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

export interface User {
  id: string;
  name: string;
  role: string;
  access: string;
  entities: string[];
}

export interface Finding {
  zone: string;
  issue: string;
  severity: "RED" | "YELLOW" | "GREEN";
  source?: string;
  confidence: number;
}

export interface StagedFile {
  name: string;
  size: number;
  type: string;
  preview: string | null;
  raw: File;
}

export interface ChatMessage {
  id: number;
  isBot: boolean;
  time: string;
  text: string | null;
  intent?: string;
  entity?: string;
  confidence?: number;
  attachments?: StagedFile[];
  findings?: Finding[];
}

export interface OpenQuestion {
  question_id: string;
  content: string;
  owner_role: "SOVEREIGN" | "STANDARD" | "FIELD";
  source_type: "CONFLICT" | "ASSERTION" | "IEA" | "MANUAL";
  sla_hours: number;
  due_at: string;
  dependency_list: string[];
  created_at: string;
  status: "OPEN" | "ANSWERED" | "DEFERRED";
}

export interface Primitive {
  id: string;
  label: string;
  status: string;
}

export interface EntityOption {
  vin: string;
  entity: string;
  year: number;
  model: string;
  color: string;
  insurance: string;
  lot: string;
  daysOnLot: number;
}

export interface InventoryItem {
  vin: string;
  make: string;
  model: string;
  year: number;
  entity: string;
  status: string;
  days: number;
  price: number;
  color: string;
}

export const USERS: Record<string, User> = {
  AHSIN: { id: "AHSIN_CEO", name: "Ahsin", role: "CEO", access: "SOVEREIGN", entities: ["ALL"] },
  MOAZ: { id: "MOAZ_LOGISTICS", name: "Moaz", role: "Logistics", access: "FIELD", entities: ["FLUIDITRUCK", "CARLUX"] },
  ASIM: { id: "ASIM_SALES", name: "Asim", role: "Sales/Ops", access: "STANDARD", entities: ["KAMM", "AUTOHAUS_SERVICES"] },
  MOHSIN: { id: "MOHSIN_OPS", name: "Mohsin", role: "Lane B Ops", access: "STANDARD", entities: ["ASTROLOGISTICS", "AUTOHAUS_SERVICES"] },
};

export const FINANCE_DATA = [
  { week: "W1", AutoHaus: 14200, KAMM: 8400, AstroLogistics: 5100, Carlux: 3200 },
  { week: "W2", AutoHaus: 16800, KAMM: 9100, AstroLogistics: 6300, Carlux: 4100 },
  { week: "W3", AutoHaus: 13400, KAMM: 7800, AstroLogistics: 7900, Carlux: 3800 },
  { week: "W4", AutoHaus: 18900, KAMM: 11200, AstroLogistics: 5600, Carlux: 5200 },
  { week: "W5", AutoHaus: 21300, KAMM: 9800, AstroLogistics: 8200, Carlux: 4600 },
  { week: "W6", AutoHaus: 19700, KAMM: 12400, AstroLogistics: 9100, Carlux: 6100 },
];

export const TWIN_FLAGS: Finding[] = [
  { zone: "Engine Bay", issue: "Oil seepage detected — valve cover gasket", severity: "RED", source: "Mechanic Audio", confidence: 94 },
  { zone: "Subframe", issue: "Surface oxidation — minor rust present", severity: "YELLOW", source: "Gemini Veo", confidence: 88 },
  { zone: "Front Bumper", issue: "Paint chip 2cm — door ding pattern", severity: "YELLOW", source: "Visual Scribe", confidence: 91 },
  { zone: "Tires", issue: "7/32 tread depth — within acceptable range", severity: "GREEN", source: "Walk-around", confidence: 97 },
  { zone: "Interior", issue: "No anomalies detected", severity: "GREEN", source: "Visual Scribe", confidence: 99 },
  { zone: "Transmission", issue: "Fluid analysis clear — no anomalies", severity: "GREEN", source: "Fluid Analysis", confidence: 96 },
];

export const ENTITY_OPTIONS: EntityOption[] = [
  { vin: "WBA93HM0XP1234567", entity: "KAMM_LLC", year: 2023, model: "BMW M4 Competition", color: "Frozen Black", insurance: "Unified Auto-Owners — Garagekeepers", lot: "KAMM Lot A", daysOnLot: 23 },
  { vin: "WBA93HM0XP9876543", entity: "FLUIDITRUCK_LLC", year: 2023, model: "BMW M4 Competition", color: "Isle of Man Green", insurance: "Unified Auto-Owners — Fleet", lot: "Fluiditruck Bay 3", daysOnLot: 7 },
];

export const INVENTORY_DATA: InventoryItem[] = [
  { vin: "WBA93HM0XP1234567", make: "BMW", model: "M4 Competition", year: 2023, entity: "KAMM", status: "RECON", days: 23, price: 74900, color: "Frozen Black" },
  { vin: "1FTEW1EG0NFC12345", make: "Ford", model: "F-150 Raptor", year: 2022, entity: "FLUIDITRUCK", status: "AVAILABLE", days: 8, price: 62500, color: "Shadow Black" },
  { vin: "WDDGF4HB5EA123456", make: "Mercedes", model: "C300", year: 2021, entity: "AUTOHAUS_SVC", status: "SERVICE", days: 3, price: 34900, color: "Polar White" },
  { vin: "5YJSA1E26MF123456", make: "Tesla", model: "Model S Plaid", year: 2022, entity: "KAMM", status: "AVAILABLE", days: 12, price: 89900, color: "Midnight Silver" },
  { vin: "WBXYJ3C50JEJ12345", make: "BMW", model: "X5 M50i", year: 2021, entity: "ASTROLOGISTICS", status: "COSMETIC", days: 5, price: 71200, color: "Carbon Black" },
];

export const PRIMITIVES: Primitive[] = [
  { id: "identity_engine", label: "Identity Engine", status: "ACTIVE" },
  { id: "agentic_router", label: "Agentic Router", status: "ACTIVE" },
  { id: "jit_websocket", label: "JIT WebSocket", status: "ACTIVE" },
  { id: "sovereign_memory", label: "Sovereign Memory", status: "ACTIVE" },
  { id: "anomaly_monitor", label: "Anomaly Monitor", status: "ACTIVE" },
  { id: "omnichannel", label: "Omnichannel/Twilio", status: "ACTIVE" },
  { id: "customer_quotes", label: "Customer Quotes", status: "ACTIVE" },
  { id: "logistics", label: "Logistics Tracking", status: "ACTIVE" },
  { id: "crm_intake", label: "CRM Intake", status: "ACTIVE" },
  { id: "semantic_catalog", label: "Semantic Catalog", status: "ACTIVE" },
  { id: "lineage_log", label: "Lineage Log", status: "ACTIVE" },
];

export const FLOWS = {
  keywords: {
    finance: ["financ", "p&l", "revenue", "margin", "money", "kamm financials", "lane a", "show me kamm"],
    twin: ["twin", "m4", "digital twin", "bmw", "vehicle", "vin"],
    anomaly: ["anomal", "alert", "monitor", "sleep", "spike", "flag", "warning"],
    collision: ["update", "mileage", "which", "two", "both"],
    inventory: ["inventory", "stock", "lot", "fleet", "available", "vehicles"],
    logistics: ["dispatch", "driver", "track", "delivery", "carlux", "moaz", "transport"],
  } as Record<string, string[]>,
  responses: {
    finance: { text: "Running finance aggregation across all active entities. Six-week margin breakdown ready — pulling from BigQuery ledger now.", plate: "FINANCE", intent: "FINANCE", entity: "ALL_ENTITIES", confidence: 97 },
    twin: { text: "Digital Twin loaded for VIN WBA93HM0XP1234567. I'm flagging 1 RED anomaly requiring immediate attention — engine bay oil seepage. 2 YELLOW flags also active.", plate: "TWIN", intent: "INVENTORY", entity: "BMW_M4_KAMM", confidence: 94 },
    anomaly: { text: "Sleep Monitor fired 14 minutes ago. Transport cost for VIN WBA123 registered at $847 — 2.3σ above the 30-day mean of $312. Carlux dispatch via Moaz. Insurance transfer context assembled. Action required.", plate: "ANOMALY", intent: "COMPLIANCE", entity: "CARLUX_LLC", confidence: 99 },
    collision: { text: "I found two BMW M4 Competition units in inventory_master. Identity Engine cannot auto-resolve — both match your query. Collision plate mounted. Select the correct vehicle to resume workflow.", plate: "COLLISION", intent: "INVENTORY", entity: "AMBIGUOUS", confidence: 72 },
    inventory: { text: "Pulling current inventory state across KAMM, Fluiditruck, AutoHaus Services, and AstroLogistics. 5 vehicles active across 4 entities.", plate: "INVENTORY", intent: "INVENTORY", entity: "ALL_ENTITIES", confidence: 98 },
    logistics: { text: "Carlux dispatch active. Moaz is currently en route — 12 minutes from customer location. Live tracking plate mounted.", plate: "LOGISTICS", intent: "LOGISTICS", entity: "CARLUX_LLC", confidence: 96 },
  } as Record<string, { text: string; plate: string; intent: string; entity: string; confidence: number }>,
};





export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function classifyIntent(text: string): string | null {
  const lower = text.toLowerCase();
  for (const [key, words] of Object.entries(FLOWS.keywords)) {
    if (words.some((w: string) => lower.includes(w))) return key;
  }
  return null;
}

export function useTyping(text: string, speed = 14, active = true) {
  const [displayed, setDisplayed] = useState(active ? "" : text);
  const [done, setDone] = useState(!active);
  useEffect(() => {
    if (!active) { setDisplayed(text); setDone(true); return; }
    setDisplayed(""); setDone(false);
    let i = 0;
    const t = setInterval(() => {
      i++;
      setDisplayed(text.slice(0, i));
      if (i >= text.length) { clearInterval(t); setDone(true); }
    }, speed);
    return () => clearInterval(t);
  }, [text, active, speed]);
  return { displayed, done };
}

interface OrchestratorState {
  user: User;
  setUser: (u: User) => void;
  messages: ChatMessage[];
  setMessages: React.Dispatch<React.SetStateAction<ChatMessage[]>>;
  input: string;
  setInput: (s: string) => void;
  plate: string | null;
  setPlate: (p: string | null) => void;
  processing: boolean;
  mode: string;
  setMode: (m: string) => void;
  wsState: string;
  anomalyCount: number;
  stagedFiles: StagedFile[];
  setStagedFiles: React.Dispatch<React.SetStateAction<StagedFile[]>>;
  dragOver: boolean;
  setDragOver: (d: boolean) => void;
  sendMessage: (text: string, files?: StagedFile[]) => void;
  stageFiles: (rawFiles: FileList) => void;
  removeStaged: (i: number) => void;
  handleDrop: (e: React.DragEvent) => void;
  handleResolve: (vehicle: EntityOption) => void;
  handleAnomalyDecision: (type: string) => void;
  openQuestions: OpenQuestion[];
  answerQuestion: (id: string) => void;
  deferQuestion: (id: string) => void;
  chatRef: React.RefObject<HTMLDivElement | null>;
  fileInputRef: React.RefObject<HTMLInputElement | null>;
}

const OrchestratorContext = createContext<OrchestratorState | null>(null);
export const useOrchestrator = () => {
  const ctx = useContext(OrchestratorContext);
  if (!ctx) throw new Error("useOrchestrator must be used within OrchestratorProvider");
  return ctx;
};

export function OrchestratorProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User>(USERS.AHSIN);
  const [messages, setMessages] = useState<ChatMessage[]>([{
    id: 0, isBot: true, time: "09:41",
    text: `Good morning, Ahsin. All ${PRIMITIVES.length} primitives active. Anomaly monitor swept 4 minutes ago — 1 flag requires your attention. Lineage log clean. How would you like to begin?`,
    intent: "SYSTEM", entity: "CARBON_LLC", confidence: 100
  }]);
  const [input, setInput] = useState("");
  const [plate, setPlate] = useState<string | null>(null);
  const [processing, setProcessing] = useState(false);
  const [mode, setMode] = useState("STANDARD");
  const [wsState, setWsState] = useState("CONNECTING");
  const [anomalyCount] = useState(1);
  const [stagedFiles, setStagedFiles] = useState<StagedFile[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const [openQuestions, setOpenQuestions] = useState<OpenQuestion[]>([]);
  const chatRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const wsRef = useRef<WebSocket | null>(null);

  const now = () => new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

  useEffect(() => {
    chatRef.current?.scrollTo({ top: chatRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, processing]);

  useEffect(() => {
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${proto}//${window.location.host}/ws/chat`);
    wsRef.current = ws;

    ws.onopen = () => {
      setWsState("LIVE");
      ws.send(JSON.stringify({ type: "identify", user_id: user.id }));
    };
    ws.onclose = () => setWsState("CONNECTING");
    ws.onerror = () => setWsState("CONNECTING");

    ws.onmessage = (evt) => {
      try {
        const data = JSON.parse(evt.data);
        if (data.type === "MOUNT_PLATE" && data.plate_id) {
          setPlate(data.plate_id);
        }
        if (data.action === "mount_plate" && data.component) {
          setPlate(data.component);
        }
        if (data.type === "greeting" && data.text) {
          setMessages(prev => {
            const updated = [...prev];
            if (updated.length > 0 && updated[0].id === 0) {
              updated[0] = { ...updated[0], text: data.text };
            }
            return updated;
          });
        }
        if (data.type === "OPEN_QUESTION" && data.question_id) {
          const q: OpenQuestion = {
            question_id: data.question_id,
            content: data.content,
            owner_role: data.owner_role,
            source_type: data.source_type,
            sla_hours: data.sla_hours,
            due_at: data.due_at,
            dependency_list: data.dependency_list || [],
            created_at: data.created_at,
            status: "OPEN",
          };
          setOpenQuestions(prev => {
            if (prev.some(existing => existing.question_id === q.question_id)) return prev;
            return [q, ...prev];
          });
        }
      } catch { /* ignore non-JSON */ }
    };

    return () => { ws.close(); };
  }, []);

  const stageFiles = useCallback((rawFiles: FileList) => {
    const files: StagedFile[] = Array.from(rawFiles).map(f => ({
      name: f.name, size: f.size, type: f.type,
      preview: f.type.startsWith("image/") ? URL.createObjectURL(f) : null,
      raw: f,
    }));
    setStagedFiles(p => [...p, ...files].slice(0, 5));
  }, []);

  const removeStaged = (i: number) => setStagedFiles(p => p.filter((_, idx) => idx !== i));

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault(); setDragOver(false);
    if (e.dataTransfer.files?.length) stageFiles(e.dataTransfer.files);
  }, [stageFiles]);

  const sendMessage = useCallback(async (text: string, files: StagedFile[] = []) => {
    const hasText = text.trim().length > 0;
    const hasFiles = files.length > 0;
    if ((!hasText && !hasFiles) || processing) return;

    const userMsg: ChatMessage = { id: Date.now(), isBot: false, time: now(), text: hasText ? text : null, attachments: hasFiles ? files : undefined };
    setMessages(p => [...p, userMsg]);
    setInput("");
    setStagedFiles([]);
    setProcessing(true);

    if (wsRef.current?.readyState === WebSocket.OPEN && hasText) {
      wsRef.current.send(JSON.stringify({ type: "chat", text, user_id: user.id }));
    }

    if (hasFiles) {
      try {
        const formData = new FormData();
        formData.append("file", files[0].raw);
        formData.append("actor_id", user.id);
        formData.append("actor_role", user.role);

        const res = await fetch("/api/media/ingest", {
          method: "POST",
          body: formData,
        });

        if (!res.ok) {
          throw new Error("Ingestion error: " + res.statusText);
        }

        const data = await res.json();
        const numClaims = data.extracted_claims ? data.extracted_claims.length : 0;
        const textResp = `File successfully processed by CIL Extraction Engine. Extracted ${numClaims} claims. Generated Proposal ID: ${data.proposal_id}`;

        const reply: ChatMessage = {
          id: Date.now() + 1,
          isBot: true,
          time: now(),
          text: textResp,
          intent: "INGEST",
          entity: "PIPELINE",
          confidence: 100
        };
        setMessages(p => [...p, reply]);
      } catch (err: any) {
        const reply: ChatMessage = {
          id: Date.now() + 1,
          isBot: true,
          time: now(),
          text: `Error processing file: ${err.message}`,
          intent: "ERROR",
          entity: "SYSTEM",
          confidence: 0
        };
        setMessages(p => [...p, reply]);
      } finally {
        setProcessing(false);
      }
    } else {
      setTimeout(() => {
        const intent = classifyIntent(text);
        const flow = intent ? FLOWS.responses[intent] : undefined;
        let reply: ChatMessage = flow
          ? { id: Date.now() + 1, isBot: true, time: now(), text: flow.text, intent: flow.intent, entity: flow.entity, confidence: flow.confidence }
          : { id: Date.now() + 1, isBot: true, time: now(), text: "Command received and routed through the Agentic Router. Intent classified — executing via CIL.", intent: "PROCESSING", entity: "CIL", confidence: 85 };
        if (flow?.plate) setPlate(flow.plate);
        setMessages(p => [...p, reply]);
        setProcessing(false);
      }, 1100);
    }
  }, [processing, user.id, user.role]);

  const handleResolve = useCallback((vehicle: EntityOption) => {
    setMessages(p => [...p, { id: Date.now(), isBot: true, time: now(), text: `Collision resolved. Entity confirmed: ${vehicle.entity} · VIN ${vehicle.vin}. Workflow resumed. Identity Engine updated. What update would you like to apply?`, intent: "INVENTORY", entity: vehicle.entity, confidence: 100 }]);
    setPlate(null);
  }, []);

  const handleAnomalyDecision = useCallback((type: string) => {
    setTimeout(() => {
      setMessages(p => [...p, { id: Date.now(), isBot: true, time: now(), text: type === "APPROVED" ? "Anomaly approved. Transport cost logged as accepted exception. system_audit_ledger updated — AHSIN_CEO. Anomaly cleared from active queue." : "Override logged with reason. Exception recorded in system_audit_ledger with full context. Insurance team notified. Anomaly cleared.", intent: "COMPLIANCE", entity: "CARBON_LLC", confidence: 100 }]);
    }, 800);
  }, []);

  const answerQuestion = useCallback((id: string) => {
    setOpenQuestions(prev => prev.map(q => q.question_id === id ? { ...q, status: "ANSWERED" as const } : q));
    setMessages(p => [...p, {
      id: Date.now(), isBot: true, time: now(),
      text: `Open question ${id.slice(0, 8)}… marked as ANSWERED. Resolution recorded in governance ledger.`,
      intent: "GOVERNANCE", entity: "CIL", confidence: 100,
    }]);
  }, []);

  const deferQuestion = useCallback((id: string) => {
    setOpenQuestions(prev => prev.map(q => q.question_id === id ? { ...q, status: "DEFERRED" as const } : q));
    setMessages(p => [...p, {
      id: Date.now(), isBot: true, time: now(),
      text: `Open question ${id.slice(0, 8)}… deferred. SLA timer paused — will resurface on next governance sweep.`,
      intent: "GOVERNANCE", entity: "CIL", confidence: 100,
    }]);
  }, []);

  return (
    <OrchestratorContext.Provider value={{
      user, setUser, messages, setMessages, input, setInput,
      plate, setPlate, processing, mode, setMode,
      wsState, anomalyCount, stagedFiles, setStagedFiles,
      dragOver, setDragOver, sendMessage, stageFiles,
      removeStaged, handleDrop, handleResolve, handleAnomalyDecision,
      openQuestions, answerQuestion, deferQuestion,
      chatRef, fileInputRef,
    }}>
      {children}
    </OrchestratorContext.Provider>
  );
}
