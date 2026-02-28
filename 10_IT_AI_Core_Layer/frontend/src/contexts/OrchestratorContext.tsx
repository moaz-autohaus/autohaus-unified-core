import { useState, useEffect, useRef, useCallback, createContext, useContext } from "react";

export const T = {
  bg:       "#080808",
  surface:  "#0f0f0f",
  elevated: "#141414",
  border:   "#1c1c1c",
  border2:  "#242424",
  gold:     "#C5A059",
  goldDim:  "#8a6d3b",
  red:      "#E30613",
  green:    "#22c55e",
  blue:     "#3b82f6",
  purple:   "#a78bfa",
  dim:      "#525252",
  muted:    "#3a3a3a",
  text:     "#e8e8e8",
  textDim:  "#888888",
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
  AHSIN:  { id: "AHSIN_CEO",       name: "Ahsin",  role: "CEO",       access: "SOVEREIGN",  entities: ["ALL"] },
  MOAZ:   { id: "MOAZ_LOGISTICS",  name: "Moaz",   role: "Logistics", access: "FIELD",      entities: ["FLUIDITRUCK","CARLUX"] },
  ASIM:   { id: "ASIM_SALES",      name: "Asim",   role: "Sales/Ops", access: "STANDARD",   entities: ["KAMM","AUTOHAUS_SERVICES"] },
  MOHSIN: { id: "MOHSIN_OPS",      name: "Mohsin", role: "Lane B Ops",access: "STANDARD",   entities: ["ASTROLOGISTICS","AUTOHAUS_SERVICES"] },
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
  { zone: "Engine Bay",   issue: "Oil seepage detected — valve cover gasket",     severity: "RED",    source: "Mechanic Audio", confidence: 94 },
  { zone: "Subframe",     issue: "Surface oxidation — minor rust present",         severity: "YELLOW", source: "Gemini Veo",     confidence: 88 },
  { zone: "Front Bumper", issue: "Paint chip 2cm — door ding pattern",             severity: "YELLOW", source: "Visual Scribe",  confidence: 91 },
  { zone: "Tires",        issue: "7/32 tread depth — within acceptable range",     severity: "GREEN",  source: "Walk-around",    confidence: 97 },
  { zone: "Interior",     issue: "No anomalies detected",                           severity: "GREEN",  source: "Visual Scribe",  confidence: 99 },
  { zone: "Transmission", issue: "Fluid analysis clear — no anomalies",            severity: "GREEN",  source: "Fluid Analysis", confidence: 96 },
];

export const ENTITY_OPTIONS: EntityOption[] = [
  { vin: "WBA93HM0XP1234567", entity: "KAMM_LLC",        year: 2023, model: "BMW M4 Competition", color: "Frozen Black",      insurance: "Unified Auto-Owners — Garagekeepers", lot: "KAMM Lot A", daysOnLot: 23 },
  { vin: "WBA93HM0XP9876543", entity: "FLUIDITRUCK_LLC", year: 2023, model: "BMW M4 Competition", color: "Isle of Man Green", insurance: "Unified Auto-Owners — Fleet",         lot: "Fluiditruck Bay 3", daysOnLot: 7 },
];

export const INVENTORY_DATA: InventoryItem[] = [
  { vin: "WBA93HM0XP1234567", make: "BMW",     model: "M4 Competition", year: 2023, entity: "KAMM",            status: "RECON",    days: 23, price: 74900, color: "Frozen Black" },
  { vin: "1FTEW1EG0NFC12345", make: "Ford",    model: "F-150 Raptor",   year: 2022, entity: "FLUIDITRUCK",     status: "AVAILABLE",days: 8,  price: 62500, color: "Shadow Black" },
  { vin: "WDDGF4HB5EA123456", make: "Mercedes",model: "C300",           year: 2021, entity: "AUTOHAUS_SVC",    status: "SERVICE",  days: 3,  price: 34900, color: "Polar White" },
  { vin: "5YJSA1E26MF123456", make: "Tesla",   model: "Model S Plaid",  year: 2022, entity: "KAMM",            status: "AVAILABLE",days: 12, price: 89900, color: "Midnight Silver" },
  { vin: "WBXYJ3C50JEJ12345", make: "BMW",     model: "X5 M50i",        year: 2021, entity: "ASTROLOGISTICS",  status: "COSMETIC", days: 5,  price: 71200, color: "Carbon Black" },
];

export const PRIMITIVES: Primitive[] = [
  { id: "identity_engine",   label: "Identity Engine",    status: "ACTIVE" },
  { id: "agentic_router",    label: "Agentic Router",     status: "ACTIVE" },
  { id: "jit_websocket",     label: "JIT WebSocket",      status: "ACTIVE" },
  { id: "sovereign_memory",  label: "Sovereign Memory",   status: "ACTIVE" },
  { id: "anomaly_monitor",   label: "Anomaly Monitor",    status: "ACTIVE" },
  { id: "omnichannel",       label: "Omnichannel/Twilio", status: "ACTIVE" },
  { id: "customer_quotes",   label: "Customer Quotes",    status: "ACTIVE" },
  { id: "logistics",         label: "Logistics Tracking", status: "ACTIVE" },
  { id: "crm_intake",        label: "CRM Intake",         status: "ACTIVE" },
  { id: "semantic_catalog",  label: "Semantic Catalog",   status: "ACTIVE" },
  { id: "lineage_log",       label: "Lineage Log",        status: "ACTIVE" },
];

export const FLOWS = {
  keywords: {
    finance:    ["financ","p&l","revenue","margin","money","kamm financials","lane a","show me kamm"],
    twin:       ["twin","m4","digital twin","bmw","vehicle","vin"],
    anomaly:    ["anomal","alert","monitor","sleep","spike","flag","warning"],
    collision:  ["update","mileage","which","two","both"],
    inventory:  ["inventory","stock","lot","fleet","available","vehicles"],
    logistics:  ["dispatch","driver","track","delivery","carlux","moaz","transport"],
  } as Record<string, string[]>,
  responses: {
    finance:   { text: "Running finance aggregation across all active entities. Six-week margin breakdown ready — pulling from BigQuery ledger now.", plate: "FINANCE",   intent: "FINANCE",    entity: "ALL_ENTITIES",    confidence: 97 },
    twin:      { text: "Digital Twin loaded for VIN WBA93HM0XP1234567. I'm flagging 1 RED anomaly requiring immediate attention — engine bay oil seepage. 2 YELLOW flags also active.", plate: "TWIN",      intent: "INVENTORY",  entity: "BMW_M4_KAMM",     confidence: 94 },
    anomaly:   { text: "Sleep Monitor fired 14 minutes ago. Transport cost for VIN WBA123 registered at $847 — 2.3σ above the 30-day mean of $312. Carlux dispatch via Moaz. Insurance transfer context assembled. Action required.", plate: "ANOMALY",   intent: "COMPLIANCE", entity: "CARLUX_LLC",      confidence: 99 },
    collision: { text: "I found two BMW M4 Competition units in inventory_master. Identity Engine cannot auto-resolve — both match your query. Collision plate mounted. Select the correct vehicle to resume workflow.", plate: "COLLISION", intent: "INVENTORY",  entity: "AMBIGUOUS",       confidence: 72 },
    inventory: { text: "Pulling current inventory state across KAMM, Fluiditruck, AutoHaus Services, and AstroLogistics. 5 vehicles active across 4 entities.", plate: "INVENTORY", intent: "INVENTORY",  entity: "ALL_ENTITIES",    confidence: 98 },
    logistics: { text: "Carlux dispatch active. Moaz is currently en route — 12 minutes from customer location. Live tracking plate mounted.", plate: "LOGISTICS", intent: "LOGISTICS",  entity: "CARLUX_LLC",      confidence: 96 },
  } as Record<string, { text: string; plate: string; intent: string; entity: string; confidence: number }>,
};

interface MediaResponse {
  text: string;
  findings?: Finding[];
  intent: string;
  entity: string;
  confidence: number;
  mediaType?: string;
}

const MEDIA_RESPONSES: Record<string, MediaResponse[]> = {
  image: [
    {
      text: "Visual Scribe analysis complete. Gemini Veo detected 2 surface anomalies in the uploaded photo: paint chip (~3cm) on rear quarter panel — severity YELLOW, and brake dust accumulation on rear rotors consistent with worn pads — severity RED. Flagging for Digital Twin update. Which VIN should I attribute this to?",
      findings: [
        { zone: "Rear Quarter Panel", issue: "Paint chip ~3cm detected", severity: "YELLOW", confidence: 91 },
        { zone: "Rear Rotors",        issue: "Brake dust — possible pad wear", severity: "RED",    confidence: 87 },
      ],
      intent: "SERVICE", entity: "VISUAL_SCRIBE", confidence: 91,
    },
    {
      text: "Walk-around photo processed. Gemini Veo extracted 3 observations: clean exterior with minor swirl marks on hood (YELLOW), tires showing uneven wear pattern on front-left (YELLOW), and no visible undercarriage anomalies from this angle (GREEN). Ready to write findings to Digital Twin — confirm VIN.",
      findings: [
        { zone: "Hood",           issue: "Swirl marks — detail required",       severity: "YELLOW", confidence: 88 },
        { zone: "Front-Left Tire", issue: "Uneven wear pattern detected",       severity: "YELLOW", confidence: 83 },
        { zone: "Undercarriage",  issue: "No anomalies visible from this angle", severity: "GREEN",  confidence: 79 },
      ],
      intent: "SERVICE", entity: "VISUAL_SCRIBE", confidence: 88,
    },
    {
      text: "Photo ingested and analyzed. Gemini Vision identified this as a vehicle interior shot. Observations: dashboard in good condition (GREEN), driver seat shows minor wear on bolster (YELLOW), no visible spills or damage to headliner (GREEN). I can append these findings to an existing Digital Twin record — which VIN?",
      findings: [
        { zone: "Dashboard",    issue: "Good condition — no anomalies",    severity: "GREEN",  confidence: 96 },
        { zone: "Driver Seat",  issue: "Bolster wear — detail recommended", severity: "YELLOW", confidence: 82 },
        { zone: "Headliner",    issue: "No damage detected",               severity: "GREEN",  confidence: 94 },
      ],
      intent: "SERVICE", entity: "VISUAL_SCRIBE", confidence: 90,
    },
  ],
  pdf: [
    {
      text: "PDF ingested by the Intelligence Layer. Gemini extracted the following: Document type — Auction Purchase Receipt. VIN: WBA99X0XP1234500, 2022 BMW 330i xDrive, Purchase Price: $28,400, Auction: Manheim Chicago, Date: 2026-02-24. Entity attribution: KAMM LLC (Iowa Dealer). Staging for governance review — approve to promote to inventory_master?",
      intent: "INVENTORY", entity: "KAMM_LLC", confidence: 96,
    },
    {
      text: "Document processed. Gemini classified this as a Transport Invoice — Carlux LLC. Extracted: Driver: Moaz Sial, VIN: WBA93HM0XP1234567, Origin: Chicago IL, Destination: Iowa City IA, Amount: $847.00, Date: 2026-02-23. ⚠ This matches the open anomaly in the Sleep Monitor queue. Should I cross-reference and close the anomaly flag?",
      intent: "COMPLIANCE", entity: "CARLUX_LLC", confidence: 94,
    },
    {
      text: "PDF analyzed. Document type: Dealer Title Transfer — Iowa DOT Form 411007. VIN extracted: 5YJSA1E26MF123456. Seller: Previous Owner, Buyer: KAMM LLC. Title status: CLEAN — no liens detected. Recommend filing to Drive: 03_Titles_KAMM/{VIN}/. Shall I rename and route this automatically?",
      intent: "COMPLIANCE", entity: "KAMM_LLC", confidence: 98,
    },
  ],
  video: [
    {
      text: "Walk-around video uploaded. Gemini Veo processing 47 frames... Analysis complete. Audio transcript extracted: mechanic noted 'slight knock on cold start' and 'passenger window slow to respond.' Visual scan detected rust spotting on subframe (YELLOW) and a hairline crack on rear diffuser lip (YELLOW). Writing 4 findings to Digital Twin. Confirm VIN to commit.",
      findings: [
        { zone: "Engine (Audio)",   issue: "Knock on cold start — investigation warranted", severity: "YELLOW", confidence: 84 },
        { zone: "Window Regulator", issue: "Slow response — possible motor wear",           severity: "YELLOW", confidence: 80 },
        { zone: "Subframe",         issue: "Rust spotting — surface level",                  severity: "YELLOW", confidence: 91 },
        { zone: "Rear Diffuser",    issue: "Hairline crack on lip",                          severity: "YELLOW", confidence: 88 },
      ],
      intent: "SERVICE", entity: "VISUAL_SCRIBE", confidence: 87,
    },
  ],
  doc: [
    {
      text: "Document ingested. Gemini classified this as an Insurance Certificate — Auto-Owners Policy. Extracted policy number, effective date 2026-01-01, covered entities: AutoHaus Services LLC, AstroLogistics LLC, KAMM LLC. Coverage types: Garagekeepers, Bailee, Fleet. This matches the Unified Auto-Owners anchor. Filing to 12_Insurance/ in Drive. No action required.",
      intent: "COMPLIANCE", entity: "CARBON_LLC", confidence: 97,
    },
  ],
};

export function getMediaResponse(file: StagedFile): MediaResponse {
  const ext = file.name.split(".").pop()?.toLowerCase() || "";
  const type = file.type.startsWith("image/") ? "image"
    : file.type === "application/pdf" || ext === "pdf" ? "pdf"
    : file.type.startsWith("video/") ? "video"
    : "doc";
  const pool = MEDIA_RESPONSES[type] || MEDIA_RESPONSES.doc;
  return { ...pool[Math.floor(Math.random() * pool.length)], mediaType: type };
}

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

    ws.onopen = () => setWsState("LIVE");
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

  const sendMessage = useCallback((text: string, files: StagedFile[] = []) => {
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

    setTimeout(() => {
      let reply: ChatMessage;
      if (hasFiles) {
        const mediaResp = getMediaResponse(files[0]);
        reply = { id: Date.now() + 1, isBot: true, time: now(), text: mediaResp.text, findings: mediaResp.findings, intent: mediaResp.intent, entity: mediaResp.entity, confidence: mediaResp.confidence };
      } else {
        const intent = classifyIntent(text);
        const flow = intent ? FLOWS.responses[intent] : undefined;
        reply = flow
          ? { id: Date.now() + 1, isBot: true, time: now(), text: flow.text, intent: flow.intent, entity: flow.entity, confidence: flow.confidence }
          : { id: Date.now() + 1, isBot: true, time: now(), text: "Command received and routed through the Agentic Router. Intent classified — executing via CIL.", intent: "PROCESSING", entity: "CIL", confidence: 85 };
        if (flow?.plate) setPlate(flow.plate);
      }
      setMessages(p => [...p, reply]);
      setProcessing(false);
    }, hasFiles ? 1800 : 1100);
  }, [processing, user.id]);

  const handleResolve = useCallback((vehicle: EntityOption) => {
    setMessages(p => [...p, { id: Date.now(), isBot: true, time: now(), text: `Collision resolved. Entity confirmed: ${vehicle.entity} · VIN ${vehicle.vin}. Workflow resumed. Identity Engine updated. What update would you like to apply?`, intent: "INVENTORY", entity: vehicle.entity, confidence: 100 }]);
    setPlate(null);
  }, []);

  const handleAnomalyDecision = useCallback((type: string) => {
    setTimeout(() => {
      setMessages(p => [...p, { id: Date.now(), isBot: true, time: now(), text: type === "APPROVED" ? "Anomaly approved. Transport cost logged as accepted exception. system_audit_ledger updated — AHSIN_CEO. Anomaly cleared from active queue." : "Override logged with reason. Exception recorded in system_audit_ledger with full context. Insurance team notified. Anomaly cleared.", intent: "COMPLIANCE", entity: "CARBON_LLC", confidence: 100 }]);
    }, 800);
  }, []);

  return (
    <OrchestratorContext.Provider value={{
      user, setUser, messages, setMessages, input, setInput,
      plate, setPlate, processing, mode, setMode,
      wsState, anomalyCount, stagedFiles, setStagedFiles,
      dragOver, setDragOver, sendMessage, stageFiles,
      removeStaged, handleDrop, handleResolve, handleAnomalyDecision,
      chatRef, fileInputRef,
    }}>
      {children}
    </OrchestratorContext.Provider>
  );
}
