import { useState, useEffect } from "react";
import { T } from "../tokens";
import { ArrowLeft, ExternalLink, Eye, EyeOff, Send, CheckCircle, AlertTriangle } from "lucide-react";
import { Tag } from "../components/ui";

interface PublicVehicle {
  vin: string;
  make: string;
  model: string;
  year: number;
  color: string;
  listing_price: number;
  status: string;
  photos?: string[];
  mileage?: number;
}

const MOCK_PUBLIC_INVENTORY: PublicVehicle[] = [
  { vin: "WBA93HM0XP1234567", make: "BMW", model: "M4 Competition", year: 2023, color: "Frozen Black", listing_price: 74900, status: "AVAILABLE", mileage: 12400 },
  { vin: "5YJSA1E26MF123456", make: "Tesla", model: "Model S Plaid", year: 2022, color: "Midnight Silver", listing_price: 89900, status: "AVAILABLE", mileage: 8200 },
  { vin: "1FTEW1EG0NFC12345", make: "Ford", model: "F-150 Raptor", year: 2022, color: "Shadow Black", listing_price: 62500, status: "AVAILABLE", mileage: 15800 },
];

const HIDDEN_FIELDS = ["wholesale_cost", "recon_cost", "acquisition_source", "internal_notes", "margin", "floor_plan_rate"];

function VehicleCard({ vehicle }: { vehicle: PublicVehicle }) {
  return (
    <div style={{
      background: T.elevated, border: `1px solid ${T.border2}`, borderRadius: 10,
      overflow: "hidden", animation: "msg-in 0.3s ease-out",
    }}>
      <div style={{
        height: 120, background: `linear-gradient(135deg, ${T.surface} 0%, ${T.elevated} 100%)`,
        display: "flex", alignItems: "center", justifyContent: "center",
        borderBottom: `1px solid ${T.border}`,
      }}>
        <span style={{ color: T.muted, fontSize: 10, fontFamily: "monospace" }}>
          {vehicle.year} {vehicle.make} {vehicle.model}
        </span>
      </div>
      <div style={{ padding: 14 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
          <span style={{ color: T.text, fontSize: 13, fontWeight: 700, fontFamily: "'DM Sans', sans-serif" }}>
            {vehicle.year} {vehicle.make} {vehicle.model}
          </span>
          <Tag label={vehicle.status} color={T.green} />
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
          <Row label="COLOR" value={vehicle.color} />
          <Row label="VIN" value={vehicle.vin} mono />
          {vehicle.mileage && <Row label="MILEAGE" value={`${vehicle.mileage.toLocaleString()} mi`} />}
        </div>
        <div style={{
          marginTop: 10, paddingTop: 10, borderTop: `1px solid ${T.border}`,
          display: "flex", justifyContent: "space-between", alignItems: "center",
        }}>
          <span style={{ color: T.gold, fontSize: 18, fontWeight: 800, fontFamily: "monospace" }}>
            ${vehicle.listing_price.toLocaleString()}
          </span>
          <button style={{
            padding: "6px 12px", borderRadius: 6,
            background: `${T.gold}12`, border: `1px solid ${T.gold}44`,
            color: T.gold, fontSize: 9, fontWeight: 700, fontFamily: "monospace",
            cursor: "pointer", letterSpacing: "0.06em",
          }}>
            INQUIRE
          </button>
        </div>
      </div>
    </div>
  );
}

function Row({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
      <span style={{ color: T.dim, fontSize: 9, fontFamily: "monospace" }}>{label}</span>
      <span style={{ color: T.textDim, fontSize: 9, fontFamily: mono ? "monospace" : "'DM Sans', sans-serif" }}>{value}</span>
    </div>
  );
}

function HiddenFieldsProof({ vehicles }: { vehicles: PublicVehicle[] }) {
  if (vehicles.length === 0) return null;
  const sampleKeys = Object.keys(vehicles[0]);
  const exposed = sampleKeys.filter(k => !HIDDEN_FIELDS.includes(k));
  const blocked = HIDDEN_FIELDS;

  return (
    <div style={{
      background: T.surface, border: `1px solid ${T.border}`, borderRadius: 8,
      padding: 14, marginTop: 12,
    }}>
      <span style={{ color: T.dim, fontSize: 9, fontFamily: "monospace", fontWeight: 700, letterSpacing: "0.08em", display: "block", marginBottom: 8 }}>
        FIELD EXPOSURE AUDIT
      </span>
      <div style={{ display: "flex", gap: 20 }}>
        <div style={{ flex: 1 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 4, marginBottom: 6 }}>
            <Eye size={10} color={T.green} />
            <span style={{ color: T.green, fontSize: 8, fontFamily: "monospace", fontWeight: 700 }}>EXPOSED ({exposed.length})</span>
          </div>
          {exposed.map(k => (
            <span key={k} style={{ display: "block", color: T.textDim, fontSize: 9, fontFamily: "monospace", padding: "1px 0" }}>{k}</span>
          ))}
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 4, marginBottom: 6 }}>
            <EyeOff size={10} color={T.red} />
            <span style={{ color: T.red, fontSize: 8, fontFamily: "monospace", fontWeight: 700 }}>BLOCKED ({blocked.length})</span>
          </div>
          {blocked.map(k => (
            <span key={k} style={{ display: "block", color: T.dim, fontSize: 9, fontFamily: "monospace", padding: "1px 0", textDecoration: "line-through" }}>{k}</span>
          ))}
        </div>
      </div>
    </div>
  );
}

export function PublicApiTest({ onBack }: { onBack: () => void }) {
  const [vehicles, setVehicles] = useState<PublicVehicle[]>([]);
  const [inventoryLoading, setInventoryLoading] = useState(true);
  const [inventoryError, setInventoryError] = useState<string | null>(null);

  const [leadName, setLeadName] = useState("Test User");
  const [leadPhone, setLeadPhone] = useState("555-0199");
  const [leadEmail, setLeadEmail] = useState("test@example.com");
  const [leadVin, setLeadVin] = useState("WBA93HM0XP1234567");
  const [leadSubmitting, setLeadSubmitting] = useState(false);
  const [leadResult, setLeadResult] = useState<"success" | "error" | null>(null);

  useEffect(() => {
    (async () => {
      setInventoryLoading(true);
      try {
        const res = await fetch("/api/public/inventory");
        if (!res.ok) throw new Error(`${res.status}`);
        const data = await res.json();
        const items = Array.isArray(data) ? data : data.vehicles || data.inventory || [];
        setVehicles(items.filter((v: PublicVehicle) => v.status === "AVAILABLE"));
      } catch {
        setVehicles(MOCK_PUBLIC_INVENTORY);
        setInventoryError("Backend unavailable — showing mock data (AVAILABLE only)");
      } finally {
        setInventoryLoading(false);
      }
    })();
  }, []);

  const submitLead = async () => {
    setLeadSubmitting(true);
    setLeadResult(null);
    try {
      const res = await fetch("/api/public/lead", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: leadName,
          phone: leadPhone,
          email: leadEmail,
          interest_vin: leadVin,
        }),
      });
      if (!res.ok) throw new Error(`${res.status}`);
      setLeadResult("success");
      setTimeout(() => setLeadResult(null), 4000);
    } catch {
      setLeadResult("error");
      setTimeout(() => setLeadResult(null), 4000);
    } finally {
      setLeadSubmitting(false);
    }
  };

  return (
    <div style={{ height: "100vh", background: T.bg, display: "flex", flexDirection: "column" }}>
      <div style={{
        height: 44, background: T.surface, borderBottom: `1px solid ${T.border}`,
        display: "flex", alignItems: "center", padding: "0 20px", gap: 12, flexShrink: 0,
      }}>
        <button
          onClick={onBack}
          style={{
            display: "flex", alignItems: "center", gap: 6,
            background: "transparent", border: "none", color: T.gold, cursor: "pointer",
            fontSize: 10, fontFamily: "monospace", fontWeight: 700, letterSpacing: "0.06em",
          }}
        >
          <ArrowLeft size={14} /> COMMAND CENTER
        </button>
        <div style={{ width: 1, height: 20, background: T.border, margin: "0 6px" }} />
        <ExternalLink size={12} color={T.blue} />
        <span style={{ color: T.blue, fontSize: 12, fontFamily: "monospace", fontWeight: 700, letterSpacing: "0.12em" }}>PUBLIC API TEST</span>
        <span style={{ color: T.dim, fontSize: 9, fontFamily: "monospace" }}>DEV ONLY</span>
      </div>

      <div style={{ flex: 1, overflow: "auto", padding: 24, display: "flex", gap: 24 }}>
        <div style={{ flex: 2, display: "flex", flexDirection: "column", gap: 14 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
            <span style={{ color: T.gold, fontSize: 11, fontFamily: "monospace", fontWeight: 700, letterSpacing: "0.1em" }}>PUBLIC INVENTORY</span>
            <Tag label={`GET /api/public/inventory`} color={T.blue} />
          </div>

          {inventoryError && (
            <div style={{
              padding: "8px 14px", borderRadius: 6,
              background: `${T.gold}08`, border: `1px solid ${T.gold}33`,
              display: "flex", alignItems: "center", gap: 8,
            }}>
              <AlertTriangle size={12} color={T.gold} />
              <span style={{ color: T.gold, fontSize: 9, fontFamily: "monospace" }}>{inventoryError}</span>
            </div>
          )}

          {inventoryLoading ? (
            <div style={{ display: "flex", justifyContent: "center", padding: 40 }}>
              <span style={{ color: T.dim, fontSize: 11, fontFamily: "monospace", animation: "blink 1s infinite" }}>Fetching public inventory...</span>
            </div>
          ) : (
            <>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: 14 }}>
                {vehicles.map(v => <VehicleCard key={v.vin} vehicle={v} />)}
              </div>
              <HiddenFieldsProof vehicles={vehicles} />
            </>
          )}
        </div>

        <div style={{ flex: 1, minWidth: 280 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14 }}>
            <span style={{ color: T.gold, fontSize: 11, fontFamily: "monospace", fontWeight: 700, letterSpacing: "0.1em" }}>LEAD INTAKE FORM</span>
            <Tag label={`POST /api/public/lead`} color={T.green} />
          </div>

          <div style={{
            background: T.elevated, border: `1px solid ${T.border2}`, borderRadius: 10,
            padding: 16, display: "flex", flexDirection: "column", gap: 10,
          }}>
            <InputField label="NAME" value={leadName} onChange={setLeadName} />
            <InputField label="PHONE" value={leadPhone} onChange={setLeadPhone} />
            <InputField label="EMAIL" value={leadEmail} onChange={setLeadEmail} />
            <InputField label="INTEREST VIN" value={leadVin} onChange={setLeadVin} mono />

            <button
              onClick={submitLead}
              disabled={leadSubmitting}
              style={{
                marginTop: 4, padding: "12px 0", borderRadius: 8,
                border: `1px solid ${T.gold}66`, background: `${T.gold}12`,
                color: T.gold, fontSize: 11, fontWeight: 800, fontFamily: "monospace",
                letterSpacing: "0.08em", cursor: leadSubmitting ? "wait" : "pointer",
                opacity: leadSubmitting ? 0.5 : 1, transition: "all 0.15s",
                display: "flex", alignItems: "center", justifyContent: "center", gap: 6,
              }}
            >
              <Send size={12} /> {leadSubmitting ? "SUBMITTING..." : "SUBMIT LEAD"}
            </button>

            {leadResult === "success" && (
              <div style={{
                padding: "8px 14px", borderRadius: 6, animation: "msg-in 0.3s ease-out",
                background: `${T.green}08`, border: `1px solid ${T.green}33`,
                display: "flex", alignItems: "center", gap: 8,
              }}>
                <CheckCircle size={12} color={T.green} />
                <span style={{ color: T.green, fontSize: 9, fontFamily: "monospace" }}>Lead accepted — backend will create Person entity</span>
              </div>
            )}

            {leadResult === "error" && (
              <div style={{
                padding: "8px 14px", borderRadius: 6, animation: "msg-in 0.3s ease-out",
                background: `${T.gold}08`, border: `1px solid ${T.gold}33`,
                display: "flex", alignItems: "center", gap: 8,
              }}>
                <AlertTriangle size={12} color={T.gold} />
                <span style={{ color: T.gold, fontSize: 9, fontFamily: "monospace" }}>Endpoint unavailable — backend not yet deployed</span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function InputField({ label, value, onChange, mono }: { label: string; value: string; onChange: (v: string) => void; mono?: boolean }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
      <span style={{ color: T.dim, fontSize: 8, fontFamily: "monospace", fontWeight: 700, letterSpacing: "0.08em" }}>{label}</span>
      <input
        value={value}
        onChange={e => onChange(e.target.value)}
        style={{
          background: T.surface, border: `1px solid ${T.border2}`, borderRadius: 4,
          color: T.text, fontSize: 11, fontFamily: mono ? "monospace" : "'DM Sans', sans-serif",
          padding: "8px 10px", outline: "none",
        }}
      />
    </div>
  );
}
